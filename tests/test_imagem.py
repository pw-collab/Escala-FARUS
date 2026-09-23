"""Imagem PNG da escala em formato de tabela."""

import io
from datetime import date

import pytest
from PIL import Image

from escala import imagem
from escala.grade import ColunaCulto, montar_grade
from escala.imagem import (
    COR_CEIA,
    COR_DO_CULTO,
    _cabecalho,
    carregar_fonte,
    limpar_para_imagem,
    quebrar,
    renderizar_png,
)
from escala.modelos import CULTO_DOMINGO, CULTO_EVENTO, CULTO_ORACAO, Atribuicao

ORDEM = ["Staff", "Abertura", "Louvor"]
HOJE = date(2026, 3, 1)


def linha(dia, funcao, nome, culto="Domingo"):
    return Atribuicao(data=date(2026, 3, dia), culto=culto, funcao=funcao, nome=nome)


def desenhar(atribuicoes, **kwargs):
    kwargs.setdefault("gerada_em", HOJE)
    return renderizar_png(montar_grade(atribuicoes, ORDEM), "Escala — Março/2026", **kwargs)


def tamanho(png: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(png)).size


@pytest.fixture
def sem_fontes_embutidas(monkeypatch, tmp_path):
    monkeypatch.setattr(imagem, "PASTA_FONTES", tmp_path)
    carregar_fonte.cache_clear()
    yield
    carregar_fonte.cache_clear()


def test_devolve_um_png_valido():
    png = desenhar([linha(1, "Staff", "Ana"), linha(8, "Louvor", "Bruno")])
    assert png.startswith(b"\x89PNG")
    figura = Image.open(io.BytesIO(png))
    figura.verify()
    assert figura.format == "PNG"


def test_mais_cultos_deixam_a_imagem_mais_larga():
    um = desenhar([linha(1, "Staff", "Ana")])
    tres = desenhar([linha(1, "Staff", "Ana"), linha(8, "Staff", "Bia"), linha(15, "Staff", "Cid")])
    assert tamanho(tres)[0] > tamanho(um)[0]


def test_mais_nomes_na_celula_deixam_a_imagem_mais_alta():
    um = desenhar([linha(1, "Louvor", "Ana")])
    tres = desenhar([linha(1, "Louvor", n) for n in ("Ana", "Bia", "Cid")])
    assert tamanho(tres)[1] > tamanho(um)[1]


def test_escala_controla_a_resolucao():
    dados = [linha(1, "Staff", "Ana"), linha(8, "Staff", "Bia")]
    largura_1x, altura_1x = tamanho(desenhar(dados, escala=1))
    largura_2x, altura_2x = tamanho(desenhar(dados, escala=2))
    assert largura_2x == pytest.approx(2 * largura_1x, rel=0.02)
    assert altura_2x == pytest.approx(2 * altura_1x, rel=0.02)


def test_mesmos_dados_geram_a_mesma_imagem():
    dados = [linha(1, "Staff", "Ana"), linha(8, "Louvor", "Bruno")]
    assert desenhar(dados) == desenhar(dados)


def test_nome_muito_longo_nao_quebra_a_renderizacao():
    enorme = "Maria Aparecida dos Santos Albuquerque de Vasconcelos Figueiredo"
    png = desenhar([linha(1, "Staff", enorme), linha(1, "Coordenação Geral do Ministério", "Ana")])
    assert png.startswith(b"\x89PNG")


def test_emoji_no_rodape_e_nos_nomes_nao_quebra():
    png = desenhar([linha(1, "Staff", "Ana ✨")], rodape="Avise com antecedência 🙏", subtitulo="🎉")
    assert png.startswith(b"\x89PNG")


def test_grade_vazia_e_recusada():
    with pytest.raises(ValueError):
        renderizar_png(montar_grade([]), "Escala")


def test_funciona_sem_as_fontes_embutidas(sem_fontes_embutidas):
    png = desenhar([linha(1, "Staff", "Ana"), linha(18, "Staff", "Bia", culto="Oração")])
    assert png.startswith(b"\x89PNG")


def test_fontes_embutidas_estao_no_repositorio():
    assert (imagem.PASTA_FONTES / imagem.FONTE_REGULAR).is_file()
    assert (imagem.PASTA_FONTES / imagem.FONTE_NEGRITO).is_file()
    assert (imagem.PASTA_FONTES / "OFL.txt").is_file()


# ---------------------------------------------------------------------------
# Peças internas
# ---------------------------------------------------------------------------

def test_limpar_para_imagem_remove_emoji_e_preserva_acentos():
    assert limpar_para_imagem("Avise 🙏 👍🏽 ❤️") == "Avise"
    assert limpar_para_imagem("Maná Coffee — Intercessão · Ceia") == "Maná Coffee — Intercessão · Ceia"
    assert limpar_para_imagem(None) == ""


def test_quebrar_respeita_a_largura():
    fonte = carregar_fonte(28)
    largura = 200
    linhas = quebrar("Maria Aparecida dos Santos Albuquerque", fonte, largura)
    assert len(linhas) > 1
    assert all(fonte.getlength(l) <= largura for l in linhas)
    assert " ".join(linhas) == "Maria Aparecida dos Santos Albuquerque"


def test_quebrar_corta_palavra_maior_que_a_coluna():
    fonte = carregar_fonte(28)
    linhas = quebrar("Anticonstitucionalissimamente", fonte, 120)
    assert len(linhas) > 1
    assert all(fonte.getlength(l) <= 120 for l in linhas)
    assert "".join(linhas) == "Anticonstitucionalissimamente"


def test_quebrar_texto_vazio():
    assert quebrar("", carregar_fonte(28), 200) == []


def test_cabecalho_de_cada_tipo_de_culto():
    domingo = ColunaCulto(date(2026, 3, 8), "Domingo", CULTO_DOMINGO)
    ceia = ColunaCulto(date(2026, 3, 1), "Domingo", CULTO_DOMINGO, e_ceia=True)
    oracao = ColunaCulto(date(2026, 3, 18), "Oração", CULTO_ORACAO)
    evento = ColunaCulto(date(2026, 3, 20), "Evento: Vigília", CULTO_EVENTO, nome_evento="Vigília")

    assert _cabecalho(domingo) == ("Dom 08/03", "", COR_DO_CULTO[CULTO_DOMINGO])
    assert _cabecalho(ceia) == ("Dom 01/03", "Ceia", COR_CEIA)
    assert _cabecalho(oracao) == ("Qua 18/03", "Culto de Oração", COR_DO_CULTO[CULTO_ORACAO])
    assert _cabecalho(evento) == ("Sex 20/03", "Vigília", COR_DO_CULTO[CULTO_EVENTO])


def test_cabecalho_de_evento_com_ceia():
    evento = ColunaCulto(
        date(2026, 3, 20), "Evento: Vigília", CULTO_EVENTO, e_ceia=True, nome_evento="Vigília"
    )
    assert _cabecalho(evento)[1] == "Vigília · Ceia"


def test_mes_de_demonstracao_inteiro(demo):
    from escala.motor import gerar_escala

    resultado = gerar_escala(demo, 3, 2026)
    grade = montar_grade(resultado.atribuicoes, demo.ordem_das_funcoes(), demo.config.datas_ceia)
    png = renderizar_png(grade, "Escala — Março/2026", gerada_em=HOJE)
    largura, altura = tamanho(png)
    assert len(grade.colunas) == 7
    assert 1500 < largura < 3500 and 1000 < altura < 3000
