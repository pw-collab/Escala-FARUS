"""Fluxo completo do mês, contra um repositório em memória."""

from datetime import date

import pytest
from conftest import aba, montar_planilha

from escala import servico
from escala.dados import (
    ABA_ESCALA,
    ABA_HISTORICO,
    ABA_TROCAS,
    ABA_VOLUNTARIOS,
    ABA_CONFIG,
    ABA_FUNCOES,
)
from escala.demo import planilha_demo
from escala.modelos import TROCA_APLICADA, TROCA_PENDENTE, Troca
from escala.motor import gerar_escala
from escala.planilha import Aba
from escala.repositorio import RepositorioMemoria
from escala.textos import normalizar


@pytest.fixture
def repo():
    return RepositorioMemoria(planilha_demo(3, 2026))


def test_ciclo_mensal_completo(repo):
    """Gerar → salvar rascunho → publicar → histórico alimenta o mês seguinte."""
    base = servico.carregar(repo)
    resultado = gerar_escala(base, 3, 2026)
    assert resultado.atribuicoes

    servico.salvar_escala(repo, base, resultado.atribuicoes)
    base = servico.carregar(repo)
    assert len(base.escala) == len(resultado.atribuicoes)
    assert base.escala[0].data == resultado.atribuicoes[0].data

    historico_antes = len(base.historico)
    publicacao = servico.publicar(repo, base, base.escala)
    assert publicacao.publicado

    base = servico.carregar(repo)
    assert len(base.historico) == historico_antes + len(resultado.atribuicoes)


def test_publicar_bloqueia_data_ja_publicada(repo):
    base = servico.carregar(repo)
    escala = gerar_escala(base, 3, 2026).atribuicoes
    servico.publicar(repo, base, escala)

    base = servico.carregar(repo)
    segunda = servico.publicar(repo, base, escala)
    assert not segunda.publicado
    assert "já estão no Histórico" in segunda.mensagem
    assert segunda.datas_em_conflito


def test_publicar_com_substituir_nao_duplica(repo):
    base = servico.carregar(repo)
    escala = gerar_escala(base, 3, 2026).atribuicoes
    servico.publicar(repo, base, escala)

    base = servico.carregar(repo)
    total_antes = len(base.historico)
    servico.publicar(repo, base, escala, substituir=True)

    base = servico.carregar(repo)
    assert len(base.historico) == total_antes


def test_publicar_escala_vazia_e_recusado(repo):
    base = servico.carregar(repo)
    assert not servico.publicar(repo, base, []).publicado


def test_troca_registrada_e_aplicada_no_rascunho(repo):
    base = servico.carregar(repo)
    escala = gerar_escala(base, 3, 2026).atribuicoes
    servico.salvar_escala(repo, base, escala)
    base = servico.carregar(repo)

    alvo = base.escala[0]
    substituto = next(
        v.nome
        for v in base.voluntarios_ativos
        if v.exerce(alvo.funcao) and v.nome != alvo.nome
    )
    servico.registrar_troca(
        repo,
        base,
        Troca(
            data=alvo.data,
            funcao=alvo.funcao,
            nome_original=alvo.nome,
            nome_substituto=substituto,
            motivo="teste",
            status=TROCA_PENDENTE,
        ),
    )

    base = servico.carregar(repo)
    resultado = servico.processar_trocas(repo, base)
    assert resultado.aplicadas == 1

    base = servico.carregar(repo)
    assert base.escala[0].nome == substituto
    assert base.trocas[0].status == TROCA_APLICADA


def test_troca_depois_de_publicada_corrige_o_historico(repo):
    base = servico.carregar(repo)
    escala = gerar_escala(base, 3, 2026).atribuicoes
    servico.publicar(repo, base, escala)
    base = servico.carregar(repo)

    alvo = next(h for h in base.historico if h.data and h.data.month == 3)
    servico.registrar_troca(
        repo,
        base,
        Troca(
            data=alvo.data,
            funcao=alvo.funcao,
            nome_original=alvo.nome,
            nome_substituto="Substituto Teste",
            motivo="doente",
            status=TROCA_PENDENTE,
        ),
    )

    base = servico.carregar(repo)
    assert servico.processar_trocas(repo, base).aplicadas == 1

    base = servico.carregar(repo)
    assert any(h.nome == "Substituto Teste" for h in base.historico)
    assert not any(
        h.nome == alvo.nome and h.data == alvo.data and h.funcao == alvo.funcao
        for h in base.historico
    )


def test_gravacao_preserva_colunas_extras_do_admin():
    planilha = montar_planilha(
        v=aba(ABA_VOLUNTARIOS, [["Ana", "", "Sim", "Staff", ""]]),
        f=aba(ABA_FUNCOES, [["Staff", "Domingo", "1", "1", "Não", "Não"]]),
        c=aba(ABA_CONFIG, [["Mês/Ano", "03/2026"], ["Data da Ceia", "nenhuma"]]),
        h=Aba(
            ABA_HISTORICO,
            ["Data", "Culto", "Função", "Nome", "Confirmado?"],
            [["01/02/2026", "Domingo", "Staff", "Ana", "sim"]],
        ),
        e=aba(ABA_ESCALA, []),
        t=aba(ABA_TROCAS, []),
    )
    repo = RepositorioMemoria(planilha)
    base = servico.carregar(repo)

    escala = gerar_escala(base, 3, 2026).atribuicoes
    servico.publicar(repo, base, escala)

    gravada = repo.carregar().obter(ABA_HISTORICO)
    assert gravada.cabecalho[-1] == "Confirmado?"
    antiga = next(l for l in gravada.linhas if l[0] == "01/02/2026")
    assert antiga[4] == "sim"


def test_abas_faltantes_sao_detectadas_e_criadas():
    planilha = montar_planilha(v=aba(ABA_VOLUNTARIOS, []))
    repo = RepositorioMemoria(planilha)
    base = servico.carregar(repo)

    faltantes = servico.abas_faltantes(base)
    assert ABA_HISTORICO in faltantes

    criadas = servico.garantir_estrutura(repo, base)
    assert set(criadas) == set(faltantes)

    base = servico.carregar(repo)
    assert servico.abas_faltantes(base) == []
    # As abas de catálogo vêm com exemplos; as de dados vêm vazias.
    assert base.funcoes
    assert base.historico == []


def test_nomes_conhecidos_sai_ordenado(repo):
    base = servico.carregar(repo)
    nomes = servico.nomes_conhecidos(base)
    assert nomes == sorted(nomes, key=normalizar)
    assert "Ana Paula Ferreira" in nomes


def test_repositorio_memoria_isola_o_snapshot(repo):
    """Alterar o que foi lido não pode alterar a fonte."""
    primeira = repo.carregar()
    primeira.obter(ABA_VOLUNTARIOS).linhas.clear()
    assert repo.carregar().obter(ABA_VOLUNTARIOS).linhas
