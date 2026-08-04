"""Ferramenta de Escala de Voluntários — interface web (Streamlit).

Fluxo mensal: conferir configurações → gerar escala → revisar/ajustar →
gerar texto do WhatsApp → publicar no histórico. Trocas entram a qualquer
momento e são refletidas na escala ou no histórico, conforme o caso.
"""

from __future__ import annotations

import hmac
from datetime import date

import pandas as pd
import streamlit as st

from escala import servico
from escala.calendario import descrever_culto, montar_cultos
from escala.dados import (
    ABA_CONFIG,
    ABA_ESCALA,
    ABA_FUNCOES,
    ABA_HISTORICO,
    BaseDados,
)
from escala.demo import repositorio_demo
from escala.modelos import TROCA_PENDENTE, Atribuicao, Troca
from escala.motor import (
    descrever_pendencia,
    gerar_escala,
    resumo_por_voluntario,
    voluntarios_nao_escalados,
)
from escala.textos import competencia, formatar_data, nome_mes, normalizar
from escala.whatsapp import gerar_texto_whatsapp

st.set_page_config(
    page_title="Escala de Voluntários",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Secrets e autenticação
# ---------------------------------------------------------------------------

def segredo(secao: str, chave: str | None = None, padrao=None):
    """Lê `st.secrets` sem quebrar quando o arquivo não existe (modo local)."""
    try:
        valor = st.secrets[secao]
    except Exception:
        return padrao
    if chave is None:
        return valor
    try:
        return valor[chave]
    except Exception:
        return padrao


def autenticado() -> bool:
    """Porteiro por senha compartilhada. Sem senha configurada, o app abre livre."""
    senha_esperada = segredo("app", "senha", "")
    if not senha_esperada:
        return True
    if st.session_state.get("_autenticado"):
        return True

    st.title("🗓️ Escala de Voluntários")
    st.caption("Acesso restrito à equipe de coordenação.")
    with st.form("login"):
        digitada = st.text_input("Senha da equipe", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            if hmac.compare_digest(str(digitada), str(senha_esperada)):
                st.session_state["_autenticado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    return False


# ---------------------------------------------------------------------------
# Repositório e carregamento
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def conectar_planilha(identificador: str, _credenciais: dict):
    """Conexão reaproveitada entre reruns (o `_` evita hashear a credencial)."""
    from escala.sheets import RepositorioSheets

    return RepositorioSheets.conectar(_credenciais, identificador)


def obter_repositorio():
    """Usa o Google Sheets quando há credenciais; senão, cai no modo demonstração."""
    if "_repositorio" in st.session_state:
        return st.session_state["_repositorio"]

    credenciais = segredo("gcp_service_account")
    identificador = segredo("planilha", "id") or segredo("planilha", "url")

    if credenciais and identificador:
        try:
            repositorio = conectar_planilha(str(identificador), dict(credenciais))
            st.session_state["_modo_demo"] = False
        except Exception as erro:  # noqa: BLE001
            st.session_state["_erro_conexao"] = str(erro)
            repositorio = repositorio_demo()
            st.session_state["_modo_demo"] = True
    else:
        repositorio = repositorio_demo()
        st.session_state["_modo_demo"] = True

    st.session_state["_repositorio"] = repositorio
    return repositorio


def carregar_dados(recarregar: bool = False) -> BaseDados:
    if recarregar or "_base" not in st.session_state:
        with st.spinner("Lendo a planilha..."):
            st.session_state["_base"] = servico.carregar(obter_repositorio())
    return st.session_state["_base"]


def invalidar_dados() -> None:
    st.session_state.pop("_base", None)


def nova_versao_editor() -> None:
    """Força o `data_editor` a recarregar do zero.

    O editor guarda as edições como um diff sobre os dados de entrada; ao
    substituir a escala inteira (gerar de novo, aplicar trocas, recarregar) esse
    diff precisa ser descartado, e trocar a chave do widget é o jeito de fazer.
    """
    st.session_state["_versao_editor"] = st.session_state.get("_versao_editor", 0) + 1


# ---------------------------------------------------------------------------
# Conversões entre objetos e tabelas
# ---------------------------------------------------------------------------

COLUNAS_TABELA = ["Data", "Culto", "Função", "Nome"]


def para_tabela(atribuicoes: list[Atribuicao]) -> pd.DataFrame:
    tabela = pd.DataFrame(
        [
            {
                "Data": a.data,
                "Culto": a.culto,
                "Função": a.funcao,
                "Nome": a.nome,
            }
            for a in atribuicoes
        ],
        columns=COLUNAS_TABELA,
    )
    # `DateColumn` exige coluna datetime; objetos `date` viriam como `object`.
    tabela["Data"] = pd.to_datetime(tabela["Data"], errors="coerce")
    return tabela


def para_atribuicoes(tabela: pd.DataFrame) -> list[Atribuicao]:
    registros: list[Atribuicao] = []
    for _, linha in tabela.iterrows():
        bruto = linha.get("Data")
        if pd.isna(bruto):
            continue
        data = bruto.date() if hasattr(bruto, "date") else bruto
        nome = str(linha.get("Nome") or "").strip()
        funcao = str(linha.get("Função") or "").strip()
        if not nome or not funcao:
            continue
        registros.append(
            Atribuicao(
                data=data,
                culto=str(linha.get("Culto") or "").strip(),
                funcao=funcao,
                nome=nome,
            )
        )
    return registros


def rascunho_atual(base: BaseDados) -> list[Atribuicao]:
    """Prioriza o que está sendo editado na sessão; senão, o que está na planilha."""
    if st.session_state.get("_rascunho"):
        return st.session_state["_rascunho"]
    return list(base.escala)


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------

def barra_lateral(base: BaseDados) -> tuple[int, int]:
    st.sidebar.title("🗓️ Escala")

    if st.session_state.get("_modo_demo"):
        st.sidebar.warning("**Modo demonstração**", icon="🧪")
        st.sidebar.caption(
            "Dados de exemplo, em memória. Nada é gravado na planilha real. "
            "Configure os Secrets para conectar ao Google Sheets."
        )
        if erro := st.session_state.get("_erro_conexao"):
            with st.sidebar.expander("Detalhe da falha de conexão"):
                st.caption(erro)
    else:
        st.sidebar.success(f"Conectado: **{obter_repositorio().nome}**", icon="✅")
        if url := obter_repositorio().url():
            st.sidebar.markdown(f"[Abrir a planilha]({url})")

    if st.sidebar.button("🔄 Recarregar dados", use_container_width=True):
        invalidar_dados()
        st.session_state.pop("_rascunho", None)
        nova_versao_editor()
        st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("Mês da escala")

    mes_padrao = base.config.mes or date.today().month
    ano_padrao = base.config.ano or date.today().year
    mes = st.sidebar.selectbox(
        "Mês",
        options=list(range(1, 13)),
        index=mes_padrao - 1,
        format_func=nome_mes,
    )
    ano = st.sidebar.number_input(
        "Ano", min_value=2020, max_value=2100, value=int(ano_padrao), step=1
    )

    if (mes, ano) != (base.config.mes, base.config.ano):
        st.sidebar.caption(
            f"A planilha indica {competencia(base.config.mes, base.config.ano)}."
            if base.config.mes and base.config.ano
            else "A planilha não indica um mês; usando a seleção acima."
        )

    st.sidebar.divider()
    st.sidebar.caption(
        f"**{len(base.voluntarios_ativos)}** voluntários ativos · "
        f"**{len(base.funcoes)}** funções · "
        f"**{len(base.historico)}** linhas de histórico"
    )
    return int(mes), int(ano)


# ---------------------------------------------------------------------------
# Abas
# ---------------------------------------------------------------------------

def aba_painel(base: BaseDados, mes: int, ano: int) -> None:
    st.subheader(f"Painel — {competencia(mes, ano)}")

    cultos = montar_cultos(base.config, mes, ano)
    colunas = st.columns(4)
    colunas[0].metric("Cultos no mês", len(cultos))
    colunas[1].metric("Voluntários ativos", len(base.voluntarios_ativos))
    colunas[2].metric("Funções cadastradas", len(base.funcoes))
    colunas[3].metric("Trocas pendentes", sum(1 for t in base.trocas if t.pendente))

    if base.avisos:
        with st.expander(f"⚠️ Diagnóstico da planilha ({len(base.avisos)})", expanded=True):
            for aviso in base.avisos:
                st.warning(aviso, icon="⚠️")
    else:
        st.success("Nenhum problema encontrado nos cadastros.", icon="✅")

    esquerda, direita = st.columns(2)

    with esquerda:
        st.markdown("##### Cultos previstos")
        if cultos:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Data": formatar_data(c.data, com_ano=True),
                            "Culto": descrever_culto(c),
                            "Ceia": "Sim" if c.ceia else "",
                        }
                        for c in cultos
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info(
                "Nenhum culto para este mês. Confira `Data do culto de oração` "
                f"e `Datas sem culto` na aba `{ABA_CONFIG}`."
            )

    with direita:
        st.markdown("##### Configurações lidas")
        if base.config.itens:
            st.dataframe(
                pd.DataFrame(base.config.itens, columns=["Campo", "Valor"]),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info(f"A aba `{ABA_CONFIG}` está vazia.")

    with st.expander("👥 Voluntários e funções"):
        col_a, col_b = st.columns([3, 2])
        col_a.dataframe(
            pd.DataFrame(
                [
                    {
                        "Nome": v.nome,
                        "Ativo": "Sim" if v.ativo else "Não",
                        "Funções": ", ".join(v.funcoes),
                    }
                    for v in base.voluntarios
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
        col_b.dataframe(
            pd.DataFrame(
                [
                    {
                        "Função": f.nome,
                        "Culto": f.culto,
                        "Qtd.": f"{f.qtd_min}–{f.qtd_max}",
                        "Coringa": "Sim" if f.coringa else "",
                        "Data fixa": "Sim" if f.data_fixa else "",
                    }
                    for f in base.funcoes
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )


def aba_gerar(base: BaseDados, mes: int, ano: int) -> None:
    st.subheader("Gerar escala do mês")
    st.caption(
        "O sistema sugere; você decide. Depois de gerar, ajuste qualquer linha "
        "na tabela abaixo e salve na planilha."
    )

    esquerda, direita = st.columns([1, 3])
    with esquerda:
        if st.button("⚙️ Gerar escala do mês", type="primary", use_container_width=True):
            resultado = gerar_escala(base, mes, ano)
            st.session_state["_rascunho"] = resultado.atribuicoes
            st.session_state["_pendencias"] = resultado.pendencias
            st.session_state["_avisos_geracao"] = resultado.avisos
            nova_versao_editor()
            st.rerun()
    with direita:
        if base.escala and not st.session_state.get("_rascunho"):
            st.info(
                f"Existe uma escala na aba `{ABA_ESCALA}` com "
                f"{len(base.escala)} linhas. Gerar de novo substitui esse rascunho.",
                icon="ℹ️",
            )

    for aviso in st.session_state.get("_avisos_geracao", []):
        st.warning(aviso, icon="⚠️")

    pendencias = st.session_state.get("_pendencias", [])
    if pendencias:
        with st.expander(f"🕳️ Vagas em aberto ({len(pendencias)})", expanded=True):
            st.caption("Preencha manualmente na tabela abaixo ou ajuste os cadastros.")
            for pendencia in pendencias:
                st.write("• " + descrever_pendencia(pendencia))

    atribuicoes = rascunho_atual(base)
    if not atribuicoes:
        st.info("Nenhuma escala carregada. Clique em **Gerar escala do mês**.")
        return

    st.markdown("##### Rascunho — edite à vontade")
    editada = st.data_editor(
        para_tabela(atribuicoes),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"editor_escala_{st.session_state.get('_versao_editor', 0)}",
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", required=True),
            "Culto": st.column_config.TextColumn("Culto", required=True),
            "Função": st.column_config.TextColumn("Função", required=True),
            "Nome": st.column_config.TextColumn("Nome", required=True),
        },
    )
    st.session_state["_rascunho"] = para_atribuicoes(editada)
    atual = st.session_state["_rascunho"]

    col_a, col_b = st.columns([1, 3])
    with col_a:
        if st.button("💾 Salvar na planilha", use_container_width=True):
            try:
                servico.salvar_escala(obter_repositorio(), base, atual)
                invalidar_dados()
                st.success(f"Escala gravada na aba `{ABA_ESCALA}`.", icon="✅")
            except Exception as erro:  # noqa: BLE001
                st.error(f"Não consegui gravar: {erro}")
    with col_b:
        st.caption(
            "Salvar sobrescreve a aba `Escala Gerada`. O histórico só muda "
            "quando você publicar."
        )

    with st.expander("📊 Distribuição de carga"):
        carga = resumo_por_voluntario(atual)
        if carga:
            st.dataframe(
                pd.DataFrame(carga.items(), columns=["Voluntário", "Escalas no mês"]),
                hide_index=True,
                use_container_width=True,
            )
        de_fora = voluntarios_nao_escalados(base, atual)
        if de_fora:
            st.warning(
                "Voluntários ativos sem nenhuma escala neste mês: " + ", ".join(de_fora),
                icon="👀",
            )


def aba_whatsapp(base: BaseDados, mes: int, ano: int) -> None:
    st.subheader("Texto para o WhatsApp")

    atribuicoes = rascunho_atual(base)
    if not atribuicoes:
        st.info("Gere ou carregue uma escala primeiro.")
        return

    col_a, col_b = st.columns(2)
    rodape = col_a.text_input(
        "Rodapé (opcional)",
        value="Qualquer imprevisto, avise a coordenação com antecedência 🙏",
    )
    apenas_um = col_b.checkbox("Gerar só de um culto")

    filtradas = atribuicoes
    if apenas_um:
        datas = sorted({a.data for a in atribuicoes if a.data})
        if datas:
            escolhida = st.selectbox(
                "Culto", options=datas, format_func=lambda d: formatar_data(d, com_ano=True)
            )
            filtradas = [a for a in atribuicoes if a.data == escolhida]

    texto = gerar_texto_whatsapp(
        filtradas,
        mes=mes,
        ano=ano,
        ordem_funcoes=base.ordem_das_funcoes(),
        data_ceia=base.config.data_ceia,
        rodape=rodape.strip(),
    )

    if not texto:
        st.info("Nada para publicar.")
        return

    st.caption(
        "Use o botão de copiar no canto do bloco, cole no grupo e depois "
        "confirme a publicação na aba **Publicar**."
    )
    st.code(texto, language=None)
    st.download_button(
        "⬇️ Baixar como .txt",
        data=texto.encode("utf-8"),
        file_name=f"escala-{ano}-{mes:02d}.txt",
        mime="text/plain",
    )

    with st.expander("👁️ Pré-visualização formatada"):
        st.markdown(texto.replace("*", "**").replace("\n", "  \n"))


def aba_trocas(base: BaseDados) -> None:
    st.subheader("Trocas")
    st.caption(
        "Registre a troca avisada pelo voluntário e aplique. Trocas na escala "
        "ainda não publicada mudam o rascunho; depois de publicada, mudam o "
        "histórico — que é o que alimenta o rodízio dos próximos meses."
    )

    nomes = servico.nomes_conhecidos(base)
    datas_disponiveis = sorted(
        {a.data for a in rascunho_atual(base) if a.data}
        | {h.data for h in base.historico if h.data},
        reverse=True,
    )

    # Sem `st.form`: os três primeiros campos são encadeados (a função depende da
    # data, e quem sai depende da função), então precisam reagir a cada escolha.
    st.markdown("##### Registrar nova troca")
    linhas_conhecidas = rascunho_atual(base) + base.historico

    col_a, col_b, col_c = st.columns(3)
    if datas_disponiveis:
        data = col_a.selectbox(
            "Data do culto",
            options=datas_disponiveis,
            format_func=lambda d: formatar_data(d, com_ano=True),
        )
    else:
        data = col_a.date_input("Data do culto", value=date.today())

    funcoes_possiveis = sorted(
        {a.funcao for a in linhas_conhecidas if a.data == data and a.funcao}
    ) or base.ordem_das_funcoes()
    funcao = (
        col_b.selectbox("Função", options=funcoes_possiveis)
        if funcoes_possiveis
        else col_b.text_input("Função")
    )

    escalados = sorted(
        {
            a.nome
            for a in linhas_conhecidas
            if a.data == data and normalizar(a.funcao) == normalizar(funcao) and a.nome
        }
    )
    original = (
        col_c.selectbox("Quem sai", options=escalados)
        if escalados
        else col_c.text_input("Quem sai")
    )

    col_d, col_e = st.columns(2)
    candidatos = [n for n in nomes if normalizar(n) != normalizar(str(original))]
    substituto = col_d.selectbox(
        "Quem entra", options=candidatos, index=None, placeholder="Escolha o substituto"
    )
    motivo = col_e.text_input("Motivo", placeholder="Viagem, trabalho, saúde...")

    if st.button("➕ Registrar troca", type="primary"):
        if not substituto:
            st.error("Escolha quem entra no lugar.")
        elif not str(original).strip():
            st.error("Informe quem sai da escala.")
        else:
            nova = Troca(
                data=data,
                funcao=str(funcao),
                nome_original=str(original),
                nome_substituto=substituto,
                motivo=motivo,
                status=TROCA_PENDENTE,
            )
            try:
                servico.registrar_troca(obter_repositorio(), base, nova)
                invalidar_dados()
                st.success("Troca registrada. Clique em **Aplicar trocas** abaixo.")
                st.rerun()
            except Exception as erro:  # noqa: BLE001
                st.error(f"Não consegui registrar: {erro}")

    st.divider()
    st.markdown("##### Trocas registradas")
    if not base.trocas:
        st.info("Nenhuma troca registrada ainda.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Data": formatar_data(t.data, com_ano=True) if t.data else "",
                    "Função": t.funcao,
                    "Sai": t.nome_original,
                    "Entra": t.nome_substituto,
                    "Motivo": t.motivo,
                    "Status": t.status,
                }
                for t in base.trocas
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )

    pendentes = sum(1 for t in base.trocas if t.pendente)
    col_a, col_b = st.columns([1, 3])
    with col_a:
        if st.button(
            f"🔁 Aplicar trocas ({pendentes})",
            type="primary",
            disabled=pendentes == 0,
            use_container_width=True,
        ):
            try:
                resultado = servico.processar_trocas(obter_repositorio(), base)
                invalidar_dados()
                st.session_state.pop("_rascunho", None)
                nova_versao_editor()
                if resultado.aplicadas:
                    st.success(f"{resultado.aplicadas} troca(s) aplicada(s).", icon="✅")
                for mensagem in resultado.mensagens:
                    st.write("• " + mensagem)
                if not resultado.aplicadas:
                    st.warning("Nenhuma troca pôde ser aplicada.", icon="⚠️")
            except Exception as erro:  # noqa: BLE001
                st.error(f"Falha ao aplicar trocas: {erro}")
    with col_b:
        st.caption(
            "Trocas com status `Não encontrada` continuam pendentes: corrija a "
            "data, a função ou o nome na planilha e aplique de novo."
        )


def aba_publicar(base: BaseDados, mes: int, ano: int) -> None:
    st.subheader("Publicar no histórico")
    st.caption(
        "Faça isso **depois** de colar a escala no grupo. Publicar grava as "
        f"linhas na aba `{ABA_HISTORICO}`, que é a memória do rodízio."
    )

    atribuicoes = rascunho_atual(base)
    if not atribuicoes:
        st.info("Não há escala para publicar.")
        return

    conflitos = servico.datas_ja_publicadas(base, atribuicoes)
    st.metric("Linhas a publicar", len(atribuicoes))

    if conflitos:
        st.warning(
            "Estas datas já constam no histórico: "
            + ", ".join(formatar_data(d, com_ano=True) for d in conflitos),
            icon="⚠️",
        )
    substituir = st.checkbox(
        "Substituir o que já existe no histórico nessas datas",
        value=False,
        disabled=not conflitos,
        help="Use ao republicar um mês que precisou ser regerado.",
    )

    if st.button("✅ Confirmar publicação", type="primary"):
        try:
            resultado = servico.publicar(
                obter_repositorio(), base, atribuicoes, substituir=substituir
            )
            if resultado.publicado:
                invalidar_dados()
                st.success(resultado.mensagem, icon="✅")
                st.balloons()
            else:
                st.error(resultado.mensagem)
        except Exception as erro:  # noqa: BLE001
            st.error(f"Falha ao publicar: {erro}")

    with st.expander("📚 Histórico atual"):
        if base.historico:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Data": formatar_data(h.data, com_ano=True) if h.data else "",
                            "Culto": h.culto,
                            "Função": h.funcao,
                            "Nome": h.nome,
                        }
                        for h in sorted(
                            base.historico, key=lambda h: (h.data or date.min), reverse=True
                        )
                    ]
                ),
                hide_index=True,
                use_container_width=True,
                height=320,
            )
        else:
            st.info("Histórico vazio — o primeiro mês será distribuído por sorteio justo.")


def aba_ajuda(base: BaseDados) -> None:
    st.subheader("Configuração e ajuda")

    faltantes = servico.abas_faltantes(base)
    if faltantes:
        st.error("Abas faltando na planilha: " + ", ".join(f"`{a}`" for a in faltantes))
        if not st.session_state.get("_modo_demo") and st.button("🛠️ Criar abas que faltam"):
            try:
                criadas = servico.garantir_estrutura(obter_repositorio(), base)
                invalidar_dados()
                st.success("Abas criadas: " + ", ".join(criadas))
                st.rerun()
            except Exception as erro:  # noqa: BLE001
                st.error(f"Falha ao criar abas: {erro}")
    else:
        st.success("Todas as abas esperadas existem na planilha.", icon="✅")

    st.markdown(
        f"""
##### Como o rodízio funciona
Para cada culto, em ordem cronológica, e para cada função na ordem da aba
`{ABA_FUNCOES}`, o sistema:

1. filtra quem está **ativo**, **apto** à função, **sem indisponibilidade** na
   data e **ainda não escalado** naquele culto;
2. ordena por **quem está há mais tempo sem servir naquela função**;
3. preenche a quantidade da função (mínimo a máximo);
4. se `Abertura` ou `Oferta` ficarem sem gente, usa alguém já escalado em
   função **coringa** naquele mesmo culto;
5. acrescenta `Servo da Ceia` no domingo de Ceia e as funções de data fixa nas
   datas marcadas.

Cada escolha realimenta o rodízio na hora — por isso a mesma pessoa não se
repete em cultos seguidos quando existe outra apta.

##### Campos de `{ABA_CONFIG}`
| Campo | Exemplo | Observação |
|---|---|---|
| `Mês/Ano` | `Março/2026` ou `03/2026` | competência da escala |
| `Data da Ceia` | `1º domingo` ou `01/03` | em branco = 1º domingo; `nenhuma` = sem Ceia |
| `Data do culto de oração` | `3ª quarta` ou `18/03` | aceita várias datas separadas por `;` |
| `Data do Infantil 10-12` | `2º domingo` | uma linha `Data do ...` para cada função de data fixa |
| `Datas sem culto` | `29/03` | pula essas datas |
| `Funções cobertas por coringa` | `Abertura; Oferta` | padrão se ausente |
| `Preencher até a quantidade máxima` | `Sim` | `Não` preenche só o mínimo |
| `Evento` | `27/03 \\| Vigília \\| Oração \\| Recepção; Maná Coffee` | `data \\| nome \\| base \\| funções extras` |

Datas aceitam `01/03/2026`, `01/03`, só o dia (`1`) e expressões como
`1º domingo`, `última quarta`.

##### Fluxo do mês
1. Confira a aba `{ABA_CONFIG}` (datas de Ceia, oração, infantil, eventos).
2. **Gerar escala do mês** → revise e ajuste o rascunho → **Salvar na planilha**.
3. **Texto para o WhatsApp** → copiar → colar no grupo.
4. **Publicar** → grava no `{ABA_HISTORICO}` e fecha o rodízio do mês.
5. Trocas ao longo do mês: registre em **Trocas** e clique em **Aplicar trocas**.
"""
    )

    with st.expander("🔐 Configurar o acesso ao Google Sheets"):
        st.markdown(
            f"""
1. No [Google Cloud](https://console.cloud.google.com/), crie um projeto e
   habilite a **Google Sheets API**.
2. Crie uma **Service Account** e gere uma chave JSON.
3. Compartilhe a planilha com o `client_email` da Service Account, como
   **Editor**.
4. No Streamlit Community Cloud, em *Settings → Secrets*, cole o conteúdo do
   arquivo `.streamlit/secrets.toml.example` deste repositório, preenchido.

A planilha precisa das abas: {", ".join(f"`{a}`" for a in servico.ABAS_OBRIGATORIAS)}.
Colunas com nomes ligeiramente diferentes (sem acento, abreviadas) são
reconhecidas automaticamente; colunas extras suas são preservadas.
"""
        )


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def principal() -> None:
    if not autenticado():
        return

    try:
        base = carregar_dados()
    except Exception as erro:  # noqa: BLE001
        st.error(f"Não consegui ler a planilha: {erro}")
        st.stop()
        return

    mes, ano = barra_lateral(base)

    st.title("Escala de Voluntários")

    abas = st.tabs(
        ["📋 Painel", "⚙️ Gerar escala", "💬 WhatsApp", "🔁 Trocas", "✅ Publicar", "❓ Ajuda"]
    )
    with abas[0]:
        aba_painel(base, mes, ano)
    with abas[1]:
        aba_gerar(base, mes, ano)
    with abas[2]:
        aba_whatsapp(base, mes, ano)
    with abas[3]:
        aba_trocas(base)
    with abas[4]:
        aba_publicar(base, mes, ano)
    with abas[5]:
        aba_ajuda(base)


principal()
