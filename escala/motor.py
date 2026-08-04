"""Algoritmo de montagem automática da escala.

Ideia central: para cada culto do mês, em ordem cronológica, e para cada função
na ordem da aba `Funções`, escolhemos entre os voluntários aptos aquele que está
há mais tempo sem servir naquela função. Cada escolha realimenta imediatamente o
estado do rodízio, então a mesma pessoa não é repetida em cultos seguidos quando
existe outra apta disponível.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date

from .calendario import funcoes_do_culto, montar_cultos
from .dados import BaseDados
from .modelos import (
    Atribuicao,
    Culto,
    Funcao,
    Indisponibilidade,
    Pendencia,
    ResultadoGeracao,
    Voluntario,
)
from .textos import formatar_data, normalizar

# Data sentinela para "nunca serviu": ordena antes de qualquer data real.
NUNCA = date(1900, 1, 1)


# ---------------------------------------------------------------------------
# Estado do rodízio
# ---------------------------------------------------------------------------

@dataclass
class EstadoRodizio:
    """Memória de quem serviu o quê e quando.

    Alimentada pelo `Histórico` da planilha e atualizada a cada atribuição feita
    durante a geração — é isso que faz o algoritmo "aprender" dentro do próprio
    mês, sem precisar de um limite rígido de escalas por pessoa.
    """

    ultimo_na_funcao: dict[tuple[str, str], date] = field(default_factory=dict)
    ultimo_geral: dict[str, date] = field(default_factory=dict)
    contagem_na_funcao: dict[tuple[str, str], int] = field(default_factory=dict)
    contagem_geral: dict[str, int] = field(default_factory=dict)

    @classmethod
    def a_partir_do_historico(cls, historico: list[Atribuicao]) -> "EstadoRodizio":
        estado = cls()
        for registro in historico:
            if registro.data is None or not registro.nome:
                continue
            estado.registrar(registro.chave_nome, registro.chave_funcao, registro.data)
        return estado

    def registrar(self, nome: str, funcao: str, data: date) -> None:
        chave = (nome, funcao)
        if data > self.ultimo_na_funcao.get(chave, NUNCA):
            self.ultimo_na_funcao[chave] = data
        if data > self.ultimo_geral.get(nome, NUNCA):
            self.ultimo_geral[nome] = data
        self.contagem_na_funcao[chave] = self.contagem_na_funcao.get(chave, 0) + 1
        self.contagem_geral[nome] = self.contagem_geral.get(nome, 0) + 1

    def ultima_vez(self, nome: str, funcao: str) -> date:
        return self.ultimo_na_funcao.get((nome, funcao), NUNCA)

    def vezes(self, nome: str, funcao: str) -> int:
        return self.contagem_na_funcao.get((nome, funcao), 0)


def _desempate(semente: str, funcao: str, nome: str) -> int:
    """Desempate determinístico e estável.

    Sem isto, empates (por exemplo, no primeiro mês de uso, quando ninguém tem
    histórico) seriam resolvidos por ordem alfabética, e as mesmas pessoas
    seriam sempre escolhidas. O hash embaralha de forma reprodutível: gerar a
    escala duas vezes com os mesmos dados dá exatamente o mesmo resultado.
    """
    bruto = f"{semente}|{funcao}|{nome}".encode()
    return int.from_bytes(hashlib.sha256(bruto).digest()[:8], "big")


# ---------------------------------------------------------------------------
# Elegibilidade
# ---------------------------------------------------------------------------

def esta_indisponivel(
    voluntario: Voluntario, dia: date, indisponibilidades: list[Indisponibilidade]
) -> bool:
    return any(
        i.chave == voluntario.chave and i.cobre(dia) for i in indisponibilidades
    )


def candidatos_para(
    funcao: Funcao,
    culto: Culto,
    voluntarios: list[Voluntario],
    indisponibilidades: list[Indisponibilidade],
    ja_escalados: set[str],
) -> list[Voluntario]:
    """Passo 1 do algoritmo: quem pode assumir esta função neste culto."""
    return [
        v
        for v in voluntarios
        if v.ativo
        and v.exerce(funcao.nome)
        and v.chave not in ja_escalados
        and not esta_indisponivel(v, culto.data, indisponibilidades)
    ]


def ordenar_por_rodizio(
    candidatos: list[Voluntario],
    funcao_chave: str,
    estado: EstadoRodizio,
    semente: str,
) -> list[Voluntario]:
    """Passo 2: quem está há mais tempo sem servir nesta função vem primeiro.

    Critérios, em ordem:
      1. data da última vez nesta função (mais antiga primeiro);
      2. quantas vezes já fez esta função (menos vezes primeiro);
      3. data da última vez em qualquer função (espalha a carga geral);
      4. total de escalas em qualquer função;
      5. desempate determinístico por hash.
    """

    def chave(v: Voluntario):
        return (
            estado.ultima_vez(v.chave, funcao_chave),
            estado.vezes(v.chave, funcao_chave),
            estado.ultimo_geral.get(v.chave, NUNCA),
            estado.contagem_geral.get(v.chave, 0),
            _desempate(semente, funcao_chave, v.chave),
        )

    return sorted(candidatos, key=chave)


# ---------------------------------------------------------------------------
# Geração
# ---------------------------------------------------------------------------

def gerar_escala(
    base: BaseDados,
    mes: int | None = None,
    ano: int | None = None,
) -> ResultadoGeracao:
    """Monta a escala completa do mês e devolve atribuições + pendências."""
    mes = mes or base.config.mes
    ano = ano or base.config.ano
    resultado = ResultadoGeracao()

    if not mes or not ano:
        resultado.avisos.append(
            "Mês/ano não definido. Preencha `Mês/Ano` em `Configurações do Mês` "
            "ou escolha o mês na tela de geração."
        )
        return resultado

    cultos = montar_cultos(base.config, mes, ano)
    resultado.cultos = cultos
    if not cultos:
        resultado.avisos.append("Nenhum culto encontrado para o mês informado.")
        return resultado

    if not base.voluntarios_ativos:
        resultado.avisos.append("Nenhum voluntário ativo cadastrado.")
        return resultado

    # Escalação manual sobrando de uma data que deixou de ter culto.
    datas_com_culto = {c.data for c in cultos}
    for manual in base.config.manuais:
        if manual.nomes and manual.data not in datas_com_culto:
            resultado.avisos.append(
                f"{formatar_data(manual.data)}: escalação manual de "
                f"`{manual.funcao}` ignorada — não há culto nessa data."
            )

    # O rodízio parte do histórico já publicado, ignorando registros do próprio
    # mês que está sendo gerado (evita contar duas vezes ao regerar).
    historico_anterior = [
        h
        for h in base.historico
        if h.data is not None and not (h.data.year == ano and h.data.month == mes)
    ]
    estado = EstadoRodizio.a_partir_do_historico(historico_anterior)
    semente = f"{ano:04d}-{mes:02d}"

    for culto in cultos:
        resultado.atribuicoes.extend(
            _gerar_culto(
                culto, base, estado, semente, resultado.pendencias, resultado.avisos
            )
        )

    if not resultado.atribuicoes:
        resultado.avisos.append(
            "Nenhuma vaga pôde ser preenchida. Verifique se os voluntários têm "
            "as funções cadastradas na coluna `Funções que exerce`."
        )
    return resultado


def _fixos_do_culto(
    culto: Culto, funcoes: list[Funcao], base: BaseDados, avisos: list[str]
) -> dict[str, list[Voluntario]]:
    """Resolve as escalações manuais daquele dia em voluntários de verdade."""
    disponiveis = {f.chave for f in funcoes}
    fixos: dict[str, list[Voluntario]] = {}

    for chave_funcao, nomes in base.config.manuais_de(culto.data).items():
        if chave_funcao not in disponiveis:
            avisos.append(
                f"{formatar_data(culto.data)}: escalação manual ignorada — a função "
                "indicada não faz parte desse culto."
            )
            continue
        for nome in nomes:
            voluntario = base.voluntario_por_nome(nome)
            if voluntario is None:
                avisos.append(
                    f"{formatar_data(culto.data)}: `{nome}` foi escalado à mão mas não "
                    "está na aba `Voluntários`."
                )
                continue
            if esta_indisponivel(voluntario, culto.data, base.indisponibilidades):
                avisos.append(
                    f"{formatar_data(culto.data)}: {voluntario.nome} foi escalado à mão "
                    "mesmo constando como indisponível nessa data."
                )
            ja = fixos.setdefault(chave_funcao, [])
            if voluntario.chave not in {v.chave for v in ja}:
                ja.append(voluntario)
    return fixos


def _gerar_culto(
    culto: Culto,
    base: BaseDados,
    estado: EstadoRodizio,
    semente: str,
    pendencias: list[Pendencia],
    avisos: list[str],
) -> list[Atribuicao]:
    """Preenche um culto: primeiro as funções normais, depois a cobertura coringa."""
    funcoes = funcoes_do_culto(culto, base.funcoes, base.config)
    extras_hoje: dict[str, int] = {}  # quantas funções adicionais cada um acumulou
    coringas_do_culto: list[Voluntario] = []
    atribuicoes: list[Atribuicao] = []
    vagas_abertas: list[tuple[Funcao, int]] = []

    # Quem foi escalado à mão é reservado antes de tudo, para que a distribuição
    # automática de uma função anterior não "roube" essa pessoa.
    fixos = _fixos_do_culto(culto, funcoes, base, avisos)
    escalados: set[str] = {v.chave for lista in fixos.values() for v in lista}

    for funcao in funcoes:
        desejado = funcao.qtd_max if base.config.preencher_maximo else funcao.qtd_min
        desejado = max(desejado, funcao.qtd_min)
        if desejado <= 0:
            continue

        # As escolhas manuais valem como estão, mesmo acima da quantidade máxima.
        pre_escalados = fixos.get(funcao.chave, [])
        vagas_restantes = max(desejado - len(pre_escalados), 0)

        candidatos = candidatos_para(
            funcao, culto, base.voluntarios, base.indisponibilidades, escalados
        )
        automaticos = ordenar_por_rodizio(candidatos, funcao.chave, estado, semente)[
            :vagas_restantes
        ]
        escolhidos = pre_escalados + automaticos

        for voluntario in escolhidos:
            atribuicoes.append(
                Atribuicao(
                    data=culto.data,
                    culto=culto.rotulo,
                    funcao=funcao.nome,
                    nome=voluntario.nome,
                )
            )
            escalados.add(voluntario.chave)
            estado.registrar(voluntario.chave, funcao.chave, culto.data)
            if funcao.coringa:
                coringas_do_culto.append(voluntario)

        faltam = funcao.qtd_min - len(escolhidos)
        if faltam > 0:
            vagas_abertas.append((funcao, faltam))

    # Passo 4: Abertura/Oferta (ou o que estiver configurado) podem ser cobertas
    # por quem já está escalado em função coringa neste mesmo culto.
    for funcao, faltam in vagas_abertas:
        cobertos = 0
        if base.config.aceita_coringa(funcao.nome) and coringas_do_culto:
            cobertos = _cobrir_com_coringa(
                funcao,
                culto,
                faltam,
                coringas_do_culto,
                extras_hoje,
                estado,
                semente,
                atribuicoes,
                base,
            )
        restante = faltam - cobertos
        if restante > 0:
            pendencias.append(
                Pendencia(
                    data=culto.data,
                    culto=culto.rotulo,
                    funcao=funcao.nome,
                    faltam=restante,
                    motivo=_motivo_pendencia(funcao, culto, base),
                )
            )
    return atribuicoes


def _cobrir_com_coringa(
    funcao: Funcao,
    culto: Culto,
    faltam: int,
    coringas: list[Voluntario],
    extras_hoje: dict[str, int],
    estado: EstadoRodizio,
    semente: str,
    atribuicoes: list[Atribuicao],
    base: BaseDados,
) -> int:
    """Escolhe, entre os coringas do culto, quem acumula a função descoberta.

    Prioriza quem ainda não pegou função extra hoje e, em seguida, quem é apto
    à função — depois disso vale o mesmo critério de rodízio das demais funções.
    """
    disponiveis = [
        v
        for v in coringas
        if not esta_indisponivel(v, culto.data, base.indisponibilidades)
    ]
    if not disponiveis:
        return 0

    def chave(v: Voluntario):
        return (
            extras_hoje.get(v.chave, 0),
            0 if v.exerce(funcao.nome) else 1,
            estado.ultima_vez(v.chave, funcao.chave),
            estado.vezes(v.chave, funcao.chave),
            _desempate(semente, funcao.chave, v.chave),
        )

    escolhidos = sorted(disponiveis, key=chave)[:faltam]
    for voluntario in escolhidos:
        atribuicoes.append(
            Atribuicao(
                data=culto.data,
                culto=culto.rotulo,
                funcao=funcao.nome,
                nome=voluntario.nome,
                via_coringa=True,
            )
        )
        extras_hoje[voluntario.chave] = extras_hoje.get(voluntario.chave, 0) + 1
        estado.registrar(voluntario.chave, funcao.chave, culto.data)
    return len(escolhidos)


def _motivo_pendencia(funcao: Funcao, culto: Culto, base: BaseDados) -> str:
    """Explica, em uma linha, por que a vaga ficou aberta."""
    aptos = [v for v in base.voluntarios_ativos if v.exerce(funcao.nome)]
    if not aptos:
        return "nenhum voluntário ativo está cadastrado nesta função"

    livres = [
        v for v in aptos if not esta_indisponivel(v, culto.data, base.indisponibilidades)
    ]
    if not livres:
        return "todos os aptos estão indisponíveis nesta data"
    return "os aptos já foram escalados em outra função neste culto"


# ---------------------------------------------------------------------------
# Resumos para a interface
# ---------------------------------------------------------------------------

def resumo_por_voluntario(atribuicoes: list[Atribuicao]) -> dict[str, int]:
    """Quantas vezes cada pessoa aparece na escala — para conferir sobrecarga."""
    contagem: dict[str, int] = {}
    for registro in atribuicoes:
        if registro.nome:
            contagem[registro.nome] = contagem.get(registro.nome, 0) + 1
    return dict(sorted(contagem.items(), key=lambda item: (-item[1], item[0])))


def voluntarios_nao_escalados(
    base: BaseDados, atribuicoes: list[Atribuicao]
) -> list[str]:
    """Quem ficou de fora do mês — o outro lado do "ninguém esquecido"."""
    escalados = {normalizar(a.nome) for a in atribuicoes}
    return sorted(v.nome for v in base.voluntarios_ativos if v.chave not in escalados)


def descrever_pendencia(pendencia: Pendencia) -> str:
    plural = "vaga" if pendencia.faltam == 1 else "vagas"
    return (
        f"{formatar_data(pendencia.data)} · {pendencia.culto} · {pendencia.funcao}: "
        f"{pendencia.faltam} {plural} em aberto ({pendencia.motivo})."
    )
