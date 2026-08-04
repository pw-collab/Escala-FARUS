"""Calendário do mês e composição das funções de cada culto."""

from datetime import date

from conftest import aba, base_de, montar_planilha

from escala.calendario import descrever_culto, funcoes_do_culto, montar_cultos
from escala.dados import (
    ABA_CONFIG,
    ABA_FUNCOES,
    ABA_VOLUNTARIOS,
)
from escala.modelos import CULTO_DOMINGO, CULTO_EVENTO, CULTO_ORACAO, FUNCAO_CEIA

FUNCOES = [
    ["Staff", "Ambos", "1", "1", "Não", "Não"],
    ["Abertura", "Domingo", "1", "1", "Não", "Não"],
    ["Intercessão", "Ambos", "1", "2", "Sim", "Não"],
    ["Infantil 10-12", "Domingo", "1", "1", "Não", "Sim"],
    ["Servo da Ceia", "Domingo", "1", "1", "Não", "Sim"],
]


def _base(config_linhas, funcoes=None):
    return base_de(
        montar_planilha(
            v=aba(ABA_VOLUNTARIOS, [["Ana", "", "Sim", "Staff", ""]]),
            f=aba(ABA_FUNCOES, funcoes or FUNCOES),
            c=aba(ABA_CONFIG, config_linhas),
        )
    )


def test_monta_domingos_oracao_e_evento_em_ordem():
    base = _base(
        [
            ["Mês/Ano", "03/2026"],
            ["Data da Ceia", "01/03"],
            ["Data do culto de oração", "18/03"],
            ["Evento", "20/03 | Vigília | Oração"],
        ]
    )
    cultos = montar_cultos(base.config, 3, 2026)
    assert [(c.data.day, c.tipo) for c in cultos] == [
        (1, CULTO_DOMINGO),
        (8, CULTO_DOMINGO),
        (15, CULTO_DOMINGO),
        (18, CULTO_ORACAO),
        (20, CULTO_EVENTO),
        (22, CULTO_DOMINGO),
        (29, CULTO_DOMINGO),
    ]


def test_marca_apenas_o_domingo_da_ceia():
    base = _base([["Mês/Ano", "03/2026"], ["Data da Ceia", "08/03"]])
    cultos = montar_cultos(base.config, 3, 2026)
    assert [c.ceia for c in cultos] == [False, True, False, False, False]


def test_datas_sem_culto_sao_puladas():
    base = _base(
        [["Mês/Ano", "03/2026"], ["Data da Ceia", "nenhuma"], ["Datas sem culto", "29/03"]]
    )
    cultos = montar_cultos(base.config, 3, 2026)
    assert date(2026, 3, 29) not in {c.data for c in cultos}
    assert len(cultos) == 4


def test_varias_datas_de_oracao():
    base = _base(
        [["Mês/Ano", "03/2026"], ["Data da Ceia", "nenhuma"],
         ["Data do culto de oração", "04/03; 18/03"]]
    )
    cultos = montar_cultos(base.config, 3, 2026)
    oracoes = [c.data.day for c in cultos if c.tipo == CULTO_ORACAO]
    assert oracoes == [4, 18]


# ---------------------------------------------------------------------------

def test_funcoes_do_domingo_excluem_data_fixa_fora_da_data():
    base = _base(
        [["Mês/Ano", "03/2026"], ["Data da Ceia", "01/03"],
         ["Data do Infantil 10-12", "08/03"]]
    )
    cultos = {c.data.day: c for c in montar_cultos(base.config, 3, 2026)}

    nomes_15 = [f.nome for f in funcoes_do_culto(cultos[15], base.funcoes, base.config)]
    assert "Infantil 10-12" not in nomes_15
    assert FUNCAO_CEIA not in nomes_15

    nomes_08 = [f.nome for f in funcoes_do_culto(cultos[8], base.funcoes, base.config)]
    assert "Infantil 10-12" in nomes_08


def test_domingo_de_ceia_inclui_servo_da_ceia():
    base = _base([["Mês/Ano", "03/2026"], ["Data da Ceia", "01/03"]])
    culto = montar_cultos(base.config, 3, 2026)[0]
    nomes = [f.nome for f in funcoes_do_culto(culto, base.funcoes, base.config)]
    assert FUNCAO_CEIA in nomes


def test_servo_da_ceia_e_criado_mesmo_fora_do_catalogo():
    """A regra da Ceia vale mesmo que ninguém tenha cadastrado a função."""
    sem_ceia = [linha for linha in FUNCOES if linha[0] != "Servo da Ceia"]
    base = _base([["Mês/Ano", "03/2026"], ["Data da Ceia", "01/03"]], funcoes=sem_ceia)
    culto = montar_cultos(base.config, 3, 2026)[0]
    nomes = [f.nome for f in funcoes_do_culto(culto, base.funcoes, base.config)]
    assert nomes.count(FUNCAO_CEIA) == 1


def test_culto_de_oracao_so_tem_funcoes_de_oracao_ou_ambos():
    base = _base(
        [["Mês/Ano", "03/2026"], ["Data da Ceia", "nenhuma"],
         ["Data do culto de oração", "18/03"]]
    )
    culto = next(c for c in montar_cultos(base.config, 3, 2026) if c.tipo == CULTO_ORACAO)
    nomes = [f.nome for f in funcoes_do_culto(culto, base.funcoes, base.config)]
    assert nomes == ["Staff", "Intercessão"]


def test_evento_herda_base_e_soma_funcoes_proprias():
    base = _base(
        [["Mês/Ano", "03/2026"], ["Data da Ceia", "nenhuma"],
         ["Evento", "20/03 | Vigília | Oração | Sonorização"]]
    )
    culto = next(c for c in montar_cultos(base.config, 3, 2026) if c.tipo == CULTO_EVENTO)
    nomes = [f.nome for f in funcoes_do_culto(culto, base.funcoes, base.config)]
    assert nomes == ["Staff", "Intercessão", "Sonorização"]


def test_evento_sem_base_usa_so_as_funcoes_proprias():
    base = _base(
        [["Mês/Ano", "03/2026"], ["Data da Ceia", "nenhuma"],
         ["Evento", "20/03 | Ensaio | Nenhum | Louvor"]]
    )
    culto = next(c for c in montar_cultos(base.config, 3, 2026) if c.tipo == CULTO_EVENTO)
    nomes = [f.nome for f in funcoes_do_culto(culto, base.funcoes, base.config)]
    assert nomes == ["Louvor"]


def test_descrever_culto():
    base = _base(
        [["Mês/Ano", "03/2026"], ["Data da Ceia", "01/03"],
         ["Data do culto de oração", "18/03"],
         ["Evento", "20/03 | Vigília | Oração"]]
    )
    cultos = {c.data.day: c for c in montar_cultos(base.config, 3, 2026)}
    assert descrever_culto(cultos[1]) == "01/03 — Domingo (Ceia)"
    assert descrever_culto(cultos[18]) == "18/03 — Culto de Oração"
    assert descrever_culto(cultos[20]) == "20/03 — Vigília"
