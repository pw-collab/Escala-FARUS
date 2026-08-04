"""Tradução entre as abas da planilha e os objetos de domínio.

Aqui ficam concentrados: os nomes das abas, os apelidos aceitos para cada
coluna, a leitura das `Configurações do Mês` e a serialização de volta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .modelos import (
    ALVOS_CORINGA_PADRAO,
    CULTO_AMBOS,
    CULTO_DOMINGO,
    CULTO_ORACAO,
    FUNCAO_CEIA,
    TROCA_PENDENTE,
    Atribuicao,
    Evento,
    Funcao,
    Indisponibilidade,
    Troca,
    Voluntario,
)
from .planilha import Aba, MapaColunas, Planilha
from .textos import (
    domingos_do_mes,
    formatar_data_iso,
    limpar,
    normalizar,
    parse_bool,
    parse_data,
    parse_datas,
    parse_int,
    parse_lista,
    parse_mes_ano,
    vazio,
)

# ---------------------------------------------------------------------------
# Nomes das abas
# ---------------------------------------------------------------------------

ABA_VOLUNTARIOS = "Voluntários"
ABA_FUNCOES = "Funções"
ABA_CONFIG = "Configurações do Mês"
ABA_INDISPONIBILIDADES = "Indisponibilidades"
ABA_HISTORICO = "Histórico"
ABA_ESCALA = "Escala Gerada"
ABA_TROCAS = "Trocas"

ABAS_OBRIGATORIAS = (
    ABA_VOLUNTARIOS,
    ABA_FUNCOES,
    ABA_CONFIG,
    ABA_INDISPONIBILIDADES,
    ABA_HISTORICO,
    ABA_ESCALA,
    ABA_TROCAS,
)

# ---------------------------------------------------------------------------
# Apelidos aceitos para cada coluna
#
# A ordem importa: campos declarados antes têm prioridade na resolução.
# ---------------------------------------------------------------------------

COLUNAS_VOLUNTARIOS: dict[str, tuple[str, ...]] = {
    "nome": ("Nome",),
    "telefone": ("Telefone", "Celular", "WhatsApp", "Contato"),
    "ativo": ("Ativo", "Está ativo"),
    "funcoes": ("Funções que exerce", "Funções", "Funcoes que exerce", "Habilidades"),
    "observacoes": ("Observações", "Obs"),
}

COLUNAS_FUNCOES: dict[str, tuple[str, ...]] = {
    "nome": ("Função", "Nome da função", "Nome"),
    "culto": ("Culto (Domingo/Oração/Ambos)", "Culto", "Tipo de culto"),
    "qtd_min": ("Qtd. mín.", "Qtd min", "Quantidade mínima", "Mínimo", "Min"),
    "qtd_max": ("Qtd. máx.", "Qtd max", "Quantidade máxima", "Máximo", "Max"),
    "coringa": ("É coringa?", "Coringa"),
    "data_fixa": ("É de data fixa no mês?", "Data fixa", "É de data fixa"),
}

COLUNAS_CONFIG: dict[str, tuple[str, ...]] = {
    "campo": ("Campo", "Chave", "Parâmetro", "Item"),
    "valor": ("Valor", "Conteúdo"),
}

COLUNAS_INDISPONIBILIDADES: dict[str, tuple[str, ...]] = {
    "nome": ("Nome",),
    "inicio": ("Data início", "Início", "Data inicial", "De"),
    "fim": ("Data fim", "Fim", "Data final", "Até"),
    "motivo": ("Motivo", "Observação"),
}

COLUNAS_ATRIBUICAO: dict[str, tuple[str, ...]] = {
    "data": ("Data",),
    "culto": ("Culto",),
    "funcao": ("Função",),
    "nome": ("Nome", "Voluntário"),
}

COLUNAS_TROCAS: dict[str, tuple[str, ...]] = {
    "data": ("Data do culto", "Data"),
    "funcao": ("Função",),
    "nome_original": ("Nome original", "Original", "Escalado"),
    "nome_substituto": ("Nome substituto", "Substituto", "Substituição"),
    "motivo": ("Motivo",),
    "status": ("Status", "Situação"),
}

CABECALHOS_PADRAO: dict[str, list[str]] = {
    ABA_VOLUNTARIOS: ["Nome", "Telefone", "Ativo", "Funções que exerce", "Observações"],
    ABA_FUNCOES: [
        "Função",
        "Culto (Domingo/Oração/Ambos)",
        "Qtd. mín.",
        "Qtd. máx.",
        "É coringa?",
        "É de data fixa no mês?",
    ],
    ABA_CONFIG: ["Campo", "Valor"],
    ABA_INDISPONIBILIDADES: ["Nome", "Data início", "Data fim", "Motivo"],
    ABA_HISTORICO: ["Data", "Culto", "Função", "Nome"],
    ABA_ESCALA: ["Data", "Culto", "Função", "Nome"],
    ABA_TROCAS: [
        "Data do culto",
        "Função",
        "Nome original",
        "Nome substituto",
        "Motivo",
        "Status",
    ],
}

COLUNAS_POR_ABA: dict[str, dict[str, tuple[str, ...]]] = {
    ABA_VOLUNTARIOS: COLUNAS_VOLUNTARIOS,
    ABA_FUNCOES: COLUNAS_FUNCOES,
    ABA_CONFIG: COLUNAS_CONFIG,
    ABA_INDISPONIBILIDADES: COLUNAS_INDISPONIBILIDADES,
    ABA_HISTORICO: COLUNAS_ATRIBUICAO,
    ABA_ESCALA: COLUNAS_ATRIBUICAO,
    ABA_TROCAS: COLUNAS_TROCAS,
}

# ---------------------------------------------------------------------------
# Chaves reconhecidas em `Configurações do Mês`
# ---------------------------------------------------------------------------

CHAVE_MES_ANO = ("mes ano", "mes/ano", "competencia", "mes de referencia", "mes")
CHAVE_CEIA = ("data da ceia", "ceia", "data ceia")
CHAVE_ORACAO = (
    "data do culto de oracao",
    "culto de oracao",
    "data da oracao",
    "data do culto de oracao 1x mes",
)
CHAVE_ALVOS_CORINGA = (
    "funcoes cobertas por coringa",
    "funcoes que o coringa cobre",
    "cobertura coringa",
)
CHAVE_PREENCHER_MAXIMO = (
    "preencher ate a quantidade maxima",
    "preencher ate o maximo",
    "usar quantidade maxima",
)
CHAVE_SEM_CULTO = ("datas sem culto", "domingos sem culto", "datas canceladas")
PREFIXO_EVENTO = "evento"


@dataclass
class ConfiguracoesMes:
    """Leitura interpretada da aba `Configurações do Mês`."""

    mes: int | None = None
    ano: int | None = None
    data_ceia: date | None = None
    datas_oracao: list[date] = field(default_factory=list)
    datas_por_funcao: dict[str, list[date]] = field(default_factory=dict)
    eventos: list[Evento] = field(default_factory=list)
    alvos_coringa: list[str] = field(default_factory=lambda: list(ALVOS_CORINGA_PADRAO))
    preencher_maximo: bool = True
    datas_sem_culto: list[date] = field(default_factory=list)
    itens: list[tuple[str, str]] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def datas_da_funcao(self, funcao: str) -> list[date]:
        return self.datas_por_funcao.get(normalizar(funcao), [])

    def aceita_coringa(self, funcao: str) -> bool:
        alvo = normalizar(funcao)
        return any(normalizar(a) == alvo for a in self.alvos_coringa)


@dataclass
class BaseDados:
    """Tudo o que o motor precisa, já convertido para objetos de domínio."""

    voluntarios: list[Voluntario] = field(default_factory=list)
    funcoes: list[Funcao] = field(default_factory=list)
    config: ConfiguracoesMes = field(default_factory=ConfiguracoesMes)
    indisponibilidades: list[Indisponibilidade] = field(default_factory=list)
    historico: list[Atribuicao] = field(default_factory=list)
    escala: list[Atribuicao] = field(default_factory=list)
    trocas: list[Troca] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    planilha: Planilha = field(default_factory=Planilha)

    @property
    def voluntarios_ativos(self) -> list[Voluntario]:
        return [v for v in self.voluntarios if v.ativo]

    def funcao_por_nome(self, nome: str) -> Funcao | None:
        alvo = normalizar(nome)
        for funcao in self.funcoes:
            if funcao.chave == alvo:
                return funcao
        return None

    def ordem_das_funcoes(self) -> list[str]:
        """Ordem canônica de exibição das funções (a da aba `Funções`)."""
        return [f.nome for f in sorted(self.funcoes, key=lambda f: f.ordem)]


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def _mapa(aba: Aba, colunas: dict[str, tuple[str, ...]]) -> MapaColunas:
    return MapaColunas(aba.cabecalho, colunas)


def ler_voluntarios(aba: Aba | None, avisos: list[str]) -> list[Voluntario]:
    if aba is None:
        avisos.append(f"Aba `{ABA_VOLUNTARIOS}` não encontrada.")
        return []
    mapa = _mapa(aba, COLUNAS_VOLUNTARIOS)
    if faltando := mapa.faltando(("nome",)):
        avisos.append(f"Aba `{aba.titulo}`: coluna obrigatória não encontrada: {faltando}.")
        return []

    voluntarios: list[Voluntario] = []
    vistos: set[str] = set()
    for linha in aba.linhas_uteis():
        nome = mapa.ler(linha, "nome")
        if vazio(nome):
            continue
        chave = normalizar(nome)
        if chave in vistos:
            avisos.append(f"Voluntário duplicado em `{aba.titulo}`: {nome}. Usando a primeira ocorrência.")
            continue
        vistos.add(chave)
        voluntarios.append(
            Voluntario(
                nome=nome,
                telefone=mapa.ler(linha, "telefone"),
                ativo=parse_bool(mapa.ler(linha, "ativo"), padrao=True),
                funcoes=parse_lista(mapa.ler(linha, "funcoes")),
                observacoes=mapa.ler(linha, "observacoes"),
                bruto=list(linha),
            )
        )
    return voluntarios


def ler_funcoes(aba: Aba | None, avisos: list[str]) -> list[Funcao]:
    if aba is None:
        avisos.append(f"Aba `{ABA_FUNCOES}` não encontrada.")
        return []
    mapa = _mapa(aba, COLUNAS_FUNCOES)
    if faltando := mapa.faltando(("nome",)):
        avisos.append(f"Aba `{aba.titulo}`: coluna obrigatória não encontrada: {faltando}.")
        return []

    funcoes: list[Funcao] = []
    vistos: set[str] = set()
    for ordem, linha in enumerate(aba.linhas_uteis()):
        nome = mapa.ler(linha, "nome")
        if vazio(nome):
            continue
        chave = normalizar(nome)
        if chave in vistos:
            avisos.append(f"Função duplicada em `{aba.titulo}`: {nome}. Usando a primeira ocorrência.")
            continue
        vistos.add(chave)

        qtd_min = parse_int(mapa.ler(linha, "qtd_min"), padrao=1)
        qtd_max = parse_int(mapa.ler(linha, "qtd_max"), padrao=qtd_min)
        if qtd_max < qtd_min:
            qtd_max = qtd_min
        culto = mapa.ler(linha, "culto") or CULTO_DOMINGO
        funcoes.append(
            Funcao(
                nome=nome,
                culto=culto,
                qtd_min=qtd_min,
                qtd_max=qtd_max,
                coringa=parse_bool(mapa.ler(linha, "coringa")),
                data_fixa=parse_bool(mapa.ler(linha, "data_fixa")),
                ordem=ordem,
                bruto=list(linha),
            )
        )
    return funcoes


def ler_indisponibilidades(
    aba: Aba | None, ano: int | None, mes: int | None, avisos: list[str]
) -> list[Indisponibilidade]:
    if aba is None:
        return []
    mapa = _mapa(aba, COLUNAS_INDISPONIBILIDADES)
    if mapa.faltando(("nome",)):
        avisos.append(f"Aba `{aba.titulo}`: coluna `Nome` não encontrada.")
        return []

    registros: list[Indisponibilidade] = []
    for linha in aba.linhas_uteis():
        nome = mapa.ler(linha, "nome")
        if vazio(nome):
            continue
        inicio = parse_data(mapa.ler(linha, "inicio"), ano=ano, mes=mes)
        fim = parse_data(mapa.ler(linha, "fim"), ano=ano, mes=mes)
        if inicio is None and fim is None:
            avisos.append(f"Indisponibilidade de {nome} ignorada: nenhuma data legível.")
            continue
        registros.append(
            Indisponibilidade(
                nome=nome,
                inicio=inicio,
                fim=fim,
                motivo=mapa.ler(linha, "motivo"),
                bruto=list(linha),
            )
        )
    return registros


def ler_atribuicoes(
    aba: Aba | None, ano: int | None, mes: int | None, avisos: list[str]
) -> list[Atribuicao]:
    if aba is None:
        return []
    mapa = _mapa(aba, COLUNAS_ATRIBUICAO)
    if faltando := mapa.faltando(("data", "funcao", "nome")):
        avisos.append(f"Aba `{aba.titulo}`: colunas não encontradas: {faltando}.")
        return []

    registros: list[Atribuicao] = []
    for linha in aba.linhas_uteis():
        nome = mapa.ler(linha, "nome")
        funcao = mapa.ler(linha, "funcao")
        if vazio(nome) and vazio(funcao):
            continue
        registros.append(
            Atribuicao(
                data=parse_data(mapa.ler(linha, "data"), ano=ano, mes=mes),
                culto=mapa.ler(linha, "culto"),
                funcao=funcao,
                nome=nome,
                bruto=list(linha),
            )
        )
    return registros


def ler_trocas(
    aba: Aba | None, ano: int | None, mes: int | None, avisos: list[str]
) -> list[Troca]:
    if aba is None:
        return []
    mapa = _mapa(aba, COLUNAS_TROCAS)
    if faltando := mapa.faltando(("data", "funcao", "nome_original")):
        avisos.append(f"Aba `{aba.titulo}`: colunas não encontradas: {faltando}.")
        return []

    registros: list[Troca] = []
    for linha in aba.linhas_uteis():
        original = mapa.ler(linha, "nome_original")
        funcao = mapa.ler(linha, "funcao")
        if vazio(original) and vazio(funcao):
            continue
        registros.append(
            Troca(
                data=parse_data(mapa.ler(linha, "data"), ano=ano, mes=mes),
                funcao=funcao,
                nome_original=original,
                nome_substituto=mapa.ler(linha, "nome_substituto"),
                motivo=mapa.ler(linha, "motivo"),
                status=mapa.ler(linha, "status") or TROCA_PENDENTE,
                bruto=list(linha),
            )
        )
    return registros


def _pares_config(aba: Aba | None) -> list[tuple[str, str]]:
    if aba is None:
        return []
    mapa = _mapa(aba, COLUNAS_CONFIG)
    pares: list[tuple[str, str]] = []
    for linha in aba.linhas_uteis():
        if mapa.tem("campo"):
            campo = mapa.ler(linha, "campo")
            valor = mapa.ler(linha, "valor")
        else:  # aba sem cabeçalho reconhecível: assume duas primeiras colunas
            campo = limpar(linha[0]) if linha else ""
            valor = limpar(linha[1]) if len(linha) > 1 else ""
        if vazio(campo):
            continue
        pares.append((campo, valor))
    return pares


def _casa_chave(campo: str, chaves: tuple[str, ...]) -> bool:
    alvo = normalizar(campo)
    return any(alvo == normalizar(c) for c in chaves)


def ler_configuracoes(
    aba: Aba | None, funcoes: list[Funcao], avisos: list[str]
) -> ConfiguracoesMes:
    """Interpreta a aba `Configurações do Mês`.

    A leitura acontece em duas passadas: primeiro a competência (mês/ano),
    porque ela é o contexto para datas curtas como "08/03"; depois o resto.
    """
    config = ConfiguracoesMes()
    pares = _pares_config(aba)
    config.itens = pares

    if aba is None:
        avisos.append(f"Aba `{ABA_CONFIG}` não encontrada.")
        return config

    for campo, valor in pares:
        if _casa_chave(campo, CHAVE_MES_ANO):
            lido = parse_mes_ano(valor)
            if lido:
                config.mes, config.ano = lido
            elif not vazio(valor):
                config.avisos.append(f"Não entendi a competência `{valor}` em `{campo}`.")
            break

    if config.mes is None:
        config.avisos.append(
            "Campo `Mês/Ano` ausente ou ilegível em `Configurações do Mês` — "
            "informe o mês na tela de geração."
        )

    ano, mes = config.ano, config.mes

    for campo, valor in pares:
        if _casa_chave(campo, CHAVE_MES_ANO):
            continue

        if _casa_chave(campo, CHAVE_CEIA):
            if normalizar(valor) in {"nenhuma", "nenhum", "sem ceia", "nao"}:
                config.data_ceia = None
            else:
                lida = parse_data(valor, ano=ano, mes=mes)
                if lida:
                    config.data_ceia = lida
                elif not vazio(valor):
                    config.avisos.append(f"Não entendi a data da Ceia: `{valor}`.")
            continue

        if _casa_chave(campo, CHAVE_ORACAO):
            config.datas_oracao = parse_datas(valor, ano=ano, mes=mes)
            if not config.datas_oracao and not vazio(valor):
                config.avisos.append(f"Não entendi a data do culto de oração: `{valor}`.")
            continue

        if _casa_chave(campo, CHAVE_ALVOS_CORINGA):
            itens = parse_lista(valor)
            if itens:
                config.alvos_coringa = itens
            continue

        if _casa_chave(campo, CHAVE_PREENCHER_MAXIMO):
            config.preencher_maximo = parse_bool(valor, padrao=True)
            continue

        if _casa_chave(campo, CHAVE_SEM_CULTO):
            config.datas_sem_culto = parse_datas(valor, ano=ano, mes=mes)
            continue

        if normalizar(campo).startswith(PREFIXO_EVENTO):
            evento = _ler_evento(campo, valor, ano, mes, config.avisos)
            if evento:
                config.eventos.append(evento)
            continue

        # Sobrou: pode ser a data de uma função "de data fixa no mês".
        alvo = _funcao_de_data_fixa(campo, funcoes)
        if alvo:
            datas = parse_datas(valor, ano=ano, mes=mes)
            if datas:
                config.datas_por_funcao.setdefault(alvo, []).extend(datas)
            elif not vazio(valor):
                config.avisos.append(f"Não entendi a data de `{campo}`: `{valor}`.")

    # A Ceia tem padrão: 1º domingo do mês.
    if config.data_ceia is None and not _tem_chave(pares, CHAVE_CEIA) and ano and mes:
        domingos = domingos_do_mes(ano, mes)
        if domingos:
            config.data_ceia = domingos[0]
            config.avisos.append(
                "Sem `Data da Ceia` nas configurações: assumindo o 1º domingo "
                f"({config.data_ceia.strftime('%d/%m')})."
            )

    # A função da Ceia herda a data da Ceia.
    if config.data_ceia:
        config.datas_por_funcao.setdefault(normalizar(FUNCAO_CEIA), []).append(config.data_ceia)

    for chave, datas in config.datas_por_funcao.items():
        config.datas_por_funcao[chave] = sorted(set(datas))

    return config


def _tem_chave(pares: list[tuple[str, str]], chaves: tuple[str, ...]) -> bool:
    return any(_casa_chave(campo, chaves) for campo, _ in pares)


def _funcao_de_data_fixa(campo: str, funcoes: list[Funcao]) -> str | None:
    """Liga uma linha "Data do X" à função de data fixa correspondente.

    Aceita `Data do Infantil 10-12`, `Data Infantil 10-12` ou o nome puro da
    função, sempre comparando de forma normalizada.
    """
    alvo = normalizar(campo)
    for prefixo in ("data de ", "data do ", "data da ", "data dos ", "data das ", "data "):
        if alvo.startswith(prefixo):
            alvo = alvo[len(prefixo):]
            break

    if not alvo:
        return None
    for funcao in funcoes:
        if not funcao.data_fixa:
            continue
        if funcao.chave == alvo or alvo.startswith(funcao.chave) or funcao.chave.startswith(alvo):
            return funcao.chave
    return None


def _ler_evento(
    campo: str, valor: str, ano: int | None, mes: int | None, avisos: list[str]
) -> Evento | None:
    """Lê ``Evento`` = ``data | nome | base | funções extras``.

    `base` e `funções extras` são opcionais. `base` aceita "Domingo", "Oração"
    ou "Nenhum" (o evento só terá as funções próprias listadas).
    """
    partes = [limpar(p) for p in str(valor).split("|")]
    if len(partes) == 1 and vazio(partes[0]):
        return None

    data = parse_data(partes[0] if partes else "", ano=ano, mes=mes)
    if data is None:
        avisos.append(f"Evento `{campo}` ignorado: data ilegível em `{valor}`.")
        return None

    nome = partes[1] if len(partes) > 1 and partes[1] else ""
    if not nome:
        # "Evento: Vigília" -> o nome pode estar no próprio campo.
        nome = limpar(str(campo).split(":", 1)[1]) if ":" in str(campo) else "Evento"

    # Campo em branco = usar o padrão; "Nenhum" = evento sem culto base.
    base = CULTO_DOMINGO
    if len(partes) > 2 and partes[2]:
        chave_base = normalizar(partes[2])
        if chave_base.startswith("orac"):
            base = CULTO_ORACAO
        elif chave_base in {"nenhum", "nenhuma", "so extras", "somente extras", "proprias"}:
            base = ""
        elif chave_base.startswith("domingo") or chave_base == normalizar(CULTO_AMBOS):
            base = CULTO_DOMINGO
        else:
            avisos.append(
                f"Evento `{nome}`: base `{partes[2]}` desconhecida, assumindo Domingo."
            )

    extras = parse_lista(partes[3]) if len(partes) > 3 else []
    return Evento(data=data, nome=nome, base=base, funcoes_extras=extras)


def carregar_base(planilha: Planilha) -> BaseDados:
    """Ponto de entrada: converte o snapshot da planilha em `BaseDados`."""
    avisos: list[str] = []
    funcoes = ler_funcoes(planilha.obter(ABA_FUNCOES), avisos)
    config = ler_configuracoes(planilha.obter(ABA_CONFIG), funcoes, avisos)
    ano, mes = config.ano, config.mes

    base = BaseDados(
        voluntarios=ler_voluntarios(planilha.obter(ABA_VOLUNTARIOS), avisos),
        funcoes=funcoes,
        config=config,
        indisponibilidades=ler_indisponibilidades(
            planilha.obter(ABA_INDISPONIBILIDADES), ano, mes, avisos
        ),
        historico=ler_atribuicoes(planilha.obter(ABA_HISTORICO), ano, mes, avisos),
        escala=ler_atribuicoes(planilha.obter(ABA_ESCALA), ano, mes, avisos),
        trocas=ler_trocas(planilha.obter(ABA_TROCAS), ano, mes, avisos),
        avisos=avisos,
        planilha=planilha,
    )
    base.avisos.extend(config.avisos)
    base.avisos.extend(_diagnosticar(base))
    return base


def _diagnosticar(base: BaseDados) -> list[str]:
    """Avisos úteis que só aparecem quando cruzamos as abas."""
    avisos: list[str] = []
    nomes_funcoes = {f.chave for f in base.funcoes}

    desconhecidas: set[str] = set()
    for voluntario in base.voluntarios:
        for funcao in voluntario.funcoes:
            chave = normalizar(funcao)
            if chave and chave not in nomes_funcoes and chave not in {"todas", "todos"}:
                desconhecidas.add(funcao)
    if desconhecidas:
        avisos.append(
            "Funções citadas em `Voluntários` que não existem na aba `Funções`: "
            + ", ".join(sorted(desconhecidas))
        )

    nomes_voluntarios = {v.chave for v in base.voluntarios}
    ausentes = {
        i.nome for i in base.indisponibilidades if i.chave not in nomes_voluntarios
    }
    if ausentes:
        avisos.append(
            "Nomes em `Indisponibilidades` que não estão em `Voluntários`: "
            + ", ".join(sorted(ausentes))
        )

    for funcao in base.funcoes:
        if not funcao.data_fixa:
            continue
        if not base.config.datas_da_funcao(funcao.nome):
            avisos.append(
                f"Função `{funcao.nome}` está marcada como de data fixa, mas não há "
                f"linha `Data do {funcao.nome}` em `{ABA_CONFIG}` — ela não será escalada."
            )

    sem_gente = [
        f.nome
        for f in base.funcoes
        if not any(v.exerce(f.nome) for v in base.voluntarios_ativos)
    ]
    if sem_gente:
        avisos.append(
            "Funções sem nenhum voluntário ativo apto: " + ", ".join(sem_gente)
        )
    return avisos


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------

def aba_para_atribuicoes(
    titulo: str, cabecalho: list[str] | None, registros: list[Atribuicao]
) -> Aba:
    """Reconstrói uma aba de escala/histórico a partir dos objetos."""
    colunas = list(cabecalho) if cabecalho else list(CABECALHOS_PADRAO[ABA_ESCALA])
    mapa = MapaColunas(colunas, COLUNAS_ATRIBUICAO)
    linhas = [
        mapa.montar(
            {
                "data": formatar_data_iso(registro.data),
                "culto": registro.culto,
                "funcao": registro.funcao,
                "nome": registro.nome,
            },
            base=registro.bruto,
        )
        for registro in registros
    ]
    return Aba(titulo=titulo, cabecalho=colunas, linhas=linhas)


def aba_para_trocas(
    titulo: str, cabecalho: list[str] | None, registros: list[Troca]
) -> Aba:
    colunas = list(cabecalho) if cabecalho else list(CABECALHOS_PADRAO[ABA_TROCAS])
    mapa = MapaColunas(colunas, COLUNAS_TROCAS)
    linhas = [
        mapa.montar(
            {
                "data": formatar_data_iso(registro.data),
                "funcao": registro.funcao,
                "nome_original": registro.nome_original,
                "nome_substituto": registro.nome_substituto,
                "motivo": registro.motivo,
                "status": registro.status,
            },
            base=registro.bruto,
        )
        for registro in registros
    ]
    return Aba(titulo=titulo, cabecalho=colunas, linhas=linhas)
