import streamlit as st
import pandas as pd
import random
import time
from collections import Counter
from math import comb

st.set_page_config(
    page_title="Lotofácil Pro — IA & Engenharia de Dados",
    layout="wide",
)

st.markdown("""
<style>
.main { background-color: #0e1117; color: white; }
.stButton>button { width: 100%; border-radius: 5px; height: 3em;
                   background-color: #ff4b4b; color: white; }
.volante { display: grid; grid-template-columns: repeat(5, 1fr);
           gap: 5px; max-width: 260px; margin: auto; }
.dezena { border: 1px solid #444; padding: 10px; text-align: center;
          border-radius: 50%; width: 40px; height: 40px; line-height: 20px; }
.selecionada { background-color: #2e7d32; color: white; border: none; }
</style>
""", unsafe_allow_html=True)

# ── CONSTANTES ─────────────────────────────────────────────────────────────────
TODAS = set(range(1, 26))
COLUNAS_BOLAS = [f"Bola{i}" for i in range(1, 16)]

# ── VALIDAÇÃO ──────────────────────────────────────────────────────────────────
def validar_soma(jogo):
    return 180 <= sum(jogo) <= 220

def validar_sequencia(jogo):
    s = sorted(jogo); seq = 1
    for i in range(len(s) - 1):
        if s[i] + 1 == s[i + 1]:
            seq += 1
            if seq > 4: return False
        else:
            seq = 1
    return True

def validar_ineditismo(jogo, historico_sets):
    js = set(jogo)
    return all(len(js & h) < 14 for h in historico_sets)

def validar_jogo_loto(jogo, historico_sets):
    return validar_soma(jogo) and validar_sequencia(jogo) and validar_ineditismo(jogo, historico_sets)

# ── FUNÇÕES AUXILIARES ─────────────────────────────────────────────────────────
def calcular_frequencia(historico_sets):
    freq = {i: 0 for i in range(1, 26)}
    for s in historico_sets:
        for n in s:
            freq[n] += 1
    return freq

def top_quentes(frequencia, n=10):
    ranked = sorted(frequencia.items(), key=lambda x: x[1], reverse=True)
    return [d[0] for d in ranked[:n]]

def numeros_atrasados(historico_sets, n=10):
    ultimo_idx = {i: -1 for i in range(1, 26)}
    for idx, s in enumerate(historico_sets):
        for num in s:
            ultimo_idx[num] = idx
    ranked = sorted(ultimo_idx.items(), key=lambda x: x[1])
    return [d[0] for d in ranked[:n]]

def tendencia_recente(historico_sets, janela=20):
    ultimos = historico_sets[-janela:] if len(historico_sets) >= janela else historico_sets
    freq = Counter()
    for s in ultimos:
        freq.update(s)
    return [n for n, _ in freq.most_common(15)]

def detectar_acumulada(col_ganhadores):
    """Conta concursos consecutivos sem ganhador no prêmio máximo."""
    vals = col_ganhadores.dropna().tolist()
    cnt = 0
    for v in reversed(vals):
        try:
            if int(v) == 0:
                cnt += 1
            else:
                break
        except (ValueError, TypeError):
            break
    return cnt

def auto_fixas_loto(historico_sets):
    ultimos = historico_sets[-10:] if len(historico_sets) >= 10 else historico_sets
    contagem = Counter()
    for s in ultimos:
        contagem.update(s)
    threshold = max(1, round(len(ultimos) * 0.6))
    fixas = sorted([n for n, c in contagem.items() if c >= threshold])
    if len(fixas) < 3:
        top = sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:5]
        fixas = sorted([n for n, _ in top])
    return fixas[:10]

def auto_pool_loto(historico_sets):
    ultimos = historico_sets[-10:] if len(historico_sets) >= 10 else historico_sets
    pool = set()
    for s in ultimos:
        pool.update(s)
    return sorted(pool)

def _completar_jogo(dezenas, pool=None):
    p = pool if pool is not None else TODAS
    restante = list(p - dezenas)
    faltam = 15 - len(dezenas)
    if faltam > 0 and len(restante) >= faltam:
        dezenas.update(random.sample(restante, faltam))
    return dezenas

def _fallback(historico_sets, pool=None):
    p = pool if pool is not None else TODAS
    p_list = sorted(p)
    if len(p_list) < 15:
        return p_list
    for _ in range(500):
        j = sorted(random.sample(p_list, 15))
        if validar_soma(j) and validar_sequencia(j):
            return j
    return sorted(random.sample(p_list, 15))

# ── GERADORES DE ESTRATÉGIA ────────────────────────────────────────────────────
def gerar_inversao_suprema(historico_sets, ultimo, pool=None):
    """6 ausentes + 9 presentes — distribuição flexível que evita teto de acertos."""
    p = pool if pool is not None else TODAS
    ultimo_set = set(ultimo)
    ausentes_p  = sorted((TODAS - ultimo_set) & p)
    presentes_p = sorted(ultimo_set & p)
    for _ in range(1000):
        dez = set()
        dez.update(random.sample(ausentes_p, min(6, len(ausentes_p))))
        disp_p = [x for x in presentes_p if x not in dez]
        dez.update(random.sample(disp_p, min(9, len(disp_p))))
        dez = _completar_jogo(dez, pool=p)
        j = sorted(dez)
        if len(j) == 15 and validar_jogo_loto(j, historico_sets):
            return j
    return _fallback(historico_sets, pool=p)

def gerar_cercamento(historico_sets, ultimo, pool=None):
    """7 ausentes + 8 presentes."""
    p = pool if pool is not None else TODAS
    ultimo_set = set(ultimo)
    ausentes_p  = sorted((TODAS - ultimo_set) & p)
    presentes_p = sorted(ultimo_set & p)
    for _ in range(1000):
        dez = set()
        if len(ausentes_p) >= 7:
            dez.update(random.sample(ausentes_p, 7))
        disp_p = [x for x in presentes_p if x not in dez]
        if len(disp_p) >= 8:
            dez.update(random.sample(disp_p, 8))
        dez = _completar_jogo(dez, pool=p)
        j = sorted(dez)
        if len(j) == 15 and validar_jogo_loto(j, historico_sets):
            return j
    return _fallback(historico_sets, pool=p)

def gerar_fixas_ouro(historico_sets, fixas, pool=None):
    """Dezenas fixas + complemento filtrado."""
    p = pool if pool is not None else TODAS
    fixas_v = [f for f in fixas if f in p]
    for _ in range(1000):
        dez = set(fixas_v)
        dez = _completar_jogo(dez, pool=p)
        j = sorted(dez)
        if len(j) == 15 and validar_jogo_loto(j, historico_sets):
            return j
    return _fallback(historico_sets, pool=p)

def gerar_equilibrio(historico_sets, pool=None):
    """Frias dos últimos 3 + equilíbrio par/ímpar (7 ou 8 ímpares)."""
    p = pool if pool is not None else TODAS
    frias = []
    if len(historico_sets) >= 3:
        ult3 = historico_sets[-3:]
        frias = sorted((TODAS - (ult3[0] | ult3[1] | ult3[2])) & p)
    for _ in range(1000):
        dez = set()
        if frias:
            dez.update(random.sample(frias, min(len(frias), 3)))
        impares = [n for n in p if n % 2 != 0]
        pares   = [n for n in p if n % 2 == 0]
        n_imp = random.choice([7, 8])
        ri = [n for n in impares if n not in dez]
        rp = [n for n in pares   if n not in dez]
        ni = n_imp - len([n for n in dez if n % 2 != 0])
        if ni > 0 and len(ri) >= ni:
            dez.update(random.sample(ri, ni))
        np_ = 15 - len(dez)
        if np_ > 0 and len(rp) >= np_:
            dez.update(random.sample(rp, np_))
        dez = _completar_jogo(dez, pool=p)
        j = sorted(dez)
        if len(j) == 15 and validar_jogo_loto(j, historico_sets):
            return j
    return _fallback(historico_sets, pool=p)

def gerar_ranking_frequencia(historico_sets, frequencia, pool=None):
    """Sample ponderado por frequência histórica de todos os números do pool."""
    p = pool if pool is not None else TODAS
    pool_list = sorted(p)
    pesos = [max(frequencia.get(n, 1), 1) for n in pool_list]
    for _ in range(1000):
        dez = set()
        pool_d = pool_list[:]
        pesos_d = pesos[:]
        while len(dez) < 15 and pool_d:
            total = sum(pesos_d)
            r = random.uniform(0, total)
            acc = 0
            for i, pw in enumerate(pesos_d):
                acc += pw
                if acc >= r:
                    dez.add(pool_d[i])
                    pool_d.pop(i)
                    pesos_d.pop(i)
                    break
        j = sorted(dez)
        if len(j) == 15 and validar_jogo_loto(j, historico_sets):
            return j
    return _fallback(historico_sets, pool=p)

def gerar_fechamento_dezenas(historico_sets, pool_fixas, pool=None):
    """Jogos exclusivamente dentro do pool definido."""
    p = pool if pool is not None else TODAS
    pool_v = [n for n in pool_fixas if n in p]
    if len(pool_v) < 15:
        pool_v = sorted(p)
    for _ in range(1000):
        dez = set(random.sample(pool_v, min(15, len(pool_v))))
        j = sorted(dez)
        if len(j) == 15 and validar_jogo_loto(j, historico_sets):
            return j
    return _fallback(historico_sets, pool=p)

def gerar_ciclo3(historico_sets, pool=None):
    """Frias dos últimos 3 como âncora opcional (0–3) + fill livre."""
    p = pool if pool is not None else TODAS
    frias = []
    if len(historico_sets) >= 3:
        ult3 = historico_sets[-3:]
        frias = sorted((TODAS - (ult3[0] | ult3[1] | ult3[2])) & p)
    for _ in range(1000):
        dez = set()
        if frias:
            dez.update(random.sample(frias, min(len(frias), 3)))
        dez = _completar_jogo(dez, pool=p)
        j = sorted(dez)
        if len(j) == 15 and validar_jogo_loto(j, historico_sets):
            return j
    return _fallback(historico_sets, pool=p)

def gerar_fechamento_17_dezenas(escolhidas_17, fixas_5):
    """Fechamento de 17 dezenas em 6 jogos (Radar Loto)."""
    restantes = [n for n in escolhidas_17 if n not in fixas_5]
    random.shuffle(restantes)
    jogos = []
    for i in range(6):
        indices = [(i + j) % 12 for j in range(10)]
        combinacao = [restantes[idx] for idx in indices if idx < len(restantes)]
        jogos.append(sorted(fixas_5 + combinacao[:10]))
    return jogos

def gerar_fechamento_13_fixas(fixas_13, todas_25):
    """Garante 15 pontos se acertar as 13 fixas."""
    restantes = [n for n in todas_25 if n not in fixas_13]
    random.shuffle(restantes)
    jogos = []
    for i in range(0, min(12, len(restantes) - 1), 2):
        par = restantes[i:i + 2]
        if len(par) == 2:
            jogos.append(sorted(fixas_13 + par))
    return jogos

# ── DISPATCHER ─────────────────────────────────────────────────────────────────
def gerar_estrategia_loto(tipo, frequencia, historico_sets, ultimo, fixas=None, pool=None):
    if fixas is None:
        fixas = []
    p = pool
    if tipo == "Inversão Suprema":
        return gerar_inversao_suprema(historico_sets, ultimo, pool=p)
    elif tipo == "Cercamento 7/8":
        return gerar_cercamento(historico_sets, ultimo, pool=p)
    elif tipo == "Fixas de Ouro":
        return gerar_fixas_ouro(historico_sets, fixas, pool=p)
    elif tipo == "Equilíbrio IA 2026":
        return gerar_equilibrio(historico_sets, pool=p)
    elif tipo == "Ranking Frequência":
        return gerar_ranking_frequencia(historico_sets, frequencia, pool=p)
    elif tipo == "Fechamento de Dezenas":
        return gerar_fechamento_dezenas(historico_sets, fixas, pool=p)
    elif tipo == "Rastreio Ciclo 3":
        return gerar_ciclo3(historico_sets, pool=p)
    return _fallback(historico_sets, pool=p)

# ── PONTUAÇÃO ──────────────────────────────────────────────────────────────────
def pontuar_jogo_loto(jogo, historico_sets, frequencia):
    if not historico_sets:
        return 0.0
    jogo_set = set(jogo)
    ultimo = historico_sets[-1]
    moldura = {1, 2, 3, 4, 5, 6, 10, 11, 15, 16, 20, 21, 22, 23, 24, 25}
    score_moldura = 50 if 9 <= len(jogo_set & moldura) <= 11 else 0
    score_rep     = 50 if 8 <= len(jogo_set & ultimo)   <= 10 else 0
    acertos_med   = sum(len(jogo_set & h) for h in historico_sets) / len(historico_sets)
    return round(score_moldura + score_rep + (acertos_med * 10), 2)

# ── MELHOR JOGO (IA) ───────────────────────────────────────────────────────────
def gerar_melhor_jogo_loto(frequencia, historico_sets, ultimo, pool=None):
    candidatos_est = [
        "Inversão Suprema",
        "Cercamento 7/8",
        "Equilíbrio IA 2026",
        "Ranking Frequência",
        "Rastreio Ciclo 3",
    ]
    candidatos = []
    for tipo in candidatos_est:
        jogo = gerar_estrategia_loto(tipo, frequencia, historico_sets, ultimo, pool=pool)
        score = pontuar_jogo_loto(jogo, historico_sets, frequencia)
        candidatos.append((jogo, tipo, score))
    candidatos.sort(key=lambda x: x[2], reverse=True)
    ranking = [(nome, score) for (_, nome, score) in candidatos]
    jogo_best, nome_best, score_best = candidatos[0]
    return jogo_best, nome_best, score_best, ranking

# ── SIMULAÇÃO ──────────────────────────────────────────────────────────────────
def simular_ate_acertar(resultado_alvo, min_acertos, frequencia, pool,
                        max_tentativas, historico_sets, ultimo,
                        estrategia="Aleatório Ponderado (Rápido)"):
    alvo = set(resultado_alvo)
    p = sorted(pool if pool is not None else TODAS)
    if len(p) < 15:
        return max_tentativas, None

    if estrategia != "Aleatório Ponderado (Rápido)":
        for tent in range(1, max_tentativas + 1):
            jogo = gerar_estrategia_loto(
                estrategia, frequencia,
                historico_sets=[],   # desabilita ineditismo para performance
                ultimo=ultimo,
                pool=pool,
            )
            if len(set(jogo) & alvo) >= min_acertos:
                return tent, jogo
        return max_tentativas, None

    # Modo rápido: amostragem ponderada por frequência
    pesos = [max(frequencia.get(n, 1), 1) for n in p]
    from bisect import bisect
    from itertools import accumulate

    def _sorteia():
        idx_d = list(range(len(p)))
        pw_d  = list(pesos)
        escolhidos = []
        for _ in range(15):
            cum = list(accumulate(pw_d))
            total = cum[-1]
            if total <= 0:
                return None
            r   = random.uniform(0, total)
            idx = min(bisect(cum, r), len(idx_d) - 1)
            escolhidos.append(p[idx_d[idx]])
            idx_d.pop(idx)
            pw_d.pop(idx)
        return sorted(escolhidos)

    for tent in range(1, max_tentativas + 1):
        jogo = _sorteia()
        if jogo is None or len(jogo) != 15:
            continue
        if not validar_soma(jogo) or not validar_sequencia(jogo):
            continue
        if len(set(jogo) & alvo) >= min_acertos:
            return tent, jogo
    return max_tentativas, None

# ── RENDER ─────────────────────────────────────────────────────────────────────
def render_volante(jogo):
    jogo_set = set(jogo)
    html = '<div class="volante">'
    for n in range(1, 26):
        cls = "dezena selecionada" if n in jogo_set else "dezena"
        html += f'<div class="{cls}">{n:02d}</div>'
    html += '</div>'
    return html

def info_jogo(jogo):
    pares   = sum(1 for x in jogo if x % 2 == 0)
    impares = 15 - pares
    soma    = sum(jogo)
    moldura = {1, 2, 3, 4, 5, 6, 10, 11, 15, 16, 20, 21, 22, 23, 24, 25}
    n_mold  = len(set(jogo) & moldura)
    return f"Soma: {soma} | Par/Ímpar: {pares}/{impares} | Moldura: {n_mold}/16"

# ── INTERFACE ──────────────────────────────────────────────────────────────────
st.title("🎯 Lotofácil Pro — Engenharia de Dados & IA")

# ── Sidebar 1: Upload ─────────────────────────────────────────────────────────
st.sidebar.header("1. Upload de Dados")
file = st.sidebar.file_uploader(
    "Arraste o Excel da Caixa (Lotofácil)",
    type=["xlsx"],
    help="Colunas esperadas: Concurso, Data Sorteio, Bola1–Bola15, Ganhadores 15 acertos, ..."
)

historico_sets    = []
frequencia        = {i: 0 for i in range(1, 26)}
quentes_global    = []
ultimo_resultado  = list(range(1, 16))
proximo_concurso  = 1
acumulada_info    = 0

if file:
    try:
        df = pd.read_excel(file, header=0)
        cols_faltando = [c for c in COLUNAS_BOLAS if c not in df.columns]
        if cols_faltando:
            st.sidebar.error(f"Colunas não encontradas: {', '.join(cols_faltando)}")
        else:
            linhas_v = df[COLUNAS_BOLAS].dropna()
            historico_sets = [set(int(v) for v in row) for row in linhas_v.values]
            ultimo_resultado = [int(v) for v in linhas_v.iloc[-1].values]
            frequencia = calcular_frequencia(historico_sets)
            quentes_global = top_quentes(frequencia, 10)

            try:
                proximo_concurso = int(df.iloc[-1, 0]) + 1
            except (ValueError, TypeError, IndexError):
                proximo_concurso = len(historico_sets) + 1

            # Detecta acumulada na coluna "Ganhadores 15 acertos"
            ganh_col = next(
                (c for c in df.columns if "ganh" in str(c).lower() and "15" in str(c)),
                None
            )
            if ganh_col:
                acumulada_info = detectar_acumulada(df[ganh_col])

            st.sidebar.success(f"✅ {len(historico_sets)} concursos carregados!")
            if acumulada_info > 0:
                plural = "S" if acumulada_info > 1 else ""
                st.sidebar.warning(f"🔥 ACUMULADA HÁ {acumulada_info} CONCURSO{plural}!")
            st.sidebar.caption(
                f"Último resultado: {[f'{n:02d}' for n in sorted(ultimo_resultado)]}"
            )
    except Exception as e:
        st.sidebar.error(f"Erro ao ler o arquivo: {e}")

# ── Sidebar 2: Configurar Jogo ────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("2. Configurar Jogo")

excluir_nums = st.sidebar.multiselect(
    "Excluir números",
    options=list(range(1, 26)),
    default=[],
    format_func=lambda x: f"{x:02d}",
    help="Remove estas dezenas do universo de todas as estratégias."
)
pool_disponivel = (TODAS - set(excluir_nums)) if excluir_nums else None

qtd_jogos = st.sidebar.slider("Quantidade de jogos", min_value=1, max_value=50, value=5)

# ── Sidebar 3: Estratégia ─────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("3. Escolher Estratégia")

estrategia = st.sidebar.selectbox("Estratégia", [
    "Melhor Jogo (IA)",
    "Inversão Suprema",
    "Cercamento 7/8",
    "Fixas de Ouro",
    "Equilíbrio IA 2026",
    "Ranking Frequência",
    "Fechamento de Dezenas",
    "Fechamento 17 Dezenas (6 Jogos)",
    "Matriz 13 Fixas (Ouro)",
    "Rastreio Ciclo 3",
])

fixas = []
if estrategia == "Fixas de Ouro":
    st.sidebar.markdown("**Dezenas Fixas** (até 14)")
    fixas = st.sidebar.multiselect(
        "Selecione as dezenas fixas:",
        options=list(range(1, 26)), default=[],
        format_func=lambda x: f"{x:02d}"
    )
    if len(fixas) >= 15:
        st.sidebar.error("Selecione no máximo 14 dezenas fixas.")
        fixas = fixas[:14]

elif estrategia == "Fechamento de Dezenas":
    st.sidebar.markdown("**Pool de Fechamento** (mínimo 15)")
    st.sidebar.caption("Jogos gerados exclusivamente com as dezenas do pool.")
    fixas = st.sidebar.multiselect(
        "Pool:", options=list(range(1, 26)), default=list(range(1, 21)),
        format_func=lambda x: f"{x:02d}"
    )
    if len(fixas) < 15:
        st.sidebar.error("Selecione pelo menos 15 dezenas.")
    else:
        st.sidebar.info(f"Pool {len(fixas)} dezenas → C({len(fixas)},15) combinações.")

elif estrategia == "Fechamento 17 Dezenas (6 Jogos)":
    st.sidebar.markdown("**17 Dezenas para o fechamento**")
    fixas = st.sidebar.multiselect(
        "Escolha 17:", options=list(range(1, 26)), default=list(range(1, 18)),
        format_func=lambda x: f"{x:02d}"
    )

elif estrategia == "Matriz 13 Fixas (Ouro)":
    st.sidebar.markdown("**13 Dezenas Fixas**")
    fixas = st.sidebar.multiselect(
        "Escolha 13:", options=list(range(1, 26)), default=list(range(1, 14)),
        format_func=lambda x: f"{x:02d}"
    )

btn_gerar = st.sidebar.button("Gerar Jogos", type="primary")

# ── Sidebar 4: Painel Completo ────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("4. Painel Completo")
st.sidebar.caption("1 jogo por estratégia. Fixas e pool escolhidos automaticamente pelo histórico.")
btn_painel = st.sidebar.button("Gerar Painel Completo (Auto)")

# ── Sidebar 5: Simulação ──────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("5. Simulação de Eficiência")

resultado_alvo_sim = st.sidebar.multiselect(
    "Resultado alvo (15 dezenas):",
    options=list(range(1, 26)),
    default=[],
    format_func=lambda x: f"{x:02d}",
    help="Cole o resultado de um sorteio real para medir a eficiência da estratégia."
)
min_acertos_sim = st.sidebar.slider("Mínimo de acertos para 'ganhar'", 11, 15, 12)
n_ciclos_sim    = st.sidebar.number_input("Ciclos", min_value=1, max_value=20, value=10, step=1)
max_tent_sim    = st.sidebar.number_input(
    "Máx. tentativas por ciclo", min_value=1_000, max_value=500_000,
    value=50_000, step=1_000,
    help="Se atingir o limite sem acertar, registra como 'não encontrado'."
)

_opcoes_sim = [
    "Aleatório Ponderado (Rápido)",
    "Inversão Suprema",
    "Cercamento 7/8",
    "Equilíbrio IA 2026",
    "Ranking Frequência",
    "Rastreio Ciclo 3",
]
estrategia_sim_sel = st.sidebar.selectbox(
    "Estratégia da simulação:", _opcoes_sim,
    help="'Aleatório Ponderado' é mais rápido. As demais usam a lógica completa da estratégia."
)
btn_simular = st.sidebar.button("🔬 Iniciar Simulação")

# ── MAIN: Gerar Jogos ─────────────────────────────────────────────────────────
if btn_gerar:
    for _k in ["_sim_media_val", "_sim_estrategia", "_sim_min_acertos", "_jogo_media"]:
        st.session_state.pop(_k, None)

    st.header(f"Resultados: {estrategia} — {qtd_jogos} jogo(s)")

    if acumulada_info > 0:
        st.warning(f"🔥 Lotofácil ACUMULADA há {acumulada_info} concurso(s)!")

    jogos_gerados = []

    if estrategia == "Melhor Jogo (IA)":
        with st.spinner("Analisando todas as estratégias..."):
            jogo_best, nome_best, score_best, ranking = gerar_melhor_jogo_loto(
                frequencia, historico_sets, ultimo_resultado, pool=pool_disponivel
            )
        st.success(f"Melhor estratégia identificada: **{nome_best}** (Score IA: {score_best:.1f})")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(render_volante(jogo_best), unsafe_allow_html=True)
            st.caption(info_jogo(jogo_best))
        with col2:
            st.subheader("Ranking das Estratégias")
            for i, (nome, score) in enumerate(ranking):
                medal = ["🥇", "🥈", "🥉", "4º", "5º"][i]
                st.write(f"{medal} **{nome}** — Score: {score:.1f}")
        jogos_gerados.append(jogo_best)

    elif estrategia == "Fechamento 17 Dezenas (6 Jogos)":
        if len(fixas) != 17:
            st.error("Selecione exatamente 17 dezenas.")
        else:
            fixas_5   = fixas[:5]
            jogos_17  = gerar_fechamento_17_dezenas(fixas[:17], fixas_5)
            cols = st.columns(3)
            for i, jogo in enumerate(jogos_17):
                with cols[i % 3]:
                    st.markdown(f"**Jogo {i + 1}**")
                    st.markdown(render_volante(jogo), unsafe_allow_html=True)
                    st.caption(info_jogo(jogo))
                    st.divider()
                jogos_gerados.append(jogo)

    elif estrategia == "Matriz 13 Fixas (Ouro)":
        if len(fixas) != 13:
            st.error("Selecione exatamente 13 dezenas fixas.")
        else:
            jogos_13 = gerar_fechamento_13_fixas(fixas[:13], list(range(1, 26)))
            cols = st.columns(3)
            for i, jogo in enumerate(jogos_13):
                with cols[i % 3]:
                    st.markdown(f"**Jogo {i + 1}**")
                    st.markdown(render_volante(jogo), unsafe_allow_html=True)
                    st.caption(info_jogo(jogo))
                    st.divider()
                jogos_gerados.append(jogo)

    else:
        cols = st.columns(3)
        for i in range(qtd_jogos):
            with st.spinner(f"Gerando jogo {i + 1}..."):
                jogo = gerar_estrategia_loto(
                    estrategia, frequencia, historico_sets,
                    ultimo_resultado, fixas=fixas, pool=pool_disponivel
                )
            score = pontuar_jogo_loto(jogo, historico_sets, frequencia)
            jogos_gerados.append(jogo)
            with cols[i % 3]:
                st.markdown(f"**Jogo {i + 1}**")
                st.markdown(render_volante(jogo), unsafe_allow_html=True)
                st.caption(info_jogo(jogo))
                st.write(f"Score IA: {score:.1f}")
                st.divider()

    if jogos_gerados:
        df_exp = pd.DataFrame(jogos_gerados)
        csv = df_exp.to_csv(index=False, header=False).encode("utf-8")
        st.download_button("⬇️ Baixar Jogos (CSV)", csv, "jogos_lotofacil.csv", "text/csv")

# ── MAIN: Painel Completo ─────────────────────────────────────────────────────
elif btn_painel:
    for _k in ["_sim_media_val", "_sim_estrategia", "_sim_min_acertos", "_jogo_media"]:
        st.session_state.pop(_k, None)

    st.header("Painel Completo — 1 Jogo por Estratégia")

    if acumulada_info > 0:
        st.warning(f"🔥 Lotofácil ACUMULADA há {acumulada_info} concurso(s)!")

    fixas_auto = auto_fixas_loto(historico_sets) if historico_sets else []
    pool_auto  = auto_pool_loto(historico_sets)  if historico_sets else list(range(1, 21))

    estrategias_painel = [
        ("Inversão Suprema",      [],         ""),
        ("Cercamento 7/8",        [],         ""),
        ("Fixas de Ouro",         fixas_auto, f"Fixas auto: {[f'{n:02d}' for n in fixas_auto]}" if fixas_auto else ""),
        ("Equilíbrio IA 2026",    [],         ""),
        ("Ranking Frequência",    [],         ""),
        ("Fechamento de Dezenas", pool_auto,  f"Pool auto: {len(pool_auto)} dezenas"),
        ("Rastreio Ciclo 3",      [],         ""),
    ]

    painel_jogos = []
    cols = st.columns(3)
    for idx, (nome, params, info_str) in enumerate(estrategias_painel):
        with st.spinner(f"Gerando: {nome}..."):
            jogo = gerar_estrategia_loto(
                nome, frequencia, historico_sets,
                ultimo_resultado, fixas=params, pool=pool_disponivel
            )
        score = pontuar_jogo_loto(jogo, historico_sets, frequencia)
        painel_jogos.append(jogo)
        with cols[idx % 3]:
            st.markdown(f"**{nome}**")
            if info_str:
                st.caption(info_str)
            st.markdown(render_volante(jogo), unsafe_allow_html=True)
            st.caption(info_jogo(jogo))
            st.write(f"Score IA: {score:.1f}")
            st.divider()

    df_exp = pd.DataFrame(painel_jogos)
    csv = df_exp.to_csv(index=False, header=False).encode("utf-8")
    st.download_button("⬇️ Baixar Painel (CSV)", csv, "painel_lotofacil.csv", "text/csv")

# ── MAIN: Simulação ───────────────────────────────────────────────────────────
elif btn_simular:
    if len(resultado_alvo_sim) != 15:
        st.error("Selecione exatamente 15 dezenas como resultado alvo.")
    else:
        alvo_sim = sorted(resultado_alvo_sim)
        st.header(f"🔬 Simulação: {min_acertos_sim}+ acertos em {int(n_ciclos_sim)} ciclos")
        st.caption(f"Estratégia: **{estrategia_sim_sel}**")

        col_info = st.columns(4)
        col_info[0].metric("Resultado alvo", " · ".join(f"{n:02d}" for n in alvo_sim))
        col_info[1].metric("Dezenas por jogo", 15)
        col_info[2].metric("Mínimo de acertos", min_acertos_sim)
        col_info[3].metric("Máx. tentativas/ciclo", f"{int(max_tent_sim):,}")

        try:
            n_alvo    = len(alvo_sim)
            n_fora    = 25 - n_alvo
            favoraveis = sum(
                comb(n_alvo, k) * comb(n_fora, 15 - k)
                for k in range(min_acertos_sim, n_alvo + 1)
            )
            prob     = favoraveis / comb(25, 15)
            esperado = round(1 / prob) if prob > 0 else "∞"
        except Exception:
            prob = 0; esperado = "N/D"

        st.caption(
            f"Probabilidade teórica (uniforme, sem filtros): "
            f"{prob * 100:.4f}% → esperado **~{esperado:,} tentativas** por ciclo."
            if isinstance(esperado, int) else
            "Probabilidade teórica não calculada."
        )

        st.divider()
        progress_bar      = st.progress(0, text="Iniciando...")
        placeholder_tabela = st.empty()

        resultados_sim = []
        for ciclo in range(1, int(n_ciclos_sim) + 1):
            progress_bar.progress(
                (ciclo - 1) / int(n_ciclos_sim),
                text=f"Ciclo {ciclo}/{int(n_ciclos_sim)}..."
            )
            t0 = time.time()
            tentativas, jogo_venc = simular_ate_acertar(
                alvo_sim, min_acertos_sim, frequencia,
                pool_disponivel, int(max_tent_sim),
                historico_sets, ultimo_resultado, estrategia_sim_sel,
            )
            elapsed_ms = round((time.time() - t0) * 1000)

            if jogo_venc:
                acertos  = len(set(jogo_venc) & set(alvo_sim))
                jogo_str = "  ".join(f"{n:02d}" for n in jogo_venc)
                encontrou = "✅"
            else:
                acertos  = 0
                jogo_str = "—"
                encontrou = "❌ limite"

            resultados_sim.append({
                "Ciclo":         ciclo,
                "Tentativas":    tentativas,
                "Resultado":     encontrou,
                "Acertos":       acertos,
                "Jogo vencedor": jogo_str,
                "Tempo (ms)":    elapsed_ms,
            })
            placeholder_tabela.dataframe(
                pd.DataFrame(resultados_sim), use_container_width=True, hide_index=True
            )

        progress_bar.progress(1.0, text="Concluído!")

        # ── Resumo estatístico ───────────────────────────────────────────────
        st.divider()
        st.subheader("Resumo dos Ciclos")

        tent_list   = [r["Tentativas"] for r in resultados_sim if r["Resultado"] == "✅"]
        encontrados = len(tent_list)
        nao_enc     = int(n_ciclos_sim) - encontrados

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Ciclos encontrados", f"{encontrados}/{int(n_ciclos_sim)}")
        if tent_list:
            media_val = sum(tent_list) // len(tent_list)
            c2.metric("Mínimo",  f"{min(tent_list):,}")
            c3.metric("Máximo",  f"{max(tent_list):,}")
            c4.metric("Média",   f"{media_val:,}")
            sorted_t = sorted(tent_list)
            c5.metric("Mediana", f"{sorted_t[len(sorted_t) // 2]:,}")
        if nao_enc:
            st.warning(f"{nao_enc} ciclo(s) atingiram o limite de {int(max_tent_sim):,} tentativas sem acertar.")

        if tent_list and isinstance(esperado, int):
            ratio = (sum(tent_list) / len(tent_list)) / esperado
            st.caption(
                f"**{estrategia_sim_sel}** usou em média **{ratio:.2f}×** o esperado teórico "
                f"({'mais eficiente' if ratio < 1 else 'menos eficiente'} que sorteio uniforme)."
            )

        if tent_list:
            st.session_state["_sim_media_val"]   = media_val
            st.session_state["_sim_estrategia"]  = estrategia_sim_sel
            st.session_state["_sim_min_acertos"] = min_acertos_sim
            st.session_state.pop("_jogo_media", None)

# ── MAIN: Tela inicial ────────────────────────────────────────────────────────
else:
    if "_sim_media_val" not in st.session_state:
        st.info("Configure a estratégia na lateral e clique em 'Gerar Jogos'.")

    if historico_sets and "_sim_media_val" not in st.session_state:
        st.subheader("Resumo do Histórico Carregado")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Concursos", len(historico_sets))
        c2.metric("Mais Sorteado", f"{quentes_global[0]:02d}" if quentes_global else "—")
        n_atras = numeros_atrasados(historico_sets, 1)
        c3.metric("Mais Atrasado", f"{n_atras[0]:02d}" if n_atras else "—")
        if acumulada_info > 0:
            c4.metric("Acumulada", f"{acumulada_info} conc.")
        else:
            c4.metric("Status", "Normal")

    elif "_sim_media_val" not in st.session_state:
        st.markdown("""
        ### Como usar
        1. **Upload**: Arraste o Excel da Lotofácil na lateral esquerda
           *(Colunas: Concurso · Data Sorteio · Bola1–Bola15 · Ganhadores 15 acertos)*
        2. **Configure**: Escolha a quantidade de jogos e exclua números se desejar
        3. **Estratégia**: Selecione a lógica de geração desejada
        4. **Gere**: Clique em **Gerar Jogos** ou **Painel Completo**

        ### Filtros aplicados automaticamente
        | Filtro | Regra |
        |--------|-------|
        | Soma | Entre 180 e 220 |
        | Sequência | No máximo 4 números consecutivos |
        | Ineditismo | Sem 14+ dezenas em comum com qualquer resultado histórico |
        """)

# ── JOGO DA MÉDIA ──────────────────────────────────────────────────────────────
if "_sim_media_val" in st.session_state and historico_sets:
    _mv   = st.session_state["_sim_media_val"]
    _est  = st.session_state["_sim_estrategia"]
    _meta = st.session_state["_sim_min_acertos"]
    _cap  = min(_mv, 5_000)

    st.divider()
    st.subheader("🎯 Jogo da Média")
    st.caption(
        f"Estratégia **{_est}** encontra {_meta}+ acertos em média a cada **{_mv:,} jogos**."
        + (f" *(limitado a {_cap:,} para não travar a interface)*" if _cap < _mv else "")
    )

    if st.button(f"Gerar jogo #{_cap:,}", key="btn_jogo_media"):
        _est_uso = _est if _est != "Aleatório Ponderado (Rápido)" else "Inversão Suprema"
        with st.spinner(f"Gerando {_cap:,} jogos com {_est_uso}..."):
            _jogo = None
            for _ in range(_cap):
                _jogo = gerar_estrategia_loto(
                    _est_uso, frequencia,
                    historico_sets=[],       # ineditismo desabilitado para performance
                    ultimo=ultimo_resultado,
                    pool=pool_disponivel,
                )
        st.session_state["_jogo_media"] = _jogo

    if st.session_state.get("_jogo_media"):
        _jm = st.session_state["_jogo_media"]
        st.success(f"Jogo da posição **#{_cap:,}**: {' · '.join(f'{n:02d}' for n in _jm)}")
        st.markdown(render_volante(_jm), unsafe_allow_html=True)
        st.caption(info_jogo(_jm))

# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Aviso: Este software é uma ferramenta de análise estatística. "
    "Loterias são jogos de azar e não há garantia de lucro. Jogue com responsabilidade."
)
