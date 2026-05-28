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

def treinar_e_filtrar(estrategia_nome, ultimo_res, freq, hist_sets, params):
    """
    Versão Avançada: Valida o jogo atual e verifica a 'janela deslizante' 
    para confirmar se a estratégia está em uma onda de acertos.
    """
    if len(hist_sets) < 50:
        jogo = gerar_estrategia(estrategia_nome, ultimo_res, freq, hist_sets, params)
        return {"jogo": jogo, "tentativas": 1, "sucessos": "Dados insuficientes"}

    ultimos_25 = list(hist_sets)[-25:]
    tentativas_globais = 0
    
    while tentativas_globais < 2000:
        tentativas_globais += 1
        # 1. Gera o candidato para o próximo concurso
        candidato = gerar_estrategia(estrategia_nome, ultimo_res, freq, hist_sets, params)
        candidato_set = set(candidato)
        
        # 2. Teste de 'Calor' (O que você faz na mão: 11 e 12 nos últimos 25)
        onze, doze, treze = 0, 0, 0
        for hist in ultimos_25:
            acertos = len(candidato_set & hist)
            if acertos == 11: onze += 1
            elif acertos == 12: doze += 1
            elif acertos >= 13: treze += 1
        
        # 3. Teste de 'Janela Deslizante' (A lógica de voltar no tempo)
        # Vamos ver se a ESTRATÉGIA acertaria algo nos últimos 3 concursos reais
        sucessos_janela = 0
        for i in range(1, 4):
            ponto_corte = -i
            vizinhança = hist_sets[ponto_corte-25 : ponto_corte]
            alvo_passado = hist_sets[ponto_corte]
            
            # Simula um jogo rápido daquela época
            simulado = gerar_estrategia(estrategia_nome, list(vizinhança[-1]), {}, vizinhança, params)
            if len(set(simulado) & alvo_passado) >= 11:
                sucessos_janela += 1

        # CRITÉRIO DE APROVAÇÃO:
        # O jogo atual tem que ser bom (11 e 12) E a estratégia tem que ter acertado 
        # pelo menos 1 vez nos últimos 3 concursos (está em uma onda)
        if doze >= 1 and onze >= 1 and sucessos_janela >= 1:
            return {
                "jogo": candidato, 
                "tentativas": tentativas_globais, 
                "sucessos": f"Atual: 11({onze}x), 12({doze}x) | Onda: {sucessos_janela}/3"
            }
            
    return {"jogo": candidato, "tentativas": tentativas_globais, "sucessos": "Meta parcial"}

def gerar_estrategia(tipo, ultimo, frequencia, historico_sets, fixas=[]):
    tentativas = 0
    while tentativas < 1000:
        tentativas += 1
        dezenas = set()
        todas = set(range(1, 26))
        presentes = set(ultimo)
        ausentes = todas - presentes
        
        if tipo == "Inversão Suprema":
            # 6 aus + 9 pres: teto de hits = 6+9 = 15 (flexível).
            # Original 10+5 limitava o teto a 10 hits para muitos resultados.
            dezenas.update(random.sample(list(ausentes), min(6, len(ausentes))))
            disp_p = [x for x in presentes if x not in dezenas]
            dezenas.update(random.sample(disp_p, min(9, len(disp_p))))
            rest = list(todas - dezenas)
            faltam = 15 - len(dezenas)
            if faltam > 0 and len(rest) >= faltam:
                dezenas.update(random.sample(rest, faltam))
            
        elif tipo == "Cercamento 7/8":
            dezenas.update(random.sample(list(ausentes), 7))
            dezenas.update(random.sample(list(presentes), 8))
            
        elif tipo == "Fixas de Ouro":
            dezenas.update(fixas)
            restante = list(todas - set(fixas))
            dezenas.update(random.sample(restante, 15 - len(fixas)))

        elif tipo == "Equilíbrio IA 2026":
            # Padrão Carlos Cruz: Dezenas que sumiram nos últimos 3 concursos
            if len(historico_sets) >= 3:
                ultimos_3 = list(historico_sets)[-3:]
                frias = todas - (ultimos_3[0] | ultimos_3[1] | ultimos_3[2])
                # Garante pelo menos 3 dezenas "quentes" para voltar
                dezenas.update(random.sample(list(frias), min(len(frias), 3)))
            
            # Padrão Matemático: 7 ou 8 Pares
            impares = [n for n in todas if n % 2 != 0]
            pares = [n for n in todas if n % 2 == 0]
            
            n_imp = random.choice([7, 8])
            restante_imp = [n for n in impares if n not in dezenas]
            restante_par = [n for n in pares if n not in dezenas]
            
            dezenas.update(random.sample(restante_imp, n_imp - len([n for n in dezenas if n % 2 != 0])))
            dezenas.update(random.sample(restante_par, 15 - len(dezenas)))

        elif tipo == "Ranking Frequência":
            # Sample ponderado por frequência de todos os 25 números.
            # Top-10 fixo forçava até 5 não-alvos permanentes (teto 10 hits).
            pool_rk = list(range(1, 26))
            pesos_rk = [max(frequencia.get(n, 1), 1) for n in pool_rk]
            pool_d = pool_rk[:]
            pesos_d = pesos_rk[:]
            while len(dezenas) < 15 and pool_d:
                total = sum(pesos_d)
                r = random.uniform(0, total)
                acc = 0
                for _i, _p in enumerate(pesos_d):
                    acc += _p
                    if acc >= r:
                        dezenas.add(pool_d[_i])
                        pool_d.pop(_i)
                        pesos_d.pop(_i)
                        break

        elif tipo == "Rastreio Ciclo 3":
            if len(historico_sets) >= 3:
                ult3 = list(historico_sets)[-3:]
                frias_c3 = sorted(todas - (ult3[0] | ult3[1] | ult3[2]))
                if frias_c3:
                    dezenas.update(random.sample(frias_c3, min(len(frias_c3), 3)))
            rest_c3 = list(todas - dezenas)
            faltam_c3 = 15 - len(dezenas)
            if faltam_c3 > 0 and len(rest_c3) >= faltam_c3:
                dezenas.update(random.sample(rest_c3, faltam_c3))

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


def pontuar_jogo(jogo, historico_sets):
    """
    Versão Evoluída (IA 2026): Pontua baseado em Moldura, 
    Repetição do Anterior e Frequência Geral.
    """
    if not historico_sets:
        return 0.0
    
    jogo_set = set(jogo)
    ultimo_concurso = list(historico_sets)[-1]
    
    # 1. Filtro de Moldura (Bordas do volante)
    moldura = {1,2,3,4,5,6,10,11,15,16,20,21,22,23,24,25}
    pontos_moldura = len(jogo_set & moldura)
    # Score alto se estiver no padrão clássico de 9 a 11 na moldura
    score_moldura = 50 if 9 <= pontos_moldura <= 11 else 0
    
    # 2. Repetição do Anterior (Padrão de 8 a 10 repetidas)
    repetidas = len(jogo_set & ultimo_concurso)
    score_repeticao = 50 if 8 <= repetidas <= 10 else 0
    
    # 3. Frequência Acumulada (Aderência ao histórico)
    acertos_med = sum(len(jogo_set & h) for h in historico_sets) / len(historico_sets)
    
    return round(score_moldura + score_repeticao + (acertos_med * 10), 2)

# --- NOVAS LÓGICAS DE FECHAMENTO ---

def gerar_fechamento_17_dezenas(escolhidas_17, fixas_5):
    """Implementa o fechamento de 17 dezenas em 6 jogos (Radar Loto)."""
    # Garante que as 5 fixas estão nos jogos
    restantes = [n for n in escolhidas_17 if n not in fixas_5]
    random.shuffle(restantes)
    
    jogos = []
    # Distribuição circular para garantir que cada dezena apareça proporcionalmente
    for i in range(6):
        # Seleciona 10 dezenas das 12 restantes de forma rotativa
        indices = [(i + j) % 12 for j in range(10)]
        combinacao = [restantes[idx] for idx in indices]
        jogos.append(sorted(fixas_5 + combinacao))
    return jogos

def gerar_fechamento_13_fixas(fixas_13, todas_25):
    """Garante 15 pontos se acertar as 13 fixas (Prof. Xavier)."""
    restantes = [n for n in todas_25 if n not in fixas_13]
    random.shuffle(restantes)
    
    jogos = []
    # Agrupa as 12 dezenas restantes em 6 pares
    for i in range(0, 12, 2):
        par = restantes[i:i+2]
        jogos.append(sorted(fixas_13 + par))
    return jogos

def analisar_ciclo_3_concursos(historico_sets):
    """
    Rastreia dezenas frias (ausentes nos últimos 3) como âncora opcional.
    Quentes forçados removidos — forçar todos os quentes bloqueava até 4 slots
    com não-alvos, tornando 12+ acertos estruturalmente impossível.
    """
    if len(historico_sets) < 3:
        return sorted(random.sample(range(1, 26), 15))

    ultimos_3 = historico_sets[-3:]
    todas = set(range(1, 26))
    frias = sorted(todas - (ultimos_3[0] | ultimos_3[1] | ultimos_3[2]))

    todas_list = list(range(1, 26))
    for _ in range(500):
        base = set()
        if frias:
            base.update(random.sample(frias, min(len(frias), 3)))
        restante = [n for n in todas_list if n not in base]
        faltam = 15 - len(base)
        if faltam > 0 and len(restante) >= faltam:
            base.update(random.sample(restante, faltam))
        jogo = sorted(base)
        if len(jogo) == 15:
            soma = sum(jogo)
            if 180 <= soma <= 220:
                return jogo
    return sorted(random.sample(range(1, 26), 15))

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
estrategia_ref = st.sidebar.selectbox("Escolha a Lógica", [
    "Inversão Suprema", "Cercamento 7/8", "Fixas de Ouro", 
    "Equilíbrio IA 2026", "Ranking Frequência", "Fechamento de Dezenas",
    "Fechamento 17 Dezenas (6 Jogos)", "Matriz 13 Fixas (Ouro)", "Rastreio Ciclo 3"
])

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

    # Lógica específica para as novas estratégias de Matriz
    if estrategia_ref == "Fechamento 17 Dezenas (6 Jogos)":
        # Aqui você pode pedir 17 dezenas via multiselect na sidebar similar ao pool
        pool_17 = st.sidebar.multiselect("Escolha 17 dezenas:", range(1,26), default=list(range(1,18)))
        fixas_5 = pool_17[:5] # Ou peça para o usuário escolher
        meus_jogos = gerar_fechamento_17_dezenas(pool_17, fixas_5)
        
    elif estrategia_ref == "Matriz 13 Fixas (Ouro)":
        fixas_13 = st.sidebar.multiselect("Escolha 13 Fixas:", range(1,26), default=list(range(1,14)))
        meus_jogos = gerar_fechamento_13_fixas(fixas_13, list(range(1,26)))
        
    elif estrategia_ref == "Rastreio Ciclo 3":
        for _ in range(qtd_jogos):
            meus_jogos.append(analisar_ciclo_3_concursos(historico_sets))

    cols = st.columns(3)
    for i in range(qtd_jogos):
        # Chama o treino e recebe o dicionário completo
        resultado = treinar_e_filtrar(estrategia_ref, ultimo_resultado, frequencia, historico_sets, fixas)
        jogo = resultado["jogo"] # Extrai a lista de números
        meus_jogos.append(jogo)

        with cols[i % 3]:
            st.markdown(f"**Jogo {i+1}**")
            st.markdown(render_volante(jogo), unsafe_allow_html=True)
            # Exibe as métricas de treino para cada jogo gerado
            st.caption(f"🎯 {resultado['sucessos']}") 
            st.write(f"Soma: {sum(jogo)} | Gen: {resultado['tentativas']}")
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
        with st.spinner(f"IA treinando {nome}..."):
            # 1. Chamamos o treino (retorna um dicionário)
            resultado = treinar_e_filtrar(
                nome, 
                ultimo_resultado, 
                frequencia, 
                historico_sets, 
                params
            )
            
            # 2. EXTRAÍMOS o jogo e as métricas do dicionário
            jogo = resultado["jogo"]
            tentativas = resultado["tentativas"]
            performance = resultado["sucessos"]
            
        painel_jogos.append(jogo)

        with cols[idx % 3]:
            st.markdown(f"**{nome}**")
            if info:
                st.caption(info)
            
            # 3. Agora o render_volante recebe a LISTA correta
            st.markdown(render_volante(jogo), unsafe_allow_html=True)
            
            # 4. Mostramos os dados do treino para cada estratégia
            st.caption(f"📊 {performance}")
            st.write(f"Soma: {sum(jogo)} | Gen: {tentativas}")
            st.divider()

    df_export = pd.DataFrame(painel_jogos)
    csv = df_export.to_csv(index=False, header=False).encode('utf-8')
    st.download_button("Baixar Painel (CSV)", csv, "painel_completo.csv", "text/csv")
    
elif btn_rapido:
    st.header("⚡ Jogo Rápido — Análise de Performance IA")

    hist_score = historico_sets[-n_parcial:] if n_parcial and len(historico_sets) >= n_parcial else historico_sets
    
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
    with st.spinner("IA treinando e validando gerações..."):
        for nome, params in estrategias_todas:
            resultado = treinar_e_filtrar(nome, ultimo_resultado, frequencia, historico_sets, params)
            score = pontuar_jogo(resultado["jogo"], hist_score)
            candidatos.append({
                "nome": nome, 
                "jogo": resultado["jogo"], 
                "score": score, 
                "tentativas": resultado["tentativas"],
                "sucessos": resultado["sucessos"]
            })

    # Ordenar por Score
    candidatos.sort(key=lambda x: x["score"], reverse=True)
    top2 = candidatos[:2]

    # Exibição dos Top 2
    cols = st.columns(2)
    for idx, c in enumerate(top2):
        with cols[idx]:
            st.subheader(f"#{idx+1} — {c['nome']}")
            st.markdown(render_volante(c['jogo']), unsafe_allow_html=True)
            # MÉTRICAS DE TREINO AQUI:
            st.info(f"**Treino:** {c['tentativas']} gerações analisadas")
            st.success(f"**Performance:** Fez +11 pontos em {c['sucessos']} dos últimos 25 concursos.")
            st.write(f"Soma: {sum(c['jogo'])} | Score: {c['score']:.1f}")

    # Ranking Completo Expandido
    with st.expander("Ver Ranking de Treino Completo"):
        for i, c in enumerate(candidatos):
            col_a, col_b, col_c = st.columns([1, 2, 2])
            col_a.write(f"**{i+1}º**")
            col_b.write(f"**{c['nome']}**")
            col_c.write(f"Gen: {c['tentativas']} | Exitos: {c['sucessos']} | Score: {c['score']:.1f}")

    # Botão de Download
    df_export = pd.DataFrame([c['jogo'] for c in top2])
    csv = df_export.to_csv(index=False, header=False).encode('utf-8')
    st.download_button("Baixar Top 2 (CSV)", csv, "jogo_rapido.csv", "text/csv")

else:
    st.info("Aguardando comando... Selecione uma estratégia na lateral e clique em Gerar, ou use o Painel Completo.")

# --- FOOTER ---
st.markdown("---")
st.caption("Aviso: Este software é uma ferramenta de análise estatística. Loterias são jogos de azar e não há garantia de lucro.")