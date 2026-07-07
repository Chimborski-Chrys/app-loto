import streamlit as st
import pandas as pd
import random
import time
import io
from collections import Counter
from math import comb
from itertools import combinations
from openpyxl import Workbook
from openpyxl.styles import PatternFill

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
MOLDURA = {1, 2, 3, 4, 5, 6, 10, 11, 15, 16, 20, 21, 22, 23, 24, 25}
LINHAS_GRID  = [set(range(1 + 5 * i, 6 + 5 * i)) for i in range(5)]
COLUNAS_GRID = [set(range(1 + i, 26, 5)) for i in range(5)]
DIAG_PRINCIPAL  = {1, 7, 13, 19, 25}
DIAG_SECUNDARIA = {5, 9, 13, 17, 21}

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

def validar_curva_acertos(jogo, historico_sets, janela=30):
    """Indicador informativo (não é filtro de geração): média de acertos do jogo
    contra os últimos `janela` concursos. Pela distribuição hipergeométrica, a
    média esperada de qualquer combinação de 15 dezenas contra o histórico é ~9,
    com baixíssima variância — isto é, quase todo jogo cai nessa faixa, o que é
    comportamento estatístico normal e não prediz o resultado do próximo sorteio
    (concursos são eventos independentes)."""
    if not historico_sets:
        return True
    recentes = historico_sets[-janela:] if len(historico_sets) >= janela else historico_sets
    if not recentes:
        return True
    js = set(jogo)
    media = sum(len(js & h) for h in recentes) / len(recentes)
    return round(media) not in (8, 9, 10)

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

# (fechamentos heurísticos antigos substituídos por gerar_fechamento_garantido)

# ── ANTI-POPULARIDADE ──────────────────────────────────────────────────────────
def indice_popularidade(jogo, historico_sets=None):
    """Penalidade por padrões que multidões costumam jogar (menor = melhor).
    Não muda a chance de acertar — reduz a divisão do prêmio em caso de acerto."""
    js = set(jogo)
    pen = 0
    motivos = []

    # Sequências longas (1-2-3-4-5...)
    s = sorted(jogo)
    run = melhor_run = 1
    for i in range(len(s) - 1):
        run = run + 1 if s[i] + 1 == s[i + 1] else 1
        melhor_run = max(melhor_run, run)
    if melhor_run >= 6:
        pen += 30; motivos.append(f"{melhor_run} consecutivos")
    elif melhor_run == 5:
        pen += 15; motivos.append("5 consecutivos")

    # Padrões geométricos no volante
    for i, ln in enumerate(LINHAS_GRID):
        if ln <= js:
            pen += 25; motivos.append(f"linha {i + 1} completa")
    for i, cl in enumerate(COLUNAS_GRID):
        if cl <= js:
            pen += 25; motivos.append(f"coluna {i + 1} completa")
    if DIAG_PRINCIPAL <= js and DIAG_SECUNDARIA <= js:
        pen += 20; motivos.append("X (diagonais) completo")

    # Viés de datas/aniversários (concentração em 1–12)
    baixos = sum(1 for n in jogo if n <= 12)
    if baixos >= 10:
        pen += 20; motivos.append(f"{baixos} dezenas ≤ 12 (viés de datas)")

    # Moldura extrema (padrão visual muito jogado)
    m = len(js & MOLDURA)
    if m >= 14 or m <= 5:
        pen += 15; motivos.append(f"moldura {m}/16")

    # Repetição de resultado já sorteado (muita gente repete)
    if historico_sets and any(len(js & h) >= 14 for h in historico_sets):
        pen += 25; motivos.append("≈ resultado já sorteado")

    return pen, motivos

def gerar_anti_popular(historico_sets, pool=None, tentativas=400):
    """Gera jogo válido minimizando o índice de popularidade."""
    p = pool if pool is not None else TODAS
    p_list = sorted(p)
    if len(p_list) < 15:
        return p_list
    melhor_j, melhor_pen = None, float("inf")
    for _ in range(tentativas):
        j = sorted(random.sample(p_list, 15))
        if not (validar_soma(j) and validar_sequencia(j)):
            continue
        if not validar_ineditismo(j, historico_sets):
            continue
        pen, _ = indice_popularidade(j)
        if pen < melhor_pen:
            melhor_pen, melhor_j = pen, j
            if pen == 0:
                break
    return melhor_j if melhor_j else _fallback(historico_sets, pool=p)

# ── FECHAMENTO GARANTIDO (COBERTURA) ───────────────────────────────────────────
def gerar_fechamento_garantido(pool_dez, garantia=14, max_jogos=60):
    """Set cover guloso: se as 15 sorteadas estiverem dentro do pool,
    pelo menos um jogo terá >= `garantia` acertos. Garantia verificada."""
    pool_dez = sorted(pool_dez)
    alvos = [frozenset(c) for c in combinations(pool_dez, 15)]
    nao_cobertos = set(range(len(alvos)))
    jogos = []
    while nao_cobertos and len(jogos) < max_jogos:
        candidatos = alvos if len(alvos) <= 1500 else random.sample(alvos, 1500)
        melhor, cobre_melhor = None, set()
        for cand in candidatos:
            cobre = {i for i in nao_cobertos if len(cand & alvos[i]) >= garantia}
            if len(cobre) > len(cobre_melhor):
                melhor, cobre_melhor = cand, cobre
        if not cobre_melhor:
            break
        jogos.append(sorted(melhor))
        nao_cobertos -= cobre_melhor
    return jogos, len(nao_cobertos) == 0


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
    elif tipo == "Anti-Popular":
        return gerar_anti_popular(historico_sets, pool=p)
    return _fallback(historico_sets, pool=p)

# ── JOGO MÚLTIPLO ───────────────────────────────────────────────────────────────
ESTRATEGIAS_MULTIPLO = [
    "Anti-Popular",
    "Inversão Suprema",
    "Cercamento 7/8",
    "Equilíbrio IA 2026",
    "Ranking Frequência",
    "Rastreio Ciclo 3",
]

CORES_ESTRATEGIA = {
    "Anti-Popular":         "FFD6D6",
    "Inversão Suprema":     "D6E6FF",
    "Cercamento 7/8":       "D6FFDA",
    "Equilíbrio IA 2026":   "FFF3D6",
    "Ranking Frequência":   "EAD6FF",
    "Rastreio Ciclo 3":     "D6FFF6",
}

def gerar_jogo_multiplo(qtd_por_estrategia, frequencia, historico_sets, ultimo, pool=None):
    """Gera `qtd_por_estrategia` jogos de CADA uma das 6 estratégias principais,
    em blocos agrupados (todos os jogos de uma estratégia antes de passar para a
    próxima — sem intercalar). Total de jogos = qtd_por_estrategia * 6.
    Cada jogo é validado contra o histórico + os jogos já gerados neste lote
    (evita repetir a mesma combinação dentro do próprio múltiplo)."""
    jogos = []
    sets_lote = list(historico_sets)
    for tipo in ESTRATEGIAS_MULTIPLO:
        for _ in range(qtd_por_estrategia):
            jogo = None
            for _ in range(20):
                candidato = gerar_estrategia_loto(tipo, frequencia, historico_sets, ultimo, pool=pool)
                if validar_ineditismo(candidato, sets_lote):
                    jogo = candidato
                    break
            if jogo is None:
                jogo = candidato
            sets_lote.append(set(jogo))
            jogos.append((jogo, tipo))
    return jogos

def exportar_multiplo_xlsx(resultado_multiplo):
    """Monta um .xlsx com uma linha por jogo, coluna 'Estrategia' e cor de
    fundo diferente por estratégia (CSV puro não suporta cor de célula)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Jogo Multiplo"
    ws.append([f"Bola{i}" for i in range(1, 16)] + ["Estrategia"])
    for jogo, tipo in resultado_multiplo:
        ws.append(list(jogo) + [tipo])
        fill = PatternFill(start_color=CORES_ESTRATEGIA.get(tipo, "FFFFFF"),
                            end_color=CORES_ESTRATEGIA.get(tipo, "FFFFFF"),
                            fill_type="solid")
        for cell in ws[ws.max_row]:
            cell.fill = fill
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

# ── PONTUAÇÃO (popularidade — menor é melhor) ──────────────────────────────────
def pontuar_jogo_loto(jogo, historico_sets, frequencia):
    pen, _ = indice_popularidade(jogo, historico_sets)
    return float(pen)

# ── MELHOR JOGO (menor popularidade) ───────────────────────────────────────────
def gerar_melhor_jogo_loto(frequencia, historico_sets, ultimo, pool=None):
    candidatos_est = [
        "Anti-Popular",
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
    candidatos.sort(key=lambda x: x[2])  # menor popularidade primeiro
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
    n_mold  = len(set(jogo) & MOLDURA)
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

qtd_jogos = st.sidebar.slider(
    "Quantidade de jogos", min_value=1, max_value=50, value=5,
    help="Em 'Jogo Múltiplo (6 Estratégias)' este valor é por estratégia (total = valor × 6)."
)

# ── Sidebar 3: Estratégia ─────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("3. Escolher Estratégia")

estrategia = st.sidebar.selectbox("Estratégia", [
    "Anti-Popular (Recomendado)",
    "Melhor Jogo (IA)",
    "Jogo Múltiplo (6 Estratégias)",
    "Inversão Suprema",
    "Cercamento 7/8",
    "Fixas de Ouro",
    "Equilíbrio IA 2026",
    "Ranking Frequência",
    "Fechamento de Dezenas",
    "Fechamento Garantido (Cobertura)",
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

elif estrategia == "Fechamento Garantido (Cobertura)":
    st.sidebar.markdown("**Pool do fechamento (16 a 18 dezenas)**")
    st.sidebar.caption(
        "Garantia matemática: se as 15 sorteadas estiverem no pool, "
        "ao menos um jogo terá o mínimo de acertos escolhido."
    )
    fixas = st.sidebar.multiselect(
        "Pool:", options=list(range(1, 26)), default=list(range(1, 17)),
        format_func=lambda x: f"{x:02d}"
    )
    garantia_fech = st.sidebar.slider("Garantia mínima de acertos", 13, 14, 14)
    if not 16 <= len(fixas) <= 18:
        st.sidebar.error("Selecione entre 16 e 18 dezenas.")

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
    "Anti-Popular",
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

    estrategia_exec = "Anti-Popular" if estrategia.startswith("Anti-Popular") else estrategia

    if estrategia == "Jogo Múltiplo (6 Estratégias)":
        _total_multiplo = qtd_jogos * len(ESTRATEGIAS_MULTIPLO)
        st.header(f"Resultados: {estrategia} — {qtd_jogos} por estratégia ({_total_multiplo} no total)")
    else:
        st.header(f"Resultados: {estrategia} — {qtd_jogos} jogo(s)")

    if acumulada_info > 0:
        st.warning(f"🔥 Lotofácil ACUMULADA há {acumulada_info} concurso(s)!")

    jogos_gerados = []

    if estrategia == "Melhor Jogo (IA)":
        with st.spinner("Analisando todas as estratégias..."):
            jogo_best, nome_best, score_best, ranking = gerar_melhor_jogo_loto(
                frequencia, historico_sets, ultimo_resultado, pool=pool_disponivel
            )
        st.success(f"Menor popularidade: **{nome_best}** (Índice: {score_best:.0f})")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(render_volante(jogo_best), unsafe_allow_html=True)
            st.caption(info_jogo(jogo_best))
        with col2:
            st.subheader("Ranking por Popularidade (menor = melhor)")
            medals = ["🥇", "🥈", "🥉"]
            for i, (nome, score) in enumerate(ranking):
                medal = medals[i] if i < 3 else f"{i + 1}º"
                st.write(f"{medal} **{nome}** — Índice: {score:.0f}")
        jogos_gerados.append(jogo_best)

    elif estrategia == "Jogo Múltiplo (6 Estratégias)":
        _total_multiplo = qtd_jogos * len(ESTRATEGIAS_MULTIPLO)
        if _total_multiplo > 90:
            st.warning(f"{_total_multiplo} jogos no total — geração/renderização pode demorar.")
        with st.spinner(f"Gerando {qtd_jogos} jogo(s) de cada uma das 6 estratégias ({_total_multiplo} no total)..."):
            resultado_multiplo = gerar_jogo_multiplo(
                qtd_jogos, frequencia, historico_sets, ultimo_resultado, pool=pool_disponivel
            )
        st.caption(
            f"Blocos agrupados (sem intercalar), {qtd_jogos} por estratégia: "
            "Anti-Popular → Inversão Suprema → Cercamento 7/8 → Equilíbrio IA 2026 → Ranking Frequência → Rastreio Ciclo 3"
        )
        _tipo_atual = None
        cols = st.columns(3)
        for i, (jogo, tipo) in enumerate(resultado_multiplo):
            if tipo != _tipo_atual:
                st.subheader(tipo)
                cols = st.columns(3)
                _tipo_atual = tipo
                _idx_bloco = 0
            pop, motivos = indice_popularidade(jogo, historico_sets)
            curva_segura = validar_curva_acertos(jogo, historico_sets)
            jogos_gerados.append(jogo)
            with cols[_idx_bloco % 3]:
                st.markdown(f"**Jogo {_idx_bloco + 1}**")
                st.markdown(render_volante(jogo), unsafe_allow_html=True)
                st.caption(info_jogo(jogo))
                st.write(f"Popularidade: {pop:.0f} (menor = melhor)")
                if motivos:
                    st.caption("⚠️ " + "; ".join(motivos))
                st.caption(
                    f"Distopia de Acertos: {'Foge dos 79% (Seguro)' if curva_segura else 'Risco de 8-10 pontos'} "
                    "*(indicador estatístico, não altera a chance real — sorteios são independentes)*"
                )
                st.divider()
            _idx_bloco += 1

        xlsx_bytes = exportar_multiplo_xlsx(resultado_multiplo)
        st.download_button(
            "⬇️ Baixar Jogo Múltiplo (Excel colorido por estratégia)",
            xlsx_bytes,
            "jogo_multiplo_lotofacil.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    elif estrategia == "Fechamento Garantido (Cobertura)":
        if not 16 <= len(fixas) <= 18:
            st.error("Selecione entre 16 e 18 dezenas para o pool.")
        else:
            with st.spinner("Calculando cobertura mínima (set cover guloso)..."):
                jogos_fech, garantido = gerar_fechamento_garantido(fixas, garantia_fech)
            if garantido:
                st.success(
                    f"✅ Garantia verificada: {len(jogos_fech)} jogos cobrem "
                    f"{garantia_fech}+ acertos se as 15 sorteadas estiverem no pool de {len(fixas)}."
                )
            else:
                st.warning("Cobertura parcial — aumente o limite de jogos ou reduza a garantia.")
            custo = len(jogos_fech) * 3.50
            st.caption(f"Custo estimado: {len(jogos_fech)} jogos × R$ 3,50 = R$ {custo:.2f}")
            cols = st.columns(3)
            for i, jogo in enumerate(jogos_fech):
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
                    estrategia_exec, frequencia, historico_sets,
                    ultimo_resultado, fixas=fixas, pool=pool_disponivel
                )
            pop, motivos = indice_popularidade(jogo, historico_sets)
            curva_segura = validar_curva_acertos(jogo, historico_sets)
            jogos_gerados.append(jogo)
            with cols[i % 3]:
                st.markdown(f"**Jogo {i + 1}**")
                st.markdown(render_volante(jogo), unsafe_allow_html=True)
                st.caption(info_jogo(jogo))
                st.write(f"Popularidade: {pop:.0f} (menor = melhor)")
                if motivos:
                    st.caption("⚠️ " + "; ".join(motivos))
                st.caption(
                    f"Distopia de Acertos: {'Foge dos 79% (Seguro)' if curva_segura else 'Risco de 8-10 pontos'} "
                    "*(indicador estatístico, não altera a chance real — sorteios são independentes)*"
                )
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
        ("Anti-Popular",          [],         "Minimiza divisão do prêmio"),
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
        pop, motivos = indice_popularidade(jogo, historico_sets)
        curva_segura = validar_curva_acertos(jogo, historico_sets)
        painel_jogos.append(jogo)
        with cols[idx % 3]:
            st.markdown(f"**{nome}**")
            if info_str:
                st.caption(info_str)
            st.markdown(render_volante(jogo), unsafe_allow_html=True)
            st.caption(info_jogo(jogo))
            st.write(f"Popularidade: {pop:.0f} (menor = melhor)")
            if motivos:
                st.caption("⚠️ " + "; ".join(motivos))
            st.caption(
                f"Distopia de Acertos: {'Foge dos 79% (Seguro)' if curva_segura else 'Risco de 8-10 pontos'} "
                "*(indicador estatístico, não altera a chance real — sorteios são independentes)*"
            )
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