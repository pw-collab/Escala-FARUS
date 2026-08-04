"""Utilidades compartilhadas pelos testes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from escala.dados import CABECALHOS_PADRAO, carregar_base  # noqa: E402
from escala.planilha import Aba, Planilha  # noqa: E402


def aba(titulo: str, linhas: list[list[str]], cabecalho: list[str] | None = None) -> Aba:
    return Aba(titulo, list(cabecalho or CABECALHOS_PADRAO[titulo]), [list(l) for l in linhas])


def montar_planilha(**abas: Aba) -> Planilha:
    planilha = Planilha()
    for item in abas.values():
        planilha.definir(item)
    return planilha


def base_de(planilha: Planilha):
    return carregar_base(planilha)


@pytest.fixture
def demo():
    """Base de demonstração fixada em Março/2026 (mês com 5 domingos)."""
    from escala.demo import planilha_demo

    return carregar_base(planilha_demo(3, 2026))
