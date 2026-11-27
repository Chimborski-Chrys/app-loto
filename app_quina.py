import streamlit as st
import pandas as pd
import random
from collections import Counter
from math import comb

st.set_page_config(page_title="Quina Pro — Engenharia de Dados", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #260085; color: white; }
    .volante-quina { display: grid; grid-template-columns: repeat(10, 1fr); gap: 4px; max-width: 460px; margin: auto; }
    .dezena { border: 1px solid #444; padding: 4px; text-align: center; border-radius: 50%;
              width: 34px; height: 34px; line-height: 26px; font-size: 10px; }
    .selecionada { background-color: #260085; color: white; border: none; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ── CONSTANTES ──────────────────────────────────────────────────────────────────
TOTAL = 80                       # universo da Quina: 01–80
PADRAO = 5                       # dezenas do jogo padrão (acertar 5 = prêmio principal)
TODAS = set(range(1, TOTAL + 1))
COLUNAS_BOLAS = [f"Bola{i}" for i in range(1, PADRAO + 1)]
QUADRANTES = [
    set(range(1, 21)),    # Q1: 01–20
    set(range(21, 41)),   # Q2: 21–40
    set(range(41, 61)),   # Q3: 41–60
    set(range(61, 81)),   # Q4: 61–80
]


# ── ANÁLISE ────────────────────────────────────────────────────────────────────

def calcular_frequencia(historico_sets):
    freq = {i: 0 for i in range(1, TOTAL + 1)}
    for s in historico_sets:
        for n in s:
            if n in freq:
                freq[n] += 1
    return freq


def top_quentes(frequencia, n=10):
    ranked = sorted(frequencia.items(), key=lambda x: x[1], reverse=True)
    return [d[0] for d in ranked[:n]]


def numeros_atrasados(historico_sets, n=15):
    """Números com o índice de última aparição mais baixo (mais atrasados)."""
    ultimo_idx = {i: -1 for i in range(1, TOTAL + 1)}
    for idx, s in enumerate(historico_sets):
        for num in s:
            ultimo_idx[num] = idx
    ranked = sorted(ultimo_idx.items(), key=lambda x: x[1])
    return [d[0] for d in ranked[:n]]


def atraso_dezena(historico_sets, dezena):
    """Quantos concursos desde a última aparição da dezena (TOTAL = nunca saiu)."""
    for atraso, s in enumerate(reversed(historico_sets)):
        if dezena in s:
            return atraso
    return len(historico_sets)


def tendencia_recente(historico_sets, janela=20):
    ultimos = historico_sets[-janela:] if len(historico_sets) >= janela else historico_sets
    freq = Counter()
    for s in ultimos:
        freq.update(s)
    return [n for n, _ in freq.most_common(15)]


def detectar_acumulada(col_ganhadores):
    """Conta concursos consecutivos com 0 ganhadores (5 acertos) ao final da lista."""
    valores = list(col_ganhadores)[::-1]
    count = 0
    for v in valores:
        try:
            if int(v) == 0:
                count += 1
            else:
                break
        except (ValueError, TypeError):
            break
    return count


# ── VALIDAÇÃO (estratégia aleatória) ────────────────────────────────────────────

def validar_soma(jogo):
    """Soma proporcional: faixa ~130–275 para 5 dezenas, escala para N."""
    n = len(jogo)
    lower = round(130 * n / PADRAO)
    upper = round(275 * n / PADRAO)
    return lower <= sum(jogo) <= upper


def validar_sequencia(jogo):
    """Nenhuma sequência de 3 ou mais números consecutivos."""
    s = sorted(jogo)
    seq = 1
    for i in range(len(s) - 1):
        if s[i] + 1 == s[i + 1]:
            seq += 1
            if seq >= 3:
                return False
        else:
            seq = 1
    return True


def validar_finais(jogo):
    """No máximo 2 dezenas com o mesmo algarismo final."""
    finais = Counter(n % 10 for n in jogo)
    return max(finais.values()) <= 2


def validar_ineditismo(jogo, historico_sets):
    """
    Regra da Caixa adaptada à Quina: não repetir um jogo que já teria
    sido premiado. Rejeita se 4+ dezenas coincidirem com qualquer
    resultado histórico (4 = quadra, 5 = quina já sorteada).
    """
    if not historico_sets:
        return True
    js = set(jogo)
    return all(len(js & h) < 4 for h in historico_sets)


def validar_quadrantes(jogo):
    """Dezenas distribuídas em pelo menos 2 dos 4 quadrantes do volante."""
    jogo_set = set(jogo)
    return sum(1 for q in QUADRANTES if jogo_set & q) >= 2


def validar_jogo_quina(jogo, historico_sets):
    return (
        validar_soma(jogo)
        and validar_sequencia(jogo)
        and validar_finais(jogo)
        and validar_ineditismo(jogo, historico_sets)
        and validar_quadrantes(jogo)
    )


# ── MÉTODO 1 — DESDOBRAMENTO ECONÓMICO: 25 DEZENAS EM 9 JOGOS DE 5 ───────────────

def desdobramento_25_em_9(dezenas):
    """
    Distribui 25 dezenas em 9 jogos de 5 (45 posições) por carrossel sequencial:

      Passo 1: as 14 primeiras dezenas — cada uma em 2 jogos consecutivos.
      Passo 2: as 3 dezenas seguintes — cada uma em 3 jogos consecutivos,
               continuando do ponto de parada.
      Passo 3: as 8 dezenas restantes — uma por jogo.

    Ao fim, um balanceamento garante exatamente 5 dezenas distintas por jogo
    (remove excedentes / completa lacunas com dezenas do próprio conjunto).
    Todas as 25 dezenas escolhidas aparecem em pelo menos um jogo.
    """
    dz = sorted(set(int(x) for x in dezenas))
    if len(dz) != 25:
        raise ValueError("Selecione exatamente 25 dezenas distintas.")

    jogos = [set() for _ in range(9)]
    pos = 0

    # Passo 1 — 14 dezenas em 2 jogos consecutivos (carrossel)
    for d in dz[:14]:
        jogos[pos % 9].add(d)
        jogos[(pos + 1) % 9].add(d)
        pos += 2

    # Passo 2 — 3 dezenas em 3 jogos consecutivos (continua de onde parou)
    for d in dz[14:17]:
        for k in range(3):
            jogos[(pos + k) % 9].add(d)
        pos += 3

    # Passo 3 — 8 dezenas restantes, uma por jogo
    for i, d in enumerate(dz[17:25]):
        jogos[i % 9].add(d)

    # Balanceamento — exatamente 5 dezenas por jogo
    for jg in jogos:
        while len(jg) > 5:
            jg.pop()
    for jg in jogos:
        i = 0
        while len(jg) < 5 and i < len(dz):
            jg.add(dz[i])
            i += 1

    return [sorted(jg) for jg in jogos]


# ── MÉTODO 2 — FECHAMENTO POR MÉDIA POSICIONAL (DIVISÃO POR 3) ───────────────────

def _ajustar_unicos(valores):
    """Garante 5 dezenas distintas em 1–80, empurrando colisões para o vizinho livre."""
    usados = set()
    resultado = []
    for v in valores:
        v = max(1, min(TOTAL, int(v)))
        if v not in usados:
            usados.add(v)
            resultado.append(v)
            continue
        # procura o livre mais próximo (sobe, depois desce)
        achou = None
        for delta in range(1, TOTAL):
            for cand in (v + delta, v - delta):
                if 1 <= cand <= TOTAL and cand not in usados:
                    achou = cand
                    break
            if achou is not None:
                break
        usados.add(achou)
        resultado.append(achou)
    return resultado


def fechamento_media_posicional(r1, r2, r3):
    """
    Média aritmética truncada de cada coluna vertical dos 3 últimos resultados
    (cada um ordenado em ordem crescente). Retorna um único jogo de 5 dezenas.
    """
    a, b, c = sorted(r1), sorted(r2), sorted(r3)
    if not (len(a) == len(b) == len(c) == PADRAO):
        raise ValueError("Cada resultado precisa ter exatamente 5 dezenas.")
    medias = [(a[i] + b[i] + c[i]) // 3 for i in range(PADRAO)]  # truncado
    return sorted(_ajustar_unicos(medias))


# ── MÉTODO 3 — DESDOBRAMENTO EM MATRIZ RETANGULAR: 7 DEZENAS EM 4 JOGOS ──────────

def desdobramento_7_em_4(dezenas):
    """
    Wheel de cobertura para 7 dezenas em 4 jogos de 5.

    Padrão de repetição: 6 dezenas aparecem em 3 dos 4 jogos e 1 dezena em 2.
    Garantia matemática: se 5 das 7 dezenas forem sorteadas, ao menos um jogo
    contém 4 delas (Quadra). Prova: cada jogo omite um par; como todo elemento
    está em algum par omitido, qualquer par de 'não-sorteadas' intercepta um
    jogo, deixando-o com 4 das 5 sorteadas.
    """
    n = sorted(set(int(x) for x in dezenas))
    if len(n) != 7:
        raise ValueError("Selecione exatamente 7 dezenas distintas.")
    n1, n2, n3, n4, n5, n6, n7 = n
    blocos = [
        [n2, n3, n4, n5, n6],   # omite (n1, n7)
        [n1, n3, n4, n5, n6],   # omite (n2, n7)
        [n1, n2, n5, n6, n7],   # omite (n3, n4)
        [n1, n2, n3, n4, n7],   # omite (n5, n6)
    ]
    return [sorted(b) for b in blocos]


def auto_7_dezenas_quina(historico_sets, frequencia):
    """
    Seleciona 7 dezenas para o Método 3: dos 80 números, exclui os 7 mais
    frequentes e os 7 menos frequentes; do miolo, escolhe 7 evitando dezenas
    que saíram nos últimos 5 concursos (para não repetir). Relaxa o critério
    se não houver candidatos suficientes.
    """
    ranked = sorted(range(1, TOTAL + 1), key=lambda n: frequencia.get(n, 0), reverse=True)
    miolo = ranked[7:-7] if len(ranked) > 14 else ranked            # remove 7 mais e 7 menos
    recentes = set()
    for s in historico_sets[-5:]:
        recentes |= s
    candidatos = [n for n in miolo if n not in recentes]
    if len(candidatos) < 7:                                          # relaxa: usa todo o miolo
        candidatos = miolo
    if len(candidatos) < 7:                                          # último recurso
        candidatos = list(range(1, TOTAL + 1))
    # prioriza os mais atrasados dentro dos candidatos (tendência de "vão sair")
    candidatos = sorted(candidatos, key=lambda n: atraso_dezena(historico_sets, n), reverse=True)
    return sorted(candidatos[:7])


# ── MÉTODO 4 — FECHAMENTO DOS FALTANTES (ANÁLISE DE CICLO) ───────────────────────

def analisar_ciclo_quina(historico_sets):
    """
    Analisa o 'ciclo de fechamento': quantos concursos são necessários para que
    todas as 80 dezenas saiam pelo menos uma vez.

    Retorna:
      ciclos        — lista do tamanho (em concursos) de cada ciclo fechado
      faltantes     — dezenas ainda não sorteadas no ciclo aberto atual
      conc_aberto   — concursos já decorridos no ciclo aberto
      media_ciclo   — média histórica de concursos por ciclo (aprendizagem)
    """
    ciclos = []
    seen = set()
    aberto = 0
    for s in historico_sets:
        seen |= s
        aberto += 1
        if len(seen) == TOTAL:
            ciclos.append(aberto)
            seen = set()
            aberto = 0
    faltantes = TODAS - seen                      # dezenas pendentes no ciclo aberto
    media_ciclo = round(sum(ciclos) / len(ciclos), 1) if ciclos else None
    return ciclos, sorted(faltantes), aberto, media_ciclo


def dezenas_abertura_ciclo(historico_sets):
    """
    Frequência de cada dezena como 'abridora' de ciclo: percorre o histórico e,
    sempre que um ciclo fecha (todas as 80 saíram), o concurso seguinte abre um
    novo ciclo — suas dezenas somam +1 no contador. O 1º concurso do histórico
    também conta como abertura. Dezenas com contagem alta tendem a sair logo no
    início de um novo ciclo.
    """
    aberturas = Counter()
    seen = set()
    abrindo = True
    for s in historico_sets:
        if abrindo:
            aberturas.update(s)
            abrindo = False
        seen |= s
        if len(seen) == TOTAL:
            seen = set()
            abrindo = True          # próximo concurso abre o ciclo seguinte
    return aberturas


def _amostra_ponderada(pesos, k):
    """Amostra k itens distintos sem reposição, com probabilidade ∝ peso."""
    itens = list(pesos.keys())
    w = [max(0.0001, pesos[i]) for i in itens]
    escolhidos = []
    while itens and len(escolhidos) < k:
        i = random.choices(range(len(itens)), weights=w, k=1)[0]
        escolhidos.append(itens.pop(i))
        w.pop(i)
    return escolhidos


def estrategia_faltantes(historico_sets, n_numeros, mesclar_abertura=True):
    """
    Monta um jogo focado nas dezenas que faltam fechar o ciclo atual (as mais
    'devidas'), com sorteio ponderado — varia a cada clique.

    • Muitas faltantes (ciclo recém-aberto): amostra ponderada pelo atraso.
    • Poucas faltantes (ciclo quase fechando): TODAS as faltantes entram e o
      restante mescla as dezenas que historicamente ABREM novos ciclos
      (tendência de sair no fechamento/abertura) + mais atrasadas.
    """
    _, faltantes, _, _ = analisar_ciclo_quina(historico_sets)
    n_hist = max(1, len(historico_sets))
    aberturas = dezenas_abertura_ciclo(historico_sets) if mesclar_abertura else Counter()
    max_ab = max(aberturas.values()) if aberturas else 1

    if len(faltantes) >= n_numeros:
        pesos = {n: 0.5 + atraso_dezena(historico_sets, n) / n_hist for n in faltantes}
        return sorted(_amostra_ponderada(pesos, n_numeros))

    escolhidas = list(faltantes)                         # poucas faltantes: todas entram
    pesos = {}
    for n in range(1, TOTAL + 1):
        if n in escolhidas:
            continue
        peso = 0.4 + atraso_dezena(historico_sets, n) / n_hist
        if aberturas.get(n):
            peso += 2.5 * aberturas[n] / max_ab          # tendência de abertura de ciclo
        pesos[n] = peso
    escolhidas += _amostra_ponderada(pesos, n_numeros - len(escolhidas))
    return sorted(escolhidas)


# ── ESTRATÉGIA ALEATÓRIA FILTRADA ───────────────────────────────────────────────

def _completar_jogo(dezenas, n_numeros, pool=None):
    p = pool if pool is not None else TODAS
    restante = list(p - dezenas)
    faltam = n_numeros - len(dezenas)
    if faltam > 0 and len(restante) >= faltam:
        dezenas.update(random.sample(restante, faltam))
    return dezenas


def expandir_jogo(jogo, n_alvo, pool=None, frequencia=None):
    """
    Ajusta um jogo para exatamente n_alvo dezenas (aposta Quina 5–15).
    Se faltam dezenas, completa com as mais frequentes do pool disponível
    (desempate aleatório quando não há frequência). Se sobram, trunca.
    """
    dz = list(dict.fromkeys(int(x) for x in jogo))   # remove duplicatas, mantém ordem
    if len(dz) >= n_alvo:
        return sorted(dz[:n_alvo])
    p = pool if pool is not None else TODAS
    candidatos = [n for n in p if n not in dz]
    if frequencia:
        candidatos.sort(key=lambda n: frequencia.get(n, 0), reverse=True)
    else:
        random.shuffle(candidatos)
    for c in candidatos:
        if len(dz) >= n_alvo:
            break
        dz.append(c)
    return sorted(dz)


def gerar_aleatorio_filtrado(n_numeros, historico_sets, frequencia, pool=None):
    """Sorteio ponderado por frequência + tendência recente, com filtros aplicados."""
    p = pool if pool is not None else TODAS
    p_list = sorted(p)
    if len(p_list) < n_numeros:
        return p_list
    tendentes = [n for n in tendencia_recente(historico_sets, 20) if n in p] if historico_sets else []
    for _ in range(2000):
        dezenas = set()
        if tendentes:
            n_t = max(1, round(n_numeros * 0.4))
            dezenas.update(random.sample(tendentes, min(n_t, len(tendentes))))
        dezenas = _completar_jogo(dezenas, n_numeros, pool=p)
        jogo = sorted(dezenas)
        if len(jogo) == n_numeros and validar_jogo_quina(jogo, historico_sets):
            return jogo
    # fallback: sorteio simples com filtros mínimos
    for _ in range(2000):
        jogo = sorted(random.sample(p_list, n_numeros))
        if validar_soma(jogo) and validar_ineditismo(jogo, historico_sets):
            return jogo
    return sorted(random.sample(p_list, n_numeros))


# ── RENDER ─────────────────────────────────────────────────────────────────────

def render_volante_quina(jogo):
    jogo_set = set(jogo)
    html = '<div class="volante-quina">'
    for n in range(1, TOTAL + 1):
        classe = "dezena selecionada" if n in jogo_set else "dezena"
        html += f'<div class="{classe}">{n:02d}</div>'
    html += '</div>'
    return html


def info_jogo(jogo):
    pares = sum(1 for x in jogo if x % 2 == 0)
    impares = len(jogo) - pares
    soma = sum(jogo)
    quads = sum(1 for q in QUADRANTES if set(jogo) & q)
    return f"Soma: {soma} | Par/Ímpar: {pares}/{impares} | Quadrantes: {quads}/4"


def grade_jogos(jogos):
    """Renderiza uma lista de jogos em colunas de 3 com volante + info."""
    if not jogos:
        return
    cols = st.columns(min(3, len(jogos)))
    for i, jogo in enumerate(jogos):
        with cols[i % len(cols)]:
            st.markdown(f"**Jogo {i + 1}**")
            st.markdown(render_volante_quina(jogo), unsafe_allow_html=True)
            st.caption(info_jogo(jogo))
            st.divider()


def exportar_csv(jogos, nome="jogos_quina.csv"):
    df_export = pd.DataFrame(jogos)
    csv = df_export.to_csv(index=False, header=False).encode("utf-8")
    st.download_button("⬇️ Baixar Jogos (CSV)", csv, nome, "text/csv")


# ── INTERFACE ──────────────────────────────────────────────────────────────────

st.title("🎰 Quina Pro — Engenharia de Dados & IA")

st.sidebar.header("1. Upload de Dados")
file = st.sidebar.file_uploader(
    "Arraste o Excel da Caixa (Quina)",
    type=["xlsx"],
    help="Colunas esperadas: Concurso, Data Sorteio, Bola1–Bola5, Ganhadores 5 acertos, ..."
)

historico_sets = []
frequencia = {i: 0 for i in range(1, TOTAL + 1)}
quentes_global = []
acumulada_info = 0
proximo_concurso = 1

if file:
    try:
        df = pd.read_excel(file, header=0)
        # Detecta colunas das bolas: Bola1–Bola5, senão posições 2–6
        cols_faltando = [c for c in COLUNAS_BOLAS if c not in df.columns]
        if not cols_faltando:
            cols_bolas = df[COLUNAS_BOLAS]
        elif df.shape[1] >= 7:
            cols_bolas = df.iloc[:, 2:7]
        else:
            cols_bolas = None
            st.sidebar.error("Arquivo precisa de Bola1–Bola5 ou 7+ colunas (Concurso, Data + 5 dezenas).")

        if cols_bolas is not None:
            for _, row in cols_bolas.iterrows():
                try:
                    nums = set(int(x) for x in row if pd.notna(x) and 1 <= int(x) <= TOTAL)
                    if len(nums) == PADRAO:
                        historico_sets.append(nums)
                except (ValueError, TypeError):
                    pass

            frequencia = calcular_frequencia(historico_sets)
            quentes_global = top_quentes(frequencia, 10)

            # Detecta coluna de ganhadores (5 acertos) para acumulada
            ganh_col = next(
                (c for c in df.columns if "ganh" in str(c).lower() and "5" in str(c)),
                None
            )
            if ganh_col:
                acumulada_info = detectar_acumulada(df[ganh_col])

            st.sidebar.success(f"✅ {len(historico_sets)} concursos carregados!")
            try:
                proximo_concurso = int(df.iloc[-1, 0]) + 1
            except (ValueError, TypeError, IndexError):
                proximo_concurso = len(historico_sets) + 1

            if acumulada_info > 0:
                plural = "S" if acumulada_info > 1 else ""
                st.sidebar.warning(f"🔥 ACUMULADA HÁ {acumulada_info} CONCURSO{plural}!")
            if historico_sets:
                ultimo = sorted(historico_sets[-1])
                st.sidebar.caption(f"Último resultado: {[f'{n:02d}' for n in ultimo]}")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler o arquivo: {e}")

st.sidebar.divider()
st.sidebar.header("2. Escolher Método")

estrategia = st.sidebar.selectbox("Método", [
    "Método 1 — Desdobramento 25→9",
    "Método 2 — Média Posicional",
    "Método 3 — Matriz 7→4",
    "Método 4 — Fechamento dos Faltantes",
    "Aleatório Filtrado",
])

st.sidebar.divider()
st.sidebar.header("3. Dezenas por Jogo")
dezenas_por_jogo = st.sidebar.slider(
    "Dezenas por jogo (aposta Quina 5–15)", PADRAO, 15, PADRAO,
    help="Quantas dezenas o sistema coloca em cada jogo. 5 = aposta mínima. "
         "Nos desdobramentos, cada jogo é completado com as dezenas mais quentes do conjunto."
)

st.sidebar.divider()
st.sidebar.header("🚫 Excluir Números")
excluidos = st.sidebar.multiselect(
    "Remova dezenas do volante:",
    options=list(range(1, TOTAL + 1)),
    default=[],
    format_func=lambda x: f"{x:02d}",
    help="Aplicado às estratégias aleatórias e à seleção automática."
)
pool_disponivel = TODAS - set(excluidos) if excluidos else None


# ── PARÂMETROS POR MÉTODO ───────────────────────────────────────────────────────

opcoes_dezenas = list(range(1, TOTAL + 1))

if estrategia == "Método 1 — Desdobramento 25→9":
    st.sidebar.info("Selecione 25 dezenas. Geram-se 9 jogos de 5 por carrossel sequencial (14×2, 3×3, 8×1).")
    sel_25 = st.sidebar.multiselect(
        "25 dezenas:", options=opcoes_dezenas, default=[],
        format_func=lambda x: f"{x:02d}",
    )
    st.sidebar.caption(f"{len(sel_25)}/25 selecionadas.")

elif estrategia == "Método 2 — Média Posicional":
    st.sidebar.info("Informe os 3 últimos resultados (5 dezenas cada). A média truncada de cada coluna gera 1 jogo.")
    usar_hist = st.sidebar.checkbox("Usar os 3 últimos do histórico carregado", value=bool(len(historico_sets) >= 3))

elif estrategia == "Método 3 — Matriz 7→4":
    st.sidebar.info("7 dezenas → 4 jogos com garantia de Quadra se 5 das 7 saírem.")
    modo_7 = st.sidebar.radio("Seleção das 7 dezenas:", ["Automática (sistema)", "Manual"], index=0)
    sel_7 = []
    if modo_7 == "Manual":
        sel_7 = st.sidebar.multiselect(
            "7 dezenas:", options=opcoes_dezenas, default=[],
            format_func=lambda x: f"{x:02d}",
        )
        st.sidebar.caption(f"{len(sel_7)}/7 selecionadas.")
    else:
        st.sidebar.caption("Exclui os 7 mais e os 7 menos frequentes; escolhe no miolo evitando os últimos 5 concursos.")

elif estrategia == "Método 4 — Fechamento dos Faltantes":
    st.sidebar.info("Identifica as dezenas que faltam fechar o ciclo (todas as 80 saírem) e monta um jogo com elas.")
    mesclar_abertura = st.sidebar.checkbox(
        "Mesclar dezenas de abertura de ciclo", value=True,
        help="Quando o ciclo está quase fechando, inclui dezenas que historicamente abrem novos ciclos."
    )
    st.sidebar.caption(f"Jogo com {dezenas_por_jogo} dezenas (ajuste em 'Dezenas por Jogo'). Sorteio varia a cada clique.")

else:  # Aleatório Filtrado
    st.sidebar.caption(f"Cada jogo terá {dezenas_por_jogo} dezenas (ajuste em 'Dezenas por Jogo').")
    qtd_aleatorio = st.sidebar.slider("Quantidade de jogos", 1, 50, 5)

st.sidebar.divider()
btn_gerar = st.sidebar.button("🎯 Gerar Jogos", type="primary")


# ── MAIN ────────────────────────────────────────────────────────────────────────

if btn_gerar:
    st.header(f"Resultados — {estrategia}")
    if acumulada_info > 0:
        st.warning(f"🔥 Quina ACUMULADA há {acumulada_info} concurso(s)!")

    jogos_gerados = []

    # ── MÉTODO 1 ──
    if estrategia == "Método 1 — Desdobramento 25→9":
        if len(sel_25) != 25:
            st.error(f"Selecione exatamente 25 dezenas (atual: {len(sel_25)}).")
        else:
            jogos_gerados = desdobramento_25_em_9(sel_25)
            if dezenas_por_jogo > PADRAO:
                jogos_gerados = [
                    expandir_jogo(j, dezenas_por_jogo, pool=set(sel_25), frequencia=frequencia)
                    for j in jogos_gerados
                ]
            cobertura = set()
            for j in jogos_gerados:
                cobertura |= set(j)
            st.success(f"✅ 9 jogos gerados · {len(cobertura)}/25 dezenas cobertas.")
            grade_jogos(jogos_gerados)
            exportar_csv(jogos_gerados, "quina_metodo1_25x9.csv")

    # ── MÉTODO 2 ──
    elif estrategia == "Método 2 — Média Posicional":
        r1 = r2 = r3 = None
        if usar_hist and len(historico_sets) >= 3:
            r1, r2, r3 = (sorted(historico_sets[-3]), sorted(historico_sets[-2]), sorted(historico_sets[-1]))
            st.caption("Usando os 3 últimos resultados do histórico carregado.")
        else:
            st.markdown("**Informe os 3 últimos resultados (5 dezenas cada):**")
            c1, c2, c3 = st.columns(3)
            with c1:
                r1 = st.multiselect("Resultado -3", opcoes_dezenas, format_func=lambda x: f"{x:02d}", key="m2r1")
            with c2:
                r2 = st.multiselect("Resultado -2", opcoes_dezenas, format_func=lambda x: f"{x:02d}", key="m2r2")
            with c3:
                r3 = st.multiselect("Resultado -1", opcoes_dezenas, format_func=lambda x: f"{x:02d}", key="m2r3")

        if r1 and r2 and r3 and len(r1) == len(r2) == len(r3) == 5:
            jogo = fechamento_media_posicional(r1, r2, r3)
            if dezenas_por_jogo > PADRAO:
                jogo = expandir_jogo(jogo, dezenas_por_jogo, pool=pool_disponivel, frequencia=frequencia)
            jogos_gerados = [jogo]
            st.success(f"✅ Jogo gerado pela média posicional truncada ({len(jogo)} dezenas).")
            # mostra o cálculo coluna a coluna
            a, b, c = sorted(r1), sorted(r2), sorted(r3)
            df_calc = pd.DataFrame({
                "Coluna": [f"C{i+1}" for i in range(5)],
                "R-3": a, "R-2": b, "R-1": c,
                "Soma": [a[i] + b[i] + c[i] for i in range(5)],
                "Média (trunc.)": [(a[i] + b[i] + c[i]) // 3 for i in range(5)],
            })
            st.dataframe(df_calc, use_container_width=True, hide_index=True)
            grade_jogos(jogos_gerados)
            exportar_csv(jogos_gerados, "quina_metodo2_media.csv")
        else:
            st.info("Informe os 3 resultados com 5 dezenas cada para gerar o jogo.")

    # ── MÉTODO 3 ──
    elif estrategia == "Método 3 — Matriz 7→4":
        if modo_7 == "Manual":
            dezenas_7 = sorted(sel_7)
            if len(dezenas_7) != 7:
                st.error(f"Selecione exatamente 7 dezenas (atual: {len(dezenas_7)}).")
                dezenas_7 = None
        else:
            if not historico_sets:
                st.error("Carregue o histórico para a seleção automática das 7 dezenas.")
                dezenas_7 = None
            else:
                dezenas_7 = auto_7_dezenas_quina(historico_sets, frequencia)
                st.caption(f"7 dezenas escolhidas pelo sistema: {' · '.join(f'{n:02d}' for n in dezenas_7)}")

        if dezenas_7:
            jogos_gerados = desdobramento_7_em_4(dezenas_7)
            if dezenas_por_jogo > PADRAO:
                jogos_gerados = [
                    expandir_jogo(j, dezenas_por_jogo, pool=set(dezenas_7), frequencia=frequencia)
                    for j in jogos_gerados
                ]
            st.success("✅ 4 jogos gerados · garantia de Quadra se 5 das 7 dezenas saírem.")
            grade_jogos(jogos_gerados)
            exportar_csv(jogos_gerados, "quina_metodo3_7x4.csv")

    # ── MÉTODO 4 ──
    elif estrategia == "Método 4 — Fechamento dos Faltantes":
        if not historico_sets:
            st.error("Carregue o histórico para analisar o ciclo de fechamento.")
        else:
            ciclos, faltantes, conc_aberto, media_ciclo = analisar_ciclo_quina(historico_sets)
            abridoras = dezenas_abertura_ciclo(historico_sets)
            jogo = estrategia_faltantes(historico_sets, dezenas_por_jogo, mesclar_abertura=mesclar_abertura)
            jogos_gerados = [jogo]

            c1, c2, c3 = st.columns(3)
            c1.metric("Faltam fechar ciclo", f"{len(faltantes)} dezenas")
            c2.metric("Concursos no ciclo aberto", conc_aberto)
            c3.metric("Média de ciclo (histórico)", f"{media_ciclo} conc." if media_ciclo else "—")

            if media_ciclo:
                if conc_aberto >= media_ciclo:
                    st.info(
                        f"📈 Aprendizagem: o ciclo médio fecha em ~{media_ciclo} concursos e o atual "
                        f"já tem {conc_aberto}. Tendência de fechamento próximo — as {len(faltantes)} "
                        "dezenas faltantes estão 'devidas'."
                    )
                else:
                    st.info(
                        f"📊 Aprendizagem: ciclo médio ~{media_ciclo} concursos; o atual tem {conc_aberto}. "
                        f"Faltam ~{max(0, round(media_ciclo - conc_aberto))} concursos para o fechamento típico."
                    )
            if ciclos:
                st.caption(f"Ciclos históricos (concursos p/ fechar as 80): {ciclos[-10:]}")

            st.success(f"✅ Jogo com as {dezenas_por_jogo} dezenas mais 'devidas' do ciclo atual.")
            st.write("**Faltantes (por atraso):** " + (" · ".join(
                f"{n:02d}" for n in sorted(faltantes, key=lambda n: atraso_dezena(historico_sets, n), reverse=True)[:20]
            ) or "—"))
            if mesclar_abertura and abridoras:
                top_abrid = abridoras.most_common(12)
                st.write("**Dezenas que mais abrem ciclo:** " + " · ".join(
                    f"{n:02d} ({c}×)" for n, c in top_abrid
                ))
                if len(faltantes) < dezenas_por_jogo:
                    st.caption(
                        f"Ciclo quase fechando ({len(faltantes)} faltante(s)): as faltantes entram fixas "
                        "e o restante do jogo mescla as abridoras acima."
                    )
            grade_jogos(jogos_gerados)
            exportar_csv(jogos_gerados, "quina_metodo4_faltantes.csv")

    # ── ALEATÓRIO FILTRADO ──
    else:
        with st.spinner(f"Gerando {qtd_aleatorio} jogo(s)..."):
            for _ in range(qtd_aleatorio):
                jogos_gerados.append(
                    gerar_aleatorio_filtrado(dezenas_por_jogo, historico_sets, frequencia, pool=pool_disponivel)
                )
        grade_jogos(jogos_gerados)
        exportar_csv(jogos_gerados, "quina_aleatorio.csv")

    # ── Análise do histórico ──
    if historico_sets:
        with st.expander("📊 Análise do Histórico"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Top 10 Mais Sorteados**")
                for n in quentes_global:
                    st.write(f"`{n:02d}` — {frequencia[n]}×")
            with c2:
                st.markdown("**Top 10 Mais Atrasados**")
                for n in numeros_atrasados(historico_sets, 10):
                    st.write(f"`{n:02d}` — {atraso_dezena(historico_sets, n)} conc. atrás")
            with c3:
                st.markdown("**Tendência Recente (20 conc.)**")
                freq_rec = Counter()
                for s in historico_sets[-20:]:
                    freq_rec.update(s)
                for n, cnt in freq_rec.most_common(10):
                    st.write(f"`{n:02d}` — {cnt}× nos últ. 20")

else:
    st.info("Escolha um método na lateral e clique em 'Gerar Jogos'.")

    if historico_sets:
        st.subheader("Resumo do Histórico Carregado")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Concursos", len(historico_sets))
        c2.metric("Mais Sorteado", f"{quentes_global[0]:02d}" if quentes_global else "—")
        n_atras = numeros_atrasados(historico_sets, 1)
        c3.metric("Mais Atrasado", f"{n_atras[0]:02d}" if n_atras else "—")
        if acumulada_info > 0:
            c4.metric("🔥 Acumulada", f"{acumulada_info} conc.")
        else:
            c4.metric("Status", "Não acumulada")
    else:
        st.markdown("""
        ### Como usar
        1. **Upload**: Arraste o Excel da Quina na lateral esquerda
           *(Colunas: Concurso · Data Sorteio · Bola1–Bola5 · Ganhadores 5 acertos)*
        2. **Método**: Escolha um dos 4 métodos de desdobramento/fechamento
        3. **Gere**: Clique em **Gerar Jogos**

        ### Métodos disponíveis
        | Método | Lógica |
        |--------|--------|
        | 1 — Desdobramento 25→9 | 25 dezenas distribuídas em 9 jogos de 5 (carrossel 14×2, 3×3, 8×1) |
        | 2 — Média Posicional | Média truncada de cada coluna dos 3 últimos resultados → 1 jogo |
        | 3 — Matriz 7→4 | 7 dezenas em 4 jogos com garantia de Quadra se 5 das 7 saírem |
        | 4 — Fechamento dos Faltantes | Dezenas que faltam fechar o ciclo das 80, com aprendizagem do ciclo médio |

        A Quina sorteia **5 dezenas de 01 a 80**. Acertar as 5 leva o prêmio principal.
        """)

# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Aviso: Este software é uma ferramenta de análise estatística. "
    "Loterias são jogos de azar e não há garantia de lucro. Jogue com responsabilidade."
)
