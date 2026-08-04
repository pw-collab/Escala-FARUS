"""Regras de montagem automática: elegibilidade, rodízio, coringa e Ceia."""

from datetime import date

from conftest import aba, base_de, montar_planilha

from escala.dados import (
    ABA_CONFIG,
    ABA_FUNCOES,
    ABA_HISTORICO,
    ABA_INDISPONIBILIDADES,
    ABA_VOLUNTARIOS,
)
from escala.motor import (
    EstadoRodizio,
    gerar_escala,
    resumo_por_voluntario,
    voluntarios_nao_escalados,
)

CONFIG_SIMPLES = [["Mês/Ano", "03/2026"], ["Data da Ceia", "nenhuma"]]


def montar(voluntarios, funcoes, config=None, historico=None, indisp=None):
    return base_de(
        montar_planilha(
            v=aba(ABA_VOLUNTARIOS, voluntarios),
            f=aba(ABA_FUNCOES, funcoes),
            c=aba(ABA_CONFIG, config or CONFIG_SIMPLES),
            h=aba(ABA_HISTORICO, historico or []),
            i=aba(ABA_INDISPONIBILIDADES, indisp or []),
        )
    )


def nomes_em(resultado, dia, funcao):
    return [
        a.nome
        for a in resultado.atribuicoes
        if a.data == date(2026, 3, dia) and a.funcao == funcao
    ]


# ---------------------------------------------------------------------------
# Elegibilidade
# ---------------------------------------------------------------------------

def test_so_escala_quem_e_apto_e_esta_ativo():
    base = montar(
        voluntarios=[
            ["Ana", "", "Sim", "Staff", ""],
            ["Bruno", "", "Não", "Staff", ""],
            ["Carla", "", "Sim", "Louvor", ""],
        ],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert {a.nome for a in resultado.atribuicoes} == {"Ana"}


def test_indisponibilidade_tira_a_pessoa_daquele_dia():
    base = montar(
        voluntarios=[["Ana", "", "Sim", "Staff", ""], ["Bruno", "", "Sim", "Staff", ""]],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
        indisp=[["Ana", "08/03/2026", "08/03/2026", "viagem"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert nomes_em(resultado, 8, "Staff") == ["Bruno"]


def test_ninguem_ocupa_duas_funcoes_normais_no_mesmo_culto():
    base = montar(
        voluntarios=[
            ["Ana", "", "Sim", "Staff; Projetor", ""],
            ["Bruno", "", "Sim", "Staff; Projetor", ""],
        ],
        funcoes=[
            ["Staff", "Domingo", "1", "1", "Não", "Não"],
            ["Projetor", "Domingo", "1", "1", "Não", "Não"],
        ],
    )
    resultado = gerar_escala(base, 3, 2026)
    for dia in (1, 8, 15, 22, 29):
        do_dia = [a.nome for a in resultado.atribuicoes if a.data == date(2026, 3, dia)]
        assert len(do_dia) == len(set(do_dia)) == 2


def test_vaga_sem_ninguem_apto_vira_pendencia_explicada():
    base = montar(
        voluntarios=[["Ana", "", "Sim", "Staff", ""]],
        funcoes=[
            ["Staff", "Domingo", "1", "1", "Não", "Não"],
            ["Projetor", "Domingo", "1", "1", "Não", "Não"],
        ],
    )
    resultado = gerar_escala(base, 3, 2026)
    pendencias = [p for p in resultado.pendencias if p.funcao == "Projetor"]
    assert len(pendencias) == 5
    assert "nenhum voluntário ativo" in pendencias[0].motivo


def test_pendencia_por_indisponibilidade_tem_motivo_proprio():
    base = montar(
        voluntarios=[["Ana", "", "Sim", "Staff", ""]],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
        indisp=[["Ana", "01/03/2026", "31/03/2026", "licença"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert all("indisponíveis" in p.motivo for p in resultado.pendencias)


# ---------------------------------------------------------------------------
# Rodízio
# ---------------------------------------------------------------------------

def test_nao_repete_a_mesma_pessoa_em_cultos_seguidos():
    base = montar(
        voluntarios=[
            ["Ana", "", "Sim", "Staff", ""],
            ["Bruno", "", "Sim", "Staff", ""],
            ["Carla", "", "Sim", "Staff", ""],
        ],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    escolhidos = [a.nome for a in resultado.atribuicoes]
    assert len(escolhidos) == 5
    # Com 3 aptos e 5 domingos, ninguém pode servir dois domingos seguidos.
    assert all(a != b for a, b in zip(escolhidos, escolhidos[1:]))
    # E a carga fica equilibrada (2/2/1).
    assert sorted(resumo_por_voluntario(resultado.atribuicoes).values()) == [1, 2, 2]


def test_quem_serviu_ha_mais_tempo_vem_primeiro():
    base = montar(
        voluntarios=[
            ["Ana", "", "Sim", "Staff", ""],
            ["Bruno", "", "Sim", "Staff", ""],
            ["Carla", "", "Sim", "Staff", ""],
        ],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
        historico=[
            ["01/02/2026", "Domingo", "Staff", "Ana"],
            ["08/02/2026", "Domingo", "Staff", "Bruno"],
            ["15/02/2026", "Domingo", "Staff", "Carla"],
        ],
    )
    resultado = gerar_escala(base, 3, 2026)
    # Ana serviu há mais tempo, depois Bruno, depois Carla.
    assert [a.nome for a in resultado.atribuicoes][:3] == ["Ana", "Bruno", "Carla"]


def test_quem_nunca_serviu_tem_prioridade_sobre_quem_ja_serviu():
    base = montar(
        voluntarios=[
            ["Ana", "", "Sim", "Staff", ""],
            ["Novato", "", "Sim", "Staff", ""],
        ],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
        historico=[["01/02/2026", "Domingo", "Staff", "Ana"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert resultado.atribuicoes[0].nome == "Novato"


def test_rodizio_e_por_funcao_e_nao_global():
    """Quem serviu muito em Louvor ainda é o primeiro da fila em Staff."""
    base = montar(
        voluntarios=[
            ["Ana", "", "Sim", "Staff; Louvor", ""],
            ["Bruno", "", "Sim", "Staff", ""],
        ],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
        historico=[
            ["01/02/2026", "Domingo", "Louvor", "Ana"],
            ["08/02/2026", "Domingo", "Staff", "Bruno"],
        ],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert resultado.atribuicoes[0].nome == "Ana"


def test_geracao_e_deterministica():
    dados = dict(
        voluntarios=[
            ["Ana", "", "Sim", "Staff", ""],
            ["Bruno", "", "Sim", "Staff", ""],
            ["Carla", "", "Sim", "Staff", ""],
        ],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
    )
    primeira = gerar_escala(montar(**dados), 3, 2026)
    segunda = gerar_escala(montar(**dados), 3, 2026)
    assert [a.nome for a in primeira.atribuicoes] == [a.nome for a in segunda.atribuicoes]


def test_historico_do_proprio_mes_nao_conta_duas_vezes():
    """Regerar um mês já publicado não pode penalizar quem serviu nele."""
    base_limpa = montar(
        voluntarios=[["Ana", "", "Sim", "Staff", ""], ["Bruno", "", "Sim", "Staff", ""]],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
    )
    primeira = gerar_escala(base_limpa, 3, 2026)

    ja_publicado = [
        [a.data.strftime("%d/%m/%Y"), a.culto, a.funcao, a.nome] for a in primeira.atribuicoes
    ]
    base_republicada = montar(
        voluntarios=[["Ana", "", "Sim", "Staff", ""], ["Bruno", "", "Sim", "Staff", ""]],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
        historico=ja_publicado,
    )
    segunda = gerar_escala(base_republicada, 3, 2026)
    assert [a.nome for a in primeira.atribuicoes] == [a.nome for a in segunda.atribuicoes]


# ---------------------------------------------------------------------------
# Quantidades
# ---------------------------------------------------------------------------

def test_preenche_ate_a_quantidade_maxima():
    base = montar(
        voluntarios=[
            ["Ana", "", "Sim", "Intercessão", ""],
            ["Bruno", "", "Sim", "Intercessão", ""],
            ["Carla", "", "Sim", "Intercessão", ""],
        ],
        funcoes=[["Intercessão", "Domingo", "1", "2", "Não", "Não"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert len(nomes_em(resultado, 1, "Intercessão")) == 2


def test_config_pode_limitar_ao_minimo():
    base = montar(
        voluntarios=[
            ["Ana", "", "Sim", "Intercessão", ""],
            ["Bruno", "", "Sim", "Intercessão", ""],
        ],
        funcoes=[["Intercessão", "Domingo", "1", "2", "Não", "Não"]],
        config=CONFIG_SIMPLES + [["Preencher até a quantidade máxima", "Não"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert len(nomes_em(resultado, 1, "Intercessão")) == 1


def test_menos_gente_que_o_minimo_gera_pendencia_parcial():
    base = montar(
        voluntarios=[["Ana", "", "Sim", "Maná Coffee", ""]],
        funcoes=[["Maná Coffee", "Domingo", "2", "2", "Não", "Não"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert len(nomes_em(resultado, 1, "Maná Coffee")) == 1
    assert resultado.pendencias[0].faltam == 1


# ---------------------------------------------------------------------------
# Regra coringa
# ---------------------------------------------------------------------------

def _base_coringa(**extra):
    return montar(
        voluntarios=[
            ["Ana", "", "Sim", "Louvor", ""],
            ["Bruno", "", "Sim", "Louvor", ""],
            ["Carla", "", "Sim", "Staff", ""],
        ],
        funcoes=[
            ["Staff", "Domingo", "1", "1", "Não", "Não"],
            ["Abertura", "Domingo", "1", "1", "Não", "Não"],
            ["Oferta", "Domingo", "1", "1", "Não", "Não"],
            ["Louvor", "Domingo", "2", "2", "Sim", "Não"],
        ],
        **extra,
    )


def test_coringa_cobre_abertura_e_oferta():
    resultado = gerar_escala(_base_coringa(), 3, 2026)
    abertura = nomes_em(resultado, 1, "Abertura")
    oferta = nomes_em(resultado, 1, "Oferta")
    assert abertura and oferta
    # Ambos saem do Louvor (única função coringa do culto)...
    assert set(abertura + oferta) == {"Ana", "Bruno"}
    # ...e a mesma pessoa não acumula as duas.
    assert abertura != oferta
    assert not resultado.pendencias


def test_coringa_marca_a_atribuicao_como_acumulo():
    resultado = gerar_escala(_base_coringa(), 3, 2026)
    acumulos = [a for a in resultado.atribuicoes if a.via_coringa]
    assert {a.funcao for a in acumulos} == {"Abertura", "Oferta"}


def test_coringa_nao_cobre_funcao_fora_da_lista_configurada():
    """Projetor exige aptidão: coringa não substitui competência técnica."""
    base = montar(
        voluntarios=[["Ana", "", "Sim", "Louvor", ""], ["Bruno", "", "Sim", "Louvor", ""]],
        funcoes=[
            ["Projetor", "Domingo", "1", "1", "Não", "Não"],
            ["Louvor", "Domingo", "2", "2", "Sim", "Não"],
        ],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert all(p.funcao == "Projetor" for p in resultado.pendencias)
    assert not any(a.funcao == "Projetor" for a in resultado.atribuicoes)


def test_pessoa_apta_a_abertura_e_preferida_ao_coringa():
    base = montar(
        voluntarios=[
            ["Ana", "", "Sim", "Louvor", ""],
            ["Bruno", "", "Sim", "Louvor", ""],
            ["Diego", "", "Sim", "Abertura", ""],
        ],
        funcoes=[
            ["Abertura", "Domingo", "1", "1", "Não", "Não"],
            ["Louvor", "Domingo", "2", "2", "Sim", "Não"],
        ],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert nomes_em(resultado, 1, "Abertura") == ["Diego"]
    assert not any(a.via_coringa for a in resultado.atribuicoes)


# ---------------------------------------------------------------------------
# Ceia, data fixa e eventos
# ---------------------------------------------------------------------------

def test_servo_da_ceia_entra_so_no_domingo_da_ceia():
    base = montar(
        voluntarios=[["Ana", "", "Sim", "Staff; Servo da Ceia", ""],
                     ["Bruno", "", "Sim", "Servo da Ceia", ""]],
        funcoes=[
            ["Staff", "Domingo", "1", "1", "Não", "Não"],
            ["Servo da Ceia", "Domingo", "1", "1", "Não", "Sim"],
        ],
        config=[["Mês/Ano", "03/2026"], ["Data da Ceia", "08/03"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    dias_com_ceia = {
        a.data.day for a in resultado.atribuicoes if a.funcao == "Servo da Ceia"
    }
    assert dias_com_ceia == {8}


def test_funcao_de_data_fixa_entra_uma_vez_no_mes():
    base = montar(
        voluntarios=[["Ana", "", "Sim", "Infantil 10-12", ""]],
        funcoes=[["Infantil 10-12", "Domingo", "1", "1", "Não", "Sim"]],
        config=[
            ["Mês/Ano", "03/2026"],
            ["Data da Ceia", "nenhuma"],
            ["Data do Infantil 10-12", "2º domingo"],
        ],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert [a.data.day for a in resultado.atribuicoes] == [8]


def test_evento_usa_o_mesmo_motor():
    base = montar(
        voluntarios=[
            ["Ana", "", "Sim", "Staff", ""],
            ["Bruno", "", "Sim", "Sonorização", ""],
        ],
        funcoes=[["Staff", "Ambos", "1", "1", "Não", "Não"]],
        config=[
            ["Mês/Ano", "03/2026"],
            ["Data da Ceia", "nenhuma"],
            ["Evento", "20/03 | Vigília | Oração | Sonorização"],
        ],
    )
    resultado = gerar_escala(base, 3, 2026)
    do_evento = [a for a in resultado.atribuicoes if a.data == date(2026, 3, 20)]
    assert {(a.funcao, a.nome) for a in do_evento} == {
        ("Staff", "Ana"),
        ("Sonorização", "Bruno"),
    }
    assert all(a.culto == "Evento: Vigília" for a in do_evento)


# ---------------------------------------------------------------------------
# Casos de borda e resumos
# ---------------------------------------------------------------------------

def test_sem_mes_definido_devolve_aviso_em_vez_de_quebrar():
    base = montar(
        voluntarios=[["Ana", "", "Sim", "Staff", ""]],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
        config=[["Data da Ceia", "nenhuma"]],
    )
    resultado = gerar_escala(base, None, None)
    assert resultado.atribuicoes == []
    assert any("Mês/ano" in a for a in resultado.avisos)


def test_sem_voluntarios_ativos_devolve_aviso():
    base = montar(
        voluntarios=[["Ana", "", "Não", "Staff", ""]],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert any("Nenhum voluntário ativo" in a for a in resultado.avisos)


def test_voluntarios_nao_escalados():
    base = montar(
        voluntarios=[["Ana", "", "Sim", "Staff", ""], ["Sozinho", "", "Sim", "Bateria", ""]],
        funcoes=[["Staff", "Domingo", "1", "1", "Não", "Não"]],
    )
    resultado = gerar_escala(base, 3, 2026)
    assert voluntarios_nao_escalados(base, resultado.atribuicoes) == ["Sozinho"]


def test_estado_rodizio_guarda_a_data_mais_recente():
    estado = EstadoRodizio()
    estado.registrar("ana", "staff", date(2026, 1, 1))
    estado.registrar("ana", "staff", date(2026, 3, 1))
    estado.registrar("ana", "staff", date(2026, 2, 1))
    assert estado.ultima_vez("ana", "staff") == date(2026, 3, 1)
    assert estado.vezes("ana", "staff") == 3


def test_demo_gera_mes_completo_sem_pendencias(demo):
    resultado = gerar_escala(demo, 3, 2026)
    assert resultado.pendencias == []
    assert len(resultado.cultos) == 7
    carga = resumo_por_voluntario(resultado.atribuicoes)
    # Ninguém sobrecarregado nem esquecido.
    assert max(carga.values()) - min(carga.values()) <= 4
    assert voluntarios_nao_escalados(demo, resultado.atribuicoes) == []
