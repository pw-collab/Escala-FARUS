"""Imagem da escala do mês em formato de tabela (PNG).

Cultos nas colunas, funções nas linhas — desenhada a partir da mesma `Grade` que
monta o texto do WhatsApp, então imagem e texto nunca divergem. Pensada para ir
no grupo: renderizada em 2× para continuar legível depois que o WhatsApp
comprime a foto.
"""

from __future__ import annotations

import io
import math
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .grade import ColunaCulto, Grade
from .modelos import CULTO_DOMINGO, CULTO_EVENTO, CULTO_ORACAO
from .textos import DIAS_SEMANA, formatar_data, limpar

# Liberation Sans (SIL OFL 1.1, ver fontes/OFL.txt): métricas do Arial e mais
# estreita que a média, o que deixa caber mais nome em cada coluna. Vai junto
# no repositório porque o servidor do Streamlit Cloud não garante fontes.
PASTA_FONTES = Path(__file__).parent / "fontes"
FONTE_REGULAR = "LiberationSans-Regular.ttf"
FONTE_NEGRITO = "LiberationSans-Bold.ttf"

# Paleta — o verde é o mesmo da interface do app.
FUNDO = "#FFFFFF"
TEXTO = "#1F2937"
TEXTO_SUAVE = "#6B7280"
TEXTO_VAZIO = "#9CA3AF"
LINHA = "#E5E7EB"
BORDA = "#D1D5DB"
ZEBRA = ("#FFFFFF", "#F7F8FA")
FUNDO_FUNCAO = ("#F1F3F5", "#E9ECEF")
CABECALHO_FUNCAO = "#1F2937"
CABECALHO_TEXTO = "#FFFFFF"
CABECALHO_ETIQUETA = "#E8EEF0"
COR_DO_CULTO = {
    CULTO_DOMINGO: "#2E7D6F",
    CULTO_ORACAO: "#3D5A80",
    CULTO_EVENTO: "#9A6412",
}
COR_CEIA = "#8E3B46"
COR_OUTRO = "#4B5563"

# Medidas em pixels lógicos; tudo é multiplicado pela `escala` na hora de desenhar.
MARGEM = 32
PAD_X = 12
PAD_Y = 9
ALTURA_LINHA = 19
ALTURA_ETIQUETA = 16
ALTURA_TITULO = 36
ALTURA_SUBTITULO = 22
ALTURA_RODAPE = 17
LARGURA_MINIMA_CONTEUDO = 360
LARGURA_FUNCAO = (120, 210)  # mínimo, máximo
LARGURA_CULTO = (118, 190)

TAM_TITULO = 30
TAM_SUBTITULO = 16
TAM_CABECALHO = 15
TAM_ETIQUETA = 12
TAM_TEXTO = 14
TAM_RODAPE = 12


@lru_cache(maxsize=32)
def carregar_fonte(tamanho: int, negrito: bool = False):
    """Fonte embutida; se o arquivo sumir, cai para a fonte padrão do Pillow."""
    arquivo = PASTA_FONTES / (FONTE_NEGRITO if negrito else FONTE_REGULAR)
    try:
        return ImageFont.truetype(str(arquivo), tamanho)
    except OSError:
        try:
            return ImageFont.load_default(size=tamanho)
        except TypeError:  # Pillow < 10.1 não aceita tamanho
            return ImageFont.load_default()


def limpar_para_imagem(texto: object) -> str:
    """Remove o que a fonte não desenha — emoji, pictogramas — sem tocar em acentos.

    O rodapé padrão do WhatsApp termina em 🙏; na imagem ele viraria um quadrado.
    """
    mantidos = []
    for caractere in str(texto or ""):
        if ord(caractere) > 0xFFFF:  # emoji ficam fora do plano básico
            continue
        if unicodedata.category(caractere) in {"So", "Cs", "Co", "Cn"}:
            continue
        if caractere in "\u200d\ufe0e\ufe0f":  # junção e seletores de variação de emoji
            continue
        mantidos.append(caractere)
    return limpar("".join(mantidos))


def quebrar(texto: str, fonte, largura: float) -> list[str]:
    """Quebra por palavra; uma palavra maior que a largura é cortada por letra."""
    linhas: list[str] = []
    atual = ""
    for palavra in texto.split():
        tentativa = f"{atual} {palavra}".strip()
        if fonte.getlength(tentativa) <= largura:
            atual = tentativa
            continue
        if atual:
            linhas.append(atual)
        while len(palavra) > 1 and fonte.getlength(palavra) > largura:
            corte = len(palavra) - 1
            while corte > 1 and fonte.getlength(palavra[:corte]) > largura:
                corte -= 1
            linhas.append(palavra[:corte])
            palavra = palavra[corte:]
        atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _cabecalho(coluna: ColunaCulto) -> tuple[str, str, str]:
    """(linha principal, etiqueta, cor de fundo) do cabeçalho de um culto."""
    principal = f"{DIAS_SEMANA[coluna.data.weekday()][:3]} {formatar_data(coluna.data)}"
    if coluna.tipo == CULTO_DOMINGO:
        if coluna.e_ceia:
            return principal, "Ceia", COR_CEIA
        return principal, "", COR_DO_CULTO[CULTO_DOMINGO]

    sufixo_ceia = " · Ceia" if coluna.e_ceia else ""
    if coluna.tipo == CULTO_ORACAO:
        return principal, "Culto de Oração" + sufixo_ceia, COR_DO_CULTO[CULTO_ORACAO]
    if coluna.tipo == CULTO_EVENTO:
        return principal, coluna.nome_evento + sufixo_ceia, COR_DO_CULTO[CULTO_EVENTO]
    return principal, coluna.rotulo + sufixo_ceia, COR_OUTRO


def _escrever(desenho, x, y_centro, texto, fonte, cor, alinhar="esquerda") -> None:
    """Escreve uma linha com o centro vertical em `y_centro`."""
    largura = fonte.getlength(texto)
    if alinhar == "centro":
        x -= largura / 2
    elif alinhar == "direita":
        x -= largura
    if isinstance(fonte, ImageFont.FreeTypeFont):
        desenho.text((x, y_centro), texto, font=fonte, fill=cor, anchor="lm")
    else:  # fonte bitmap não aceita âncora: centraliza pela caixa do texto
        _, topo, _, base = fonte.getbbox(texto)
        desenho.text((x, y_centro - (topo + base) / 2), texto, font=fonte, fill=cor)


def _limitar(valor: float, minimo: int, maximo: int) -> int:
    # Teto, não truncamento: a medida do texto é fracionária, e perder meio pixel
    # bastaria para o nome mais largo quebrar numa coluna feita sob medida para ele.
    return min(max(math.ceil(valor), minimo), maximo)


def renderizar_png(
    grade: Grade,
    titulo: str,
    subtitulo: str = "",
    rodape: str = "",
    escala: float = 2,
    gerada_em: date | None = None,
) -> bytes:
    """Desenha a grade como tabela e devolve os bytes do PNG."""
    if grade.vazia:
        raise ValueError("Não há escala para desenhar.")
    gerada_em = gerada_em or date.today()

    def px(valor: float) -> int:
        return max(1, round(valor * escala))

    f_titulo = carregar_fonte(px(TAM_TITULO), True)
    f_subtitulo = carregar_fonte(px(TAM_SUBTITULO))
    f_cabecalho = carregar_fonte(px(TAM_CABECALHO), True)
    f_etiqueta = carregar_fonte(px(TAM_ETIQUETA))
    f_funcao = carregar_fonte(px(TAM_TEXTO), True)
    f_nome = carregar_fonte(px(TAM_TEXTO))
    f_rodape = carregar_fonte(px(TAM_RODAPE))

    margem, pad_x, pad_y = px(MARGEM), px(PAD_X), px(PAD_Y)
    altura_linha, altura_etiqueta = px(ALTURA_LINHA), px(ALTURA_ETIQUETA)
    espessura = px(1)

    colunas = range(len(grade.colunas))
    rotulos_funcao = [limpar_para_imagem(f) for f in grade.funcoes]
    nomes = {
        (f, i): [limpar_para_imagem(n) for n in grade.nomes(f, i)]
        for f in grade.funcoes
        for i in colunas
    }
    cabecalhos = [_cabecalho(c) for c in grade.colunas]

    def maior(textos: list[str], fonte) -> float:
        return max((fonte.getlength(t) for t in textos if t), default=0)

    # --- Larguras: pelo maior texto, dentro de limites -----------------------
    largura_funcao = _limitar(
        maior(rotulos_funcao + ["Função"], f_funcao) + 2 * pad_x,
        px(LARGURA_FUNCAO[0]),
        px(LARGURA_FUNCAO[1]),
    )
    largura_culto = _limitar(
        max(
            maior([n for lista in nomes.values() for n in lista], f_nome),
            maior([principal for principal, _, _ in cabecalhos], f_cabecalho),
        )
        + 2 * pad_x,
        px(LARGURA_CULTO[0]),
        px(LARGURA_CULTO[1]),
    )
    util_funcao = largura_funcao - 2 * pad_x
    util_culto = largura_culto - 2 * pad_x

    largura_tabela = largura_funcao + largura_culto * len(grade.colunas)
    largura_conteudo = max(largura_tabela, px(LARGURA_MINIMA_CONTEUDO))

    # --- Conteúdo já quebrado em linhas --------------------------------------
    linhas_titulo = quebrar(limpar_para_imagem(titulo), f_titulo, largura_conteudo)
    linhas_subtitulo = quebrar(limpar_para_imagem(subtitulo), f_subtitulo, largura_conteudo)

    etiquetas = [quebrar(etiqueta, f_etiqueta, util_culto) for _, etiqueta, _ in cabecalhos]
    altura_cabecalho = (
        2 * pad_y + altura_linha + altura_etiqueta * max(len(e) for e in etiquetas)
    )

    corpo: list[tuple[list[str], list[list[str]], int]] = []
    for funcao, rotulo in zip(grade.funcoes, rotulos_funcao):
        linhas_rotulo = quebrar(rotulo, f_funcao, util_funcao)
        celulas = []
        for i in colunas:
            linhas: list[str] = []
            for nome in nomes[(funcao, i)]:
                linhas.extend(quebrar(nome, f_nome, util_culto))
            celulas.append(linhas)
        maior_celula = max([len(linhas_rotulo), 1, *(len(c) for c in celulas)])
        corpo.append((linhas_rotulo, celulas, 2 * pad_y + maior_celula * altura_linha))

    texto_gerada = f"Gerada em {formatar_data(gerada_em, com_ano=True)}"
    largura_gerada = f_rodape.getlength(texto_gerada)
    # O rodapé usa a largura da tabela; "Gerada em" divide a última linha com ele
    # se couber, senão desce para uma linha própria.
    linhas_rodape = quebrar(limpar_para_imagem(rodape), f_rodape, largura_tabela)
    linha_da_data = len(linhas_rodape) - 1 if linhas_rodape else 0
    if linhas_rodape and (
        f_rodape.getlength(linhas_rodape[-1]) + px(24) + largura_gerada > largura_tabela
    ):
        linha_da_data += 1

    # --- Tamanho final --------------------------------------------------------
    altura_topo = len(linhas_titulo) * px(ALTURA_TITULO)
    if linhas_subtitulo:
        altura_topo += px(4) + len(linhas_subtitulo) * px(ALTURA_SUBTITULO)
    altura_corpo = sum(altura for _, _, altura in corpo)
    altura_rodape = (max(len(linhas_rodape) - 1, linha_da_data) + 1) * px(ALTURA_RODAPE)

    largura_imagem = largura_conteudo + 2 * margem
    altura_imagem = (
        margem + altura_topo + px(18) + altura_cabecalho + altura_corpo
        + px(14) + altura_rodape + margem
    )

    imagem = Image.new("RGB", (int(largura_imagem), int(altura_imagem)), FUNDO)
    desenho = ImageDraw.Draw(imagem)

    # --- Título ---------------------------------------------------------------
    # Com poucos cultos a tabela fica mais estreita que o título e vai para o
    # centro; o título acompanha para o conjunto não ficar desencontrado.
    centralizar = largura_tabela < largura_conteudo
    x_titulo = margem + largura_conteudo / 2 if centralizar else margem
    alinhar_titulo = "centro" if centralizar else "esquerda"

    y = margem
    for linha in linhas_titulo:
        _escrever(
            desenho, x_titulo, y + px(ALTURA_TITULO) / 2, linha, f_titulo, TEXTO, alinhar_titulo
        )
        y += px(ALTURA_TITULO)
    if linhas_subtitulo:
        y += px(4)
        for linha in linhas_subtitulo:
            _escrever(
                desenho, x_titulo, y + px(ALTURA_SUBTITULO) / 2, linha, f_subtitulo,
                TEXTO_SUAVE, alinhar_titulo,
            )
            y += px(ALTURA_SUBTITULO)
    y += px(18)

    # --- Cabeçalho da tabela --------------------------------------------------
    x0 = margem + (largura_conteudo - largura_tabela) // 2
    y0 = y
    x_fim = x0 + largura_tabela

    def x_da_coluna(i: int) -> int:
        return x0 + largura_funcao + i * largura_culto

    desenho.rectangle(
        [x0, y0, x0 + largura_funcao - 1, y0 + altura_cabecalho - 1], fill=CABECALHO_FUNCAO
    )
    _escrever(
        desenho, x0 + pad_x, y0 + altura_cabecalho / 2, "Função", f_cabecalho, CABECALHO_TEXTO
    )
    for i, ((principal, _, cor), linhas_etiqueta) in enumerate(zip(cabecalhos, etiquetas)):
        x = x_da_coluna(i)
        centro = x + largura_culto / 2
        desenho.rectangle([x, y0, x + largura_culto - 1, y0 + altura_cabecalho - 1], fill=cor)
        bloco = altura_linha + len(linhas_etiqueta) * altura_etiqueta
        topo = y0 + (altura_cabecalho - bloco) / 2
        _escrever(
            desenho, centro, topo + altura_linha / 2, principal, f_cabecalho,
            CABECALHO_TEXTO, "centro",
        )
        for k, linha in enumerate(linhas_etiqueta):
            _escrever(
                desenho, centro, topo + altura_linha + (k + 0.5) * altura_etiqueta, linha,
                f_etiqueta, CABECALHO_ETIQUETA, "centro",
            )
        if i:  # separador claro entre cabeçalhos coloridos vizinhos
            desenho.line([(x, y0), (x, y0 + altura_cabecalho - 1)], fill=FUNDO, width=espessura)

    # --- Corpo ----------------------------------------------------------------
    y = y0 + altura_cabecalho
    for numero, (linhas_rotulo, celulas, altura) in enumerate(corpo):
        par = numero % 2
        desenho.rectangle(
            [x0, y, x0 + largura_funcao - 1, y + altura - 1], fill=FUNDO_FUNCAO[par]
        )
        topo = y + (altura - len(linhas_rotulo) * altura_linha) / 2
        for k, linha in enumerate(linhas_rotulo):
            _escrever(
                desenho, x0 + pad_x, topo + (k + 0.5) * altura_linha, linha, f_funcao, TEXTO
            )

        for i, linhas in enumerate(celulas):
            x = x_da_coluna(i)
            desenho.rectangle([x, y, x + largura_culto - 1, y + altura - 1], fill=ZEBRA[par])
            conteudo, cor = (linhas, TEXTO) if linhas else (["—"], TEXTO_VAZIO)
            topo = y + (altura - len(conteudo) * altura_linha) / 2
            for k, linha in enumerate(conteudo):
                _escrever(
                    desenho, x + largura_culto / 2, topo + (k + 0.5) * altura_linha, linha,
                    f_nome, cor, "centro",
                )

        if numero:
            desenho.line([(x0, y), (x_fim - 1, y)], fill=LINHA, width=espessura)
        y += altura
    y_fim = y

    for i in colunas:
        x = x_da_coluna(i)
        desenho.line([(x, y0 + altura_cabecalho), (x, y_fim - 1)], fill=LINHA, width=espessura)
    desenho.rectangle([x0, y0, x_fim - 1, y_fim - 1], outline=BORDA, width=espessura)

    # --- Rodapé ---------------------------------------------------------------
    y = y_fim + px(14)
    passo = px(ALTURA_RODAPE)
    for k, linha in enumerate(linhas_rodape):
        _escrever(desenho, x0, y + (k + 0.5) * passo, linha, f_rodape, TEXTO_SUAVE)
    _escrever(
        desenho, x_fim, y + (linha_da_data + 0.5) * passo, texto_gerada,
        f_rodape, TEXTO_SUAVE, "direita",
    )

    saida = io.BytesIO()
    imagem.save(saida, format="PNG", optimize=True)
    return saida.getvalue()
