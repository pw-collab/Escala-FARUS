"""Visão tabular compartilhada pelo texto do WhatsApp e pela imagem."""

from datetime import date

from escala.grade import montar_grade
from escala.modelos import CULTO_DOMINGO, CULTO_EVENTO, CULTO_ORACAO, Atribuicao

ORDEM = ["Staff", "Abertura", "Intercessão", "Louvor", "Servo da Ceia"]


def linha(dia, funcao, nome, culto="Domingo"):
    return Atribuicao(data=date(2026, 3, dia), culto=culto, funcao=funcao, nome=nome)


def test_colunas_em_ordem_cronologica():
    grade = montar_grade(
        [linha(29, "Staff", "C"), linha(1, "Staff", "A"), linha(15, "Staff", "B")]
    )
    assert [c.data.day for c in grade.colunas] == [1, 15, 29]


def test_funcoes_seguem_o_catalogo_com_extras_no_fim():
    grade = montar_grade(
        [
            linha(1, "Sonorização", "Carla"),
            linha(1, "Louvor", "Bruno"),
            linha(8, "Staff", "Ana"),
        ],
        ORDEM,
    )
    assert grade.funcoes == ["Staff", "Louvor", "Sonorização"]


def test_linhas_da_grade_cobrem_o_mes_e_colunas_so_o_que_tem_gente():
    grade = montar_grade([linha(1, "Staff", "Ana"), linha(8, "Louvor", "Bruno")], ORDEM)
    assert grade.funcoes == ["Staff", "Louvor"]
    assert grade.funcoes_da_coluna(0) == ["Staff"]
    assert grade.funcoes_da_coluna(1) == ["Louvor"]
    assert grade.nomes("Louvor", 0) == []


def test_agrupa_nomes_sem_duplicar():
    grade = montar_grade(
        [
            linha(1, "Louvor", "Ana"),
            linha(1, "Louvor", "Bruno"),
            linha(1, "Louvor", "ana"),  # mesma pessoa, digitada diferente
        ]
    )
    assert grade.nomes("Louvor", 0) == ["Ana", "Bruno"]


def test_grafias_diferentes_da_funcao_viram_uma_linha_so():
    grade = montar_grade([linha(1, "Louvor", "Ana"), linha(8, "louvor ", "Bruno")], ORDEM)
    assert grade.funcoes == ["Louvor"]
    assert grade.nomes("Louvor", 1) == ["Bruno"]


def test_ceia_pela_data_configurada():
    grade = montar_grade(
        [linha(1, "Staff", "Ana"), linha(8, "Staff", "Bruno")],
        datas_ceia=[date(2026, 3, 8)],
    )
    assert [c.e_ceia for c in grade.colunas] == [False, True]


def test_ceia_pela_presenca_da_funcao_da_ceia():
    grade = montar_grade([linha(1, "Servo da Ceia", "Ana"), linha(8, "Staff", "Bruno")])
    assert [c.e_ceia for c in grade.colunas] == [True, False]


def test_reconhece_o_tipo_de_cada_culto():
    grade = montar_grade(
        [
            linha(1, "Staff", "Ana"),
            linha(18, "Staff", "Bruno", culto="Oração"),
            linha(20, "Staff", "Carla", culto="Evento: Vigília"),
            linha(21, "Staff", "Diego", culto="Ensaio"),
        ]
    )
    tipos = [(c.tipo, c.nome_evento) for c in grade.colunas]
    assert tipos == [
        (CULTO_DOMINGO, ""),
        (CULTO_ORACAO, ""),
        (CULTO_EVENTO, "Vigília"),
        ("", ""),
    ]


def test_evento_sem_nome_recebe_nome_generico():
    grade = montar_grade([linha(20, "Staff", "Ana", culto="Evento:")])
    assert grade.colunas[0].nome_evento == "Evento"


def test_cultos_diferentes_no_mesmo_dia_viram_colunas_diferentes():
    grade = montar_grade(
        [linha(1, "Staff", "Ana"), linha(1, "Staff", "Bruno", culto="Evento: Batismo")]
    )
    assert len(grade.colunas) == 2


def test_ignora_linhas_sem_data_ou_sem_nome():
    grade = montar_grade(
        [
            linha(1, "Staff", "Ana"),
            linha(1, "Oferta", ""),
            Atribuicao(data=None, culto="Domingo", funcao="Staff", nome="Bruno"),
        ]
    )
    assert grade.funcoes == ["Staff"]
    assert len(grade.colunas) == 1


def test_grade_vazia():
    assert montar_grade([]).vazia
    assert not montar_grade([linha(1, "Staff", "Ana")]).vazia
