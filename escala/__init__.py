"""Motor da ferramenta de escala de voluntários.

O pacote é dividido em camadas para que a lógica de negócio possa ser testada
sem depender do Google Sheets nem do Streamlit:

    textos.py      -> normalização e parsing tolerante (datas, sim/não, listas)
    modelos.py     -> estruturas de dados do domínio
    planilha.py    -> abstração de "aba" (cabeçalho + linhas) e leitura de colunas
    dados.py       -> converte abas em objetos de domínio e de volta
    calendario.py  -> descobre os cultos do mês a partir das configurações
    motor.py       -> algoritmo de montagem da escala (rodízio justo)
    trocas.py      -> aplicação das trocas registradas pelo admin
    whatsapp.py    -> geração do texto pronto para colar no grupo
    sheets.py      -> repositório real (gspread)
    demo.py        -> repositório em memória, usado sem credenciais
    servico.py     -> fachada usada pela interface Streamlit
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
