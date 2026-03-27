# Lotofácil Pro — Engenharia de Dados & IA

Aplicação web construída com **Streamlit** para geração e análise estatística de jogos da Lotofácil. Combina múltiplas estratégias com filtros de validação e pontuação por aderência ao histórico de resultados.

---

## Requisitos

- Python 3.9+
- Bibliotecas:

```bash
pip install streamlit pandas openpyxl
```

---

## Como executar

```bash
python -m venv venv
venv\Scripts\activate
pip install streamlit pandas openpyxl

streamlit run app_loto.py
```

---

## Arquivo de histórico

O sistema espera um arquivo `.xlsx` exportado do site da Caixa Econômica Federal com o seguinte cabeçalho:

```
Concurso | Data Sorteio | Bola1 | Bola2 | ... | Bola15 | Ganhadores 15 acertos | ...
```

Apenas as colunas `Bola1` até `Bola15` são utilizadas. O arquivo deve ter os concursos em **ordem cronológica crescente** (mais antigo no topo, mais recente no final).

> Download do histórico: [Resultados Lotofácil — Caixa](https://loterias.caixa.gov.br/Paginas/Download-Resultados.aspx)

---

## Filtros de validação

Todo jogo gerado passa obrigatoriamente por 3 filtros antes de ser aceito:

| Filtro | Regra |
|---|---|
| **Soma** | Soma das 15 dezenas entre 180 e 220 |
| **Sequência** | Nenhuma sequência consecutiva com mais de 4 números |
| **Ineditismo** | Jogo não pode ter 14 ou 15 dezenas em comum com nenhum concurso do histórico |

Se após 1.000 tentativas nenhum jogo passar nos filtros, um jogo aleatório é retornado como fallback.

---

## Modos de uso

### 1. Configurar Estratégia
Gera N jogos (1–50) com uma estratégia escolhida manualmente.

| Estratégia | Lógica |
|---|---|
| **Inversão Suprema** | Usa todas as 10 dezenas ausentes no último resultado + 5 do último resultado |
| **Cercamento 7/8** | 7 dezenas ausentes no último resultado + 8 do último resultado |
| **Fixas de Ouro** | Dezenas fixas escolhidas pelo usuário (até 14) + complemento aleatório |
| **Equilíbrio IA 2026** | 8 ímpares + 7 pares (ou 7+8), distribuição equilibrada |
| **Ranking Frequência** | Top 10 dezenas mais frequentes no histórico completo + 5 aleatórias |
| **Fechamento de Dezenas** | Todos os jogos saem exclusivamente de um pool definido pelo usuário (mín. 15 dezenas) |

**Estratégias com configuração adicional:**

- **Fixas de Ouro** → multiselect para escolher as dezenas fixas (máx. 14)
- **Fechamento de Dezenas** → multiselect para definir o pool (mín. 15); exibe o número de combinações possíveis `C(n,15)`

---

### 2. Painel Completo (Auto)
Gera **1 jogo por estratégia** (6 jogos no total) em um único clique.

Para as estratégias que exigem parâmetros, o sistema os calcula automaticamente com base nos **últimos 10 concursos**:

- **Fixas de Ouro auto** → dezenas que apareceram em ≥ 60% dos últimos 10 concursos (máx. 10 fixas)
- **Fechamento de Dezenas auto** → união de todas as dezenas únicas dos últimos 10 concursos

---

### 3. Jogo Rápido
Roda todas as 6 estratégias internamente, pontua cada jogo gerado e apresenta os **2 melhores**.

**Sistema de pontuação (`pontuar_jogo`):**

```
pontuação = Σ frequência(dezena) + (acertos_médios × 50)
```

- **Frequência**: soma de quantas vezes cada dezena do jogo apareceu no histórico selecionado
- **Acertos médios**: média de acertos do jogo contra cada concurso do histórico (multiplicada por 50 para normalizar o peso)

**Escopo do histórico para pontuação:**
- `Completo` — usa todos os concursos carregados
- `Parcial (últimos N)` — usa apenas os últimos N concursos (slider configurável)

Também exibe um **ranking completo** das 6 estratégias com pontuação e dezenas, disponível em expander.

---

## Exportação

Cada modo oferece download em CSV:

| Arquivo | Conteúdo |
|---|---|
| `jogos_lotofacil.csv` | Jogos gerados pela estratégia selecionada |
| `painel_completo.csv` | 1 jogo por estratégia (Painel Completo) |
| `jogo_rapido.csv` | Top 2 jogos (Jogo Rápido) |

---

## Estrutura do projeto

```
previsao/
├── app_loto.py   # Aplicação principal
└── README.md
```

---

## Aviso

Este software é uma ferramenta de **análise estatística**. Loterias são jogos de azar e não há garantia de lucro. Jogue com responsabilidade.
