"""Formato do texto colado no grupo do WhatsApp."""

from datetime import date

from escala.modelos import Atribuicao
from escala.whatsapp import gerar_texto_de_um_culto, gerar_texto_whatsapp

ORDEM = ["Staff", "Abertura", "Oferta", "Intercessão", "Louvor", "Servo da Ceia"]


def linha(dia, funcao, nome, culto="Domingo"):
    return Atribuicao(data=date(2026, 3, dia), culto=culto, funcao=funcao, nome=nome)


def test_estrutura_do_texto_segue_o_modelo_do_prd():
    atribuicoes = [
        linha(1, "Staff", "Fulano"),
        linha(1, "Abertura", "Fulana"),
        linha(1, "Servo da Ceia", "Fulano"),
        linha(18, "Staff", "Fulano", culto="Oração"),
        linha(18, "Intercessão", "Fulana", culto="Oração"),
        linha(18, "Intercessão", "Beltrano", culto="Oração"),
    ]
    texto = gerar_texto_whatsapp(
        atribuicoes, mes=3, ano=2026, ordem_funcoes=ORDEM, data_ceia=date(2026, 3, 1)
    )
    assert texto == "\n".join(
        [
            "*Escala — Março/2026*",
            "",
            "*Domingo, 01/03 (Ceia)*",
            "Staff: Fulano",
            "Abertura: Fulana",
            "Servo da Ceia: Fulano",
            "",
            "*Culto de Oração — Quarta, 18/03*",
            "Staff: Fulano",
            "Intercessão: Fulana, Beltrano",
        ]
    )


def test_marca_ceia_pela_presenca_da_funcao_mesmo_sem_a_data():
    texto = gerar_texto_whatsapp(
        [linha(1, "Servo da Ceia", "Ana")], mes=3, ano=2026, ordem_funcoes=ORDEM
    )
    assert "*Domingo, 01/03 (Ceia)*" in texto


def test_domingo_comum_nao_recebe_marca_de_ceia():
    texto = gerar_texto_whatsapp(
        [linha(8, "Staff", "Ana")], mes=3, ano=2026, data_ceia=date(2026, 3, 1)
    )
    assert "*Domingo, 08/03*" in texto
    assert "Ceia" not in texto


def test_evento_usa_o_proprio_nome_no_cabecalho():
    texto = gerar_texto_whatsapp(
        [linha(20, "Staff", "Ana", culto="Evento: Vigília de Oração")], mes=3, ano=2026
    )
    assert "*Vigília de Oração — Sexta, 20/03*" in texto


def test_respeita_a_ordem_das_funcoes_do_catalogo():
    """A ordem de saída é a da aba `Funções`, não a de geração."""
    atribuicoes = [
        linha(1, "Louvor", "Carla"),
        linha(1, "Staff", "Ana"),
        linha(1, "Abertura", "Bruno"),
    ]
    texto = gerar_texto_whatsapp(atribuicoes, mes=3, ano=2026, ordem_funcoes=ORDEM)
    assert texto.splitlines()[3:] == ["Staff: Ana", "Abertura: Bruno", "Louvor: Carla"]


def test_funcao_fora_do_catalogo_vai_para_o_fim():
    atribuicoes = [linha(1, "Sonorização", "Carla"), linha(1, "Staff", "Ana")]
    texto = gerar_texto_whatsapp(atribuicoes, mes=3, ano=2026, ordem_funcoes=ORDEM)
    assert texto.splitlines()[-2:] == ["Staff: Ana", "Sonorização: Carla"]


def test_agrupa_varios_nomes_da_mesma_funcao():
    atribuicoes = [linha(1, "Louvor", n) for n in ("Ana", "Bruno", "Carla")]
    texto = gerar_texto_whatsapp(atribuicoes, mes=3, ano=2026, ordem_funcoes=ORDEM)
    assert "Louvor: Ana, Bruno, Carla" in texto


def test_cultos_saem_em_ordem_cronologica():
    atribuicoes = [linha(29, "Staff", "C"), linha(1, "Staff", "A"), linha(15, "Staff", "B")]
    texto = gerar_texto_whatsapp(atribuicoes, mes=3, ano=2026)
    assert texto.index("01/03") < texto.index("15/03") < texto.index("29/03")


def test_rodape_opcional():
    texto = gerar_texto_whatsapp(
        [linha(1, "Staff", "Ana")], mes=3, ano=2026, rodape="Qualquer imprevisto, avise 🙏"
    )
    assert texto.endswith("Qualquer imprevisto, avise 🙏")


def test_ignora_linhas_sem_nome_ou_sem_data():
    atribuicoes = [
        linha(1, "Staff", "Ana"),
        Atribuicao(data=date(2026, 3, 1), culto="Domingo", funcao="Oferta", nome=""),
        Atribuicao(data=None, culto="Domingo", funcao="Staff", nome="Bruno"),
    ]
    texto = gerar_texto_whatsapp(atribuicoes, mes=3, ano=2026)
    assert "Oferta" not in texto
    assert "Bruno" not in texto


def test_escala_vazia_devolve_string_vazia():
    assert gerar_texto_whatsapp([], mes=3, ano=2026) == ""


def test_texto_de_um_culto_so():
    atribuicoes = [linha(1, "Staff", "Ana"), linha(8, "Staff", "Bruno")]
    texto = gerar_texto_de_um_culto(atribuicoes, date(2026, 3, 8), ordem_funcoes=ORDEM)
    assert texto.startswith("*Domingo, 08/03*")
    assert "Ana" not in texto
