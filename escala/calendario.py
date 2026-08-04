"""Montagem do calendário do mês e das funções de cada culto."""

from __future__ import annotations

from datetime import date

from .dados import ConfiguracoesMes
from .modelos import (
    CULTO_DOMINGO,
    CULTO_EVENTO,
    CULTO_ORACAO,
    FUNCAO_CEIA,
    Culto,
    Funcao,
)
from .textos import domingos_do_mes, formatar_data, normalizar


def montar_cultos(config: ConfiguracoesMes, mes: int, ano: int) -> list[Culto]:
    """Lista, em ordem cronológica, todos os cultos do mês.

    Inclui os domingos, o(s) culto(s) de oração configurado(s) e os eventos
    pontuais. Datas listadas em `Datas sem culto` são puladas.
    """
    sem_culto = set(config.datas_sem_culto)
    cultos: list[Culto] = []

    for domingo in domingos_do_mes(ano, mes):
        if domingo in sem_culto:
            continue
        cultos.append(
            Culto(
                data=domingo,
                tipo=CULTO_DOMINGO,
                rotulo=CULTO_DOMINGO,
                base=CULTO_DOMINGO,
                ceia=(config.data_ceia == domingo),
            )
        )

    for data_oracao in config.datas_oracao:
        if data_oracao in sem_culto:
            continue
        cultos.append(
            Culto(
                data=data_oracao,
                tipo=CULTO_ORACAO,
                rotulo=CULTO_ORACAO,
                base=CULTO_ORACAO,
            )
        )

    for evento in config.eventos:
        if evento.data in sem_culto:
            continue
        cultos.append(
            Culto(
                data=evento.data,
                tipo=CULTO_EVENTO,
                rotulo=f"Evento: {evento.nome}",
                base=evento.base,
                nome_evento=evento.nome,
                funcoes_extras=list(evento.funcoes_extras),
            )
        )

    return sorted(cultos, key=lambda c: c.ordenacao)


def funcoes_do_culto(
    culto: Culto, catalogo: list[Funcao], config: ConfiguracoesMes
) -> list[Funcao]:
    """Quais funções precisam ser preenchidas neste culto específico.

    Regras aplicadas:
    - herda do catálogo as funções do tipo de culto base (ou "Ambos");
    - funções marcadas como "de data fixa no mês" só entram na data configurada;
    - domingos de Ceia ganham a função `Servo da Ceia`, mesmo que ela não esteja
      cadastrada no catálogo;
    - eventos podem somar funções nominais próprias.
    """
    selecionadas: list[Funcao] = []
    ja_incluidas: set[str] = set()

    if culto.base:
        for funcao in sorted(catalogo, key=lambda f: f.ordem):
            if not funcao.vale_para(culto.base):
                continue
            if funcao.data_fixa and culto.data not in config.datas_da_funcao(funcao.nome):
                continue
            selecionadas.append(funcao)
            ja_incluidas.add(funcao.chave)

    if culto.ceia and normalizar(FUNCAO_CEIA) not in ja_incluidas:
        # A função da Ceia é garantida por regra de negócio, esteja ela ou não
        # no catálogo (o catálogo pode não ter sido atualizado).
        selecionadas.append(
            Funcao(
                nome=FUNCAO_CEIA,
                culto=CULTO_DOMINGO,
                qtd_min=1,
                qtd_max=1,
                ordem=10_000,
            )
        )
        ja_incluidas.add(normalizar(FUNCAO_CEIA))

    for nome_extra in culto.funcoes_extras:
        chave = normalizar(nome_extra)
        if not chave or chave in ja_incluidas:
            continue
        do_catalogo = next((f for f in catalogo if f.chave == chave), None)
        if do_catalogo is not None:
            selecionadas.append(do_catalogo)
        else:
            selecionadas.append(
                Funcao(nome=nome_extra, culto=CULTO_EVENTO, qtd_min=1, qtd_max=1, ordem=20_000)
            )
        ja_incluidas.add(chave)

    return selecionadas


def descrever_culto(culto: Culto) -> str:
    """Rótulo curto para listagens na interface."""
    sufixo = " (Ceia)" if culto.ceia else ""
    if culto.tipo == CULTO_ORACAO:
        return f"{formatar_data(culto.data)} — Culto de Oração"
    if culto.tipo == CULTO_EVENTO:
        return f"{formatar_data(culto.data)} — {culto.nome_evento}"
    return f"{formatar_data(culto.data)} — Domingo{sufixo}"


def datas_dos_cultos(cultos: list[Culto]) -> set[date]:
    return {culto.data for culto in cultos}
