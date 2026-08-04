"""Estruturas de dados do domínio.

Nada aqui conhece Google Sheets ou Streamlit: são objetos puros, o que permite
testar todo o algoritmo de rodízio sem rede e sem credenciais.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .textos import normalizar

# Tipos de culto reconhecidos na coluna "Culto" da aba `Funções`.
CULTO_DOMINGO = "Domingo"
CULTO_ORACAO = "Oração"
CULTO_AMBOS = "Ambos"
CULTO_EVENTO = "Evento"

# Função criada automaticamente nos domingos de Ceia.
FUNCAO_CEIA = "Servo da Ceia"

# Funções que, por padrão, podem ser cobertas por quem já está em função coringa.
ALVOS_CORINGA_PADRAO = ("Abertura", "Oferta")

# Marca usada quando o voluntário pode exercer qualquer função.
CURINGA_TODAS = {"todas", "todos", "qualquer", "*", "tudo"}


@dataclass
class Voluntario:
    nome: str
    telefone: str = ""
    ativo: bool = True
    funcoes: list[str] = field(default_factory=list)
    observacoes: str = ""
    bruto: list[str] | None = None

    @property
    def chave(self) -> str:
        return normalizar(self.nome)

    def exerce(self, funcao: str) -> bool:
        """O voluntário está apto para esta função?"""
        alvo = normalizar(funcao)
        for registrada in self.funcoes:
            atual = normalizar(registrada)
            if atual == alvo or atual in CURINGA_TODAS:
                return True
        return False


@dataclass
class Funcao:
    nome: str
    culto: str = CULTO_DOMINGO
    qtd_min: int = 1
    qtd_max: int = 1
    coringa: bool = False
    data_fixa: bool = False
    ordem: int = 0
    bruto: list[str] | None = None

    @property
    def chave(self) -> str:
        return normalizar(self.nome)

    def vale_para(self, tipo_culto: str) -> bool:
        """A função pertence ao culto de domingo, ao de oração ou a ambos?"""
        alvo = normalizar(self.culto)
        if not alvo or alvo == normalizar(CULTO_AMBOS):
            return True
        return alvo == normalizar(tipo_culto)


@dataclass
class Indisponibilidade:
    nome: str
    inicio: date | None
    fim: date | None
    motivo: str = ""
    bruto: list[str] | None = None

    @property
    def chave(self) -> str:
        return normalizar(self.nome)

    def cobre(self, dia: date) -> bool:
        """A indisponibilidade abrange o dia informado (intervalo inclusivo)?"""
        inicio = self.inicio or self.fim
        fim = self.fim or self.inicio
        if inicio is None or fim is None:
            return False
        if fim < inicio:
            inicio, fim = fim, inicio
        return inicio <= dia <= fim


@dataclass
class Atribuicao:
    """Uma linha das abas `Escala Gerada` / `Histórico`."""

    data: date | None
    culto: str
    funcao: str
    nome: str
    via_coringa: bool = False  # só existe em memória, não vai para a planilha
    bruto: list[str] | None = None

    @property
    def chave_funcao(self) -> str:
        return normalizar(self.funcao)

    @property
    def chave_nome(self) -> str:
        return normalizar(self.nome)


# Status possíveis da aba `Trocas`.
TROCA_PENDENTE = "Pendente"
TROCA_APLICADA = "Aplicada"
TROCA_CANCELADA = "Cancelada"
TROCA_NAO_ENCONTRADA = "Não encontrada"


@dataclass
class Troca:
    data: date | None
    funcao: str
    nome_original: str
    nome_substituto: str
    motivo: str = ""
    status: str = TROCA_PENDENTE
    bruto: list[str] | None = None

    @property
    def pendente(self) -> bool:
        atual = normalizar(self.status)
        return atual in {"", normalizar(TROCA_PENDENTE), normalizar(TROCA_NAO_ENCONTRADA)}


@dataclass
class Evento:
    """Evento pontual cadastrado na aba `Configurações do Mês`."""

    data: date
    nome: str
    base: str = CULTO_DOMINGO  # "Domingo", "Oração" ou "" (só funções próprias)
    funcoes_extras: list[str] = field(default_factory=list)


@dataclass
class Culto:
    """Uma ocorrência concreta no calendário do mês."""

    data: date
    tipo: str  # CULTO_DOMINGO | CULTO_ORACAO | CULTO_EVENTO
    rotulo: str  # o que vai para a coluna "Culto" da planilha
    base: str = ""  # de qual catálogo herda as funções
    ceia: bool = False
    nome_evento: str = ""
    funcoes_extras: list[str] = field(default_factory=list)

    @property
    def ordenacao(self) -> tuple[date, int]:
        prioridade = {CULTO_DOMINGO: 0, CULTO_ORACAO: 1, CULTO_EVENTO: 2}
        return (self.data, prioridade.get(self.tipo, 3))


@dataclass
class Pendencia:
    """Vaga que o algoritmo não conseguiu preencher."""

    data: date
    culto: str
    funcao: str
    faltam: int
    motivo: str = ""


@dataclass
class ResultadoGeracao:
    atribuicoes: list[Atribuicao] = field(default_factory=list)
    pendencias: list[Pendencia] = field(default_factory=list)
    cultos: list[Culto] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def total_vagas_preenchidas(self) -> int:
        return len(self.atribuicoes)
