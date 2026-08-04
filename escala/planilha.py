"""Abstração de "aba de planilha": cabeçalho + linhas de texto.

Esta camada não sabe nada sobre voluntários ou escala. Ela só resolve duas
coisas chatas e recorrentes:

1. Encontrar a coluna certa mesmo quando o cabeçalho foi digitado de um jeito
   um pouco diferente do previsto ("Qtd. mín." vs "Qtd min" vs "Mínimo").
2. Reescrever linhas preservando as colunas que o sistema não conhece — se o
   admin criou uma coluna extra de anotações, ela não é apagada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .textos import limpar, normalizar


@dataclass
class Aba:
    """Cópia em memória de uma aba: primeira linha é cabeçalho, o resto é dado."""

    titulo: str
    cabecalho: list[str] = field(default_factory=list)
    linhas: list[list[str]] = field(default_factory=list)

    def valores(self) -> list[list[str]]:
        """Matriz completa (cabeçalho + linhas), pronta para gravar."""
        largura = max([len(self.cabecalho), *(len(linha) for linha in self.linhas)])
        matriz = [_ajustar(self.cabecalho, largura)]
        matriz.extend(_ajustar(linha, largura) for linha in self.linhas)
        return matriz

    def copiar(self) -> "Aba":
        return Aba(
            titulo=self.titulo,
            cabecalho=list(self.cabecalho),
            linhas=[list(l) for l in self.linhas],
        )

    def linhas_uteis(self) -> list[list[str]]:
        """Descarta linhas totalmente em branco (comuns no fim da planilha)."""
        return [linha for linha in self.linhas if any(limpar(c) for c in linha)]


def _ajustar(linha: list[str], largura: int) -> list[str]:
    faltam = largura - len(linha)
    return list(linha) + [""] * faltam if faltam > 0 else list(linha[:largura])


class MapaColunas:
    """Resolve nomes de campo do sistema para índices de coluna da aba.

    A resolução acontece em três passadas — igualdade exata, depois "começa
    com", depois "contém" — sempre respeitando as colunas já reservadas. Isso
    evita que um apelido genérico ("Data") roube a coluna de um campo que tem
    correspondência exata ("Data início").
    """

    def __init__(self, cabecalho: list[str], campos: dict[str, tuple[str, ...]]):
        self.cabecalho = cabecalho
        self.campos = campos
        self.indices = self._resolver(cabecalho, campos)

    @staticmethod
    def _resolver(
        cabecalho: list[str], campos: dict[str, tuple[str, ...]]
    ) -> dict[str, int]:
        colunas = [normalizar(c) for c in cabecalho]
        usadas: set[int] = set()
        indices: dict[str, int] = {}

        def tentar(teste) -> None:
            for campo, apelidos in campos.items():
                if campo in indices:
                    continue
                for apelido in apelidos:
                    alvo = normalizar(apelido)
                    if not alvo:
                        continue
                    for i, coluna in enumerate(colunas):
                        if i in usadas or not coluna:
                            continue
                        if teste(coluna, alvo):
                            indices[campo] = i
                            usadas.add(i)
                            break
                    if campo in indices:
                        break

        tentar(lambda coluna, alvo: coluna == alvo)
        tentar(lambda coluna, alvo: coluna.startswith(alvo))
        tentar(lambda coluna, alvo: alvo in coluna)
        return indices

    def tem(self, campo: str) -> bool:
        return campo in self.indices

    def faltando(self, obrigatorios: tuple[str, ...]) -> list[str]:
        return [campo for campo in obrigatorios if campo not in self.indices]

    def ler(self, linha: list[str], campo: str, padrao: str = "") -> str:
        indice = self.indices.get(campo)
        if indice is None or indice >= len(linha):
            return padrao
        return limpar(linha[indice])

    def escrever(self, linha: list[str], campo: str, valor: str) -> list[str]:
        """Grava o valor na coluna do campo, preservando as demais colunas."""
        indice = self.indices.get(campo)
        if indice is None:
            return linha
        largura = max(len(linha), len(self.cabecalho), indice + 1)
        nova = _ajustar(linha, largura)
        nova[indice] = valor
        return nova

    def nova_linha(self) -> list[str]:
        largura = max(len(self.cabecalho), (max(self.indices.values()) + 1) if self.indices else 0)
        return [""] * largura

    def montar(self, valores: dict[str, str], base: list[str] | None = None) -> list[str]:
        """Monta uma linha a partir de {campo: valor}, sobre `base` se houver."""
        linha = list(base) if base else self.nova_linha()
        for campo, valor in valores.items():
            linha = self.escrever(linha, campo, valor)
        return linha


@dataclass
class Planilha:
    """Snapshot de todas as abas lidas de uma vez."""

    abas: dict[str, Aba] = field(default_factory=dict)

    def obter(self, titulo: str) -> Aba | None:
        """Busca a aba pelo título, tolerando acento/caixa diferentes."""
        alvo = normalizar(titulo)
        for aba in self.abas.values():
            if normalizar(aba.titulo) == alvo:
                return aba
        return None

    def definir(self, aba: Aba) -> None:
        self.abas[aba.titulo] = aba

    def titulos(self) -> list[str]:
        return list(self.abas.keys())
