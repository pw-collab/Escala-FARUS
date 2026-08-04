"""Aplicação de trocas na escala em rascunho e no histórico publicado."""

from datetime import date

from escala.modelos import (
    TROCA_APLICADA,
    TROCA_CANCELADA,
    TROCA_NAO_ENCONTRADA,
    TROCA_PENDENTE,
    Atribuicao,
    Troca,
)
from escala.trocas import aplicar_trocas

DIA = date(2026, 3, 8)


def escalado(funcao="Staff", nome="Ana", dia=DIA):
    return Atribuicao(data=dia, culto="Domingo", funcao=funcao, nome=nome)


def troca(**kwargs):
    padrao = dict(
        data=DIA,
        funcao="Staff",
        nome_original="Ana",
        nome_substituto="Bruno",
        motivo="viagem",
        status=TROCA_PENDENTE,
    )
    padrao.update(kwargs)
    return Troca(**padrao)


def test_troca_altera_a_escala_ainda_nao_publicada():
    resultado = aplicar_trocas([troca()], [escalado()], [])
    assert resultado.aplicadas == 1
    assert resultado.escala[0].nome == "Bruno"
    assert resultado.trocas[0].status == TROCA_APLICADA
    assert "Escala Gerada" in resultado.mensagens[0]


def test_troca_altera_o_historico_quando_ja_publicada():
    resultado = aplicar_trocas([troca()], [], [escalado()])
    assert resultado.aplicadas == 1
    assert resultado.historico[0].nome == "Bruno"
    assert "Histórico" in resultado.mensagens[0]


def test_escala_tem_prioridade_sobre_historico():
    resultado = aplicar_trocas([troca()], [escalado()], [escalado()])
    assert resultado.escala[0].nome == "Bruno"
    assert resultado.historico[0].nome == "Ana"


def test_troca_preserva_data_culto_e_funcao():
    resultado = aplicar_trocas([troca()], [escalado()], [])
    alterada = resultado.escala[0]
    assert (alterada.data, alterada.culto, alterada.funcao) == (DIA, "Domingo", "Staff")


def test_troca_nao_encontrada_fica_pendente_com_status_proprio():
    resultado = aplicar_trocas([troca(nome_original="Zezinho")], [escalado()], [])
    assert resultado.aplicadas == 0
    assert resultado.trocas[0].status == TROCA_NAO_ENCONTRADA
    assert resultado.trocas[0].pendente  # continua sendo tentada depois
    assert "não achei" in resultado.mensagens[0]


def test_troca_de_outra_data_nao_e_aplicada():
    resultado = aplicar_trocas([troca(data=date(2026, 3, 15))], [escalado()], [])
    assert resultado.aplicadas == 0
    assert resultado.escala[0].nome == "Ana"


def test_troca_de_outra_funcao_nao_e_aplicada():
    resultado = aplicar_trocas([troca(funcao="Louvor")], [escalado()], [])
    assert resultado.aplicadas == 0


def test_troca_sem_substituto_e_recusada():
    resultado = aplicar_trocas([troca(nome_substituto="")], [escalado()], [])
    assert resultado.aplicadas == 0
    assert "sem nome substituto" in resultado.mensagens[0]


def test_troca_ja_aplicada_nao_e_reaplicada():
    resultado = aplicar_trocas([troca(status=TROCA_APLICADA)], [escalado()], [])
    assert resultado.aplicadas == 0
    assert resultado.ignoradas == 1
    assert resultado.escala[0].nome == "Ana"


def test_troca_cancelada_e_ignorada():
    resultado = aplicar_trocas([troca(status=TROCA_CANCELADA)], [escalado()], [])
    assert resultado.aplicadas == 0
    assert resultado.escala[0].nome == "Ana"


def test_troca_compara_nomes_ignorando_acento_e_caixa():
    escala = [escalado(nome="José Antônio")]
    resultado = aplicar_trocas([troca(nome_original="jose antonio")], escala, [])
    assert resultado.aplicadas == 1
    assert resultado.escala[0].nome == "Bruno"


def test_trocas_em_cadeia_no_mesmo_culto():
    escala = [escalado(funcao="Staff", nome="Ana"), escalado(funcao="Louvor", nome="Carla")]
    trocas = [
        troca(funcao="Staff", nome_original="Ana", nome_substituto="Bruno"),
        troca(funcao="Louvor", nome_original="Carla", nome_substituto="Diego"),
    ]
    resultado = aplicar_trocas(trocas, escala, [])
    assert resultado.aplicadas == 2
    assert [a.nome for a in resultado.escala] == ["Bruno", "Diego"]


def test_troca_nao_modifica_as_listas_originais():
    escala = [escalado()]
    original = list(escala)
    aplicar_trocas([troca()], escala, [])
    assert escala == original
    assert escala[0].nome == "Ana"
