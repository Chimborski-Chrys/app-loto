# Loterias Pro — IA & Engenharia de Dados

Aplicação web construída com **Streamlit** que reúne geradores inteligentes para **Lotofácil** e **Mega Sena**. Combina múltiplas estratégias com filtros de validação automática e pontuação por aderência ao histórico de resultados.

---

## Requisitos

- Python 3.11+

```bash
pip install -r requirements.txt
```

---

## Executar localmente

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

streamlit run app.py
```

Acesse `http://localhost:8501`. O menu lateral exibe os dois módulos disponíveis.

---

## Estrutura do projeto

```
previsao/
├── app.py                  # Home — menu de navegação
├── app_loto.py             # Lógica completa Lotofácil
├── app_megasena.py         # Lógica completa Mega Sena
├── pages/
│   ├── 1_Lotofacil.py      # Wrapper de página (executa app_loto.py)
│   └── 2_Mega_Sena.py      # Wrapper de página (executa app_megasena.py)
├── .streamlit/
│   └── config.toml         # Configurações de servidor (headless, porta)
├── requirements.txt
├── Dockerfile
├── fly.toml
└── .dockerignore
```

---

## Módulo Lotofácil

### Arquivo de histórico

Arquivo `.xlsx` exportado do site da Caixa com o seguinte cabeçalho:

```
Concurso | Data Sorteio | Bola1 | Bola2 | ... | Bola15 | Ganhadores 15 acertos | ...
```

Apenas as colunas `Bola1` até `Bola15` são usadas. Concursos em **ordem cronológica crescente** (mais antigo no topo).

> Download: [Resultados Lotofácil — Caixa](https://loterias.caixa.gov.br/Paginas/Download-Resultados.aspx)

### Filtros de validação

| Filtro | Regra |
|---|---|
| Soma | Entre 180 e 220 |
| Sequência | Nenhuma sequência consecutiva com mais de 4 números |
| Ineditismo | Menos de 14 dezenas em comum com qualquer concurso histórico |

### Estratégias disponíveis

| Estratégia | Lógica |
|---|---|
| Inversão Suprema | 10 ausentes no último resultado + 5 presentes |
| Cercamento 7/8 | 7 ausentes + 8 presentes |
| Fixas de Ouro | Dezenas fixas (até 14) + complemento aleatório |
| Equilíbrio IA 2026 | 8 ímpares + 7 pares, dezenas frias dos últimos 3 concursos |
| Ranking Frequência | Top 10 mais frequentes no histórico + 5 aleatórias |
| Fechamento de Dezenas | Jogos exclusivamente dentro de um pool definido pelo usuário |
| Fechamento 17 Dezenas | Distribuição circular de 17 dezenas em 6 jogos |
| Matriz 13 Fixas | 13 dezenas fixas + pares das 12 restantes (6 jogos) |
| Rastreio Ciclo 3 | Dezenas frias (ausentes nos últimos 3 concursos) + quentes |

### Modos de uso

- **Gerar Jogos** — N jogos com a estratégia selecionada
- **Painel Completo** — 1 jogo por estratégia em um clique (parâmetros automáticos)
- **Jogo Rápido** — roda todas as estratégias e entrega os 2 com maior pontuação

---

## Módulo Mega Sena

### Arquivo de histórico

Arquivo `.xlsx` exportado do site da Caixa com o seguinte formato posicional:

```
A: Concurso | B: Data Sorteio | C–H: 6 dezenas | I: Ganhadores (0 = acumulada)
```

A coluna I é usada para detectar automaticamente se a Mega está acumulada.

> Download: [Resultados Mega Sena — Caixa](https://loterias.caixa.gov.br/Paginas/Download-Resultados.aspx)

### Filtros de validação

Todo jogo gerado passa por 7 filtros antes de ser aceito:

| Filtro | Regra |
|---|---|
| Soma | Proporcional à faixa 150–220 para 6 dezenas (escala para jogos maiores) |
| Paridade | Entre 25% e 70% de números pares |
| Sequência | No máximo 2 números consecutivos |
| Finais | Máximo 2 dezenas com o mesmo algarismo final |
| Quentes | Pelo menos 1 número do top-10 histórico |
| Ineditismo | Menos de 5 dezenas em comum com qualquer resultado histórico |
| Quadrantes | Distribuídas em pelo menos 3 dos 4 quadrantes do volante (1–15, 16–30, 31–45, 46–60) |

### Configurações de jogo

- **Números por jogo:** 6 a 15 dezenas (aposta múltipla)
- **Quantidade de jogos:** 1 a 50
- **Excluir números:** remove dezenas do universo de todas as estratégias

### Estratégias disponíveis

| Estratégia | Lógica |
|---|---|
| **Melhor Jogo (IA)** | Roda todas as estratégias, pontua cada uma e entrega somente a de maior score |
| Frequência e Tendência | 35% quentes históricos + 30% tendência recente (20 conc.) + 1 frio estratégico |
| Equilíbrio do Volante | 1 dezena garantida por quadrante + preenchimento filtrado |
| Números Atrasados | 50% dos mais atrasados + pelo menos 1 quente |
| Fixas de Ouro | Dezenas fixas escolhidas pelo usuário + complemento filtrado |
| Técnica do Z | Padrão Z no volante deslocado pelo último dígito da soma do último resultado |
| Técnica +3/-3 | Concatena o último resultado, divide pelo nº do concurso e extrai dezenas da dízima (variações +3 e -3) |
| Desdobramento (Fechamento) | Todas as combinações C(n, k) de um pool definido pelo usuário, com filtros aplicados |

### Modos de uso

- **Gerar Jogos** — N jogos com a estratégia selecionada
- **Painel Completo** — 1 jogo por todas as 7 estratégias automáticas em um clique

---

## Deploy no Fly.io

### Pré-requisitos

```bash
# Instalar o CLI do Fly.io
winget install flyio.flyctl   # Windows
# ou: brew install flyctl     # macOS
```

### Passos

```bash
# 1. Login
flyctl auth login

# 2. Ajuste o nome do app em fly.toml (campo "app")

# 3. Crie o app (somente na primeira vez)
flyctl apps create nome-do-seu-app

# 4. Deploy
flyctl deploy
```

O deploy usa o `Dockerfile` incluído no projeto. A região padrão configurada é `gru` (São Paulo).

### Atualizações

```bash
flyctl deploy
```

---

## Aviso

Este software é uma ferramenta de **análise estatística**. Loterias são jogos de azar e não há garantia de lucro. Jogue com responsabilidade.
