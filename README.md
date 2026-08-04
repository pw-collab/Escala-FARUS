# Escala de Voluntários

Ferramenta que monta automaticamente a escala mensal dos voluntários (cultos de
domingo, culto de oração e eventos pontuais), usando a planilha Google da equipe
como banco de dados e gerando um texto pronto para colar no grupo do WhatsApp.

**Princípio:** a ferramenta decide *quem* vai em cada função; o envio da mensagem
continua sendo humano (copiar e colar). Zero custo recorrente.

---

## Como funciona

```
Google Sheets (banco de dados)
        │  gspread + Service Account
        ▼
App em Python (Streamlit)  ──►  link fixo, acessível de qualquer lugar
        │
        └──►  texto formatado para colar no WhatsApp
```

A planilha continua sendo a fonte da verdade: nada muda na forma como os dados
dos voluntários são mantidos. O app lê, sugere a escala e grava de volta.

## Fluxo do mês

1. **Gerar escala do mês** → abre a tela de configuração: mês/ano, Ceia e escala
   manual do Louvor por domingo, domingos sem culto, datas do Geração Luz e do
   Fusion, culto de oração e eventos.
2. **Gerar escala** → revisar e ajustar o rascunho na tabela →
   **Salvar na planilha**.
3. **Texto para o WhatsApp** → copiar → colar no grupo.
4. **Confirmar publicação** → grava na aba `Histórico`, fechando o ciclo de
   rodízio do mês.
5. Trocas ao longo do mês: registrar em **Trocas** e clicar em **Aplicar
   trocas** — o app corrige o rascunho ou o histórico, conforme o caso.

A configuração é feita na tela, não na planilha. Ao gerar, o app grava os
valores de volta na aba `Configurações do Mês`, então planilha e tela nunca
divergem — e editar direto na planilha continua funcionando.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sem credenciais configuradas o app abre em **modo demonstração**, com uma
planilha de exemplo em memória (28 voluntários, 14 funções e dois meses de
histórico simulado). Dá para percorrer o fluxo inteiro sem risco — nada é
gravado em lugar nenhum.

Testes:

```bash
pip install pytest && pytest
```

---

## Configurar o Google Sheets (uma vez só)

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um projeto
   gratuito e habilite a **Google Sheets API**.
2. Crie uma **Service Account** e gere uma chave JSON.
3. Abra a planilha e compartilhe com o `client_email` da Service Account, com
   permissão de **Editor** (é como adicionar mais uma pessoa à planilha).
4. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e
   preencha com o conteúdo do JSON, o id da planilha e a senha da equipe.

O id da planilha é o trecho entre `/d/` e `/edit` na URL.

### Publicar no Streamlit Community Cloud (gratuito)

1. Suba este repositório para o GitHub (pode ser privado).
2. Em [share.streamlit.io](https://share.streamlit.io), conecte o repositório e
   aponte para `app.py`.
3. Em *Settings → Secrets*, cole o mesmo conteúdo do `secrets.toml`.
4. Compartilhe o link com a equipe.

> ⚠️ `.streamlit/secrets.toml` está no `.gitignore`. A chave da Service Account
> nunca deve ser versionada.

---

## Estrutura da planilha

Sete abas. Os nomes das colunas são reconhecidos mesmo com pequenas variações
(sem acento, abreviados, sinônimos), e **colunas extras que você criar são
preservadas** quando o app regrava a aba.

### `Voluntários`
| Nome | Telefone | Ativo | Funções que exerce | Observações |
|---|---|---|---|---|
| Ana Paula | (11) 9… | Sim | Recepção; Maná Coffee | |

`Funções que exerce` aceita separação por `;`, `,` ou quebra de linha. O valor
`Todas` habilita a pessoa para qualquer função.

### `Funções` — catálogo mestre
| Função | Culto (Domingo/Oração/Ambos) | Qtd. mín. | Qtd. máx. | É coringa? | É de data fixa no mês? |
|---|---|---|---|---|---|
| Intercessão | Ambos | 1 | 2 | Sim | Não |

A **ordem das linhas** define a ordem de preenchimento e a ordem em que as
funções aparecem no texto do WhatsApp. Nenhuma regra fica travada no código:
para criar, remover ou renomear uma função, basta editar esta aba.

### `Configurações do Mês`
| Campo | Exemplo | Observação |
|---|---|---|
| `Mês/Ano` | `Março/2026` ou `03/2026` | competência da escala |
| `Data da Ceia` | `1º domingo` ou `01/03; 15/03` | em branco = 1º domingo; `nenhuma` = sem Ceia |
| `Data do culto de oração` | `3ª quarta` ou `18/03` | aceita várias datas separadas por `;` |
| `Data do Geração Luz` | `2º domingo` | uma linha `Data do …` para cada função de data fixa |
| `Data do Fusion` | `3º domingo` | |
| `Datas sem culto` | `29/03` | pula essas datas |
| `Funções cobertas por coringa` | `Abertura; Oferta` | **não fica na tela** — padrão se a linha não existir |
| `Preencher até a quantidade máxima` | `Sim` | **não fica na tela** — `Não` preenche só o mínimo |
| `Evento` | `27/03 \| Vigília \| Oração \| Recepção; Maná Coffee` | uma linha por evento |
| `Escalação manual` | `01/03 \| Louvor \| Ana; Bruno` | `data \| função \| nomes` |

Formato do evento: `data | nome | base | cargos`. A `base` (`Domingo`,
`Oração` ou `Nenhum`) define de qual culto o evento herda as funções; os cargos
são somados a elas.

As duas últimas linhas são escritas pela tela de geração — a de eventos pela
tabela editável, a de escalação manual pelo campo de Louvor de cada domingo.

Datas aceitam `01/03/2026`, `01/03`, só o dia (`1`) e expressões como
`1º domingo`, `última quarta`, `3ª sexta`.

### `Indisponibilidades`
| Nome | Data início | Data fim | Motivo |
|---|---|---|---|

Intervalo inclusivo. `Data fim` em branco = apenas um dia.

### `Histórico`
| Data | Culto | Função | Nome |
|---|---|---|---|

Preenchida pelo app ao publicar e corrigida quando trocas são aplicadas. É a
memória que alimenta o rodízio dos meses seguintes.

### `Escala Gerada`
Mesmas colunas do `Histórico`. É o rascunho do mês — o admin pode editar
qualquer linha, no app ou direto na planilha, antes de publicar.

### `Trocas`
| Data do culto | Função | Nome original | Nome substituto | Motivo | Status |
|---|---|---|---|---|---|

O `Status` é gerenciado pelo app: `Pendente` → `Aplicada`, ou `Não encontrada`
quando a linha indicada não existe (aí é só corrigir e aplicar de novo).

---

## Como o rodízio é calculado

Para cada culto do mês, **em ordem cronológica**, e para cada função na ordem da
aba `Funções`:

1. **Filtra** quem está ativo, apto à função, sem indisponibilidade naquela data
   e ainda não escalado naquele culto.
2. **Ordena** por quem está há mais tempo sem servir *naquela função*. Em caso de
   empate, desempata por: menos vezes na função → há mais tempo sem servir em
   qualquer função → menos escalas no total → embaralhamento determinístico.
3. **Preenche** a quantidade da função (`Qtd. mín.` a `Qtd. máx.`).
4. Se uma função coberta por coringa (`Abertura`/`Oferta`) ficar sem gente, usa
   alguém já escalado em função **coringa** naquele mesmo culto, priorizando quem
   ainda não acumulou função extra no dia.
5. Acrescenta `Servo da Ceia` nos domingos de Ceia e as funções de data fixa nas
   datas marcadas.

Quem foi **escalado à mão** na tela de geração (o campo de Louvor de cada
domingo) é reservado antes de tudo: não entra em outra função naquele culto, a
escolha vale mesmo acima da quantidade máxima, e as vagas restantes da função
são completadas pelo rodízio. Essas escalas contam normalmente no histórico.

**Não existe limite rígido de escalas por pessoa.** Em vez disso, cada escolha
realimenta o rodízio na hora — por isso a mesma pessoa não se repete em cultos
seguidos quando existe outra apta disponível.

O desempate é determinístico: gerar a escala duas vezes com os mesmos dados
produz exatamente o mesmo resultado. Sem ele, empates (como no primeiro mês de
uso, quando ninguém tem histórico) cairiam em ordem alfabética, e as mesmas
pessoas seriam sempre escolhidas.

Vagas que não puderam ser preenchidas viram **pendências**, listadas na tela com
o motivo (ninguém apto / todos indisponíveis / já escalados em outra função).
O sistema sugere — o admin decide.

---

## Estrutura do código

```
app.py                 interface Streamlit (autenticação, abas, formulários)
escala/
  textos.py            normalização e parsing tolerante (datas, sim/não, listas)
  modelos.py           estruturas do domínio
  planilha.py          abstração de aba e resolução de colunas
  dados.py             abas ↔ objetos de domínio; leitura das configurações
  calendario.py        cultos do mês e funções de cada culto
  motor.py             algoritmo de rodízio
  trocas.py            aplicação das trocas
  whatsapp.py          geração do texto
  repositorio.py       contrato de acesso + implementação em memória
  sheets.py            implementação sobre o Google Sheets
  demo.py              planilha de demonstração
  servico.py           fachada usada pela interface
tests/                 170 testes, sem rede e sem credenciais
```

A lógica de negócio não depende de Streamlit nem de rede: dá para testar tudo
localmente e trocar a origem dos dados no futuro sem mexer no motor.

---

## Fora do escopo desta versão

- Envio automático de mensagens pela API do WhatsApp (a Meta cobra por mensagem
  enviada pela empresa; só compensa com volume ou urgência que justifiquem).
- Autoatendimento de troca pelo voluntário.
- Coleta prévia formal de disponibilidade.
- Login individual por pessoa (esta versão usa senha compartilhada).

---

## Texto gerado

```
*Escala — Setembro/2026*

*Domingo, 06/09 (Ceia)*

* Intercessão: Antonio (@ ) — Maria (@ )
* Louvor: Pedro (@ ) — Ana (@ )
```

Cada função vira um item de lista; os nomes são separados por travessão. O
`(@ )` fica pronto para você tocar dentro do parêntese no WhatsApp e escolher a
pessoa — a menção é feita na hora do envio, sem precisar cadastrar telefone
nenhum. Dá para desligar as menções na aba **WhatsApp**.
