"""Geração do texto pronto para colar no grupo do WhatsApp.

O texto é montado a partir das linhas que estão na `Escala Gerada` no momento
(inclusive ajustes manuais do admin), e não de uma geração em memória — o que o
admin vê na planilha é exatamente o que vai para o grupo.
"""

from __future__ import annotations

from datetime import date

from .modelos import CULTO_ORACAO, Atribuicao
from .textos import (
    competencia,
    formatar_data,
    nome_dia_semana,
    normalizar,
)


def _titulo_do_culto(
    data: date, rotulo: str, e_ceia: bool
) -> str:
    """Cabeçalho de cada bloco, em negrito do WhatsApp."""
    chave = normalizar(rotulo)
    dia_semana = nome_dia_semana(data)
    data_curta = formatar_data(data)

    if chave.startswith("evento"):
        nome = rotulo.split(":", 1)[1].strip() if ":" in rotulo else "Evento"
        return f"*{nome} — {dia_semana}, {data_curta}*"

    if chave.startswith(normalizar(CULTO_ORACAO)) or "oracao" in chave:
        return f"*Culto de Oração — {dia_semana}, {data_curta}*"

    if chave.startswith("domingo") or data.weekday() == 6:
        sufixo = " (Ceia)" if e_ceia else ""
        return f"*Domingo, {data_curta}{sufixo}*"

    rotulo_limpo = rotulo or dia_semana
    return f"*{rotulo_limpo} — {dia_semana}, {data_curta}*"


def _ordem_da_funcao(nome: str, ordem_funcoes: list[str]) -> int:
    alvo = normalizar(nome)
    for indice, funcao in enumerate(ordem_funcoes):
        if normalizar(funcao) == alvo:
            return indice
    return len(ordem_funcoes)


def gerar_texto_whatsapp(
    atribuicoes: list[Atribuicao],
    mes: int | None = None,
    ano: int | None = None,
    ordem_funcoes: list[str] | None = None,
    data_ceia: date | None = None,
    titulo: str | None = None,
    rodape: str = "",
) -> str:
    """Monta a mensagem completa da escala do mês.

    As funções saem na ordem da aba `Funções`; funções que não estão no
    catálogo (extras de evento) vão para o fim, em ordem de aparição.
    """
    ordem_funcoes = ordem_funcoes or []
    validas = [a for a in atribuicoes if a.data and a.nome]
    if not validas:
        return ""

    if titulo is None:
        if mes and ano:
            titulo = f"*Escala — {competencia(mes, ano)}*"
        else:
            titulo = "*Escala*"

    # Agrupa por (data, rótulo do culto) preservando a ordem cronológica.
    grupos: dict[tuple[date, str], dict[str, list[str]]] = {}
    ordem_aparicao: dict[tuple[date, str], list[str]] = {}
    for registro in validas:
        chave_culto = (registro.data, registro.culto or "")
        funcoes = grupos.setdefault(chave_culto, {})
        aparicao = ordem_aparicao.setdefault(chave_culto, [])
        if registro.funcao not in funcoes:
            funcoes[registro.funcao] = []
            aparicao.append(registro.funcao)
        if registro.nome not in funcoes[registro.funcao]:
            funcoes[registro.funcao].append(registro.nome)

    linhas: list[str] = [titulo]

    for chave_culto in sorted(grupos, key=lambda c: (c[0], c[1])):
        data, rotulo = chave_culto
        funcoes = grupos[chave_culto]
        aparicao = ordem_aparicao[chave_culto]

        e_ceia = (data_ceia is not None and data == data_ceia) or any(
            "ceia" in normalizar(f) for f in funcoes
        )

        linhas.append("")
        linhas.append(_titulo_do_culto(data, rotulo, e_ceia))

        def posicao(funcao: str) -> tuple[int, int]:
            return (_ordem_da_funcao(funcao, ordem_funcoes), aparicao.index(funcao))

        for funcao in sorted(funcoes, key=posicao):
            nomes = ", ".join(funcoes[funcao])
            linhas.append(f"{funcao}: {nomes}")

    if rodape:
        linhas.append("")
        linhas.append(rodape)

    return "\n".join(linhas)


def gerar_texto_de_um_culto(
    atribuicoes: list[Atribuicao],
    data: date,
    ordem_funcoes: list[str] | None = None,
    data_ceia: date | None = None,
) -> str:
    """Versão curta: só um culto, útil para lembrete de véspera."""
    do_dia = [a for a in atribuicoes if a.data == data]
    if not do_dia:
        return ""
    return gerar_texto_whatsapp(
        do_dia,
        ordem_funcoes=ordem_funcoes,
        data_ceia=data_ceia,
        titulo="",
    ).lstrip("\n")
