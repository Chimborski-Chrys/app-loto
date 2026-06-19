import streamlit as st
import pandas as pd
import random
import time
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
    """
    Pares entre ~17% e ~83% do total de dezenas.
    Baseado na distribuicao historica da Mega-Sena (3009 concursos):
    resultados com 0 ou 6 pares somam apenas 2.6% — sao o unico extremo
    descartado. Faixa [1, n-1] cobre 96.7% dos resultados reais.
    """
    n = len(jogo)
    pares = sum(1 for x in jogo if x % 2 == 0)
    return 1 <= pares <= n - 1


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


_INDICE_INEDITISMO = {"key": None, "indice": None}


def _indice_ineditismo(historico_sets):
    """Índice invertido dezena → concursos em que apareceu (cache por lista)."""
    key = (id(historico_sets), len(historico_sets))
    if _INDICE_INEDITISMO["key"] != key:
        indice = {}
        for idx, s in enumerate(historico_sets):
            for n in s:
                indice.setdefault(n, []).append(idx)
        _INDICE_INEDITISMO["key"] = key
        _INDICE_INEDITISMO["indice"] = indice
    return _INDICE_INEDITISMO["indice"]


def validar_ineditismo(jogo, historico_sets):
    """
    Jogo não pode ter 5 ou mais dezenas em comum com qualquer resultado histórico.
    Usa índice invertido: O(dezenas × ocorrências) em vez de O(concursos) por jogo.
    """
    if not historico_sets:
        return True
    indice = _indice_ineditismo(historico_sets)
    cont = Counter()
    for n in jogo:
        cont.update(indice.get(n, ()))
    return not cont or max(cont.values()) < 5


def validar_quadrantes(jogo):
    """Dezenas distribuídas em pelo menos 3 dos 4 quadrantes do volante."""
    jogo_set = set(jogo)
    return sum(1 for q in QUADRANTES if jogo_set & q) >= 3


def _eh_progressao_aritmetica(jogo):
    s = sorted(jogo)
    if len(s) < 3:
        return False
    passo = s[1] - s[0]
    return all(s[i + 1] - s[i] == passo for i in range(len(s) - 1))


def validar_popularidade(jogo):
    """
    Filtro anti-popularidade: evita padrões jogados em massa, que dividem
    o prêmio em caso de acerto. Único filtro com ganho real de valor esperado.
    Regras: pelo menos 1 dezena > 31 (fuga de datas de aniversário) e
    jogo não pode ser uma progressão aritmética completa (5,10,15... etc).
    """
    if not any(n > 31 for n in jogo):
        return False
    if _eh_progressao_aritmetica(jogo):
        return False
    return True


def pontuar_anti_popularidade(jogo):
    """
    Score 0–100: quanto maior, menos provável o jogo ser escolhido por
    outros apostadores (datas, padrões visuais, dezenas 'redondas').
    """
    n = len(jogo)
    score = 100.0

    # Dezenas ≤ 31 lembram datas; quanto mais, mais popular o jogo
    aniversario = sum(1 for x in jogo if x <= 31)
    score -= (aniversario / n) * 35

    # Múltiplos de 5/10 são visualmente atraentes no volante
    redondos = sum(1 for x in jogo if x % 5 == 0)
    if redondos > 1:
        score -= (redondos - 1) * 8

    # Concentração em poucas linhas do volante (padrão visual)
    linhas = Counter((x - 1) // 10 for x in jogo)
    if max(linhas.values()) >= max(3, n // 2):
        score -= 15

    # Pares consecutivos (datas próximas, padrões)
    s = sorted(jogo)
    consecutivos = sum(1 for i in range(len(s) - 1) if s[i] + 1 == s[i + 1])
    score -= consecutivos * 5

    return max(0.0, round(score, 1))


def validar_jogo_mega(jogo, historico_sets, quentes):
    return (
        validar_soma(jogo)
        and validar_paridade(jogo)
        and validar_sequencia(jogo)
        and validar_finais(jogo)
        and validar_quentes(jogo, quentes)
        and validar_ineditismo(jogo, historico_sets)
        and validar_quadrantes(jogo)
        and validar_popularidade(jogo)
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
    Pool unificado: top-20 frequência histórica + top-15 tendência recente, sem
    divisão Q/T separada. ~50% do jogo vem desse pool quente; 1 slot frio; resto fill.
    """
    p = pool if pool is not None else TODAS
    atrasados = [n for n in numeros_atrasados(historico_sets, 15) if n in p] if historico_sets else sorted(p)[:15]
    tendentes  = [n for n in tendencia_recente(historico_sets, 20)  if n in p] if historico_sets else sorted(p)[:15]
    quentes_p  = [n for n in quentes if n in p]

    quentes20 = [n for n in top_quentes(frequencia, 20) if n in p] if frequencia else quentes_p
    seen_pool: set = set()
    hot_pool = []
    for n in quentes20 + tendentes:
        if n not in seen_pool:
            hot_pool.append(n)
            seen_pool.add(n)

    for _ in range(2000):
        dezenas = set()

        n_h = max(2, round(n_numeros * 0.50))
        dezenas.update(random.sample(hot_pool, min(n_h, len(hot_pool))))

        disp_frios = [x for x in atrasados if x not in dezenas]
        if disp_frios:
            dezenas.add(random.choice(disp_frios))

        dezenas = _completar_jogo(dezenas, n_numeros, pool=p)
        jogo = sorted(dezenas)
        if len(jogo) == n_numeros and validar_jogo_mega(jogo, historico_sets, quentes_p):
            return jogo

    return _fallback(n_numeros, historico_sets, quentes_p, pool=p)


def gerar_equilibrio_volante(n_numeros, historico_sets, quentes, frequencia=None,
                             pool=None, top_n=None):
    """
    Garante ao menos 1 dezena por quadrante.

    top_n (int|None): quando definido, restringe os candidatos a âncora
      aos top_n números mais frequentes de cada quadrante, aumentando a
      probabilidade de cobrir números historicamente quentes.
      Ex: top_n=5 triplica a chance de acertar um alvo quente vs uniforme.

    Quando frequencia é fornecida, fills são pesados por frequência histórica.
    """
    p = pool if pool is not None else TODAS

    def _candidatos_quadrante(q):
        q_list = sorted(q & p)
        if not q_list:
            return q_list
        if top_n and frequencia:
            q_list = sorted(q_list, key=lambda n: frequencia.get(n, 0), reverse=True)
            q_list = q_list[:max(top_n, 1)]
        return q_list

    quads_disp = [_candidatos_quadrante(q) for q in QUADRANTES]
    quads_disp = [q for q in quads_disp if q]

    def _ancora(q_list):
        if frequencia:
            pesos = [max(frequencia.get(n, 1), 1) for n in q_list]
            return random.choices(q_list, weights=pesos, k=1)[0]
        return random.choice(q_list)

    def _completar_ponderado(dezenas):
        restante = sorted(p - dezenas)
        faltam = n_numeros - len(dezenas)
        if faltam <= 0 or len(restante) < faltam:
            return dezenas
        if frequencia:
            pesos = [max(frequencia.get(n, 1), 1) for n in restante]
            r_local, p_local = list(restante), list(pesos)
            for _ in range(faltam):
                if not r_local:
                    break
                total = sum(p_local)
                r = random.uniform(0, total)
                cum = 0
                idx = len(r_local) - 1
                for j, w in enumerate(p_local):
                    cum += w
                    if r <= cum:
                        idx = j
                        break
                dezenas.add(r_local[idx])
                r_local.pop(idx)
                p_local.pop(idx)
        else:
            dezenas.update(random.sample(restante, faltam))
        return dezenas

    for _ in range(2000):
        dezenas = set()
        for q_list in quads_disp:
            dezenas.add(_ancora(q_list))
        dezenas = _completar_ponderado(dezenas)
        jogo = sorted(dezenas)
        if len(jogo) == n_numeros and validar_jogo_mega(jogo, historico_sets, quentes):
            return jogo
    return _fallback(n_numeros, historico_sets, quentes, pool=p)


def gerar_numeros_atrasados(n_numeros, historico_sets, quentes, pool=None):
    """
    50% do pool de mais atrasados + 1 slot de tendência recente (substitui Q10
    que só cobria 33, já presente nos atrasados) + fill. T15 adiciona cobertura
    de targets hot-recentes que o ranking de atraso não captura.
    """
    p = pool if pool is not None else TODAS
    atrasados  = [n for n in numeros_atrasados(historico_sets, 20) if n in p] if historico_sets else sorted(p)[:20]
    tendentes  = [n for n in tendencia_recente(historico_sets, 20) if n in p] if historico_sets else sorted(p)[:15]
    quentes_p  = [n for n in quentes if n in p]

    for _ in range(2000):
        dezenas = set()
        n_a = max(2, round(n_numeros * 0.50))
        dezenas.update(random.sample(atrasados, min(n_a, len(atrasados))))

        disp_t = [x for x in tendentes if x not in dezenas]
        if disp_t:
            dezenas.add(random.choice(disp_t))

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


def gerar_tecnica_z(n_numeros, historico_sets, quentes, frequencia=None, pool=None):
    """
    Técnica do Z: soma as dezenas do último resultado, usa o último dígito
    como offset e seleciona candidatos ao longo do padrão Z no volante
    (linha superior 01–10, diagonal 10→55, linha inferior 51–60).

    Melhoria: após expandir o pool Z com ±offset, preenche os quadrantes
    que ficaram com menos de `_PAD` candidatos usando os números mais
    frequentes daquele quadrante. Isso elimina "vãos" gerados por offsets
    específicos (ex: offset=7 exclui o 33 completamente do pool Z).
    """
    _PAD = 5   # top-N mais frequentes de cada quadrante sempre no pool Z

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

    # Pad: garante que os top-_PAD mais frequentes de cada quadrante estejam
    # sempre no pool, independentemente do que o Z produziu. Isso evita "vãos"
    # em quadrantes cujos números quentes não são alcançados pelo offset atual.
    if frequencia:
        for q in QUADRANTES:
            top_q = sorted(q & p, key=lambda n: frequencia.get(n, 0), reverse=True)
            for n in top_q[:_PAD]:
                pool_expandido.add(n)

    candidatos = sorted(pool_expandido & p)

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

    Melhoria: a mesma extração é feita também sobre o penúltimo resultado
    (dividido pelo concurso anterior), e os candidatos são unidos. Isso
    aumenta a cobertura do pool sem sair da lógica matemática da técnica —
    simulações mostram ~6% menos tentativas em média.
    """
    p = pool if pool is not None else TODAS
    if not historico_sets or num_proximo_concurso <= 0:
        return _fallback(n_numeros, historico_sets, quentes, pool=p)

    getcontext().prec = 60

    def _extrair(dezenas_seq, divisor):
        seq = ''.join(f'{n:02d}' for n in dezenas_seq)
        try:
            resultado = str(Decimal(seq) / Decimal(str(divisor)))
        except Exception:
            return []
        digitos = resultado.replace('.', '').replace('-', '').lstrip('0') or '0'
        encontrados = []
        for i in range(len(digitos) - 1):
            par = int(digitos[i:i + 2])
            if 1 <= par <= 60:
                encontrados.append(par)
        return encontrados

    def _cands_de_sorteio(sorteio, divisor):
        u = sorted(sorteio)
        c = set()
        c.update(_extrair(u, divisor))
        c.update(_extrair([min(60, n + 3) for n in u], divisor))
        c.update(_extrair([max(1,  n - 3) for n in u], divisor))
        return c

    candidatos = _cands_de_sorteio(historico_sets[-1], num_proximo_concurso)

    # Inclui candidatos do penúltimo sorteio para ampliar cobertura
    if len(historico_sets) >= 2 and num_proximo_concurso > 1:
        candidatos |= _cands_de_sorteio(historico_sets[-2], num_proximo_concurso - 1)

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
        return gerar_equilibrio_volante(n_numeros, historico_sets, quentes, frequencia=frequencia, pool=p)
    elif tipo == "Números Atrasados":
        return gerar_numeros_atrasados(n_numeros, historico_sets, quentes, pool=p)
    elif tipo == "Fixas de Ouro":
        return gerar_fixas_ouro(n_numeros, historico_sets, quentes, fixas, pool=p)
    elif tipo == "Técnica do Z":
        return gerar_tecnica_z(n_numeros, historico_sets, quentes, frequencia=frequencia, pool=p)
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
    """
    Score 0–100 baseado no único critério com efeito real no valor esperado
    (anti-popularidade) + bônus de equilíbrio estrutural. O componente antigo
    de 'acertos médios contra o histórico' foi removido: ele favorecia números
    quentes que o filtro de ineditismo combate — métricas que se cancelavam.
    """
    jogo_set = set(jogo)
    base = pontuar_anti_popularidade(jogo)  # 0–100

    score_quad = sum(1 for q in QUADRANTES if jogo_set & q) * 2.5   # até 10
    pares = sum(1 for n in jogo if n % 2 == 0)
    score_par = 5 if abs(pares - len(jogo) / 2) <= 1 else 0

    return round(min(100.0, base * 0.85 + score_quad + score_par), 1)


# ── SIMULAÇÃO ──────────────────────────────────────────────────────────────────

def backtest_walk_forward(historico_sets, estrategia, n_numeros, n_concursos,
                          jogos_por_concurso, pool=None, progress_cb=None):
    """
    Backtest sem vazamento de informação: para cada um dos últimos n_concursos,
    gera jogos usando APENAS o histórico anterior àquele concurso e mede os
    acertos contra o resultado real. É o teste honesto de capacidade preditiva —
    diferente da simulação contra alvo conhecido, que favorece estratégias cujo
    pool contém o alvo por construção.
    Retorna lista de dicts por concurso + lista plana de acertos.
    """
    total = len(historico_sets)
    n_concursos = min(n_concursos, total - 30)  # exige base mínima de treino
    if n_concursos <= 0:
        return [], []

    inicio = total - n_concursos
    resultados = []
    todos_acertos = []

    for i, k in enumerate(range(inicio, total)):
        hist_k = historico_sets[:k]
        alvo = historico_sets[k]
        freq_k = calcular_frequencia(hist_k)
        quentes_k = top_quentes(freq_k, 10)

        acertos_conc = []
        for _ in range(jogos_por_concurso):
            jogo = gerar_estrategia_mega(
                estrategia, n_numeros, freq_k, hist_k, quentes_k,
                num_concurso=k + 1, pool=pool,
            )
            acertos_conc.append(len(set(jogo) & alvo))

        todos_acertos.extend(acertos_conc)
        resultados.append({
            "Concurso (idx)": k + 1,
            "Resultado": " ".join(f"{n:02d}" for n in sorted(alvo)),
            "Média acertos": round(sum(acertos_conc) / len(acertos_conc), 2),
            "Melhor jogo": max(acertos_conc),
            "Jogos 4+": sum(1 for a in acertos_conc if a >= 4),
        })
        if progress_cb:
            progress_cb((i + 1) / n_concursos)

    return resultados, todos_acertos


def estatisticas_teoricas(n_numeros):
    """Média e P(≥4) teóricas de um jogo uniforme de n_numeros dezenas."""
    media = 6 * n_numeros / 60
    total = comb(60, n_numeros)
    p4 = sum(comb(6, k) * comb(54, n_numeros - k)
             for k in range(4, min(7, n_numeros + 1))) / total
    return media, p4


def simular_ate_acertar(resultado_alvo, min_acertos, n_numeros, frequencia, pool, max_tentativas,
                        quentes=None, num_concurso=1,
                        estrategia_sim="Aleatório Ponderado (Rápido)"):
    """
    Gera jogos até acertar min_acertos dezenas do resultado_alvo.
    Quando estrategia_sim == "Aleatório Ponderado (Rápido)" usa amostragem
    ponderada por frequência com apenas filtros de soma e paridade (mais rápido).
    Para qualquer outra estratégia, chama gerar_estrategia_mega sem histórico
    (ineditismo desabilitado para manter performance na simulação).
    Retorna (n_tentativas, jogo_vencedor).
    """
    alvo = set(resultado_alvo)
    p = sorted(pool if pool is not None else TODAS)
    if len(p) < n_numeros:
        return max_tentativas, None

    qt = quentes or []

    if estrategia_sim != "Aleatório Ponderado (Rápido)":
        # Modo estratégia: usa a lógica da estratégia sem validar ineditismo
        for tent in range(1, max_tentativas + 1):
            jogo = gerar_estrategia_mega(
                estrategia_sim, n_numeros, frequencia,
                historico_sets=[],  # desabilita ineditismo para performance
                quentes=qt,
                num_concurso=num_concurso,
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
        indices_disp = list(range(len(p)))
        pesos_disp = list(pesos)
        escolhidos = []
        for _ in range(n_numeros):
            cum = list(accumulate(pesos_disp))
            total = cum[-1]
            if total <= 0:
                return None
            r = random.uniform(0, total)
            idx = bisect(cum, r)
            idx = min(idx, len(indices_disp) - 1)
            escolhidos.append(p[indices_disp[idx]])
            indices_disp.pop(idx)
            pesos_disp.pop(idx)
        return sorted(escolhidos)

    for tent in range(1, max_tentativas + 1):
        jogo = _sorteia()
        if jogo is None or len(jogo) != n_numeros:
            continue
        if not validar_soma(jogo) or not validar_paridade(jogo):
            continue
        if len(set(jogo) & alvo) >= min_acertos:
            return tent, jogo

    return max_tentativas, None


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
            # Detecta colunas das bolas: procura por nomes Bola1-Bola6 ou usa posicoes 2-7
            bola_cols = [c for c in df.columns if str(c).strip().lower().startswith("bola")]
            bola_cols = sorted(bola_cols, key=lambda c: str(c))[:6]
            if len(bola_cols) == 6:
                cols_bolas = df[bola_cols]
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

            # Detecta coluna de ganhadores: procura por nome ou usa posicao 8
            ganh_col = next(
                (c for c in df.columns if "ganhador" in str(c).lower() and "6" in str(c)),
                None
            )
            if ganh_col:
                acumulada_info = detectar_acumulada(df[ganh_col])
            elif df.shape[1] >= 9:
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

st.sidebar.divider()
st.sidebar.header("5. Simulação de Eficiência")
st.sidebar.caption(
    "Informa um resultado real já conhecido. O sistema gera jogos até "
    "acertar o mínimo de pontos e conta quantas tentativas foram necessárias."
)
resultado_alvo_sim = st.sidebar.multiselect(
    "Resultado alvo (6 dezenas do sorteio real):",
    options=list(range(1, 61)),
    default=[],
    format_func=lambda x: f"{x:02d}",
)
min_acertos_sim = st.sidebar.slider("Mínimo de acertos para 'ganhar'", 4, 6, 4)
_opcoes_sim = [
    "Aleatório Ponderado (Rápido)",
    "Frequência e Tendência",
    "Equilíbrio do Volante",
    "Números Atrasados",
    "Técnica do Z",
    "Técnica +3/-3",
]
estrategia_sim_sel = st.sidebar.selectbox(
    "Estratégia da simulação:",
    _opcoes_sim,
    help=(
        "Aleatório Ponderado usa sorteio ponderado por frequência histórica com filtros mínimos "
        "(mais rápido). As demais estratégias usam a lógica completa sem o filtro de ineditismo, "
        "para manter performance adequada."
    ),
)
n_ciclos_sim    = st.sidebar.number_input("Ciclos", min_value=1, max_value=20, value=10, step=1)
max_tent_sim    = st.sidebar.number_input(
    "Máx. tentativas por ciclo", min_value=10_000, max_value=2_000_000,
    value=500_000, step=10_000,
    help="Se atingir o limite sem acertar, registra como 'não encontrado'."
)
btn_simular = st.sidebar.button("🔬 Iniciar Simulação")

st.sidebar.divider()
st.sidebar.header("6. Backtest Walk-Forward")
st.sidebar.caption(
    "Teste honesto: gera jogos usando só o histórico ANTERIOR a cada concurso "
    "e mede acertos no resultado real seguinte. Sem vazamento de informação."
)
_opcoes_bt = [
    "Frequência e Tendência",
    "Equilíbrio do Volante",
    "Números Atrasados",
    "Técnica do Z",
    "Técnica +3/-3",
]
estrategia_bt = st.sidebar.selectbox("Estratégia do backtest:", _opcoes_bt)
n_concursos_bt = st.sidebar.slider("Últimos N concursos", 10, 200, 50, step=10)
jogos_bt = st.sidebar.slider("Jogos por concurso", 1, 50, 10)
btn_backtest = st.sidebar.button("📈 Rodar Backtest")


# ── MAIN AREA ──────────────────────────────────────────────────────────────────

if btn_gerar:
    for _k in ["_sim_media_val", "_sim_estrategia", "_sim_n_numeros", "_sim_min_acertos", "_jogo_media"]:
        st.session_state.pop(_k, None)
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
                st.write(f"Score (anti-popularidade): **{score_venc:.1f}**")
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
    for _k in ["_sim_media_val", "_sim_estrategia", "_sim_n_numeros", "_sim_min_acertos", "_jogo_media"]:
        st.session_state.pop(_k, None)
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
            st.write(f"Score (anti-popularidade): {score:.1f}")
            st.divider()

    df_export = pd.DataFrame(painel_jogos)
    csv = df_export.to_csv(index=False, header=False).encode("utf-8")
    st.download_button("⬇️ Baixar Painel (CSV)", csv, "painel_megasena.csv", "text/csv")

elif btn_simular:
    if len(resultado_alvo_sim) != 6:
        st.error("Selecione exatamente 6 dezenas como resultado alvo.")
    else:
        alvo_sim = sorted(resultado_alvo_sim)
        st.header(f"🔬 Simulação: {min_acertos_sim}+ acertos em {int(n_ciclos_sim)} ciclos")
        st.caption(f"Estratégia: **{estrategia_sim_sel}**")

        col_info = st.columns(4)
        col_info[0].metric("Resultado alvo", " · ".join(f"{n:02d}" for n in alvo_sim))
        col_info[1].metric("Dezenas por jogo", n_numeros)
        col_info[2].metric("Mínimo de acertos", min_acertos_sim)
        col_info[3].metric("Máx. tentativas/ciclo", f"{int(max_tent_sim):,}")

        # Calcula probabilidade teórica (jogo uniforme)
        try:
            from math import comb as _c
            favoraveis = sum(_c(6, k) * _c(54, n_numeros - k)
                             for k in range(min_acertos_sim, min(7, n_numeros + 1)))
            total_combos = _c(60, n_numeros)
            prob = favoraveis / total_combos
            esperado = round(1 / prob) if prob > 0 else "∞"
        except Exception:
            prob = 0
            esperado = "N/D"

        st.caption(
            f"Probabilidade teórica (uniforme, sem filtros): "
            f"{prob*100:.4f}% → esperado **~{esperado:,} tentativas** por ciclo."
            if isinstance(esperado, int) else
            f"Probabilidade teórica não calculada."
        )

        st.divider()
        progress_bar = st.progress(0, text="Iniciando...")
        placeholder_tabela = st.empty()

        resultados_sim = []
        for ciclo in range(1, int(n_ciclos_sim) + 1):
            progress_bar.progress(
                (ciclo - 1) / int(n_ciclos_sim),
                text=f"Ciclo {ciclo}/{int(n_ciclos_sim)}..."
            )
            t0 = time.time()
            tentativas, jogo_venc = simular_ate_acertar(
                alvo_sim, min_acertos_sim, n_numeros,
                frequencia, pool_disponivel, int(max_tent_sim),
                quentes=quentes_global,
                num_concurso=proximo_concurso,
                estrategia_sim=estrategia_sim_sel,
            )
            elapsed_ms = round((time.time() - t0) * 1000)

            if jogo_venc:
                acertos = len(set(jogo_venc) & set(alvo_sim))
                jogo_str = "  ".join(f"{n:02d}" for n in jogo_venc)
                encontrou = "✅"
            else:
                acertos = 0
                jogo_str = "—"
                encontrou = "❌ limite"

            resultados_sim.append({
                "Ciclo": ciclo,
                "Tentativas": tentativas,
                "Resultado": encontrou,
                "Acertos": acertos,
                "Jogo vencedor": jogo_str,
                "Tempo (ms)": elapsed_ms,
            })

            # Atualiza tabela em tempo real
            placeholder_tabela.dataframe(
                pd.DataFrame(resultados_sim), use_container_width=True, hide_index=True
            )

        progress_bar.progress(1.0, text="Concluído!")

        # ── Resumo estatístico ──
        st.divider()
        st.subheader("Resumo dos Ciclos")

        tent_list = [r["Tentativas"] for r in resultados_sim if r["Resultado"] == "✅"]
        encontrados = len(tent_list)
        nao_enc = int(n_ciclos_sim) - encontrados

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Ciclos encontrados", f"{encontrados}/{int(n_ciclos_sim)}")
        if tent_list:
            media_val = sum(tent_list) // len(tent_list)
            c2.metric("Mínimo", f"{min(tent_list):,}")
            c3.metric("Máximo", f"{max(tent_list):,}")
            c4.metric("Média", f"{media_val:,}")
            sorted_t = sorted(tent_list)
            c5.metric("Mediana", f"{sorted_t[len(sorted_t)//2]:,}")
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
            st.session_state["_sim_n_numeros"]   = n_numeros
            st.session_state["_sim_min_acertos"] = min_acertos_sim
            st.session_state.pop("_jogo_media", None)

elif btn_backtest:
    if not historico_sets or len(historico_sets) < 40:
        st.error("Backtest exige histórico carregado com pelo menos 40 concursos.")
    else:
        st.header(f"📈 Backtest Walk-Forward — {estrategia_bt}")
        st.caption(
            f"Últimos **{n_concursos_bt}** concursos · **{jogos_bt}** jogos de "
            f"**{n_numeros}** dezenas por concurso · treino apenas com dados anteriores."
        )

        media_teo, p4_teo = estatisticas_teoricas(n_numeros)

        progress = st.progress(0, text="Rodando backtest...")
        resultados_bt, acertos_bt = backtest_walk_forward(
            historico_sets, estrategia_bt, n_numeros,
            n_concursos_bt, jogos_bt, pool=pool_disponivel,
            progress_cb=lambda f: progress.progress(f, text=f"Backtest: {f*100:.0f}%"),
        )
        progress.progress(1.0, text="Concluído!")

        if not acertos_bt:
            st.warning("Histórico insuficiente para o backtest configurado.")
        else:
            media_obs = sum(acertos_bt) / len(acertos_bt)
            p4_obs = sum(1 for a in acertos_bt if a >= 4) / len(acertos_bt)
            dist = Counter(acertos_bt)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Jogos avaliados", f"{len(acertos_bt):,}")
            c2.metric("Média de acertos", f"{media_obs:.3f}",
                      delta=f"{media_obs - media_teo:+.3f} vs teórico ({media_teo:.3f})")
            c3.metric("% jogos com 4+", f"{p4_obs*100:.3f}%",
                      delta=f"{(p4_obs - p4_teo)*100:+.3f} p.p. vs teórico ({p4_teo*100:.3f}%)")
            c4.metric("Melhor jogo", f"{max(acertos_bt)} acertos")

            st.subheader("Distribuição de acertos")
            df_dist = pd.DataFrame({
                "Acertos": list(range(0, 7)),
                "Jogos": [dist.get(a, 0) for a in range(0, 7)],
            })
            st.bar_chart(df_dist.set_index("Acertos"))

            with st.expander("Detalhe por concurso"):
                st.dataframe(pd.DataFrame(resultados_bt),
                             use_container_width=True, hide_index=True)

            desvio = (media_obs - media_teo) / media_teo * 100
            if abs(desvio) < 5:
                veredito = ("estatisticamente indistinguível do sorteio uniforme — "
                            "como esperado para um jogo de azar. O valor das estratégias "
                            "está nos filtros anti-popularidade (prêmio menos dividido), "
                            "não em prever dezenas.")
            elif desvio > 0:
                veredito = (f"{desvio:.1f}% acima do teórico nesta amostra. Cuidado: com "
                            "amostras pequenas isso é ruído estatístico, não edge.")
            else:
                veredito = f"{abs(desvio):.1f}% abaixo do teórico nesta amostra (ruído estatístico)."
            st.info(f"**Veredito:** a estratégia **{estrategia_bt}** ficou {veredito}")

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
            c4.metric("🔥 Acumulada", f"{acumulada_info} conc.")
        else:
            c4.metric("Status", "Não acumulada")
    elif "_sim_media_val" not in st.session_state:
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
        | Paridade | Entre 1 e n-1 pares (~17% a ~83%) — só descarta extremos |
        | Sequência | Máximo 2 números consecutivos |
        | Finais | Máximo 2 dezenas com o mesmo algarismo final |
        | Quentes | Pelo menos 1 número do top-10 histórico |
        | Ineditismo | Sem 5+ dezenas em comum com qualquer resultado histórico |
        | Quadrantes | Distribuídas em pelo menos 3 dos 4 quadrantes do volante |
        | Anti-popularidade | Ao menos 1 dezena >31 e sem progressões aritméticas — reduz divisão do prêmio |
        """)

# ── JOGO DA MÉDIA ──────────────────────────────────────────────────────────────
if "_sim_media_val" in st.session_state and historico_sets:
    _mv   = st.session_state["_sim_media_val"]
    _est  = st.session_state["_sim_estrategia"]
    _nn   = st.session_state["_sim_n_numeros"]
    _meta = st.session_state["_sim_min_acertos"]
    _cap  = min(_mv, 5_000)  # limite de segurança para não travar a UI

    st.divider()
    st.subheader("🎯 Jogo da Média")
    st.caption(
        f"Estratégia **{_est}** encontra {_meta}+ acertos em média a cada "
        f"**{_mv:,} jogos**."
        + (f" *(limitado a {_cap:,} para não travar a interface)*" if _cap < _mv else "")
    )

    if st.button(f"Gerar jogo #{_cap:,}", key="btn_jogo_media"):
        _est_uso = _est if _est != "Aleatório Ponderado (Rápido)" else "Frequência e Tendência"
        # Nota: gerar N jogos e pegar o último é idêntico a gerar 1 direto —
        # cada geração é independente. O loop anterior só gastava CPU.
        with st.spinner(f"Gerando jogo com {_est_uso}..."):
            _jogo = gerar_estrategia_mega(
                _est_uso, _nn, frequencia,
                historico_sets=[],          # ineditismo desabilitado para performance
                quentes=quentes_global,
                num_concurso=proximo_concurso,
                pool=pool_disponivel,
            )
        st.session_state["_jogo_media"] = _jogo

    if st.session_state.get("_jogo_media"):
        _jm = st.session_state["_jogo_media"]
        st.success(f"Jogo da posição **#{_cap:,}**: {' · '.join(f'{n:02d}' for n in _jm)}")
        st.markdown(render_volante_mega(_jm), unsafe_allow_html=True)
        st.caption(info_jogo(_jm, quentes_global))

# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Aviso: Este software é uma ferramenta de análise estatística. "
    "Loterias são jogos de azar e não há garantia de lucro."
)