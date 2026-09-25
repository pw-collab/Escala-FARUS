"""Visão tabular da escala: cultos nas colunas, funções nas linhas.

O texto do WhatsApp e a imagem da escala saem daqui. Montar os dois a partir do
mesmo modelo garante que nunca divirjam — na ordem das funções, no agrupamento
dos nomes ou na marcação de Ceia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .modelos import CULTO_DOMINGO, CULTO_EVENTO, CULTO_ORACAO, Atribuicao
from .textos import normalizar


@dataclass(frozen=True)
class ColunaCulto:
    """Um culto da escala, identificado pela data e pelo rótulo da coluna `Culto`."""

    data: date
    rotulo: str
    tipo: str  # CULTO_DOMINGO | CULTO_ORACAO | CULTO_EVENTO | "" (não reconhecido)
    e_ceia: bool = False
    nome_evento: str = ""


def _tipo_do_culto(data: date, rotulo: str) -> tuple[str, str]:
    """Reconhece o tipo do culto pelo rótulo gravado na planilha."""
    chave = normalizar(rotulo)
    if chave.startswith("evento"):
        nome = rotulo.split(":", 1)[1].strip() if ":" in rotulo else ""
        return CULTO_EVENTO, nome or "Evento"
    if "oracao" in chave:
        return CULTO_ORACAO, ""
    if chave.startswith("domingo") or data.weekday() == 6:
        return CULTO_DOMINGO, ""
    return "", ""


@dataclass
class Grade:
    colunas: list[ColunaCulto] = field(default_factory=list)
    funcoes: list[str] = field(default_factory=list)  # linhas, na ordem de exibição
    _celulas: dict[tuple[str, int], list[str]] = field(default_factory=dict)
    _por_coluna: dict[int, list[str]] = field(default_factory=dict)

    @property
    def vazia(self) -> bool:
        return not self.colunas

    def nomes(self, funcao: str, coluna: int) -> list[str]:
        """Quem está escalado nesta função neste culto (lista vazia se ninguém)."""
        return list(self._celulas.get((normalizar(funcao), coluna), []))

    def funcoes_da_coluna(self, coluna: int) -> list[str]:
        """Só as funções que têm alguém escalado neste culto, em ordem."""
        return list(self._por_coluna.get(coluna, []))


def montar_grade(
    atribuicoes: list[Atribuicao],
    ordem_funcoes: list[str] | None = None,
    datas_ceia: list[date] | None = None,
) -> Grade:
    """Agrupa as atribuições por culto e por função.

    As funções seguem a ordem da aba `Funções`; as que não estão no catálogo
    (extras de evento) vão para o fim, em ordem de aparição. Um culto é de Ceia
    quando a data está em `datas_ceia` ou quando alguém foi escalado numa função
    da Ceia — assim uma escala editada à mão continua marcada corretamente.
    """
    ordem_funcoes = ordem_funcoes or []
    ceias = set(datas_ceia or [])

    posicao_no_catalogo: dict[str, int] = {}
    for indice, funcao in enumerate(ordem_funcoes):
        posicao_no_catalogo.setdefault(normalizar(funcao), indice)

    grupos: dict[tuple[date, str], dict[str, list[str]]] = {}
    aparicao_no_culto: dict[tuple[date, str], list[str]] = {}
    aparicao_no_mes: list[str] = []
    grafia: dict[str, str] = {}  # chave normalizada -> como exibir

    for registro in atribuicoes:
        if not registro.data or not registro.nome:
            continue
        chave_culto = (registro.data, registro.culto or "")
        chave_funcao = normalizar(registro.funcao)
        grafia.setdefault(chave_funcao, registro.funcao)
        if chave_funcao not in aparicao_no_mes:
            aparicao_no_mes.append(chave_funcao)

        funcoes = grupos.setdefault(chave_culto, {})
        if chave_funcao not in funcoes:
            funcoes[chave_funcao] = []
            aparicao_no_culto.setdefault(chave_culto, []).append(chave_funcao)

        nomes = funcoes[chave_funcao]
        if all(normalizar(n) != registro.chave_nome for n in nomes):
            nomes.append(registro.nome)

    def em_ordem(chaves: list[str]) -> list[str]:
        def posicao(chave: str) -> tuple[int, int]:
            return (posicao_no_catalogo.get(chave, len(ordem_funcoes)), chaves.index(chave))

        return [grafia[chave] for chave in sorted(chaves, key=posicao)]

    grade = Grade(funcoes=em_ordem(aparicao_no_mes))
    for indice, chave_culto in enumerate(sorted(grupos)):
        data, rotulo = chave_culto
        funcoes = grupos[chave_culto]
        tipo, nome_evento = _tipo_do_culto(data, rotulo)
        grade.colunas.append(
            ColunaCulto(
                data=data,
                rotulo=rotulo,
                tipo=tipo,
                e_ceia=data in ceias or any("ceia" in chave for chave in funcoes),
                nome_evento=nome_evento,
            )
        )
        grade._por_coluna[indice] = em_ordem(aparicao_no_culto[chave_culto])
        for chave_funcao, nomes in funcoes.items():
            grade._celulas[(chave_funcao, indice)] = nomes
    return grade
