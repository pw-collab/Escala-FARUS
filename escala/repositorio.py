"""Contrato de acesso aos dados e implementação em memória.

O app conversa apenas com a interface `Repositorio`. Isso permite três coisas:
rodar sem credenciais (modo demonstração), testar tudo sem rede e trocar a
origem dos dados no futuro sem mexer no motor.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .planilha import Aba, Planilha
from .textos import normalizar


@runtime_checkable
class Repositorio(Protocol):
    """Leitura e escrita das abas da planilha."""

    nome: str
    editavel: bool

    def carregar(self) -> Planilha:
        """Lê todas as abas de uma vez."""

    def salvar_aba(self, aba: Aba) -> None:
        """Substitui o conteúdo inteiro de uma aba existente."""

    def criar_aba(self, titulo: str, cabecalho: list[str], linhas: list[list[str]]) -> None:
        """Cria uma aba nova com cabeçalho e (opcionalmente) linhas de exemplo."""

    def url(self) -> str:
        """Endereço da planilha, quando existir."""


class RepositorioMemoria:
    """Guarda tudo em memória — usado no modo demonstração e nos testes."""

    editavel = True

    def __init__(self, planilha: Planilha, nome: str = "Modo demonstração"):
        self._planilha = planilha
        self.nome = nome

    def carregar(self) -> Planilha:
        copia = Planilha()
        for aba in self._planilha.abas.values():
            copia.definir(aba.copiar())
        return copia

    def salvar_aba(self, aba: Aba) -> None:
        alvo = normalizar(aba.titulo)
        for titulo, existente in list(self._planilha.abas.items()):
            if normalizar(existente.titulo) == alvo:
                self._planilha.abas[titulo] = aba.copiar()
                return
        self._planilha.definir(aba.copiar())

    def criar_aba(self, titulo: str, cabecalho: list[str], linhas: list[list[str]]) -> None:
        if self._planilha.obter(titulo) is not None:
            return
        self._planilha.definir(
            Aba(titulo=titulo, cabecalho=list(cabecalho), linhas=[list(l) for l in linhas])
        )

    def url(self) -> str:
        return ""
