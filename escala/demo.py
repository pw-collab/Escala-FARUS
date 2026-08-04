"""Planilha de demonstração — o app abre funcionando mesmo sem credenciais.

Serve para três coisas: conhecer a ferramenta antes de configurar o Google
Cloud, treinar quem vai usar sem risco de estragar a planilha real, e dar aos
testes uma base de dados realista.
"""

from __future__ import annotations

from datetime import date, timedelta

from .dados import (
    ABA_CONFIG,
    ABA_ESCALA,
    ABA_FUNCOES,
    ABA_HISTORICO,
    ABA_INDISPONIBILIDADES,
    ABA_TROCAS,
    ABA_VOLUNTARIOS,
    CABECALHOS_PADRAO,
    carregar_base,
)
from .planilha import Aba, Planilha
from .textos import (
    competencia,
    dias_do_mes_na_semana,
    formatar_data_iso,
)

# (nome, telefone, ativo, funções)
VOLUNTARIOS_DEMO: list[tuple[str, str, bool, list[str]]] = [
    ("Ana Paula Ferreira", "(11) 91234-0001", True, ["Recepção", "Maná Coffee", "Intercessão"]),
    ("Bruno Carvalho", "(11) 91234-0002", True, ["Staff", "Projetor", "Captação"]),
    ("Camila Freitas", "(11) 91234-0003", True, ["Louvor", "Intercessão"]),
    ("Daniel Rocha", "(11) 91234-0004", True, ["Staff", "Abertura", "Oferta"]),
    ("Eduarda Lima", "(11) 91234-0005", True, ["Infantil 2-5", "Infantil 6-9"]),
    ("Felipe Andrade", "(11) 91234-0006", True, ["Projetor", "Captação"]),
    ("Gabriela Nunes", "(11) 91234-0007", True, ["Louvor", "Maná Coffee"]),
    ("Henrique Barros", "(11) 91234-0008", True, ["Staff", "Oferta", "Recepção"]),
    ("Isabela Moraes", "(11) 91234-0009", True, ["Infantil 6-9", "Geração Luz"]),
    ("João Vitor Pacheco", "(11) 91234-0010", True, ["Louvor", "Captação"]),
    ("Karina Souza", "(11) 91234-0011", True, ["Intercessão", "Recepção"]),
    ("Lucas Teixeira", "(11) 91234-0012", True, ["Staff", "Projetor", "Servo da Ceia"]),
    ("Mariana Alves", "(11) 91234-0013", True, ["Infantil 2-5", "Fusion"]),
    ("Nathan Ribeiro", "(11) 91234-0014", True, ["Louvor", "Abertura"]),
    ("Olívia Castro", "(11) 91234-0015", True, ["Maná Coffee", "Recepção"]),
    ("Pedro Henrique Dias", "(11) 91234-0016", True, ["Captação", "Projetor", "Servo da Ceia"]),
    ("Queila Martins", "(11) 91234-0017", True, ["Intercessão", "Infantil 6-9"]),
    ("Rafael Duarte", "(11) 91234-0018", True, ["Staff", "Abertura", "Oferta"]),
    ("Sabrina Pires", "(11) 91234-0019", True, ["Infantil 2-5", "Geração Luz"]),
    ("Thiago Mendes", "(11) 91234-0020", True, ["Louvor", "Staff"]),
    ("Úrsula Campos", "(11) 91234-0021", True, ["Recepção", "Maná Coffee"]),
    ("Vinícius Braga", "(11) 91234-0022", True, ["Oferta", "Projetor", "Fusion"]),
    ("Wesley Ramos", "(11) 91234-0023", True, ["Intercessão", "Louvor"]),
    ("Yasmin Cordeiro", "(11) 91234-0024", True, ["Infantil 2-5", "Infantil 6-9", "Servo da Ceia"]),
    ("Roberto Siqueira", "(11) 91234-0025", True, ["Staff", "Recepção"]),
    ("Beatriz Fonseca", "(11) 91234-0026", True, ["Maná Coffee", "Geração Luz", "Servo da Ceia"]),
    ("Caio Vasconcelos", "(11) 91234-0027", True, ["Captação", "Abertura"]),
    ("Débora Antunes", "(11) 91234-0028", True, ["Louvor", "Intercessão", "Fusion"]),
    ("Marcos Pinheiro", "(11) 91234-0029", False, ["Staff", "Projetor"]),
]

# (função, culto, mín., máx., coringa, data fixa)
FUNCOES_DEMO: list[tuple[str, str, int, int, bool, bool]] = [
    ("Staff", "Ambos", 1, 1, False, False),
    ("Abertura", "Domingo", 1, 1, False, False),
    ("Oferta", "Domingo", 1, 1, False, False),
    ("Projetor", "Domingo", 1, 1, False, False),
    ("Captação", "Domingo", 1, 1, True, False),
    ("Intercessão", "Ambos", 1, 2, True, False),
    ("Recepção", "Domingo", 1, 1, False, False),
    ("Maná Coffee", "Domingo", 2, 2, True, False),
    ("Infantil 2-5", "Domingo", 1, 2, False, False),
    ("Infantil 6-9", "Domingo", 1, 2, False, False),
    ("Geração Luz", "Domingo", 1, 1, False, True),
    ("Fusion", "Domingo", 1, 1, False, True),
    ("Louvor", "Domingo", 1, 3, True, False),
    ("Servo da Ceia", "Domingo", 1, 1, False, True),
]


def _sim_nao(valor: bool) -> str:
    return "Sim" if valor else "Não"


def _mes_seguinte(hoje: date) -> tuple[int, int]:
    return (1, hoje.year + 1) if hoje.month == 12 else (hoje.month + 1, hoje.year)


def _mes_anterior(mes: int, ano: int, passos: int = 1) -> tuple[int, int]:
    total = (ano * 12 + mes - 1) - passos
    return total % 12 + 1, total // 12


def _aba_voluntarios() -> Aba:
    linhas = [
        [nome, telefone, _sim_nao(ativo), "; ".join(funcoes), ""]
        for nome, telefone, ativo, funcoes in VOLUNTARIOS_DEMO
    ]
    linhas[-1][4] = "Afastado temporariamente"
    return Aba(ABA_VOLUNTARIOS, list(CABECALHOS_PADRAO[ABA_VOLUNTARIOS]), linhas)


def _aba_funcoes() -> Aba:
    linhas = [
        [nome, culto, str(minimo), str(maximo), _sim_nao(coringa), _sim_nao(fixa)]
        for nome, culto, minimo, maximo, coringa, fixa in FUNCOES_DEMO
    ]
    return Aba(ABA_FUNCOES, list(CABECALHOS_PADRAO[ABA_FUNCOES]), linhas)


def _aba_config(mes: int, ano: int) -> Aba:
    quartas = dias_do_mes_na_semana(ano, mes, 2)
    sextas = dias_do_mes_na_semana(ano, mes, 4)
    data_oracao = quartas[2] if len(quartas) > 2 else quartas[-1]
    data_evento = sextas[-1] if sextas else data_oracao

    linhas = [
        ["Mês/Ano", competencia(mes, ano)],
        ["Data da Ceia", "1º domingo"],
        ["Data do culto de oração", formatar_data_iso(data_oracao)],
        ["Data do Geração Luz", "2º domingo"],
        ["Data do Fusion", "3º domingo"],
        ["Datas sem culto", ""],
        ["Funções cobertas por coringa", "Abertura; Oferta"],
        ["Preencher até a quantidade máxima", "Sim"],
        [
            "Evento",
            f"{formatar_data_iso(data_evento)} | Vigília de Oração | Oração | Recepção; Maná Coffee",
        ],
    ]
    return Aba(ABA_CONFIG, list(CABECALHOS_PADRAO[ABA_CONFIG]), linhas)


def _aba_indisponibilidades(mes: int, ano: int) -> Aba:
    domingos = dias_do_mes_na_semana(ano, mes, 6)
    primeiro = domingos[0]
    segundo = domingos[1] if len(domingos) > 1 else primeiro
    linhas = [
        [
            "Camila Freitas",
            formatar_data_iso(primeiro - timedelta(days=2)),
            formatar_data_iso(primeiro + timedelta(days=1)),
            "Viagem a trabalho",
        ],
        [
            "Felipe Andrade",
            formatar_data_iso(segundo),
            formatar_data_iso(segundo),
            "Casamento na família",
        ],
    ]
    return Aba(
        ABA_INDISPONIBILIDADES, list(CABECALHOS_PADRAO[ABA_INDISPONIBILIDADES]), linhas
    )


def _aba_trocas() -> Aba:
    return Aba(ABA_TROCAS, list(CABECALHOS_PADRAO[ABA_TROCAS]), [])


def _aba_vazia_de_atribuicoes(titulo: str) -> Aba:
    return Aba(titulo, list(CABECALHOS_PADRAO[titulo]), [])


def _planilha_base(mes: int, ano: int) -> Planilha:
    planilha = Planilha()
    planilha.definir(_aba_voluntarios())
    planilha.definir(_aba_funcoes())
    planilha.definir(_aba_config(mes, ano))
    planilha.definir(_aba_indisponibilidades(mes, ano))
    planilha.definir(_aba_vazia_de_atribuicoes(ABA_HISTORICO))
    planilha.definir(_aba_vazia_de_atribuicoes(ABA_ESCALA))
    planilha.definir(_aba_trocas())
    return planilha


def _historico_simulado(mes: int, ano: int, meses_anteriores: int = 2) -> list[list[str]]:
    """Gera histórico rodando o próprio motor nos meses anteriores.

    Assim a demonstração já começa com rodízio "em andamento", em vez de um
    estado inicial artificial em que ninguém nunca serviu.
    """
    from .motor import gerar_escala  # import local: evita ciclo na importação

    linhas: list[list[str]] = []
    acumulado: list[list[str]] = []

    for passo in range(meses_anteriores, 0, -1):
        mes_alvo, ano_alvo = _mes_anterior(mes, ano, passo)
        planilha = _planilha_base(mes_alvo, ano_alvo)
        # Indisponibilidades e eventos são do mês corrente; não valem para o passado.
        planilha.definir(
            Aba(
                ABA_INDISPONIBILIDADES,
                list(CABECALHOS_PADRAO[ABA_INDISPONIBILIDADES]),
                [],
            )
        )
        config = _aba_config(mes_alvo, ano_alvo)
        config.linhas = [linha for linha in config.linhas if linha[0] != "Evento"]
        planilha.definir(config)
        planilha.definir(
            Aba(ABA_HISTORICO, list(CABECALHOS_PADRAO[ABA_HISTORICO]), list(acumulado))
        )

        base = carregar_base(planilha)
        resultado = gerar_escala(base, mes_alvo, ano_alvo)
        novas = [
            [formatar_data_iso(a.data), a.culto, a.funcao, a.nome]
            for a in resultado.atribuicoes
        ]
        acumulado.extend(novas)
        linhas.extend(novas)

    return linhas


def planilha_demo(mes: int | None = None, ano: int | None = None) -> Planilha:
    """Monta a planilha completa de demonstração para o mês informado."""
    if mes is None or ano is None:
        mes, ano = _mes_seguinte(date.today())

    planilha = _planilha_base(mes, ano)
    planilha.definir(
        Aba(
            ABA_HISTORICO,
            list(CABECALHOS_PADRAO[ABA_HISTORICO]),
            _historico_simulado(mes, ano),
        )
    )
    return planilha


def repositorio_demo(mes: int | None = None, ano: int | None = None):
    from .repositorio import RepositorioMemoria

    return RepositorioMemoria(planilha_demo(mes, ano), nome="Planilha de demonstração")
