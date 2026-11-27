# Loterias Pro — IA & Engenharia de Dados

Aplicação web construída com **Streamlit** que reúne geradores inteligentes para **Lotofácil**, **Mega Sena** e **Quina**. Combina múltiplas estratégias com filtros de validação automática e pontuação por aderência ao histórico de resultados.

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



```

Acesse `http://localhost:8501`. O menu lateral exibe os módulos disponíveis (Lotofácil, Mega Sena, Quina e Verificador).

---

## Estrutura do projeto

```
previsao/
├── app.py                  # Home — menu de navegação
├── app_loto.py             # Lógica completa Lotofácil
├── app_megasena.py         # Lógica completa Mega Sena
├── app_quina.py            # Lógica completa Quina
├── app_verificador.py      # Conferência de jogos (Lotofácil, Mega-Sena, Quina)
├── pages/
│   ├── 1_Lotofacil.py      # Wrapper de página (executa app_loto.py)
│   ├── 2_Mega_Sena.py      # Wrapper de página (executa app_megasena.py)
│   ├── 3_Quina.py          # Wrapper de página (executa app_quina.py)
│   └── 4_Verificador.py    # Wrapper de página (executa app_verificador.py)
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

## Módulo Quina

A Quina sorteia **5 dezenas de 01 a 80**. Acertar as 5 leva o prêmio principal; também há prêmio para Quadra (4), Terno (3) e Duque (2).

### Arquivo de histórico

Arquivo `.xlsx` exportado do site da Caixa:

```
Concurso | Data Sorteio | Bola1 | Bola2 | Bola3 | Bola4 | Bola5 | Ganhadores 5 acertos | ...
```

São usadas `Bola1`–`Bola5` (ou as posições 3–7 como fallback). A coluna de ganhadores (5 acertos) detecta automaticamente se a Quina está acumulada.

> Download: [Resultados Quina — Caixa](https://loterias.caixa.gov.br/Paginas/Download-Resultados.aspx)

### Métodos disponíveis

| Método | Lógica |
|---|---|
| **1 — Desdobramento 25→9** | 25 dezenas distribuídas em 9 jogos de 5 por carrossel sequencial (14 dezenas em 2 jogos, 3 dezenas em 3 jogos, 8 dezenas em 1 jogo) + balanceamento para 5 por jogo |
| **2 — Média Posicional** | Média aritmética **truncada** de cada coluna dos 3 últimos resultados (ordenados) → 1 jogo de 5 dezenas |
| **3 — Matriz 7→4** | 7 dezenas em 4 jogos com **garantia matemática de Quadra** se 5 das 7 saírem (6 dezenas repetem 3×, 1 repete 2×). Seleção automática exclui os 7 mais e os 7 menos frequentes e evita os últimos 5 concursos |
| **4 — Fechamento dos Faltantes** | Identifica as dezenas que faltam para **fechar o ciclo** (todas as 80 saírem) e monta o jogo com as mais atrasadas. Aprende a duração média do ciclo histórico e projeta o fechamento |
| Aleatório Filtrado | Sorteio ponderado por tendência recente com filtros de soma, sequência, finais, ineditismo e quadrantes |

### Filtros (estratégia aleatória)

| Filtro | Regra |
|---|---|
| Soma | Proporcional à faixa ~130–275 para 5 dezenas |
| Sequência | No máximo 2 números consecutivos |
| Finais | Máximo 2 dezenas com o mesmo algarismo final |
| Ineditismo | Menos de 4 dezenas em comum com qualquer resultado histórico (não repete Quadra/Quina já sorteada) |
| Quadrantes | Distribuídas em pelo menos 2 dos 4 quadrantes (1–20, 21–40, 41–60, 61–80) |

> Os métodos 1 a 4 são desdobramentos/fechamentos determinísticos e não passam pelos filtros acima.

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
