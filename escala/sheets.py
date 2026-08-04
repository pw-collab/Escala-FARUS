"""Repositório real: Google Sheets via `gspread` + Service Account.

Toda a leitura acontece em uma única chamada (`batch_get`/`get_all_values` por
aba) e a escrita substitui a aba inteira em uma chamada. Isso mantém o uso
bem abaixo das cotas gratuitas da API do Sheets, mesmo com vários admins usando
o app ao mesmo tempo.
"""

from __future__ import annotations

from .planilha import Aba, Planilha
from .textos import normalizar

ESCOPOS = ("https://www.googleapis.com/auth/spreadsheets",)


class ErroPlanilha(RuntimeError):
    """Falha ao conectar ou operar na planilha, com mensagem amigável."""


def abrir_planilha(credenciais: dict, identificador: str):
    """Autentica com a Service Account e abre a planilha por id ou URL."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as erro:  # pragma: no cover - depende do ambiente
        raise ErroPlanilha(
            "Bibliotecas `gspread`/`google-auth` não instaladas. "
            "Rode: pip install -r requirements.txt"
        ) from erro

    if not credenciais:
        raise ErroPlanilha("Credenciais da Service Account não configuradas nos Secrets.")
    if not identificador:
        raise ErroPlanilha("Informe o id ou a URL da planilha nos Secrets.")

    try:
        conta = Credentials.from_service_account_info(dict(credenciais), scopes=list(ESCOPOS))
        cliente = gspread.authorize(conta)
    except Exception as erro:  # noqa: BLE001 - a mensagem original é útil ao admin
        raise ErroPlanilha(f"Não consegui autenticar no Google: {erro}") from erro

    try:
        if identificador.startswith("http"):
            return cliente.open_by_url(identificador)
        return cliente.open_by_key(identificador)
    except Exception as erro:  # noqa: BLE001
        raise ErroPlanilha(
            "Não consegui abrir a planilha. Confira o id/URL e se ela foi "
            "compartilhada (como Editor) com o e-mail da Service Account. "
            f"Detalhe: {erro}"
        ) from erro


class RepositorioSheets:
    """Implementação de `Repositorio` sobre uma planilha do Google."""

    editavel = True

    def __init__(self, planilha_google):
        self._planilha = planilha_google
        self.nome = getattr(planilha_google, "title", "Planilha")

    @classmethod
    def conectar(cls, credenciais: dict, identificador: str) -> "RepositorioSheets":
        return cls(abrir_planilha(credenciais, identificador))

    def carregar(self) -> Planilha:
        snapshot = Planilha()
        try:
            abas = self._planilha.worksheets()
        except Exception as erro:  # noqa: BLE001
            raise ErroPlanilha(f"Não consegui listar as abas da planilha: {erro}") from erro

        for aba in abas:
            try:
                valores = aba.get_all_values()
            except Exception as erro:  # noqa: BLE001
                raise ErroPlanilha(f"Falha ao ler a aba `{aba.title}`: {erro}") from erro
            cabecalho = list(valores[0]) if valores else []
            linhas = [list(l) for l in valores[1:]] if len(valores) > 1 else []
            snapshot.definir(Aba(titulo=aba.title, cabecalho=cabecalho, linhas=linhas))
        return snapshot

    def salvar_aba(self, aba: Aba) -> None:
        alvo = self._worksheet(aba.titulo)
        if alvo is None:
            self.criar_aba(aba.titulo, aba.cabecalho, aba.linhas)
            return
        matriz = aba.valores()
        try:
            # `clear` evita deixar linhas antigas quando a escala nova é menor.
            alvo.clear()
            if matriz:
                alvo.update(matriz, "A1", value_input_option="USER_ENTERED")
        except Exception as erro:  # noqa: BLE001
            raise ErroPlanilha(f"Falha ao gravar a aba `{aba.titulo}`: {erro}") from erro

    def criar_aba(self, titulo: str, cabecalho: list[str], linhas: list[list[str]]) -> None:
        matriz = [list(cabecalho)] + [list(l) for l in linhas]
        largura = max((len(l) for l in matriz), default=1) or 1
        matriz = [l + [""] * (largura - len(l)) for l in matriz]
        try:
            nova = self._planilha.add_worksheet(
                title=titulo, rows=max(len(matriz) + 50, 100), cols=max(largura, 6)
            )
            nova.update(matriz, "A1", value_input_option="USER_ENTERED")
        except Exception as erro:  # noqa: BLE001
            raise ErroPlanilha(f"Falha ao criar a aba `{titulo}`: {erro}") from erro

    def url(self) -> str:
        return getattr(self._planilha, "url", "")

    def _worksheet(self, titulo: str):
        alvo = normalizar(titulo)
        for aba in self._planilha.worksheets():
            if normalizar(aba.title) == alvo:
                return aba
        return None
