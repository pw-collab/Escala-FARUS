"""Aplicação das trocas registradas manualmente pelo admin.

Uma troca vale para a escala ainda não publicada (`Escala Gerada`) ou para o
que já foi publicado (`Histórico`). Aplicar a troca no lugar certo é o que
garante que o rodízio dos próximos meses use quem *de fato* serviu.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .modelos import TROCA_APLICADA, TROCA_NAO_ENCONTRADA, Atribuicao, Troca
from .textos import formatar_data, normalizar, vazio


@dataclass
class ResultadoTrocas:
    aplicadas: int = 0
    ignoradas: int = 0
    escala: list[Atribuicao] = field(default_factory=list)
    historico: list[Atribuicao] = field(default_factory=list)
    trocas: list[Troca] = field(default_factory=list)
    mensagens: list[str] = field(default_factory=list)

    @property
    def houve_mudanca(self) -> bool:
        return self.aplicadas > 0


def _descrever(troca: Troca) -> str:
    quando = formatar_data(troca.data) if troca.data else "sem data"
    return f"{quando} · {troca.funcao} · {troca.nome_original}"


def _localizar(
    registros: list[Atribuicao], troca: Troca
) -> int | None:
    """Índice da linha que casa com a troca (data + função + nome original)."""
    alvo_funcao = normalizar(troca.funcao)
    alvo_nome = normalizar(troca.nome_original)
    for indice, registro in enumerate(registros):
        if troca.data is not None and registro.data != troca.data:
            continue
        if alvo_funcao and registro.chave_funcao != alvo_funcao:
            continue
        if registro.chave_nome != alvo_nome:
            continue
        return indice
    return None


def aplicar_trocas(
    trocas: list[Troca],
    escala: list[Atribuicao],
    historico: list[Atribuicao],
) -> ResultadoTrocas:
    """Aplica todas as trocas pendentes e devolve as listas já atualizadas.

    A `Escala Gerada` tem prioridade: se a linha existe lá, a troca acontece no
    rascunho. Só quando a escala daquela data já foi publicada é que a troca
    incide sobre o `Histórico`.
    """
    nova_escala = list(escala)
    novo_historico = list(historico)
    novas_trocas: list[Troca] = []
    resultado = ResultadoTrocas()

    for troca in trocas:
        atual = Troca(
            data=troca.data,
            funcao=troca.funcao,
            nome_original=troca.nome_original,
            nome_substituto=troca.nome_substituto,
            motivo=troca.motivo,
            status=troca.status,
            bruto=troca.bruto,
        )

        # Já aplicada ou cancelada: preserva como está.
        if not troca.pendente:
            novas_trocas.append(atual)
            resultado.ignoradas += 1
            continue

        if vazio(troca.nome_substituto):
            atual.status = TROCA_NAO_ENCONTRADA
            resultado.mensagens.append(
                f"{_descrever(troca)}: sem nome substituto — nada foi alterado."
            )
            novas_trocas.append(atual)
            resultado.ignoradas += 1
            continue

        indice = _localizar(nova_escala, troca)
        if indice is not None:
            alvo = nova_escala[indice]
            nova_escala[indice] = Atribuicao(
                data=alvo.data,
                culto=alvo.culto,
                funcao=alvo.funcao,
                nome=troca.nome_substituto,
                bruto=alvo.bruto,
            )
            atual.status = TROCA_APLICADA
            resultado.aplicadas += 1
            resultado.mensagens.append(
                f"{_descrever(troca)} → {troca.nome_substituto} (na Escala Gerada)."
            )
            novas_trocas.append(atual)
            continue

        indice = _localizar(novo_historico, troca)
        if indice is not None:
            alvo = novo_historico[indice]
            novo_historico[indice] = Atribuicao(
                data=alvo.data,
                culto=alvo.culto,
                funcao=alvo.funcao,
                nome=troca.nome_substituto,
                bruto=alvo.bruto,
            )
            atual.status = TROCA_APLICADA
            resultado.aplicadas += 1
            resultado.mensagens.append(
                f"{_descrever(troca)} → {troca.nome_substituto} (no Histórico)."
            )
            novas_trocas.append(atual)
            continue

        atual.status = TROCA_NAO_ENCONTRADA
        resultado.ignoradas += 1
        resultado.mensagens.append(
            f"{_descrever(troca)}: não achei essa pessoa nessa função e data "
            "nem na Escala Gerada nem no Histórico."
        )
        novas_trocas.append(atual)

    resultado.escala = nova_escala
    resultado.historico = novo_historico
    resultado.trocas = novas_trocas
    return resultado
