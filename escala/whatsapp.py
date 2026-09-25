"""Geração do texto pronto para colar no grupo do WhatsApp.

O texto é montado a partir das linhas que estão na `Escala Gerada` no momento
(inclusive ajustes manuais do admin), e não de uma geração em memória — o que o
admin vê na planilha é exatamente o que vai para o grupo.
"""

from __future__ import annotations

from datetime import date

from .grade import ColunaCulto, montar_grade
from .modelos import CULTO_DOMINGO, CULTO_EVENTO, CULTO_ORACAO, Atribuicao
from .textos import competencia, formatar_data, nome_dia_semana


def _titulo_do_culto(coluna: ColunaCulto) -> str:
    """Cabeçalho de cada bloco, em negrito do WhatsApp."""
    dia_semana = nome_dia_semana(coluna.data)
    data_curta = formatar_data(coluna.data)

    if coluna.tipo == CULTO_EVENTO:
        return f"*{coluna.nome_evento} — {dia_semana}, {data_curta}*"
    if coluna.tipo == CULTO_ORACAO:
        return f"*Culto de Oração — {dia_semana}, {data_curta}*"
    if coluna.tipo == CULTO_DOMINGO:
        sufixo = " (Ceia)" if coluna.e_ceia else ""
        return f"*Domingo, {data_curta}{sufixo}*"
    return f"*{coluna.rotulo or dia_semana} — {dia_semana}, {data_curta}*"


def formatar_nomes(nomes: list[str], mencoes: bool = True) -> str:
    """Nomes de uma função, separados por travessão.

    Com `mencoes`, cada nome ganha um `(@ )` logo depois: no WhatsApp, basta
    clicar dentro do parêntese e escolher a pessoa na lista que aparece — a
    menção é feita na hora do envio, sem precisar dos números de telefone.
    """
    sufixo = " (@ )" if mencoes else ""
    return " — ".join(f"{nome}{sufixo}" for nome in nomes)


def gerar_texto_whatsapp(
    atribuicoes: list[Atribuicao],
    mes: int | None = None,
    ano: int | None = None,
    ordem_funcoes: list[str] | None = None,
    datas_ceia: list[date] | None = None,
    titulo: str | None = None,
    rodape: str = "",
    mencoes: bool = True,
) -> str:
    """Monta a mensagem completa da escala do mês.

    As funções saem na ordem da aba `Funções`; funções que não estão no
    catálogo (extras de evento) vão para o fim, em ordem de aparição.
    """
    grade = montar_grade(atribuicoes, ordem_funcoes, datas_ceia)
    if grade.vazia:
        return ""

    if titulo is None:
        if mes and ano:
            titulo = f"*Escala — {competencia(mes, ano)}*"
        else:
            titulo = "*Escala*"

    linhas: list[str] = [titulo]

    for indice, coluna in enumerate(grade.colunas):
        linhas.append("")
        linhas.append(_titulo_do_culto(coluna))
        linhas.append("")
        for funcao in grade.funcoes_da_coluna(indice):
            nomes = formatar_nomes(grade.nomes(funcao, indice), mencoes)
            linhas.append(f"* {funcao}: {nomes}")

    if rodape:
        linhas.append("")
        linhas.append(rodape)

    return "\n".join(linhas)


def gerar_texto_de_um_culto(
    atribuicoes: list[Atribuicao],
    data: date,
    ordem_funcoes: list[str] | None = None,
    datas_ceia: list[date] | None = None,
    mencoes: bool = True,
) -> str:
    """Versão curta: só um culto, útil para lembrete de véspera."""
    do_dia = [a for a in atribuicoes if a.data == data]
    if not do_dia:
        return ""
    return gerar_texto_whatsapp(
        do_dia,
        ordem_funcoes=ordem_funcoes,
        datas_ceia=datas_ceia,
        titulo="",
        mencoes=mencoes,
    ).lstrip("\n")
