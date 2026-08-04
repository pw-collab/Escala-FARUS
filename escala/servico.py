"""Fachada usada pela interface: orquestra leitura, geração e gravação.

A interface Streamlit não fala com `gspread` nem monta linhas de planilha — ela
chama estas funções, que cuidam de converter objetos de domínio em abas e
persistir pelo repositório configurado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .dados import (
    ABA_CONFIG,
    ABA_ESCALA,
    ABA_HISTORICO,
    ABA_TROCAS,
    ABAS_OBRIGATORIAS,
    CABECALHOS_PADRAO,
    BaseDados,
    ConfiguracoesMes,
    aba_para_atribuicoes,
    aba_para_trocas,
    atualizar_aba_config,
    carregar_base,
)
from .modelos import Atribuicao, Troca
from .planilha import Aba
from .repositorio import Repositorio
from .textos import formatar_data, normalizar
from .trocas import ResultadoTrocas, aplicar_trocas


def carregar(repositorio: Repositorio) -> BaseDados:
    """Lê a planilha inteira e devolve os dados já interpretados."""
    return carregar_base(repositorio.carregar())


def _cabecalho_de(base: BaseDados, titulo: str) -> list[str]:
    aba = base.planilha.obter(titulo)
    if aba and aba.cabecalho:
        return list(aba.cabecalho)
    return list(CABECALHOS_PADRAO[titulo])


def _titulo_real(base: BaseDados, titulo: str) -> str:
    """Preserva o nome da aba como está na planilha (pode estar sem acento)."""
    aba = base.planilha.obter(titulo)
    return aba.titulo if aba else titulo


def salvar_escala(
    repositorio: Repositorio, base: BaseDados, atribuicoes: list[Atribuicao]
) -> None:
    """Substitui o conteúdo da aba `Escala Gerada` pelo rascunho atual."""
    aba = aba_para_atribuicoes(
        _titulo_real(base, ABA_ESCALA), _cabecalho_de(base, ABA_ESCALA), atribuicoes
    )
    repositorio.salvar_aba(aba)


def salvar_historico(
    repositorio: Repositorio, base: BaseDados, registros: list[Atribuicao]
) -> None:
    aba = aba_para_atribuicoes(
        _titulo_real(base, ABA_HISTORICO), _cabecalho_de(base, ABA_HISTORICO), registros
    )
    repositorio.salvar_aba(aba)


def salvar_trocas(
    repositorio: Repositorio, base: BaseDados, registros: list[Troca]
) -> None:
    aba = aba_para_trocas(
        _titulo_real(base, ABA_TROCAS), _cabecalho_de(base, ABA_TROCAS), registros
    )
    repositorio.salvar_aba(aba)


def salvar_configuracoes(
    repositorio: Repositorio, base: BaseDados, config: ConfiguracoesMes
) -> None:
    """Persiste na planilha a configuração montada na tela de geração."""
    aba = atualizar_aba_config(base.planilha.obter(ABA_CONFIG), config, base.funcoes)
    repositorio.salvar_aba(aba)


def registrar_troca(
    repositorio: Repositorio, base: BaseDados, troca: Troca
) -> list[Troca]:
    """Acrescenta uma troca à aba `Trocas` (formulário do app)."""
    registros = list(base.trocas) + [troca]
    salvar_trocas(repositorio, base, registros)
    return registros


# ---------------------------------------------------------------------------
# Publicação
# ---------------------------------------------------------------------------

@dataclass
class ResultadoPublicacao:
    publicado: bool
    mensagem: str
    linhas_gravadas: int = 0
    datas_em_conflito: list[date] = field(default_factory=list)


def datas_ja_publicadas(base: BaseDados, atribuicoes: list[Atribuicao]) -> list[date]:
    """Datas do rascunho que já têm registro no `Histórico`."""
    do_rascunho = {a.data for a in atribuicoes if a.data}
    no_historico = {h.data for h in base.historico if h.data}
    return sorted(do_rascunho & no_historico)


def publicar(
    repositorio: Repositorio,
    base: BaseDados,
    atribuicoes: list[Atribuicao],
    substituir: bool = False,
) -> ResultadoPublicacao:
    """Grava a escala no `Histórico`, fechando o ciclo de rodízio do mês.

    Se as datas já constam no histórico (regeração após uma publicação), a
    operação só prossegue com `substituir=True`, e nesse caso as linhas antigas
    daquelas datas são removidas antes da gravação. Assim o rodízio nunca conta
    o mesmo culto duas vezes.
    """
    validas = [a for a in atribuicoes if a.data and a.nome]
    if not validas:
        return ResultadoPublicacao(False, "Não há escala para publicar.")

    conflitos = datas_ja_publicadas(base, validas)
    if conflitos and not substituir:
        lista = ", ".join(formatar_data(d) for d in conflitos)
        return ResultadoPublicacao(
            False,
            "Estas datas já estão no Histórico: "
            f"{lista}. Marque a opção de substituir para regravá-las.",
            datas_em_conflito=conflitos,
        )

    datas_novas = {a.data for a in validas}
    if substituir:
        preservado = [h for h in base.historico if h.data not in datas_novas]
    else:
        preservado = list(base.historico)

    novo_historico = preservado + [
        Atribuicao(data=a.data, culto=a.culto, funcao=a.funcao, nome=a.nome)
        for a in validas
    ]
    novo_historico.sort(key=lambda a: (a.data or date.min, a.culto, a.funcao, a.nome))

    salvar_historico(repositorio, base, novo_historico)
    return ResultadoPublicacao(
        True,
        f"{len(validas)} linhas gravadas no Histórico. Rodízio do mês fechado.",
        linhas_gravadas=len(validas),
        datas_em_conflito=conflitos,
    )


# ---------------------------------------------------------------------------
# Trocas
# ---------------------------------------------------------------------------

def processar_trocas(repositorio: Repositorio, base: BaseDados) -> ResultadoTrocas:
    """Aplica as trocas pendentes e grava as abas afetadas."""
    resultado = aplicar_trocas(base.trocas, base.escala, base.historico)

    if resultado.houve_mudanca:
        if resultado.escala != base.escala:
            salvar_escala(repositorio, base, resultado.escala)
        if resultado.historico != base.historico:
            salvar_historico(repositorio, base, resultado.historico)

    if resultado.trocas != base.trocas:
        salvar_trocas(repositorio, base, resultado.trocas)

    return resultado


# ---------------------------------------------------------------------------
# Estrutura da planilha
# ---------------------------------------------------------------------------

# Só faz sentido semear linhas de exemplo em abas de catálogo/configuração.
_ABAS_COM_EXEMPLO = {"Funções", "Configurações do Mês"}


def abas_faltantes(base: BaseDados) -> list[str]:
    return [titulo for titulo in ABAS_OBRIGATORIAS if base.planilha.obter(titulo) is None]


def garantir_estrutura(repositorio: Repositorio, base: BaseDados) -> list[str]:
    """Cria as abas que estiverem faltando, já com cabeçalho e exemplos."""
    from .demo import planilha_demo

    faltantes = abas_faltantes(base)
    if not faltantes:
        return []

    modelo = planilha_demo()
    criadas: list[str] = []
    for titulo in faltantes:
        exemplo = modelo.obter(titulo)
        linhas = exemplo.linhas if exemplo and titulo in _ABAS_COM_EXEMPLO else []
        repositorio.criar_aba(titulo, list(CABECALHOS_PADRAO[titulo]), linhas)
        criadas.append(titulo)
    return criadas


def aba_bruta(base: BaseDados, titulo: str) -> Aba | None:
    return base.planilha.obter(titulo)


def escala_atual(base: BaseDados) -> list[Atribuicao]:
    """A escala que está na planilha agora (com edições manuais do admin)."""
    return list(base.escala)


def nomes_conhecidos(base: BaseDados) -> list[str]:
    return sorted((v.nome for v in base.voluntarios), key=normalizar)
