"""Normalização de texto e leitura tolerante dos valores digitados na planilha.

A planilha é preenchida por pessoas, então praticamente todo valor lido daqui
pode vir com acento faltando, caixa diferente, espaço sobrando ou um formato de
data alternativo. Todas as comparações do sistema passam por `normalizar`, e
toda leitura de valor passa por um dos `parse_*` abaixo.
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime

# ---------------------------------------------------------------------------
# Nomes em português
# ---------------------------------------------------------------------------

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

# `date.weekday()`: 0 = segunda ... 6 = domingo
DIAS_SEMANA = [
    "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
]

_DIA_SEMANA_POR_NOME = {
    "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3,
    "sexta": 4, "sabado": 5, "domingo": 6,
}

_ORDINAIS = {
    "primeiro": 1, "primeira": 1, "segundo": 2, "segunda": 2,
    "terceiro": 3, "terceira": 3, "quarto": 4, "quarta": 4,
    "quinto": 5, "quinta": 5,
    "ultimo": -1, "ultima": -1, "penultimo": -2, "penultima": -2,
}

_VALORES_VERDADEIROS = {
    "sim", "s", "x", "true", "verdadeiro", "v", "1", "ok", "yes", "y",
}
_VALORES_FALSOS = {
    "nao", "n", "false", "falso", "f", "0", "no", "-", "",
}
# Valores que significam "esse campo está deliberadamente vazio".
_VALORES_NULOS = {
    # já normalizados: "n/a" vira "n a", "--" vira ""
    "", "n a", "na", "nenhum", "nenhuma", "sem", "sem data",
    "nao ha", "nao tem", "none", "null",
}


# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------

def sem_acento(texto: str) -> str:
    """Remove acentos e converte ordinais (º, ª) em letras simples."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def normalizar(texto: object) -> str:
    """Chave canônica para comparar textos digitados por pessoas diferentes.

    Minúsculas, sem acento, sem pontuação e com espaços colapsados:

    >>> normalizar("Qtd. mín.")
    'qtd min'
    >>> normalizar("Infantil 10-12")
    'infantil 10 12'
    >>> normalizar("É coringa?")
    'e coringa'
    """
    if texto is None:
        return ""
    bruto = sem_acento(str(texto)).lower()
    bruto = re.sub(r"[^a-z0-9]+", " ", bruto)
    return re.sub(r"\s+", " ", bruto).strip()


def limpar(texto: object) -> str:
    """Texto exibível: só remove espaços das pontas e colapsa espaços internos."""
    if texto is None:
        return ""
    return re.sub(r"\s+", " ", str(texto)).strip()


def vazio(texto: object) -> bool:
    """True quando o valor representa ausência de conteúdo."""
    return normalizar(texto) in _VALORES_NULOS


# ---------------------------------------------------------------------------
# Conversões simples
# ---------------------------------------------------------------------------

def parse_bool(valor: object, padrao: bool = False) -> bool:
    """Lê colunas do tipo Sim/Não com tolerância a variações."""
    chave = normalizar(valor)
    if chave in _VALORES_VERDADEIROS:
        return True
    if chave in _VALORES_FALSOS:
        return False
    return padrao


def parse_int(valor: object, padrao: int = 0) -> int:
    """Lê um número inteiro; devolve `padrao` se não houver número no texto."""
    chave = normalizar(valor)
    achado = re.search(r"\d+", chave)
    if not achado:
        return padrao
    return int(achado.group())


def parse_lista(valor: object) -> list[str]:
    """Separa uma célula com vários itens (";", "," ou quebra de linha)."""
    if valor is None:
        return []
    partes = re.split(r"[;,\n\r]+", str(valor))
    return [limpar(p) for p in partes if not vazio(p)]


# ---------------------------------------------------------------------------
# Datas
# ---------------------------------------------------------------------------

def dias_do_mes_na_semana(ano: int, mes: int, dia_semana: int) -> list[date]:
    """Todas as datas do mês que caem no dia da semana pedido (0=seg ... 6=dom)."""
    total = calendar.monthrange(ano, mes)[1]
    return [
        date(ano, mes, dia)
        for dia in range(1, total + 1)
        if date(ano, mes, dia).weekday() == dia_semana
    ]


def domingos_do_mes(ano: int, mes: int) -> list[date]:
    return dias_do_mes_na_semana(ano, mes, 6)


def enesimo_dia_semana(ano: int, mes: int, dia_semana: int, posicao: int) -> date | None:
    """Devolve, por exemplo, o "3º domingo" (posicao=3) ou o "último" (posicao=-1)."""
    datas = dias_do_mes_na_semana(ano, mes, dia_semana)
    if not datas:
        return None
    if posicao > 0:
        indice = posicao - 1
    else:
        indice = len(datas) + posicao
    if 0 <= indice < len(datas):
        return datas[indice]
    return None


def _parse_expressao_dia_semana(chave: str, ano: int | None, mes: int | None) -> date | None:
    """Interpreta expressões como "1º domingo", "última quarta", "3a quinta"."""
    if ano is None or mes is None:
        return None
    achado = re.fullmatch(r"(\S+)\s*(?:o|a)?\s+([a-z ]+?)(?:\s+feira)?", chave)
    if not achado:
        return None
    bruto_ordinal, bruto_dia = achado.group(1), achado.group(2).strip()

    dia_semana = _DIA_SEMANA_POR_NOME.get(bruto_dia)
    if dia_semana is None:
        return None

    numero = re.fullmatch(r"(\d+)o?a?", bruto_ordinal)
    if numero:
        posicao = int(numero.group(1))
    elif bruto_ordinal in _ORDINAIS:
        posicao = _ORDINAIS[bruto_ordinal]
    else:
        return None
    return enesimo_dia_semana(ano, mes, dia_semana, posicao)


def parse_data(valor: object, ano: int | None = None, mes: int | None = None) -> date | None:
    """Lê uma data em qualquer dos formatos usados na prática pela equipe.

    Aceita ``01/03/2026``, ``01/03/26``, ``01/03`` (mês/ano do contexto),
    ``2026-03-01``, apenas o dia (``1``) e expressões como ``1º domingo`` ou
    ``última quarta``. Devolve ``None`` para células vazias ou "nenhuma".
    """
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if valor is None:
        return None

    texto = limpar(valor)
    if vazio(texto):
        return None

    # ISO: 2026-03-01
    achado = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", texto)
    if achado:
        return _data_segura(int(achado.group(1)), int(achado.group(2)), int(achado.group(3)))

    # DD/MM/AAAA, DD-MM-AA, DD.MM
    achado = re.fullmatch(r"(\d{1,2})\s*[/.\-]\s*(\d{1,2})(?:\s*[/.\-]\s*(\d{2,4}))?", texto)
    if achado:
        dia = int(achado.group(1))
        mes_lido = int(achado.group(2))
        if achado.group(3):
            ano_lido = int(achado.group(3))
            if ano_lido < 100:
                ano_lido += 2000
        elif ano is not None:
            ano_lido = ano
        else:
            return None
        return _data_segura(ano_lido, mes_lido, dia)

    chave = normalizar(texto)

    # Só o número do dia ("1", "15") — precisa do mês/ano do contexto.
    if re.fullmatch(r"\d{1,2}", chave) and ano is not None and mes is not None:
        return _data_segura(ano, mes, int(chave))

    # "1º domingo", "última quarta"
    return _parse_expressao_dia_semana(chave, ano, mes)


def _data_segura(ano: int, mes: int, dia: int) -> date | None:
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def parse_datas(valor: object, ano: int | None = None, mes: int | None = None) -> list[date]:
    """Lê uma célula que pode conter várias datas separadas por ";" ou ",".

    Datas completas (``01/03/2026``) usam o próprio ano; formatos curtos usam o
    mês/ano do contexto. Itens ilegíveis são descartados silenciosamente — a
    camada de dados reporta os avisos.
    """
    datas: list[date] = []
    for pedaco in parse_lista(valor):
        lida = parse_data(pedaco, ano=ano, mes=mes)
        if lida is not None and lida not in datas:
            datas.append(lida)
    return sorted(datas)


def parse_mes_ano(valor: object) -> tuple[int, int] | None:
    """Lê a competência: ``03/2026``, ``2026-03``, ``Março/2026``, ``marco 2026``."""
    if valor is None:
        return None
    texto = limpar(valor)
    if vazio(texto):
        return None

    achado = re.fullmatch(r"(\d{1,2})\s*[/.\-]\s*(\d{4})", texto)
    if achado:
        return _mes_ano_seguro(int(achado.group(1)), int(achado.group(2)))

    achado = re.fullmatch(r"(\d{4})\s*[/.\-]\s*(\d{1,2})", texto)
    if achado:
        return _mes_ano_seguro(int(achado.group(2)), int(achado.group(1)))

    chave = normalizar(texto)
    achado = re.fullmatch(r"([a-z]+)(?:\s+de)?\s*(\d{4})", chave)
    if achado:
        nome, ano = achado.group(1), int(achado.group(2))
        for indice, mes_nome in enumerate(MESES, start=1):
            if normalizar(mes_nome).startswith(nome) and len(nome) >= 3:
                return _mes_ano_seguro(indice, ano)
    return None


def _mes_ano_seguro(mes: int, ano: int) -> tuple[int, int] | None:
    if 1 <= mes <= 12 and 1900 <= ano <= 2999:
        return mes, ano
    return None


# ---------------------------------------------------------------------------
# Formatação para exibição
# ---------------------------------------------------------------------------

def nome_mes(mes: int) -> str:
    return MESES[mes - 1].capitalize()


def nome_dia_semana(data: date) -> str:
    return DIAS_SEMANA[data.weekday()]


def competencia(mes: int, ano: int) -> str:
    """"Março/2026"."""
    return f"{nome_mes(mes)}/{ano}"


def formatar_data(data: date, com_ano: bool = False) -> str:
    return data.strftime("%d/%m/%Y") if com_ano else data.strftime("%d/%m")


def formatar_data_iso(data: date | None) -> str:
    """Formato gravado na planilha (dd/mm/aaaa, que o Sheets entende como data)."""
    return data.strftime("%d/%m/%Y") if data else ""
