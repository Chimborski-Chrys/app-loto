import streamlit as st
import pandas as pd
import random

# Configuração da Página
st.set_page_config(page_title="Lotofácil Pro AI - Engenharia de Dados", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #ff4b4b; color: white; }
    .volante { display: grid; grid-template-columns: repeat(5, 1fr); gap: 5px; max-width: 250px; margin: auto; }
    .dezena { border: 1px solid #444; padding: 10px; text-align: center; border-radius: 50%; width: 40px; height: 40px; line-height: 20px; }
    .selecionada { background-color: #2e7d32; color: white; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE LÓGICA ---

def validar_jogo(jogo, historico_sets):
    """Aplica filtros de segurança: Soma, Sequência e Ineditismo."""
    soma = sum(jogo)
    if not (180 <= soma <= 220):
        return False
    
    # Verifica sequências longas (mais de 4 números)
    jogo_sorted = sorted(list(jogo))
    seq = 1
    for i in range(len(jogo_sorted)-1):
        if jogo_sorted[i] + 1 == jogo_sorted[i+1]:
            seq += 1
            if seq > 4: return False
        else:
            seq = 1
            
    # Filtro de Ineditismo (não pode ter 14 ou 15 pontos no histórico)
    jogo_set = set(jogo)
    for h in historico_sets:
        intersecao = len(jogo_set.intersection(h))
        if intersecao >= 14:
            return False
            
    return True

def gerar_estrategia(tipo, ultimo, frequencia, historico_sets, fixas=[]):
    tentativas = 0
    while tentativas < 1000:
        tentativas += 1
        dezenas = set()
        todas = set(range(1, 26))
        presentes = set(ultimo)
        ausentes = todas - presentes
        
        if tipo == "Inversão Suprema":
            dezenas.update(ausentes) # As 10 ausentes
            dezenas.update(random.sample(list(presentes), 5))
            
        elif tipo == "Cercamento 7/8":
            dezenas.update(random.sample(list(ausentes), 7))
            dezenas.update(random.sample(list(presentes), 8))
            
        elif tipo == "Fixas de Ouro":
            dezenas.update(fixas)
            restante = list(todas - set(fixas))
            dezenas.update(random.sample(restante, 15 - len(fixas)))

        elif tipo == "Equilíbrio IA 2026":
            # 8 ímpares e 7 pares (ou vice-versa)
            impares = [n for n in todas if n % 2 != 0]
            pares = [n for n in todas if n % 2 == 0]
            if random.choice([True, False]):
                dezenas.update(random.sample(impares, 8))
                dezenas.update(random.sample(pares, 7))
            else:
                dezenas.update(random.sample(impares, 7))
                dezenas.update(random.sample(pares, 8))

        elif tipo == "Ranking Frequência":
            rankeadas = sorted(frequencia.items(), key=lambda x: x[1], reverse=True)
            top_10 = [d[0] for d in rankeadas[:10]]
            dezenas.update(top_10)
            restante = list(todas - set(top_10))
            dezenas.update(random.sample(restante, 5))

        elif tipo == "Fechamento de Dezenas":
            # Gera jogos exclusivamente dentro do pool definido pelo usuário.
            # Com pool > 15, cada jogo é uma combinação diferente, garantindo
            # cobertura progressiva ao gerar múltiplos jogos.
            pool = list(fixas) if len(fixas) >= 15 else sorted(todas)
            dezenas.update(random.sample(pool, 15))

        jogo_lista = sorted(list(dezenas))
        if validar_jogo(jogo_lista, historico_sets):
            return jogo_lista
    return sorted(random.sample(range(1, 26), 15))


def auto_fixas_from_historico(historico_sets):
    """Dezenas que apareceram em pelo menos 60% dos últimos 10 concursos."""
    ultimos = historico_sets[-10:] if len(historico_sets) >= 10 else historico_sets
    contagem = {}
    for s in ultimos:
        for n in s:
            contagem[n] = contagem.get(n, 0) + 1
    threshold = max(1, round(len(ultimos) * 0.6))
    fixas = sorted([n for n, c in contagem.items() if c >= threshold])
    if len(fixas) < 3:
        top = sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:5]
        fixas = sorted([n for n, _ in top])
    return fixas[:10]


def auto_pool_from_historico(historico_sets):
    """União de todas as dezenas únicas dos últimos 10 concursos."""
    ultimos = historico_sets[-10:] if len(historico_sets) >= 10 else historico_sets
    pool = set()
    for s in ultimos:
        pool.update(s)
    return sorted(pool)


def pontuar_jogo(jogo, hist_score):
    """
    Pontua um jogo com dois critérios combinados:
      1. Frequência: soma de quantas vezes cada dezena apareceu no hist_score.
      2. Acertos médios: média de acertos do jogo contra cada concurso do hist_score.
    Quanto maior a pontuação, maior a aderência ao histórico selecionado.
    """
    if not hist_score:
        return 0.0
    jogo_set = set(jogo)
    freq = {}
    for h in hist_score:
        for n in h:
            freq[n] = freq.get(n, 0) + 1
    score_freq   = sum(freq.get(n, 0) for n in jogo)
    acertos_med  = sum(len(jogo_set & h) for h in hist_score) / len(hist_score)
    return round(score_freq + acertos_med * 50, 2)


# --- INTERFACE ---

st.title("🎯 Pro: Engenharia de Dados & IA")
st.sidebar.header("1. Upload de Dados")
file = st.sidebar.file_uploader("Arraste o Excel da Caixa", type=['xlsx'])

COLUNAS_BOLAS = [f"Bola{i}" for i in range(1, 16)]

historico_sets = []
ultimo_resultado = list(range(1, 16))
frequencia = {i: 0 for i in range(1, 26)}

if file:
    try:
        df = pd.read_excel(file)
        cols_faltando = [c for c in COLUNAS_BOLAS if c not in df.columns]
        if cols_faltando:
            st.sidebar.error(f"Colunas não encontradas no arquivo: {', '.join(cols_faltando)}")
        else:
            colunas_dezenas = df[COLUNAS_BOLAS]
            linhas_invalidas = colunas_dezenas.isnull().any(axis=1).sum()
            if linhas_invalidas > 0:
                st.sidebar.warning(f"⚠️ {linhas_invalidas} linha(s) com dezenas incompletas foram ignoradas.")
                colunas_dezenas = colunas_dezenas.dropna()
            historico_sets = [set(row) for row in colunas_dezenas.values]
            ultimo_resultado = list(colunas_dezenas.iloc[-1].values)  # Mais recente está no final
            for s in historico_sets:
                for n in s: frequencia[n] += 1
            st.sidebar.success(f"✅ Histórico Carregado! ({len(historico_sets)} concursos)")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler o arquivo: {e}")

st.sidebar.divider()
st.sidebar.header("2. Configurar Estratégia")
estrategia_ref = st.sidebar.selectbox("Escolha a Lógica",
    ["Inversão Suprema", "Cercamento 7/8", "Fixas de Ouro", "Equilíbrio IA 2026", "Ranking Frequência", "Fechamento de Dezenas"])

qtd_jogos = st.sidebar.slider("Quantidade de Jogos", 1, 50, 5)

fixas = []
if estrategia_ref == "Fixas de Ouro":
    st.sidebar.markdown("**Dezenas Fixas** (escolha até 14)")
    fixas = st.sidebar.multiselect(
        "Selecione as dezenas fixas:",
        options=list(range(1, 26)),
        default=[],
        format_func=lambda x: f"{x:02d}"
    )
    if len(fixas) >= 15:
        st.sidebar.error("Selecione no máximo 14 dezenas fixas.")
        fixas = fixas[:14]

elif estrategia_ref == "Fechamento de Dezenas":
    st.sidebar.markdown("**Pool de Fechamento** (mínimo 15 dezenas)")
    st.sidebar.caption("Todos os jogos serão gerados exclusivamente com as dezenas do pool. Quanto maior o pool, maior a cobertura entre os jogos.")
    fixas = st.sidebar.multiselect(
        "Selecione as dezenas do pool:",
        options=list(range(1, 26)),
        default=list(range(1, 21)),
        format_func=lambda x: f"{x:02d}"
    )
    if len(fixas) < 15:
        st.sidebar.error("Selecione pelo menos 15 dezenas no pool.")
    else:
        st.sidebar.info(f"Pool com {len(fixas)} dezenas → C({len(fixas)},15) combinações possíveis.")

btn_otimizado = st.sidebar.button("Gerar Jogos Otimizados")

st.sidebar.divider()
st.sidebar.header("3. Painel Completo")
st.sidebar.caption("Gera 1 jogo por estratégia. Parâmetros como fixas e pool são escolhidos automaticamente com base nos últimos 10 concursos.")
btn_painel = st.sidebar.button("Gerar Painel Completo (Auto)")

st.sidebar.divider()
st.sidebar.header("4. Jogo Rápido")
st.sidebar.caption("Roda todas as estratégias e entrega os 2 jogos com maior pontuação de aderência ao histórico.")
escopo_rapido = st.sidebar.radio("Histórico para pontuação:", ["Completo", "Parcial (últimos N)"], horizontal=True)
n_parcial = None
if escopo_rapido == "Parcial (últimos N)":
    max_n = max(10, len(historico_sets))
    n_parcial = st.sidebar.slider("Últimos N concursos", min_value=10, max_value=max_n, value=min(100, max_n))
btn_rapido = st.sidebar.button("⚡ Gerar Jogo Rápido")


def render_volante(jogo):
    html = '<div class="volante">'
    for n in range(1, 26):
        classe = "dezena selecionada" if n in jogo else "dezena"
        html += f'<div class="{classe}">{n:02d}</div>'
    html += '</div>'
    return html


if btn_otimizado:
    st.header(f"Resultados: {estrategia_ref}")
    meus_jogos = []

    cols = st.columns(3)
    for i in range(qtd_jogos):
        jogo = gerar_estrategia(estrategia_ref, ultimo_resultado, frequencia, historico_sets, fixas=fixas)
        meus_jogos.append(jogo)

        with cols[i % 3]:
            st.markdown(f"**Jogo {i+1}**")
            st.markdown(render_volante(jogo), unsafe_allow_html=True)
            st.write(f"Soma: {sum(jogo)} | Pares: {len([n for n in jogo if n % 2 == 0])}")
            st.divider()

    df_export = pd.DataFrame(meus_jogos)
    csv = df_export.to_csv(index=False, header=False).encode('utf-8')
    st.download_button("Baixar Jogos (CSV)", csv, "jogos_lotofacil.csv", "text/csv")

elif btn_painel:
    st.header("Painel Completo — 1 Jogo por Estratégia")

    fixas_auto = auto_fixas_from_historico(historico_sets)
    pool_auto  = auto_pool_from_historico(historico_sets)

    estrategias_painel = [
        ("Inversão Suprema",   [],         ""),
        ("Cercamento 7/8",     [],         ""),
        ("Fixas de Ouro",      fixas_auto, f"Fixas auto: {[f'{n:02d}' for n in fixas_auto]}" if fixas_auto else ""),
        ("Equilíbrio IA 2026", [],         ""),
        ("Ranking Frequência", [],         ""),
        ("Fechamento de Dezenas", pool_auto, f"Pool auto: {len(pool_auto)} dezenas {[f'{n:02d}' for n in pool_auto]}" if pool_auto else ""),
    ]

    painel_jogos = []
    cols = st.columns(3)
    for idx, (nome, params, info) in enumerate(estrategias_painel):
        jogo = gerar_estrategia(nome, ultimo_resultado, frequencia, historico_sets, fixas=params)
        painel_jogos.append(jogo)

        with cols[idx % 3]:
            st.markdown(f"**{nome}**")
            if info:
                st.caption(info)
            st.markdown(render_volante(jogo), unsafe_allow_html=True)
            st.write(f"Soma: {sum(jogo)} | Pares: {len([n for n in jogo if n % 2 == 0])}")
            st.divider()

    df_export = pd.DataFrame(painel_jogos)
    csv = df_export.to_csv(index=False, header=False).encode('utf-8')
    st.download_button("Baixar Painel (CSV)", csv, "painel_completo.csv", "text/csv")

elif btn_rapido:
    st.header("⚡ Jogo Rápido — Top 2 Jogos")

    hist_score = (
        historico_sets[-n_parcial:] if n_parcial and len(historico_sets) >= n_parcial
        else historico_sets
    )
    escopo_label = f"últimos {len(hist_score)} concursos" if n_parcial else f"histórico completo ({len(hist_score)} concursos)"
    st.caption(f"Pontuação calculada sobre: {escopo_label}")

    fixas_auto = auto_fixas_from_historico(historico_sets)
    pool_auto  = auto_pool_from_historico(historico_sets)

    estrategias_todas = [
        ("Inversão Suprema",      []),
        ("Cercamento 7/8",        []),
        ("Fixas de Ouro",         fixas_auto),
        ("Equilíbrio IA 2026",    []),
        ("Ranking Frequência",    []),
        ("Fechamento de Dezenas", pool_auto),
    ]

    candidatos = []
    for nome, params in estrategias_todas:
        jogo  = gerar_estrategia(nome, ultimo_resultado, frequencia, historico_sets, fixas=params)
        score = pontuar_jogo(jogo, hist_score)
        candidatos.append((nome, jogo, score))

    candidatos.sort(key=lambda x: x[2], reverse=True)
    top2 = candidatos[:2]

    cols = st.columns(2)
    rapido_jogos = []
    for idx, (nome, jogo, score) in enumerate(top2):
        rapido_jogos.append(jogo)
        with cols[idx]:
            st.markdown(f"**#{idx+1} — {nome}**")
            st.caption(f"Pontuação: {score:.1f}")
            st.markdown(render_volante(jogo), unsafe_allow_html=True)
            st.write(f"Soma: {sum(jogo)} | Pares: {len([n for n in jogo if n % 2 == 0])}")

    with st.expander("Ver ranking completo das 6 estratégias"):
        for i, (nome, jogo, score) in enumerate(candidatos):
            st.write(f"**{i+1}. {nome}** — Pontuação: {score:.1f} | {jogo}")

    df_export = pd.DataFrame(rapido_jogos)
    csv = df_export.to_csv(index=False, header=False).encode('utf-8')
    st.download_button("Baixar Top 2 (CSV)", csv, "jogo_rapido.csv", "text/csv")

else:
    st.info("Aguardando comando... Selecione uma estratégia na lateral e clique em Gerar, ou use o Painel Completo.")

# --- FOOTER ---
st.markdown("---")
st.caption("Aviso: Este software é uma ferramenta de análise estatística. Loterias são jogos de azar e não há garantia de lucro.")