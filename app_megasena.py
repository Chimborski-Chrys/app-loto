import streamlit as st
import pandas as pd
import random
from itertools import combinations
from math import comb
from collections import Counter
from decimal import Decimal, getcontext

st.set_page_config(page_title="Mega Sena Pro — Engenharia de Dados", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #009640; color: white; }
    .volante-mega { display: grid; grid-template-columns: repeat(10, 1fr); gap: 4px; max-width: 460px; margin: auto; }
    .dezena { border: 1px solid #444; padding: 4px; text-align: center; border-radius: 50%;
              width: 36px; height: 36px; line-height: 26px; font-size: 11px; }
    .selecionada { background-color: #009640; color: white; border: none; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

TODAS = set(range(1, 61))
QUADRANTES = [
    set(range(1, 16)),   # Q1: 01–15
    set(range(16, 31)),  # Q2: 16–30
    set(range(31, 46)),  # Q3: 31–45
    set(range(46, 61)),  # Q4: 46–60
]


# ── ANÁLISE ────────────────────────────────────────────────────────────────────

def calcular_frequencia(historico_sets):
    freq = {i: 0 for i in range(1, 61)}
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
    ultimo_idx = {i: -1 for i in range(1, 61)}
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
    """Conta concursos consecutivos com 0 ganhadores ao final da lista."""
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


# ── VALIDAÇÃO ──────────────────────────────────────────────────────────────────

def validar_soma(jogo):
    """Soma proporcional: base 150–220 para 6 dezenas, escala para N."""
    n = len(jogo)
    lower = round(150 * n / 6)
    upper = round(220 * n / 6)
    return lower <= sum(jogo) <= upper


def validar_paridade(jogo):
    """Pares entre 25% e 70% do total de dezenas."""
    n = len(jogo)
    pares = sum(1 for x in jogo if x % 2 == 0)
    return round(n * 0.25) <= pares <= round(n * 0.70)


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


def validar_quentes(jogo, quentes):
    """Pelo menos 1 número do top-10 histórico."""
    if not quentes:
        return True
    return len(set(jogo) & set(quentes)) >= 1


def validar_ineditismo(jogo, historico_sets):
    """Jogo não pode ter 5 ou mais dezenas em comum com qualquer resultado histórico."""
    jogo_set = set(jogo)
    for h in historico_sets:
        if len(jogo_set & h) >= 5:
            return False
    return True


def validar_quadrantes(jogo):
    """Dezenas distribuídas em pelo menos 3 dos 4 quadrantes do volante."""
    jogo_set = set(jogo)
    return sum(1 for q in QUADRANTES if jogo_set & q) >= 3


def validar_jogo_mega(jogo, historico_sets, quentes):
    return (
        validar_soma(jogo)
        and validar_paridade(jogo)
        and validar_sequencia(jogo)
        and validar_finais(jogo)
        and validar_quentes(jogo, quentes)
        and validar_ineditismo(jogo, historico_sets)
        and validar_quadrantes(jogo)
    )


# ── GERAÇÃO ────────────────────────────────────────────────────────────────────

def _completar_jogo(dezenas, n_numeros, pool=None):
    """Preenche o jogo até n_numeros com dezenas aleatórias do pool restante."""
    p = pool if pool is not None else TODAS
    restante = list(p - dezenas)
    faltam = n_numeros - len(dezenas)
    if faltam > 0 and len(restante) >= faltam:
        dezenas.update(random.sample(restante, faltam))
    return dezenas


def _fallback(n_numeros, historico_sets, quentes, pool=None):
    """Geração aleatória pura com filtros mínimos (soma + ineditismo)."""
    p = list(pool if pool is not None else TODAS)
    if len(p) < n_numeros:
        return sorted(random.sample(p, len(p)))
    for _ in range(5000):
        jogo = sorted(random.sample(p, n_numeros))
        if validar_soma(jogo) and validar_ineditismo(jogo, historico_sets):
            return jogo
    return sorted(random.sample(p, n_numeros))


def gerar_frequencia_tendencia(n_numeros, historico_sets, quentes, frequencia, pool=None):
    """
    Mistura números quentes históricos (~35%), tendência recente (~30%)
    e 1 número frio estratégico, completando com aleatório.
    """
    p = pool if pool is not None else TODAS
    atrasados = [n for n in numeros_atrasados(historico_sets, 15) if n in p] if historico_sets else sorted(p)[:15]
    tendentes  = [n for n in tendencia_recente(historico_sets, 20)  if n in p] if historico_sets else sorted(p)[:15]
    quentes_p  = [n for n in quentes if n in p]

    for _ in range(2000):
        dezenas = set()

        n_q = max(1, round(n_numeros * 0.35))
        dezenas.update(random.sample(quentes_p, min(n_q, len(quentes_p))))

        n_t = max(1, round(n_numeros * 0.30))
        disp_tend = [x for x in tendentes if x not in dezenas]
        dezenas.update(random.sample(disp_tend, min(n_t, len(disp_tend))))

        disp_frios = [x for x in atrasados if x not in dezenas]
        if disp_frios:
            dezenas.add(random.choice(disp_frios))

        dezenas = _completar_jogo(dezenas, n_numeros, pool=p)
        jogo = sorted(dezenas)
        if len(jogo) == n_numeros and validar_jogo_mega(jogo, historico_sets, quentes_p):
            return jogo

    return _fallback(n_numeros, historico_sets, quentes_p, pool=p)


def gerar_equilibrio_volante(n_numeros, historico_sets, quentes, pool=None):
    """
    Garante ao menos 1 dezena por quadrante e preenche priorizando
    equilíbrio de paridade e distribuição espacial.
    """
    p = pool if pool is not None else TODAS
    quads_disp = [list(q & p) for q in QUADRANTES if q & p]

    for _ in range(2000):
        dezenas = set()
        for q in quads_disp:
            dezenas.add(random.choice(q))
        dezenas = _completar_jogo(dezenas, n_numeros, pool=p)
        jogo = sorted(dezenas)
        if len(jogo) == n_numeros and validar_jogo_mega(jogo, historico_sets, quentes):
            return jogo
    return _fallback(n_numeros, historico_sets, quentes, pool=p)


def gerar_numeros_atrasados(n_numeros, historico_sets, quentes, pool=None):
    """
    Prioriza dezenas que não saem há mais concursos (~50%) e
    adiciona pelo menos 1 número quente para passar no filtro.
    """
    p = pool if pool is not None else TODAS
    atrasados = [n for n in numeros_atrasados(historico_sets, 20) if n in p] if historico_sets else sorted(p)[:20]
    quentes_p = [n for n in quentes if n in p]

    for _ in range(2000):
        dezenas = set()
        n_a = max(2, round(n_numeros * 0.50))
        dezenas.update(random.sample(atrasados, min(n_a, len(atrasados))))

        disp_q = [x for x in quentes_p if x not in dezenas]
        if disp_q:
            dezenas.add(random.choice(disp_q))

        dezenas = _completar_jogo(dezenas, n_numeros, pool=p)
        jogo = sorted(dezenas)
        if len(jogo) == n_numeros and validar_jogo_mega(jogo, historico_sets, quentes_p):
            return jogo
    return _fallback(n_numeros, historico_sets, quentes_p, pool=p)


def gerar_fixas_ouro(n_numeros, historico_sets, quentes, fixas, pool=None):
    """Mantém as dezenas fixas e preenche o restante com filtros aplicados."""
    p = pool if pool is not None else TODAS
    fixas_validas = [f for f in fixas if f in p]  # ignora fixas excluídas do pool
    for _ in range(2000):
        dezenas = set(fixas_validas)
        dezenas = _completar_jogo(dezenas, n_numeros, pool=p)
        jogo = sorted(dezenas)
        if len(jogo) == n_numeros and validar_jogo_mega(jogo, historico_sets, quentes):
            return jogo
    return _fallback(n_numeros, historico_sets, quentes, pool=p)


def gerar_tecnica_z(n_numeros, historico_sets, quentes, pool=None):
    """
    Técnica do Z: soma as dezenas do último resultado, usa o último dígito
    como offset e seleciona candidatos ao longo do padrão Z no volante
    (linha superior 01–10, diagonal 10→55, linha inferior 51–60).
    """
    p = pool if pool is not None else TODAS
    if not historico_sets:
        return _fallback(n_numeros, historico_sets, quentes, pool=p)

    ultimo = sorted(historico_sets[-1])
    soma = sum(ultimo)
    offset = soma % 10

    linha_top = list(range(1, 11))
    diagonal  = [10 - i + i * 10 for i in range(6)]
    linha_bot = list(range(51, 61))
    pool_z = set(linha_top + diagonal + linha_bot)

    pool_expandido = set()
    for n in pool_z:
        for delta in (-offset, 0, offset):
            novo = n + delta
            if 1 <= novo <= 60:
                pool_expandido.add(novo)

    candidatos = sorted(pool_expandido & p)  # respeita exclusões

    for _ in range(2000):
        dezenas = set()
        n_z = max(2, round(n_numeros * 0.6))
        dezenas.update(random.sample(candidatos, min(n_z, len(candidatos))))
        dezenas = _completar_jogo(dezenas, n_numeros, pool=p)
        jogo = sorted(dezenas)
        if len(jogo) == n_numeros and validar_jogo_mega(jogo, historico_sets, quentes):
            return jogo

    return _fallback(n_numeros, historico_sets, quentes, pool=p)


def gerar_tecnica_mais_menos_3(n_numeros, historico_sets, quentes, num_proximo_concurso, pool=None):
    """
    Técnica +3/-3: concatena as dezenas do último resultado como string,
    divide pelo número do próximo concurso com alta precisão e extrai pares
    de dígitos 01–60 da dízima resultante.
    Variações: original, cada dezena +3, cada dezena -3.
    """
    p = pool if pool is not None else TODAS
    if not historico_sets or num_proximo_concurso <= 0:
        return _fallback(n_numeros, historico_sets, quentes, pool=p)

    getcontext().prec = 60
    ultimo = sorted(historico_sets[-1])

    def _extrair(dezenas_seq):
        seq = ''.join(f'{n:02d}' for n in dezenas_seq)
        try:
            resultado = str(Decimal(seq) / Decimal(str(num_proximo_concurso)))
        except Exception:
            return []
        digitos = resultado.replace('.', '').replace('-', '').lstrip('0') or '0'
        encontrados = []
        for i in range(len(digitos) - 1):
            par = int(digitos[i:i + 2])
            if 1 <= par <= 60:
                encontrados.append(par)
        return encontrados

    candidatos = set()
    candidatos.update(_extrair(ultimo))
    candidatos.update(_extrair([min(60, n + 3) for n in ultimo]))
    candidatos.update(_extrair([max(1,  n - 3) for n in ultimo]))
    candidatos &= p  # respeita exclusões

    candidatos_lista = sorted(candidatos)

    for _ in range(2000):
        dezenas = set()
        if len(candidatos_lista) >= round(n_numeros * 0.5):
            n_c = round(n_numeros * 0.5)
            dezenas.update(random.sample(candidatos_lista, min(n_c, len(candidatos_lista))))
        elif candidatos_lista:
            dezenas.update(candidatos_lista)
        dezenas = _completar_jogo(dezenas, n_numeros, pool=p)
        jogo = sorted(dezenas)
        if len(jogo) == n_numeros and validar_jogo_mega(jogo, historico_sets, quentes):
            return jogo

    return _fallback(n_numeros, historico_sets, quentes, pool=p)


def gerar_estrategia_mega(tipo, n_numeros, frequencia, historico_sets, quentes,
                          fixas=None, num_concurso=None, pool=None):
    if fixas is None:
        fixas = []
    p = pool  # None → cada sub-função usa TODAS como default
    if tipo == "Frequência e Tendência":
        return gerar_frequencia_tendencia(n_numeros, historico_sets, quentes, frequencia, pool=p)
    elif tipo == "Equilíbrio do Volante":
        return gerar_equilibrio_volante(n_numeros, historico_sets, quentes, pool=p)
    elif tipo == "Números Atrasados":
        return gerar_numeros_atrasados(n_numeros, historico_sets, quentes, pool=p)
    elif tipo == "Fixas de Ouro":
        return gerar_fixas_ouro(n_numeros, historico_sets, quentes, fixas, pool=p)
    elif tipo == "Técnica do Z":
        return gerar_tecnica_z(n_numeros, historico_sets, quentes, pool=p)
    elif tipo == "Técnica +3/-3":
        return gerar_tecnica_mais_menos_3(n_numeros, historico_sets, quentes, num_concurso or 1, pool=p)
    return _fallback(n_numeros, historico_sets, quentes, pool=p)


def gerar_melhor_jogo(n_numeros, frequencia, historico_sets, quentes,
                      num_concurso=1, pool=None):
    """
    Executa todas as estratégias e devolve a de maior score.
    Retorna (jogo, nome_estrategia, score, ranking_completo).
    """
    candidatos = [
        ("Frequência e Tendência", {}),
        ("Equilíbrio do Volante",  {}),
        ("Números Atrasados",      {}),
        ("Técnica do Z",           {}),
        ("Técnica +3/-3",          {"num_concurso": num_concurso}),
    ]

    ranking = []
    for nome, kwargs in candidatos:
        jogo = gerar_estrategia_mega(
            nome, n_numeros, frequencia, historico_sets, quentes,
            pool=pool, **kwargs
        )
        score = pontuar_jogo_mega(jogo, historico_sets, quentes, frequencia)
        ranking.append({"nome": nome, "jogo": jogo, "score": score})

    ranking.sort(key=lambda x: x["score"], reverse=True)
    vencedor = ranking[0]
    return vencedor["jogo"], vencedor["nome"], vencedor["score"], ranking


def gerar_desdobramento(pool, n_numeros, historico_sets, quentes, max_jogos, excluidos=None):
    """
    Gera até max_jogos combinações válidas a partir do pool.
    Para pools grandes (> 50k combinações) usa amostragem aleatória.
    """
    pool = [n for n in pool if n not in (excluidos or [])]  # respeita exclusões
    total = comb(len(pool), n_numeros)
    jogos_validos = []
    seen = set()

    if total <= 50000:
        todas = list(combinations(sorted(pool), n_numeros))
        random.shuffle(todas)
        for combo in todas:
            if validar_jogo_mega(list(combo), historico_sets, quentes):
                jogos_validos.append(sorted(combo))
            if len(jogos_validos) >= max_jogos:
                break
    else:
        tentativas = 0
        while len(jogos_validos) < max_jogos and tentativas < 20000:
            tentativas += 1
            combo = tuple(sorted(random.sample(pool, n_numeros)))
            if combo not in seen:
                seen.add(combo)
                if validar_jogo_mega(list(combo), historico_sets, quentes):
                    jogos_validos.append(sorted(combo))

    return jogos_validos


def auto_fixas_mega(historico_sets, max_fixas=4):
    """Dezenas presentes em ≥60% dos últimos 10 concursos (máx max_fixas)."""
    ultimos = historico_sets[-10:] if len(historico_sets) >= 10 else historico_sets
    contagem = Counter()
    for s in ultimos:
        contagem.update(s)
    threshold = max(1, round(len(ultimos) * 0.6))
    fixas = sorted(n for n, c in contagem.items() if c >= threshold)
    if not fixas:
        fixas = [n for n, _ in contagem.most_common(3)]
    return sorted(fixas)[:max_fixas]


def auto_pool_mega(historico_sets, frequencia, tamanho=15):
    """Top dezenas mais frequentes nos últimos 10 concursos para formar o pool."""
    ultimos = historico_sets[-10:] if len(historico_sets) >= 10 else historico_sets
    freq_rec = Counter()
    for s in ultimos:
        freq_rec.update(s)
    pool = [n for n, _ in freq_rec.most_common(tamanho)]
    # Garante mínimo de tamanho usando frequência geral como fallback
    if len(pool) < tamanho:
        for n, _ in sorted(frequencia.items(), key=lambda x: x[1], reverse=True):
            if n not in pool:
                pool.append(n)
            if len(pool) >= tamanho:
                break
    return sorted(pool[:tamanho])


def pontuar_jogo_mega(jogo, historico_sets, quentes, frequencia):
    if not historico_sets:
        return 0.0
    jogo_set = set(jogo)
    acertos_med = sum(len(jogo_set & h) for h in historico_sets) / len(historico_sets)
    score_quentes = len(jogo_set & set(quentes)) * 10
    score_quad = sum(1 for q in QUADRANTES if jogo_set & q) * 15
    pares = sum(1 for n in jogo if n % 2 == 0)
    score_par = 20 if abs(pares - len(jogo) / 2) <= 1 else 0
    return round(acertos_med * 10 + score_quentes + score_quad + score_par, 2)


# ── RENDER ─────────────────────────────────────────────────────────────────────

def render_volante_mega(jogo):
    jogo_set = set(jogo)
    html = '<div class="volante-mega">'
    for n in range(1, 61):
        classe = "dezena selecionada" if n in jogo_set else "dezena"
        html += f'<div class="{classe}">{n:02d}</div>'
    html += '</div>'
    return html


def info_jogo(jogo, quentes):
    pares = sum(1 for x in jogo if x % 2 == 0)
    impares = len(jogo) - pares
    soma = sum(jogo)
    quads = sum(1 for q in QUADRANTES if set(jogo) & q)
    n_q = len(set(jogo) & set(quentes))
    return f"Soma: {soma} | Par/Ímpar: {pares}/{impares} | Quadrantes: {quads}/4 | Quentes: {n_q}"


# ── INTERFACE ──────────────────────────────────────────────────────────────────

st.title("🎰 Mega Sena Pro — Engenharia de Dados & IA")

st.sidebar.header("1. Upload de Dados")
file = st.sidebar.file_uploader(
    "Arraste o Excel da Caixa (Mega-Sena)",
    type=["xlsx"],
    help="Colunas esperadas: A=Concurso, B=Data, C–H=6 dezenas, I=Ganhadores"
)

historico_sets = []
frequencia = {i: 0 for i in range(1, 61)}
quentes_global = []
acumulada_info = 0
proximo_concurso = 1  # inferido ao carregar o Excel

if file:
    try:
        df = pd.read_excel(file, header=0)
        if df.shape[1] < 8:
            st.sidebar.error("Arquivo precisa de pelo menos 8 colunas (Concurso, Data + 6 dezenas).")
        else:
            cols_bolas = df.iloc[:, 2:8]
            for _, row in cols_bolas.iterrows():
                try:
                    nums = set(int(x) for x in row if pd.notna(x) and 1 <= int(x) <= 60)
                    if len(nums) == 6:
                        historico_sets.append(nums)
                except (ValueError, TypeError):
                    pass

            frequencia = calcular_frequencia(historico_sets)
            quentes_global = top_quentes(frequencia, 10)

            if df.shape[1] >= 9:
                acumulada_info = detectar_acumulada(df.iloc[:, 8])

            st.sidebar.success(f"✅ {len(historico_sets)} concursos carregados!")
            # Infere o número do próximo concurso a partir da coluna A
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
st.sidebar.header("2. Configurar Jogo")

n_numeros = st.sidebar.slider(
    "Números por jogo", min_value=6, max_value=15, value=6,
    help="6 = aposta simples | 7–15 = aposta múltipla (custo maior, mais chances)"
)
qtd_jogos = st.sidebar.slider("Quantidade de jogos", min_value=1, max_value=50, value=5)

st.sidebar.divider()
st.sidebar.header("3. Escolher Estratégia")

estrategia = st.sidebar.selectbox("Estratégia", [
    "Melhor Jogo (IA)",
    "Frequência e Tendência",
    "Equilíbrio do Volante",
    "Números Atrasados",
    "Fixas de Ouro",
    "Técnica do Z",
    "Técnica +3/-3",
    "Desdobramento (Fechamento)",
])

fixas = []
pool_desdobramento = []
num_concurso_input = proximo_concurso

if estrategia == "Melhor Jogo (IA)":
    st.sidebar.info(
        "Roda todas as estratégias internamente, pontua cada jogo gerado "
        "e entrega apenas o de maior score. O ranking completo fica visível "
        "em cada card gerado."
    )

elif estrategia == "Técnica do Z":
    st.sidebar.info(
        "Usa a soma do último resultado para montar o padrão Z no volante "
        "(linha 01–10, diagonal, linha 51–60) e gera candidatos via deslocamento."
    )

elif estrategia == "Técnica +3/-3":
    st.sidebar.markdown("**Número do Próximo Concurso**")
    num_concurso_input = st.sidebar.number_input(
        "Informe o nº do concurso que será jogado:",
        min_value=1,
        value=proximo_concurso,
        step=1,
        help="Usado como divisor na geração da dízima. Inferido automaticamente se carregar o Excel."
    )
    st.sidebar.caption(
        "Concatena as dezenas do último resultado, divide pelo nº do concurso "
        "e extrai pares válidos (01–60) da dízima. Aplica variações +3 e -3."
    )

elif estrategia == "Fixas de Ouro":
    max_fixas = n_numeros - 1
    st.sidebar.markdown(f"**Dezenas Fixas** (máx {max_fixas})")
    fixas = st.sidebar.multiselect(
        "Selecione as dezenas fixas:",
        options=list(range(1, 61)),
        default=[],
        format_func=lambda x: f"{x:02d}"
    )
    if len(fixas) > max_fixas:
        st.sidebar.error(f"Selecione no máximo {max_fixas} dezenas fixas.")
        fixas = fixas[:max_fixas]

elif estrategia == "Desdobramento (Fechamento)":
    min_pool = n_numeros + 1
    st.sidebar.markdown(f"**Pool para desdobramento** (mínimo {min_pool} dezenas)")
    pool_desdobramento = st.sidebar.multiselect(
        "Selecione o pool:",
        options=list(range(1, 61)),
        default=list(range(1, min(min_pool + 4, 61))),
        format_func=lambda x: f"{x:02d}"
    )
    if len(pool_desdobramento) >= min_pool:
        total_combos = comb(len(pool_desdobramento), n_numeros)
        st.sidebar.info(f"{len(pool_desdobramento)} dezenas → {total_combos:,} combinações possíveis.")
        if total_combos > 50000:
            st.sidebar.caption("Pool grande: combinações serão amostradas aleatoriamente.")
    else:
        st.sidebar.error(f"Selecione pelo menos {min_pool} dezenas no pool.")

st.sidebar.divider()
st.sidebar.header("🚫 Excluir Números")
excluidos = st.sidebar.multiselect(
    "Remova dezenas do volante:",
    options=list(range(1, 61)),
    default=[],
    format_func=lambda x: f"{x:02d}",
    help="Nenhuma estratégia usará esses números."
)
pool_disponivel = TODAS - set(excluidos) if excluidos else None  # None = usa TODAS sem restrição

if excluidos:
    restantes = len(TODAS) - len(excluidos)
    if restantes < n_numeros:
        st.sidebar.error(f"Apenas {restantes} números disponíveis — insuficiente para {n_numeros} por jogo.")
    else:
        st.sidebar.caption(f"{restantes} números disponíveis após exclusão.")

btn_gerar = st.sidebar.button("🎯 Gerar Jogos")

st.sidebar.divider()
st.sidebar.header("4. Painel Completo")
st.sidebar.caption("Gera 1 jogo por estratégia com parâmetros automáticos.")
btn_painel = st.sidebar.button("Gerar Painel Completo (Auto)")


# ── MAIN AREA ──────────────────────────────────────────────────────────────────

if btn_gerar:
    st.header(f"Resultados: {estrategia} — {n_numeros} dezenas, {qtd_jogos} jogo(s)")

    if acumulada_info > 0:
        st.warning(f"🔥 Mega-Sena ACUMULADA há {acumulada_info} concurso(s)!")

    jogos_gerados = []

    if estrategia == "Melhor Jogo (IA)":
        resultados_ia = []
        with st.spinner(f"IA avaliando todas as estratégias para {qtd_jogos} jogo(s)..."):
            for i in range(qtd_jogos):
                jogo, nome_venc, score_venc, ranking = gerar_melhor_jogo(
                    n_numeros, frequencia, historico_sets, quentes_global,
                    num_concurso=num_concurso_input, pool=pool_disponivel
                )
                resultados_ia.append((jogo, nome_venc, score_venc, ranking))
                jogos_gerados.append(jogo)

        n_cols = min(3, len(resultados_ia))
        cols = st.columns(n_cols)
        for i, (jogo, nome_venc, score_venc, ranking) in enumerate(resultados_ia):
            with cols[i % n_cols]:
                st.markdown(f"**Jogo {i + 1}**")
                st.success(f"Estratégia eleita: **{nome_venc}**")
                st.markdown(render_volante_mega(jogo), unsafe_allow_html=True)
                st.caption(info_jogo(jogo, quentes_global))
                st.write(f"Score IA: **{score_venc:.1f}**")
                with st.expander("Ver ranking interno"):
                    for pos, r in enumerate(ranking):
                        st.write(f"{pos + 1}º {r['nome']} — Score: {r['score']:.1f}")
                st.divider()

        df_export = pd.DataFrame(jogos_gerados)
        csv = df_export.to_csv(index=False, header=False).encode("utf-8")
        st.download_button("⬇️ Baixar Jogos (CSV)", csv, "jogos_megasena.csv", "text/csv")

    elif estrategia == "Desdobramento (Fechamento)":
        if len(pool_desdobramento) < n_numeros + 1:
            st.error(f"Pool insuficiente. Selecione pelo menos {n_numeros + 1} dezenas.")
        else:
            with st.spinner("Gerando desdobramento e aplicando filtros..."):
                jogos_gerados = gerar_desdobramento(
                    pool_desdobramento, n_numeros,
                    historico_sets, quentes_global,
                    max_jogos=qtd_jogos,
                    excluidos=excluidos
                )
            if not jogos_gerados:
                st.warning("Nenhuma combinação passou nos filtros. Tente ampliar o pool.")
    else:
        with st.spinner(f"Gerando {qtd_jogos} jogo(s) com a estratégia '{estrategia}'..."):
            for _ in range(qtd_jogos):
                jogo = gerar_estrategia_mega(
                    estrategia, n_numeros, frequencia,
                    historico_sets, quentes_global, fixas,
                    num_concurso=num_concurso_input,
                    pool=pool_disponivel
                )
                jogos_gerados.append(jogo)

    if jogos_gerados and estrategia != "Melhor Jogo (IA)":
        n_cols = min(3, len(jogos_gerados))
        cols = st.columns(n_cols)
        for i, jogo in enumerate(jogos_gerados):
            with cols[i % n_cols]:
                st.markdown(f"**Jogo {i + 1}**")
                st.markdown(render_volante_mega(jogo), unsafe_allow_html=True)
                st.caption(info_jogo(jogo, quentes_global))
                st.divider()

        df_export = pd.DataFrame(jogos_gerados)
        csv = df_export.to_csv(index=False, header=False).encode("utf-8")
        st.download_button("⬇️ Baixar Jogos (CSV)", csv, "jogos_megasena.csv", "text/csv")

    if historico_sets:
        with st.expander("📊 Análise do Histórico"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Top 10 Mais Sorteados (histórico)**")
                for n in quentes_global:
                    st.write(f"`{n:02d}` — {frequencia[n]}×")
            with c2:
                st.markdown("**Top 10 Mais Atrasados**")
                for n in numeros_atrasados(historico_sets, 10):
                    ultimo_idx = max(
                        (i for i, s in enumerate(historico_sets) if n in s), default=-1
                    )
                    atraso = len(historico_sets) - 1 - ultimo_idx if ultimo_idx >= 0 else len(historico_sets)
                    st.write(f"`{n:02d}` — {atraso} conc. atrás")
            with c3:
                st.markdown("**Tendência Recente (20 conc.)**")
                freq_rec = Counter()
                for s in historico_sets[-20:]:
                    freq_rec.update(s)
                for n, cnt in freq_rec.most_common(10):
                    st.write(f"`{n:02d}` — {cnt}× nos últ. 20")

elif btn_painel:
    st.header("Painel Completo — 1 Jogo por Estratégia")

    if acumulada_info > 0:
        st.warning(f"🔥 Mega-Sena ACUMULADA há {acumulada_info} concurso(s)!")

    fixas_auto = auto_fixas_mega(historico_sets) if historico_sets else []
    pool_auto  = auto_pool_mega(historico_sets, frequencia, tamanho=max(n_numeros + 3, 12)) if historico_sets else list(range(1, n_numeros + 4))

    estrategias_painel = [
        ("Frequência e Tendência", {},                                          ""),
        ("Equilíbrio do Volante",  {},                                          ""),
        ("Números Atrasados",      {},                                          ""),
        ("Técnica do Z",           {},                                          ""),
        ("Técnica +3/-3",          {"num_concurso": proximo_concurso},          f"Concurso: {proximo_concurso}"),
        ("Fixas de Ouro",          {"fixas": fixas_auto},                       f"Fixas auto: {[f'{n:02d}' for n in fixas_auto]}"),
        ("Desdobramento (Fechamento)", {},                                       f"Pool auto: {len(pool_auto)} dezenas"),
    ]

    painel_jogos = []
    cols = st.columns(3)

    for idx, (nome, kwargs, info) in enumerate(estrategias_painel):
        if nome == "Desdobramento (Fechamento)":
            with st.spinner(f"Gerando: {nome}..."):
                jogos_desdobr = gerar_desdobramento(
                    pool_auto, n_numeros, historico_sets, quentes_global,
                    max_jogos=1, excluidos=excluidos
                )
                jogo = jogos_desdobr[0] if jogos_desdobr else _fallback(n_numeros, historico_sets, quentes_global, pool=pool_disponivel)
        else:
            with st.spinner(f"Gerando: {nome}..."):
                jogo = gerar_estrategia_mega(
                    nome, n_numeros, frequencia, historico_sets, quentes_global,
                    pool=pool_disponivel, **kwargs
                )
        score = pontuar_jogo_mega(jogo, historico_sets, quentes_global, frequencia)
        painel_jogos.append(jogo)

        with cols[idx % 3]:
            st.markdown(f"**{nome}**")
            if info:
                st.caption(info)
            st.markdown(render_volante_mega(jogo), unsafe_allow_html=True)
            st.caption(info_jogo(jogo, quentes_global))
            st.write(f"Score IA: {score:.1f}")
            st.divider()

    df_export = pd.DataFrame(painel_jogos)
    csv = df_export.to_csv(index=False, header=False).encode("utf-8")
    st.download_button("⬇️ Baixar Painel (CSV)", csv, "painel_megasena.csv", "text/csv")

else:
    st.info("Configure a estratégia na lateral e clique em 'Gerar Jogos'.")

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
        1. **Upload**: Arraste o Excel da Mega-Sena na lateral esquerda
           *(Colunas: A=Concurso · B=Data · C–H=6 dezenas · I=Ganhadores)*
        2. **Configure**: Escolha quantas dezenas por jogo (6–15) e quantos jogos gerar
        3. **Estratégia**: Selecione a lógica de geração desejada
        4. **Gere**: Clique em **Gerar Jogos**

        ### Filtros aplicados automaticamente
        | Filtro | Regra |
        |--------|-------|
        | Soma | Proporcional à faixa 150–220 para 6 dezenas |
        | Paridade | Entre 25% e 70% de números pares |
        | Sequência | Máximo 2 números consecutivos |
        | Finais | Máximo 2 dezenas com o mesmo algarismo final |
        | Quentes | Pelo menos 1 número do top-10 histórico |
        | Ineditismo | Sem 5+ dezenas em comum com qualquer resultado histórico |
        | Quadrantes | Distribuídas em pelo menos 3 dos 4 quadrantes do volante |
        """)

# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Aviso: Este software é uma ferramenta de análise estatística. "
    "Loterias são jogos de azar e não há garantia de lucro."
)
