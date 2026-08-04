"""Leitura das abas: apelidos de coluna, configurações e diagnóstico."""

from datetime import date

from conftest import aba, base_de, montar_planilha

from escala.dados import (
    ABA_CONFIG,
    ABA_FUNCOES,
    ABA_INDISPONIBILIDADES,
    ABA_VOLUNTARIOS,
    ConfiguracoesMes,
    atualizar_aba_config,
    carregar_base,
)
from escala.modelos import EscalaManual, Evento
from escala.planilha import Aba, MapaColunas, Planilha


def test_mapa_colunas_prefere_correspondencia_exata():
    """"Data" não pode roubar a coluna de "Data início"."""
    mapa = MapaColunas(
        ["Nome", "Data início", "Data fim", "Motivo"],
        {
            "nome": ("Nome",),
            "inicio": ("Data início", "Início", "De"),
            "fim": ("Data fim", "Fim", "Até"),
            "motivo": ("Motivo",),
        },
    )
    assert mapa.indices == {"nome": 0, "inicio": 1, "fim": 2, "motivo": 3}


def test_mapa_colunas_tolera_variacoes_de_digitacao():
    mapa = MapaColunas(
        ["Funcao", "Culto", "Qtd min", "Qtd max", "Coringa", "Data fixa"],
        {
            "nome": ("Função", "Nome"),
            "culto": ("Culto (Domingo/Oração/Ambos)", "Culto"),
            "qtd_min": ("Qtd. mín.", "Qtd min", "Mínimo"),
            "qtd_max": ("Qtd. máx.", "Qtd max", "Máximo"),
            "coringa": ("É coringa?", "Coringa"),
            "data_fixa": ("É de data fixa no mês?", "Data fixa"),
        },
    )
    assert mapa.indices == {
        "nome": 0, "culto": 1, "qtd_min": 2, "qtd_max": 3, "coringa": 4, "data_fixa": 5
    }


def test_escrever_preserva_colunas_desconhecidas():
    """Colunas extras criadas pelo admin não podem ser apagadas na regravação."""
    mapa = MapaColunas(["Data", "Culto", "Função", "Nome", "Minha anotação"], {
        "data": ("Data",), "culto": ("Culto",), "funcao": ("Função",), "nome": ("Nome",),
    })
    original = ["01/03/2026", "Domingo", "Staff", "Ana", "conferir com o líder"]
    nova = mapa.montar({"nome": "Bruno"}, base=original)
    assert nova == ["01/03/2026", "Domingo", "Staff", "Bruno", "conferir com o líder"]


def test_aba_valores_normaliza_largura():
    item = Aba("X", ["A", "B", "C"], [["1"], ["1", "2", "3"]])
    assert item.valores() == [["A", "B", "C"], ["1", "", ""], ["1", "2", "3"]]


def test_planilha_encontra_aba_sem_acento():
    planilha = Planilha()
    planilha.definir(Aba("Voluntarios", ["Nome"], []))
    assert planilha.obter("Voluntários") is not None


# ---------------------------------------------------------------------------

def _planilha(config_linhas, funcoes_linhas=None, voluntarios_linhas=None, indisp=None):
    return montar_planilha(
        v=aba(ABA_VOLUNTARIOS, voluntarios_linhas or [["Ana", "", "Sim", "Staff", ""]]),
        f=aba(
            ABA_FUNCOES,
            funcoes_linhas
            or [["Staff", "Ambos", "1", "1", "Não", "Não"]],
        ),
        c=aba(ABA_CONFIG, config_linhas),
        i=aba(ABA_INDISPONIBILIDADES, indisp or []),
    )


def test_le_competencia_e_ceia_explicita():
    base = base_de(_planilha([["Mês/Ano", "Março/2026"], ["Data da Ceia", "08/03"]]))
    assert (base.config.mes, base.config.ano) == (3, 2026)
    assert base.config.datas_ceia == [date(2026, 3, 8)]


def test_ceia_ausente_assume_primeiro_domingo():
    base = base_de(_planilha([["Mês/Ano", "03/2026"]]))
    assert base.config.datas_ceia == [date(2026, 3, 1)]
    assert any("1º domingo" in a for a in base.avisos)


def test_ceia_pode_ser_desligada():
    base = base_de(_planilha([["Mês/Ano", "03/2026"], ["Data da Ceia", "nenhuma"]]))
    assert base.config.datas_ceia == []


def test_data_fixa_liga_configuracao_a_funcao():
    base = base_de(
        _planilha(
            [["Mês/Ano", "03/2026"], ["Data do Infantil 10-12", "2º domingo"]],
            funcoes_linhas=[
                ["Staff", "Domingo", "1", "1", "Não", "Não"],
                ["Infantil 10-12", "Domingo", "1", "1", "Não", "Sim"],
            ],
        )
    )
    assert base.config.datas_da_funcao("Infantil 10-12") == [date(2026, 3, 8)]


def test_data_fixa_sem_configuracao_gera_aviso():
    base = base_de(
        _planilha(
            [["Mês/Ano", "03/2026"], ["Data da Ceia", "nenhuma"]],
            funcoes_linhas=[["Adolescentes 13-17", "Domingo", "1", "1", "Não", "Sim"]],
        )
    )
    assert any("data fixa" in a and "Adolescentes" in a for a in base.avisos)


def test_le_evento_com_funcoes_extras():
    base = base_de(
        _planilha(
            [
                ["Mês/Ano", "03/2026"],
                ["Evento", "20/03 | Vigília | Oração | Sonorização; Recepção"],
            ]
        )
    )
    evento = base.config.eventos[0]
    assert evento.data == date(2026, 3, 20)
    assert evento.nome == "Vigília"
    assert evento.base == "Oração"
    assert evento.funcoes_extras == ["Sonorização", "Recepção"]


def test_evento_sem_base_assume_domingo():
    base = base_de(_planilha([["Mês/Ano", "03/2026"], ["Evento", "20/03 | Batismo"]]))
    assert base.config.eventos[0].base == "Domingo"


def test_evento_com_data_ilegivel_e_ignorado_com_aviso():
    base = base_de(_planilha([["Mês/Ano", "03/2026"], ["Evento", "sábado que vem | Festa"]]))
    assert base.config.eventos == []
    assert any("ignorado" in a for a in base.avisos)


def test_alvos_coringa_e_preenchimento_maximo():
    base = base_de(
        _planilha(
            [
                ["Mês/Ano", "03/2026"],
                ["Funções cobertas por coringa", "Abertura; Recepção"],
                ["Preencher até a quantidade máxima", "Não"],
            ]
        )
    )
    assert base.config.aceita_coringa("Abertura")
    assert base.config.aceita_coringa("recepcao")
    assert not base.config.aceita_coringa("Oferta")
    assert base.config.preencher_maximo is False


def test_alvos_coringa_tem_padrao_do_prd():
    base = base_de(_planilha([["Mês/Ano", "03/2026"]]))
    assert base.config.aceita_coringa("Abertura")
    assert base.config.aceita_coringa("Oferta")


def test_voluntario_le_funcoes_e_ativo():
    base = base_de(
        _planilha(
            [["Mês/Ano", "03/2026"]],
            voluntarios_linhas=[
                ["Ana", "9999", "Sim", "Staff; Louvor", ""],
                ["Bruno", "8888", "Não", "Staff", "afastado"],
            ],
        )
    )
    assert len(base.voluntarios) == 2
    assert len(base.voluntarios_ativos) == 1
    assert base.voluntarios[0].exerce("staff")
    assert base.voluntarios[0].exerce("LOUVOR")
    assert not base.voluntarios[0].exerce("Projetor")


def test_indisponibilidade_cobre_intervalo():
    base = base_de(
        _planilha(
            [["Mês/Ano", "03/2026"]],
            indisp=[["Ana", "05/03/2026", "10/03/2026", "viagem"]],
        )
    )
    indisp = base.indisponibilidades[0]
    assert indisp.cobre(date(2026, 3, 5))
    assert indisp.cobre(date(2026, 3, 10))
    assert not indisp.cobre(date(2026, 3, 11))


def test_indisponibilidade_de_um_dia_so():
    base = base_de(
        _planilha([["Mês/Ano", "03/2026"]], indisp=[["Ana", "05/03/2026", "", "médico"]])
    )
    assert base.indisponibilidades[0].cobre(date(2026, 3, 5))
    assert not base.indisponibilidades[0].cobre(date(2026, 3, 6))


def test_diagnostico_aponta_funcao_inexistente_e_nome_desconhecido():
    base = base_de(
        _planilha(
            [["Mês/Ano", "03/2026"], ["Data da Ceia", "nenhuma"]],
            voluntarios_linhas=[["Ana", "", "Sim", "Staff; Bateria", ""]],
            indisp=[["Zezinho", "05/03/2026", "", "viagem"]],
        )
    )
    assert any("Bateria" in a for a in base.avisos)
    assert any("Zezinho" in a for a in base.avisos)


def test_aba_ausente_gera_aviso_sem_quebrar():
    base = carregar_base(Planilha())
    assert base.voluntarios == []
    assert any("Voluntários" in a for a in base.avisos)


def test_le_escalacao_manual():
    base = base_de(
        _planilha(
            [
                ["Mês/Ano", "03/2026"],
                ["Escalação manual", "01/03 | Louvor | Ana; Bruno"],
                ["Escalação manual", "08/03 | Louvor | Carla"],
            ]
        )
    )
    assert base.config.nomes_manuais(date(2026, 3, 1), "Louvor") == ["Ana", "Bruno"]
    assert base.config.nomes_manuais(date(2026, 3, 8), "louvor") == ["Carla"]
    assert base.config.nomes_manuais(date(2026, 3, 15), "Louvor") == []


def test_escalacao_manual_mal_formatada_avisa():
    base = base_de(
        _planilha([["Mês/Ano", "03/2026"], ["Escalação manual", "01/03 e a Ana"]])
    )
    assert base.config.manuais == []
    assert any("data | função | nomes" in a for a in base.avisos)


# ---------------------------------------------------------------------------
# Gravação da configuração montada na tela
# ---------------------------------------------------------------------------

FUNCOES_COM_DATA_FIXA = [
    ["Staff", "Domingo", "1", "1", "Não", "Não"],
    ["Geração Luz", "Domingo", "1", "1", "Não", "Sim"],
]


def _config_gravada(config_linhas, config, funcoes_linhas=FUNCOES_COM_DATA_FIXA):
    planilha = _planilha(config_linhas, funcoes_linhas=funcoes_linhas)
    base = base_de(planilha)
    nova = atualizar_aba_config(planilha.obter(ABA_CONFIG), config, base.funcoes)
    return {linha[0]: linha[1] for linha in nova.linhas}, nova


def test_gravacao_preserva_campos_que_nao_estao_na_tela():
    """`Funções cobertas por coringa` e `Preencher…` ficam fora da tela."""
    valores, _ = _config_gravada(
        [
            ["Mês/Ano", "03/2026"],
            ["Funções cobertas por coringa", "Abertura; Recepção"],
            ["Preencher até a quantidade máxima", "Não"],
            ["Anotação da equipe", "combinar com o pastor"],
        ],
        ConfiguracoesMes(mes=4, ano=2026, datas_ceia=[date(2026, 4, 5)]),
    )
    assert valores["Funções cobertas por coringa"] == "Abertura; Recepção"
    assert valores["Preencher até a quantidade máxima"] == "Não"
    assert valores["Anotação da equipe"] == "combinar com o pastor"
    assert valores["Mês/Ano"] == "Abril/2026"
    assert valores["Data da Ceia"] == "05/04/2026"


def test_gravacao_cria_linhas_que_ainda_nao_existem():
    valores, _ = _config_gravada(
        [["Mês/Ano", "03/2026"]],
        ConfiguracoesMes(
            mes=3,
            ano=2026,
            datas_ceia=[date(2026, 3, 1)],
            datas_oracao=[date(2026, 3, 18)],
            datas_sem_culto=[date(2026, 3, 29)],
            datas_por_funcao={"geracao luz": [date(2026, 3, 8)]},
        ),
    )
    assert valores["Data do culto de oração"] == "18/03/2026"
    assert valores["Datas sem culto"] == "29/03/2026"
    assert valores["Data do Geração Luz"] == "08/03/2026"


def test_gravacao_sem_ceia_registra_nenhuma():
    valores, _ = _config_gravada(
        [["Mês/Ano", "03/2026"], ["Data da Ceia", "01/03"]],
        ConfiguracoesMes(mes=3, ano=2026),
    )
    assert valores["Data da Ceia"] == "nenhuma"


def test_gravacao_substitui_eventos_e_escalas_manuais():
    valores, nova = _config_gravada(
        [
            ["Mês/Ano", "03/2026"],
            ["Evento", "10/03 | Antigo | Domingo"],
            ["Escalação manual", "10/03 | Louvor | Fulano"],
        ],
        ConfiguracoesMes(
            mes=3,
            ano=2026,
            datas_ceia=[date(2026, 3, 1)],
            eventos=[
                Evento(date(2026, 3, 20), "Vigília", "Oração", ["Recepção", "Maná Coffee"])
            ],
            manuais=[EscalaManual(date(2026, 3, 1), "Louvor", ["Ana", "Bruno"])],
        ),
    )
    assert valores["Evento"] == "20/03/2026 | Vigília | Oração | Recepção; Maná Coffee"
    assert valores["Escalação manual"] == "01/03/2026 | Louvor | Ana; Bruno"
    assert sum(1 for linha in nova.linhas if linha[0] == "Evento") == 1


def test_ciclo_gravar_e_reler_preserva_a_configuracao():
    config = ConfiguracoesMes(
        mes=3,
        ano=2026,
        datas_ceia=[date(2026, 3, 1), date(2026, 3, 15)],
        datas_oracao=[date(2026, 3, 18)],
        datas_sem_culto=[date(2026, 3, 29)],
        datas_por_funcao={"geracao luz": [date(2026, 3, 8)]},
        eventos=[Evento(date(2026, 3, 20), "Vigília", "Oração", ["Recepção"])],
        manuais=[EscalaManual(date(2026, 3, 1), "Louvor", ["Ana", "Bruno"])],
    )
    planilha = _planilha([["Mês/Ano", "03/2026"]], funcoes_linhas=FUNCOES_COM_DATA_FIXA)
    base = base_de(planilha)
    planilha.definir(atualizar_aba_config(planilha.obter(ABA_CONFIG), config, base.funcoes))

    relida = base_de(planilha).config
    assert (relida.mes, relida.ano) == (3, 2026)
    assert relida.datas_ceia == config.datas_ceia
    assert relida.datas_oracao == config.datas_oracao
    assert relida.datas_sem_culto == config.datas_sem_culto
    assert relida.datas_da_funcao("Geração Luz") == [date(2026, 3, 8)]
    assert relida.eventos[0].nome == "Vigília"
    assert relida.eventos[0].funcoes_extras == ["Recepção"]
    assert relida.nomes_manuais(date(2026, 3, 1), "Louvor") == ["Ana", "Bruno"]
