from datetime import date

import pytest

from escala.textos import (
    competencia,
    dias_do_mes_na_semana,
    domingos_do_mes,
    enesimo_dia_semana,
    formatar_data,
    nome_dia_semana,
    normalizar,
    parse_bool,
    parse_data,
    parse_datas,
    parse_int,
    parse_lista,
    parse_mes_ano,
    vazio,
)


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("Qtd. mín.", "qtd min"),
        ("É coringa?", "e coringa"),
        ("Infantil 10-12", "infantil 10 12"),
        ("Culto (Domingo/Oração/Ambos)", "culto domingo oracao ambos"),
        ("  Maná   Coffee ", "mana coffee"),
        ("1º domingo", "1o domingo"),
        (None, ""),
    ],
)
def test_normalizar(entrada, esperado):
    assert normalizar(entrada) == esperado


def test_normalizar_ignora_acento_e_caixa():
    assert normalizar("INTERCESSÃO") == normalizar("intercessao")


@pytest.mark.parametrize("entrada", ["", "-", "Nenhuma", "n/a", "  "])
def test_vazio(entrada):
    assert vazio(entrada)


@pytest.mark.parametrize(
    "entrada, esperado",
    [("Sim", True), ("sim", True), ("S", True), ("x", True), ("1", True),
     ("Não", False), ("nao", False), ("", False), ("0", False)],
)
def test_parse_bool(entrada, esperado):
    assert parse_bool(entrada) is esperado


def test_parse_bool_usa_padrao_quando_desconhecido():
    assert parse_bool("talvez", padrao=True) is True


@pytest.mark.parametrize(
    "entrada, esperado", [("2", 2), ("Qtd 3", 3), ("", 7), ("dois", 7)]
)
def test_parse_int(entrada, esperado):
    assert parse_int(entrada, padrao=7) == esperado


def test_parse_lista_aceita_varios_separadores():
    assert parse_lista("Staff; Louvor, Projetor\nOferta") == [
        "Staff", "Louvor", "Projetor", "Oferta"
    ]
    assert parse_lista("") == []


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("01/03/2026", date(2026, 3, 1)),
        ("1/3/2026", date(2026, 3, 1)),
        ("01-03-26", date(2026, 3, 1)),
        ("2026-03-01", date(2026, 3, 1)),
        ("01/03", date(2026, 3, 1)),
        ("1", date(2026, 3, 1)),
        ("1º domingo", date(2026, 3, 1)),
        ("primeiro domingo", date(2026, 3, 1)),
        ("3ª quarta", date(2026, 3, 18)),
        ("última quarta", date(2026, 3, 25)),
        ("ultimo domingo", date(2026, 3, 29)),
        ("", None),
        ("nenhuma", None),
        ("qualquer coisa", None),
        ("31/02/2026", None),
    ],
)
def test_parse_data(entrada, esperado):
    assert parse_data(entrada, ano=2026, mes=3) == esperado


def test_parse_data_aceita_objeto_date():
    assert parse_data(date(2026, 5, 4)) == date(2026, 5, 4)


def test_parse_datas_ordena_e_remove_duplicadas():
    assert parse_datas("15/03; 01/03, 15/03", ano=2026, mes=3) == [
        date(2026, 3, 1),
        date(2026, 3, 15),
    ]


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("03/2026", (3, 2026)),
        ("3/2026", (3, 2026)),
        ("2026-03", (3, 2026)),
        ("Março/2026", (3, 2026)),
        ("marco 2026", (3, 2026)),
        ("Março de 2026", (3, 2026)),
        ("13/2026", None),
        ("", None),
    ],
)
def test_parse_mes_ano(entrada, esperado):
    assert parse_mes_ano(entrada) == esperado


def test_domingos_do_mes():
    assert domingos_do_mes(2026, 3) == [
        date(2026, 3, d) for d in (1, 8, 15, 22, 29)
    ]


def test_enesimo_dia_semana():
    assert enesimo_dia_semana(2026, 3, 6, 2) == date(2026, 3, 8)
    assert enesimo_dia_semana(2026, 3, 6, -1) == date(2026, 3, 29)
    assert enesimo_dia_semana(2026, 3, 6, 9) is None


def test_dias_do_mes_na_semana():
    assert dias_do_mes_na_semana(2026, 3, 2)[0] == date(2026, 3, 4)  # quarta


def test_formatacao_pt_br():
    assert competencia(3, 2026) == "Março/2026"
    assert nome_dia_semana(date(2026, 3, 18)) == "Quarta"
    assert formatar_data(date(2026, 3, 1)) == "01/03"
    assert formatar_data(date(2026, 3, 1), com_ano=True) == "01/03/2026"
