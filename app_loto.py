import streamlit as st
import pandas as pd
import random
import re
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

# ── CARROSSEL 142857 (raiz digital / aritmética modular de base 9) ─────────────
# A raiz digital de n é 1 + (n-1) % 9 e vale 3, 6 ou 9 exatamente quando n é
# múltiplo de 3. Os dois grupos abaixo são, portanto, a partição do volante por
# n % 3: 17 dezenas no carrossel e 8 excluídas.
#
# MEDIDO nos 3.729 concursos de `Lotofácil.xlsx` — a distribuição é indistinguível
# da hipergeométrica, isto é, o carrossel não carrega informação nenhuma:
#     carrossel:    7      8      9     10     11     12     13     14
#     teórico:   0,59%  5,95% 20,82% 33,32% 26,50% 10,60%  2,04%  0,17%
#     real:      0,67%  6,19% 19,28% 33,76% 27,22% 10,57%  2,17%  0,13%
#     média real 10,2172 contra 10,2000 esperada (ep 0,0191, t = +0,90)
GRUPO_LOTOFACIL_CARROSSEL      = {n for n in range(1, 26) if n % 3 != 0}
GRUPO_LOTOFACIL_EXCLUIDOS_369  = {n for n in range(1, 26) if n % 3 == 0}

# A BANDA É O ÚNICO PARÂMETRO DO FILTRO, E A ESCOLHA DELA FOI MEDIDA.
#
# A banda herda a estrutura do alvo: apertá-la reprova junto os jogos que
# ACERTARIAM contra ele. É o mesmo mecanismo que já derrubou os filtros deste
# arquivo uma vez — ver o bloco de SOMA_MIN/SOMA_MAX. Medido nos 400 concursos
# mais recentes, sobre os 151 jogos que fariam 14 ou 15 acertos contra cada um:
#
#   banda      vencedores sobreviventes   concursos com ZERO   15 acertos possível
#   (nenhuma)        144,0 / 151                 0,0%                95,7%
#   10–11             88,5 / 151                 9,2%                58,0%
#    9–12  <--       131,9 / 151                 0,0%                86,6%
#    8–12            140,6 / 151                 0,0%                92,7%
#
# A faixa 10–11 foi descartada: em 9,2% dos concursos NENHUM jogo vencedor
# sobreviveria aos filtros, tornando o acerto impossível por construção naqueles
# sorteios — pior que os 6,5% do bug histórico que motivou a recalibração da
# soma. Ela também não corresponde à "zona de ouro de ~68,2%": ocorre em 60,98%
# dos concursos reais (59,82% teórico); os 68,2% são a regra de ±1 desvio da
# normal, não uma medição.
#
# 9–12 cobre 90,83% dos concursos reais (91,25% teórico), mantém em zero os
# alvos impossíveis e custa 9,0% do espaço de jogos, contra 40,6% de 10–11.
# A mesma banda serve para o cartão de 16: ali ela cobre 91,30%, praticamente o
# mesmo recorte proporcional.
CARROSSEL_LOTO_FAIXA_15 = (9, 12)    # núcleo de 15 dezenas — cobre 91,25%
CARROSSEL_LOTO_FAIXA_16 = (9, 12)    # cartão estendido — cobre 91,30%


def faixa_carrossel_loto(n_dezenas):
    """`(minimo, maximo)` de dezenas do carrossel aceitas num jogo de `n_dezenas`.

    15 e 16 usam as bandas medidas acima. Outros tamanhos escalam a proporção do
    núcleo de 15 (10/15 a 11/15) e nunca aceitam o jogo inteiro de um lado só."""
    if n_dezenas == 15:
        return CARROSSEL_LOTO_FAIXA_15
    if n_dezenas == 16:
        return CARROSSEL_LOTO_FAIXA_16
    lo, hi = CARROSSEL_LOTO_FAIXA_15
    esc_lo = max(1, round(n_dezenas * lo / 15))
    esc_hi = min(n_dezenas - 1, round(n_dezenas * hi / 15))
    return esc_lo, max(esc_lo, esc_hi)


def validar_proporcao_142857(jogo):
    """Exige que o jogo caia na banda do carrossel correspondente ao seu tamanho.

    Entre 9 e 12 dezenas do carrossel, tanto no núcleo de 15 quanto no cartão
    estendido de 16 — a banda cobre ~91% dos concursos reais nos dois tamanhos.
    Ver o bloco acima para a medição que descartou a faixa 10–11."""
    lo, hi = faixa_carrossel_loto(len(jogo))
    return lo <= len(set(jogo) & GRUPO_LOTOFACIL_CARROSSEL) <= hi

COLUNAS_BOLAS = [f"Bola{i}" for i in range(1, 16)]
MOLDURA = {1, 2, 3, 4, 5, 6, 10, 11, 15, 16, 20, 21, 22, 23, 24, 25}
LINHAS_GRID  = [set(range(1 + 5 * i, 6 + 5 * i)) for i in range(5)]
COLUNAS_GRID = [set(range(1 + i, 26, 5)) for i in range(5)]
DIAG_PRINCIPAL  = {1, 7, 13, 19, 25}
DIAG_SECUNDARIA = {5, 9, 13, 17, 21}

# ── CORES OFICIAIS DAS BOLAS (cor = final do número) ───────────────────────────
FINAIS_ORDEM = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
NOME_COR = {
    1: "Vermelha", 2: "Amarela", 3: "Verde", 4: "Marrom", 5: "Azul",
    6: "Rosa", 7: "Preta", 8: "Cinza", 9: "Laranja", 0: "Branca",
}
DEZENAS_POR_COR = {f: [n for n in range(1, 26) if n % 10 == f] for f in range(10)}
# (fundo, texto) para renderização do volante
CORES_HEX = {
    1: ("#e53935", "#fff"), 2: ("#fdd835", "#000"), 3: ("#43a047", "#fff"),
    4: ("#795548", "#fff"), 5: ("#1e88e5", "#fff"), 6: ("#ec407a", "#fff"),
    7: ("#212121", "#fff"), 8: ("#9e9e9e", "#000"), 9: ("#fb8c00", "#fff"),
    0: ("#fafafa", "#000"),
}

# ── VALIDAÇÃO ──────────────────────────────────────────────────────────────────
# Limites calibrados contra os 3.729 concursos reais de `Lotofácil.xlsx`.
# Os valores antigos (soma 180–220, run ≤ 4) reprovavam 63,2% dos resultados que
# de fato saíram — e, por herdarem a estrutura do alvo, reprovavam também os
# jogos que acertariam 14+ contra ele: em 6,5% dos concursos reais nenhum dos
# 151 jogos vencedores sobrevivia, tornando o acerto impossível por construção.
SOMA_MIN, SOMA_MAX = 160, 240   # cobre 97,6% dos resultados reais (min 133, max 257)
MAX_CONSECUTIVAS   = 8          # cobre 97,8% — 55,6% dos concursos têm run ≥ 5
# Combinados: 95,7% dos resultados reais aprovados, 95,0% do espaço de jogos,
# e nenhum alvo com 0 vencedores sobreviventes nos últimos 200 concursos.

def validar_soma(jogo):
    return SOMA_MIN <= sum(jogo) <= SOMA_MAX

def validar_sequencia(jogo):
    s = sorted(jogo); seq = 1
    for i in range(len(s) - 1):
        if s[i] + 1 == s[i + 1]:
            seq += 1
            if seq > MAX_CONSECUTIVAS: return False
        else:
            seq = 1
    return True

def validar_ineditismo(jogo, historico_sets):
    js = set(jogo)
    return all(len(js & h) < 14 for h in historico_sets)

def validar_jogo_loto(jogo, historico_sets):
    return (validar_soma(jogo) and validar_sequencia(jogo)
            and validar_ineditismo(jogo, historico_sets)
            and validar_proporcao_142857(jogo))

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

def perfil_cores(jogo):
    """Contagem de dezenas por cor (final do número)."""
    cnt = Counter(n % 10 for n in jogo)
    return {f: cnt.get(f, 0) for f in FINAIS_ORDEM}

def validar_cores(jogo):
    """Faixas dominantes do histórico (3729 concursos analisados):
    - cores de 3 dezenas (finais 1-5) saem 1 a 3 vezes em ~95% dos concursos;
    - no máximo 2 cores zeradas (97,4% do histórico);
    - entre 4 e 6 cores com 2+ dezenas (96% do histórico)."""
    p = perfil_cores(jogo)
    zeradas  = sum(1 for f in FINAIS_ORDEM if p[f] == 0)
    duasmais = sum(1 for f in FINAIS_ORDEM if p[f] >= 2)
    for f in (1, 2, 3, 4, 5):
        if not 1 <= p[f] <= 3:
            return False
    return zeradas <= 2 and 4 <= duasmais <= 6

def validar_assinatura_cores(assin):
    """Mesmas faixas de validar_cores, aplicadas direto à assinatura
    (tupla de contagens na ordem FINAIS_ORDEM)."""
    zeradas  = sum(1 for c in assin if c == 0)
    duasmais = sum(1 for c in assin if c >= 2)
    if any(not 1 <= assin[i] <= 3 for i in range(5)):  # finais 1-5
        return False
    return zeradas <= 2 and 4 <= duasmais <= 6

def assinaturas_cores(historico_sets):
    """Assinaturas de cores do histórico dentro do perfil dominante
    (com repetições — amostrar daqui equivale a amostrar da
    distribuição empírica condicionada ao padrão)."""
    todas = (
        tuple(sum(1 for n in s if n % 10 == f) for f in FINAIS_ORDEM)
        for s in historico_sets
    )
    return [a for a in todas if validar_assinatura_cores(a)]

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

def atrasos_atuais(historico_sets):
    """Concursos decorridos desde a última aparição de cada dezena.
    0 = saiu no último concurso. Dezena nunca sorteada recebe len(historico)."""
    total = len(historico_sets)
    at = {d: total for d in range(1, 26)}
    vistos = set()
    for k, s in enumerate(reversed(historico_sets)):
        for d in s:
            if d not in vistos:
                vistos.add(d)
                at[d] = k
        if len(vistos) == 25:
            break
    return at

def _amostra_ponderada(itens, pesos, k):
    """Amostragem sem reposição proporcional ao peso (roleta com remoção)."""
    itens_d = list(itens)
    pesos_d = [max(float(w), 0.0) for w in pesos]
    escolhidos = []
    while len(escolhidos) < k and itens_d:
        total = sum(pesos_d)
        if total <= 0:
            escolhidos.extend(random.sample(itens_d, min(k - len(escolhidos), len(itens_d))))
            break
        r, acc = random.uniform(0, total), 0.0
        for i, w in enumerate(pesos_d):
            acc += w
            if acc >= r:
                escolhidos.append(itens_d.pop(i))
                pesos_d.pop(i)
                break
        else:
            escolhidos.append(itens_d.pop())
            pesos_d.pop()
    return sorted(escolhidos)

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
        if validar_soma(j) and validar_sequencia(j) and validar_proporcao_142857(j):
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
        j = _amostra_ponderada(pool_list, pesos, 15)
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

def gerar_padrao_cores(historico_sets, pool=None, historico_analise=None):
    """Estratégia de Cores: amostra uma assinatura de cores real do histórico
    (distribuição empírica) e monta o jogo respeitando essa assinatura.
    `historico_analise` (recorte) define de onde vêm as assinaturas;
    `historico_sets` continua sendo usado para o filtro de ineditismo.
    Fallback: geração aleatória filtrada por validar_cores."""
    p = pool if pool is not None else TODAS
    base = historico_analise if historico_analise is not None else historico_sets
    assinaturas = assinaturas_cores(base) if base else []

    if assinaturas:
        for _ in range(1000):
            assin = random.choice(assinaturas)
            dez = set()
            ok = True
            for f, qtd in zip(FINAIS_ORDEM, assin):
                disponiveis = [n for n in DEZENAS_POR_COR[f] if n in p]
                if len(disponiveis) < qtd:
                    ok = False
                    break
                dez.update(random.sample(disponiveis, qtd))
            if not ok or len(dez) != 15:
                continue
            j = sorted(dez)
            if validar_jogo_loto(j, historico_sets):
                return j

    # Fallback: sem histórico (ou pool restrito demais) — filtro de faixas
    p_list = sorted(p)
    if len(p_list) < 15:
        return p_list
    for _ in range(1000):
        j = sorted(random.sample(p_list, 15))
        if validar_cores(j) and validar_soma(j) and validar_sequencia(j) \
                and validar_ineditismo(j, historico_sets) \
                and validar_proporcao_142857(j):
            return j
    return _fallback(historico_sets, pool=p)

# ── MODELO PONDERADO (frequência + atraso + repetição) ─────────────────────────
PESOS_PONDERADO_PADRAO = {"freq": 1.0, "atraso": 1.0, "rep": 1.0}

def pesos_ponderados(historico_analise, ultimo, w_freq=1.0, w_atraso=1.0, w_rep=1.0):
    """Score por dezena combinando os três sinais do modelo, cada um normalizado
    em 0–1 para que os pesos sejam comparáveis entre si:
      - freq:   frequência da dezena no recorte / frequência máxima do recorte;
      - atraso: concursos desde a última aparição / maior atraso atual;
      - rep:    1 se a dezena saiu no último concurso, 0 caso contrário.
    freq e atraso são sinais opostos por construção (quem sai muito atrasa pouco):
    pesar os dois é escolher onde ficar entre 'quentes' e 'frias'."""
    base = historico_analise or []
    freq = calcular_frequencia(base)
    max_f = max(freq.values()) or 1
    atraso = atrasos_atuais(base)
    max_a = max(atraso.values()) or 1
    ult = set(ultimo)
    pesos = {}
    for d in range(1, 26):
        score = (
            w_freq * (freq[d] / max_f)
            + w_atraso * (atraso[d] / max_a)
            + w_rep * (1.0 if d in ult else 0.0)
        )
        pesos[d] = max(score, 0.01)   # piso > 0: nenhuma dezena fica impossível
    return pesos

def gerar_modelo_ponderado(historico_sets, ultimo, pool=None, historico_analise=None,
                           pesos_modelo=None):
    """Estratégia ponderada: amostra 15 dezenas proporcionalmente ao score
    combinado (frequência recente + atraso + repetição do último concurso)."""
    p = pool if pool is not None else TODAS
    base = historico_analise if historico_analise is not None else historico_sets
    w = pesos_modelo or PESOS_PONDERADO_PADRAO
    pesos = pesos_ponderados(
        base, ultimo,
        w.get("freq", 1.0), w.get("atraso", 1.0), w.get("rep", 1.0),
    )
    pool_list = sorted(p)
    if len(pool_list) < 15:
        return pool_list
    pesos_list = [pesos[n] for n in pool_list]
    for _ in range(1000):
        j = _amostra_ponderada(pool_list, pesos_list, 15)
        if len(j) == 15 and validar_jogo_loto(j, historico_sets):
            return j
    return _fallback(historico_sets, pool=p)

# ── ERRAR 10 (previsão das dezenas ausentes) ───────────────────────────────────
# Num jogo de 15 dezenas contra 15 sorteadas em 25, a sobreposição mínima é
# 15 + 15 - 25 = 5. Errar 10 só acontece quando as 10 dezenas que NÃO saem estão
# todas dentro do jogo — isto é, "errar 10" é exatamente "acertar quais 10 não
# saem". É o mesmo problema de previsão virado do avesso, com uma vantagem
# prática: acontece por acaso 3.003x mais que um 15 (0,0919% contra 0,0000306%),
# o que o torna o único extremo da distribuição mensurável com 3.729 concursos.
P_AUSENCIA_MARGINAL = 10 / 25   # 0,40 — fixado pelas regras, não pelos dados
K_PRIOR_AUSENCIA    = 20        # concursos-equivalentes de encolhimento p/ 0,40

def escore_ausencia(historico_analise, ultimo):
    """P(dezena ausente no próximo concurso), estimada no recorte e condicionada
    ao estado atual da dezena (saiu / não saiu no último concurso).

    Markov de ordem 1 por dezena: para cada par de concursos consecutivos do
    recorte conta-se, separadamente para cada estado anterior, quantas vezes a
    dezena ficou ausente. O escore é a taxa da célula em que a dezena está hoje,
    encolhida para a marginal 0,40 com força `K_PRIOR_AUSENCIA` (evita que uma
    dezena com 3 observações no recorte lidere o ranking por acidente).

    Leitura honesta: as regras já fixam P(ausente) = 10/25 = 0,40 e, como ~9 das
    15 dezenas se repetem de um concurso para o outro, P(ausente | saiu) e
    P(ausente | não saiu) também caem perto de 0,40. As diferenças por dezena
    são, em quase todo recorte, ruído amostral.

    Medido nos 3.729 concursos de `Lotofácil.xlsx` — o escore NÃO tem sinal:
      - sobreposição lag-1 = 8,9718 contra 9,0029 de pares aleatórios de
        concursos: diferença -0,031 (t = -1,54). Não há dependência temporal.
      - lags 2, 3, 5, 20, 100 e 500 todos dentro de |t| < 1,8 de 9,0.
      - χ² de uniformidade das 25 marginais = 24,95 com 24 gl (crítico 5% =
        36,42): as frequências desiguais são ruído, não viés de bola.
      - escores observados variam só entre 0,3741 e 0,4297 em torno de 0,40.
    Ver `gerar_errar_dez` para o artefato que este escore produz no backtest."""
    base = historico_analise or []
    ult = set(ultimo or [])
    # [ausencias, casos] por dezena, separados pelo estado no concurso anterior
    apos_presente = {d: [0, 0] for d in range(1, 26)}
    apos_ausente  = {d: [0, 0] for d in range(1, 26)}
    for ant, atual in zip(base, base[1:]):
        for d in range(1, 26):
            cel = apos_presente[d] if d in ant else apos_ausente[d]
            cel[1] += 1
            if d not in atual:
                cel[0] += 1
    escores = {}
    for d in range(1, 26):
        aus, casos = apos_presente[d] if d in ult else apos_ausente[d]
        escores[d] = ((aus + K_PRIOR_AUSENCIA * P_AUSENCIA_MARGINAL)
                      / (casos + K_PRIOR_AUSENCIA))
    return escores

def gerar_errar_dez(historico_sets, ultimo, pool=None, historico_analise=None,
                    inverter=False):
    """Monta o jogo com as 15 dezenas de MAIOR escore de ausência do recorte —
    a aposta explícita em errar 10, que ocorre se e somente se as 10 dezenas
    ausentes do sorteio estiverem todas entre elas.

    `inverter=True` devolve o jogo espelho: as 15 de MENOR escore, ou seja, o
    complemento das 10 previstas ausentes. Os dois jogos vêm do mesmo modelo:
    se o escore de ausência tiver sinal real, o espelho é a aposta que o
    aproveita, e a diferença de desempenho entre os dois no backtest é a medida
    direta desse sinal (sem sinal, ambos ficam colados na média 9,0).

    ARMADILHA MEDIDA — o gap deste par é enviesado para cima no walk-forward.
    Rodando 2.000 concursos com refit a cada passo (o que o backtest do app faz):
        gap (espelho - errar 10) = +0,1555, se = 0,0502, t = +3,10
    parece sinal forte. Não é. Dois controles matam:
      1. embaralhando o histórico (200 réplicas), o MESMO procedimento devolve
         t médio = +2,09 (sd 0,81; p2,5 = +0,64; p97,5 = +3,59). O nulo já vem
         centrado em +2, então p = 0,100 para o t observado. O viés é do método.
      2. congelando o modelo (treina no 1º terço, testa no 3º, sem refit):
         gap = +0,0008, se = 0,0636, t = +0,01. Sinal zero.
    Causa: o refit a cada concurso faz o estimador absorver os próprios alvos do
    período de teste — ao prever o concurso j, o escore já viu o concurso i < j
    que também é alvo. O ranking fica parcialmente ajustado in-sample àquilo que
    está sendo pontuado. Nenhuma informação do futuro entra em cada previsão
    isolada, mas os erros deixam de ser independentes entre si e o erro-padrão
    ingênuo subestima a variância. Só o modelo congelado testa de fato."""
    p = sorted(pool if pool is not None else TODAS)
    if len(p) < 15:
        return p
    base = historico_analise if historico_analise is not None else historico_sets
    esc = escore_ausencia(base, ultimo)
    # Desempate por dezena mantém o jogo estável quando os escores empatam.
    ordenado = sorted(p, key=(lambda d: (esc[d], d)) if inverter
                             else (lambda d: (-esc[d], d)))
    jogo = sorted(ordenado[:15])
    if validar_jogo_loto(jogo, historico_sets):
        return jogo
    # Topo do ranking reprovado por soma/sequência/ineditismo: reamostra com peso
    # quadrático na posição, mantendo a preferência pelas primeiras colocadas.
    posicao = {d: i for i, d in enumerate(ordenado)}
    pesos = [(len(ordenado) - posicao[d]) ** 2 for d in p]
    for _ in range(500):
        j = _amostra_ponderada(p, pesos, 15)
        if len(j) == 15 and validar_jogo_loto(j, historico_sets):
            return j
    return jogo   # nenhuma variante passou: devolve o ranking puro, sem distorcer

JANELA_CARTEIRA_TAM = 30    # concursos por janela (mínimo utilizável do app)

def janelas_deslizantes(total, n_jogos, tamanho=JANELA_CARTEIRA_TAM, passo=None):
    """Recortes deslizantes para transformar uma estratégia determinística numa
    carteira: a janela j termina `passo * j` concursos antes do fim e cobre
    `tamanho` concursos. Devolve lista de (ini, fim) para fatiar o histórico.

    `passo` default = `tamanho`, ou seja **janelas disjuntas**. Isso não é
    detalhe de gosto, é o que a medição manda — ver `carteira_deslizante`.
    Devolve menos janelas que `n_jogos` se o histórico não alcançar."""
    passo = tamanho if passo is None else max(1, int(passo))
    saida = []
    for j in range(int(n_jogos)):
        fim = total - passo * j
        ini = fim - tamanho
        if ini < 0:
            break
        saida.append((ini, fim))
    return saida

def carteira_deslizante(historico_sets, ultimo, n_jogos, pool=None,
                        tamanho=JANELA_CARTEIRA_TAM, passo=None, inverter=False,
                        base_recortes=None):
    """Carteira de jogos distintos de uma estratégia determinística, um por
    recorte deslizante. Devolve [(jogo, (ini, fim)), ...].

    `base_recortes` é o histórico FATIADO em janelas; `historico_sets` segue
    servindo só ao filtro de ineditismo. Separar os dois importa: o backtest
    passa um histórico de ineditismo truncado (`hist_ineditismo`, 200 por
    padrão) por custo de CPU, e usá-lo também como base das janelas limitaria a
    carteira a 200/tamanho jogos — 6 em vez dos 20 pedidos, o que compara
    carteiras de tamanhos diferentes e produz um déficit inteiramente falso.

    MEDIDO em 400 concursos walk-forward, carteiras de 50 jogos, comparando o
    MELHOR jogo da carteira (que é o que importa quando se compra N bilhetes)
    contra 50 jogos aleatórios válidos:

        tam 30, passo  5   sobrep. 9,45   melhor 11,447   t = -4,55  <- pior
        tam 30, passo 15   sobrep. 9,09   melhor 11,607   t = -1,36
        tam 30, passo 30   sobrep. 9,08   melhor 11,675   t = +0,24  <- default
        tam 30, passo 60   sobrep. 9,02   melhor 11,655   t = -0,24
        tam 60, passo 60   sobrep. 9,07   melhor 11,658   t = -0,17
        50 aleatórios      sobrep. 9,00   melhor 11,665

    Passo pequeno gera janelas que compartilham quase tudo (passo 5 em janela de
    30 = 83% dos mesmos concursos), os jogos saem quase iguais, a carteira
    concentra e o melhor bilhete PIORA — os 50 bilhetes acertam e erram juntos.
    O custo é real e mecânico: nada a ver com prever sorteio, é só geometria de
    cobertura. Com janelas disjuntas a sobreposição cai para o nível do
    aleatório e a carteira empata com ele — que é o teto, já que não há sinal a
    explorar (ver `gerar_errar_dez`)."""
    base = historico_sets if base_recortes is None else base_recortes
    jogos = []
    for ini, fim in janelas_deslizantes(len(base), n_jogos, tamanho, passo):
        jogos.append((
            gerar_errar_dez(historico_sets, ultimo, pool=pool,
                            historico_analise=base[ini:fim],
                            inverter=inverter),
            (ini, fim),
        ))
    return jogos

def diagnostico_errar_dez(jogo, historico_analise, ultimo, pool=None):
    """Quantas das 10 dezenas de maior escore de ausência o jogo cobre.
    Cobrir as 10 é condição necessária (e suficiente) para errar 10."""
    p = sorted(pool if pool is not None else TODAS)
    esc = escore_ausencia(historico_analise, ultimo)
    top10 = set(sorted(p, key=lambda d: (-esc[d], d))[:10])
    cobertas = len(top10 & set(jogo))
    espalhamento = max(esc.values()) - min(esc.values())
    return cobertas, espalhamento

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
        if not validar_proporcao_142857(j):
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


# ── CARTÃO ESTENDIDO (16 DEZENAS) ──────────────────────────────────────────────
# Uma aposta de 16 dezenas É o conjunto das C(16,15) = 16 apostas simples contidas
# nela: custa 16x e a chance de 15 sobe exatamente 16x, logo o EV por real apostado
# é o mesmo de 16 jogos aleatórios de 15. O que muda é a concentração. Se `d` das
# 15 sorteadas caem no cartão, cada um dos 16 jogos omite uma dezena do cartão:
# omitir uma sorteada dá d-1 acertos, omitir uma não sorteada dá d. Portanto
#     d jogos com (d-1) acertos  +  (16-d) jogos com d acertos
# e em d=15 isso é um 15 acompanhado de quinze 14 no mesmo bilhete. Troca de
# variância, não de retorno esperado.
#
# CONSTRUÇÃO — a estratégia escolhida gera o NÚCLEO de 15 dezenas normalmente e
# passa por `validar_jogo_loto`, que está calibrado contra os 3.729 concursos
# reais. A 16ª dezena é acrescentada depois. Nenhum gerador muda (as cotas 6/9 da
# Inversão, 7/8 do Cercamento, as assinaturas de cor do histórico — que somam 15 e
# não existem em 16 — seguem íntegras) e nenhum filtro precisa de recalibração,
# porque continuam sendo aplicados a um jogo de 15, que é para o que foram medidos.
# INEDITISMO — o único filtro que NÃO pode ficar só no núcleo. `validar_ineditismo`
# exige < 14 dezenas em comum com qualquer concurso passado. Um cartão de 16 com 14
# em comum contém DUAS apostas simples de 15 com 14 em comum com aquele resultado, e
# um com 15 em comum contém o resultado já sorteado inteiro — o filtro do núcleo não
# se propaga sozinho. Por isso a dezena acrescentada sai só de entre as que preservam
# o ineditismo do CARTÃO; ver `dezenas_proibidas_ineditismo`. Medido sobre os 3.729
# concursos reais, 200 cartões por estratégia: sem esse filtro, 72,0% dos cartões
# caíam em sobreposição 14 (200/200 em Errar 10 e no Espelho, onde o argmax do score
# acerta sempre uma dezena crítica); com ele, 3,2%. O resíduo são núcleos "encurralados"
# em que nenhuma das 10 dezenas de fora é viável (4,4% dos núcleos): ali o filtro
# relaxa — um cartão marcado é melhor que nenhum cartão — e `indice_popularidade`
# exibe "≈ resultado já sorteado" na tela.
#
# CONTRAPARTIDA HONESTA: soma, sequência e cores continuam checados só no núcleo. Não
# há como aplicá-los às 16 apostas simples sem a recalibração que esta construção
# evita, e pelo backtest de 225k jogos esses filtros não têm valor preditivo
# comprovado: servem para evitar jogos estruturalmente ruins, não para prever o
# sorteio. O ineditismo é caso à parte porque não é uma aposta estatística — é a
# garantia de não sugerir um bilhete que já saiu.
TAMANHOS_CARTAO    = [15, 16]
PRECO_JOGO_SIMPLES = 3.50

def brl(valor):
    """R$ no formato brasileiro: milhar com ponto, decimal com vírgula."""
    return "R$ " + f"{valor:,.2f}".translate(str.maketrans({",": ".", ".": ","}))

def custo_cartao(tam):
    """Apostas simples equivalentes a um cartão de `tam` dezenas: C(tam, 15)."""
    return comb(tam, 15)

def dezenas_proibidas_ineditismo(jogo, historico_sets):
    """Dezenas que, acrescentadas a `jogo`, quebrariam o ineditismo do cartão.

    O núcleo aprovado tem no máximo 13 dezenas em comum com qualquer concurso
    passado (`validar_ineditismo` exige < 14). Acrescentar uma dezena que
    pertence a um concurso onde o núcleo já bate 13 leva o cartão a 14 — e um
    cartão de 16 com 14 em comum contém DUAS apostas simples de 15 com 14 em
    comum com aquele resultado, que é precisamente o que o filtro proíbe. Se o
    núcleo bate 14 (só possível vindo de um caminho de `_fallback`, que não
    checa ineditismo), acrescentar a dezena que falta produz um cartão que
    CONTÉM o concurso inteiro: uma das 16 apostas simples é o resultado já
    sorteado, letra por letra.

    Medido sobre os 3.729 concursos reais: sem este filtro, 72% dos cartões de
    16 gerados caíam em sobreposição 14 (100% em Errar 10 e no Espelho, onde o
    argmax do score ponderado acerta sempre uma dezena crítica).

    Uma passada só pelo histórico: as sobreposições ≤ 12 não podem chegar a 14
    com uma única dezena e são ignoradas."""
    js = set(jogo)
    # Uma dezena eleva a sobreposição em 1 no máximo. Só os concursos onde o
    # jogo já bate 13+ podem chegar a 14 — os demais são irrelevantes aqui.
    # O limiar 13 é do passo unitário e não depende do tamanho do cartão:
    # `montar_cartao` acrescenta uma dezena por vez e recalcula.
    proibidas = set()
    for h in historico_sets:
        if len(js & h) >= 13:
            proibidas |= (h - js)
    return proibidas

def dezena_extra(jogo, historico_analise, ultimo, pool=None, pesos_modelo=None,
                 deterministico=False, historico_sets=None):
    """Dezena adicional do cartão estendido, escolhida entre as que ficaram fora
    do núcleo pelo score do Modelo Ponderado (frequência + atraso + repetição).

    É o único score do app que ordena as 25 dezenas por completo — os outros
    geradores são amostradores por cota e não respondem "qual é a 16ª melhor".

    `historico_sets` (histórico COMPLETO, como nos geradores) restringe os
    candidatos aos que preservam o ineditismo do cartão — ver
    `dezenas_proibidas_ineditismo`. Se nenhum candidato sobreviver, o filtro é
    relaxado e a escolha volta a ser livre: um cartão marcado por
    `indice_popularidade` como "≈ resultado já sorteado" é melhor que nenhum
    cartão, e o aviso aparece na tela.

    `deterministico=True` devolve o argmax, para as estratégias de ranking
    (Errar 10 e espelho) que precisam de um bilhete estável por recorte. Nas
    demais a dezena é sorteada com peso proporcional ao score: fixar o argmax
    colaria a MESMA dezena em todos os cartões do lote e subiria a sobreposição
    média da carteira em 1 ponto — a concentração que `carteira_deslizante`
    mede como prejudicial ao melhor bilhete (t = -4,55)."""
    p = set(pool if pool is not None else TODAS)
    fora = sorted(p - set(jogo))
    if not fora:
        return None
    if historico_sets:
        proibidas = dezenas_proibidas_ineditismo(jogo, historico_sets)
        candidatos = [d for d in fora if d not in proibidas] or fora
    else:
        candidatos = fora
    w = pesos_modelo or PESOS_PONDERADO_PADRAO
    pesos = pesos_ponderados(
        historico_analise or [], ultimo or [],
        w.get("freq", 1.0), w.get("atraso", 1.0), w.get("rep", 1.0),
    )
    if deterministico:
        return max(candidatos, key=lambda d: (pesos[d], -d))
    return _amostra_ponderada(candidatos, [pesos[d] for d in candidatos], 1)[0]

def montar_cartao(nucleo, tam, historico_analise, ultimo, pool=None,
                  pesos_modelo=None, deterministico=False, historico_sets=None):
    """Cartão final a partir do núcleo. `tam <= len(nucleo)` devolve o núcleo
    intacto — é o caminho de 15 dezenas, byte por byte igual ao anterior.

    `historico_sets` é o histórico completo, usado só para manter o ineditismo
    do cartão; sem ele a extensão é feita sem essa checagem."""
    jogo = sorted(nucleo)
    while len(jogo) < tam:
        d = dezena_extra(jogo, historico_analise, ultimo, pool=pool,
                         pesos_modelo=pesos_modelo, deterministico=deterministico,
                         historico_sets=historico_sets)
        if d is None:
            break
        jogo = sorted(jogo + [d])
    return jogo

def gerar_estrategia_loto(tipo, frequencia, historico_sets, ultimo, fixas=None, pool=None,
                          historico_analise=None, pesos_modelo=None):
    """`historico_analise` é o recorte usado para estatística (frequência, atraso,
    assinaturas de cor). `historico_sets` permanece o histórico completo, usado
    apenas no filtro de ineditismo."""
    if fixas is None:
        fixas = []
    p = pool
    if tipo == "Modelo Ponderado":
        return gerar_modelo_ponderado(historico_sets, ultimo, pool=p,
                                      historico_analise=historico_analise,
                                      pesos_modelo=pesos_modelo)
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
    elif tipo == "Padrão de Cores":
        return gerar_padrao_cores(historico_sets, pool=p,
                                  historico_analise=historico_analise)
    elif tipo == "Errar 10":
        return gerar_errar_dez(historico_sets, ultimo, pool=p,
                               historico_analise=historico_analise)
    elif tipo == "Espelho do Errar 10":
        return gerar_errar_dez(historico_sets, ultimo, pool=p,
                               historico_analise=historico_analise, inverter=True)
    return _fallback(historico_sets, pool=p)

# ── MINHA ESTRATÉGIA (CERCAMENTO ROTATIVO) ─────────────────────────────────────
# Toggle que se ACOPLA a qualquer estratégia existente em vez de substituí-la.
# Jogo 1 sai da estratégia escolhida, normalmente. Jogo N+1 fixa as dezenas que o
# jogo N deixou de fora e deixa a estratégia escolher o restante DENTRO do jogo N.
# Cartão de 15: 10 fixas + 5 livres. Cartão de 16: 9 fixas + 7 livres. A
# sobreposição entre jogos consecutivos é exatamente o número de livres — 5 e 7.
#
# EFEITO MEDIDO — 20 réplicas independentes, ganho no MELHOR bilhete da carteira
# contra uma carteira independente do mesmo tamanho:
#     cartão 15:   3 jogos +0,146 (t=+17,1)    5 jogos +0,071 (t=+7,9)
#                 10 jogos +0,032 (t=+5,9)    20 jogos +0,006 (t=+1,2)
#     cartão 16:   3 jogos +0,156 (t=+17,9)    5 jogos +0,101 (t=+13,3)
#                 10 jogos +0,047 (t=+5,7)
# Replicável: 19 ou 20 das 20 réplicas positivas em toda configuração útil. E tem
# mecanismo, não é garimpo de padrão: os bilhetes ficam anticorrelacionados. Uma
# carteira independente pode ser TODA ruim no mesmo sorteio; a rotativa não pode,
# porque os jogos 1 e 2 juntos cobrem as 25 dezenas. É o espelho exato do que
# `carteira_deslizante` mede — lá a concentração custa 0,22 acerto no melhor
# bilhete (t = -4,55). Mesma dimensão, sinal oposto.
#
# ONDE O GANHO NÃO ESTÁ — 90.000 sorteios, cartão 15, 5 jogos. O rotativo torna
# ARITMETICAMENTE IMPOSSÍVEL a carteira toda fazer <= 8 (0,0000% contra 0,4611%
# da independente) e derruba o "melhor = 9" de 12,31% para 5,73%. Em troca
# comprime o topo:
#     P(melhor >= 11)   +0,64 pp   (z = +2,74)
#     P(melhor >= 12)   -0,18 pp   (z = -1,33)
#     P(melhor >= 14)  +0,003 pp   (z = +0,52 — ruído)
# É redução de variância, não vantagem: mais R$ 6 e R$ 12 com regularidade e
# NENHUMA melhora na chance de prêmio grande. O efeito também morre com carteira
# grande (+0,006 com 20 bilhetes de 15) — rende de 3 a 5 jogos.
MAX_IGUAIS_LOTE = 11   # "não pode ter 12 ou mais iguais" entre os jogos gerados
ROTULO_ROTATIVO = "Minha Estratégia (cercamento rotativo)"
# Definido aqui, e não junto de `gerar_super_estrategia`, porque
# `ESTRATEGIAS_SEM_ROTATIVO` logo abaixo precisa dele no momento do import.
ROTULO_SUPER    = "SuperEstratégia (todas as regras)"

# Estratégias incompatíveis com a rotação:
#  - Fechamento Garantido devolve um conjunto fechado por set cover: trocar
#    qualquer jogo quebra a garantia de cobertura;
#  - "Melhor Jogo (IA)" NÃO está aqui. Ele devolve um jogo só, que é exatamente
#    o que a âncora precisa, e é estocástico (30 chamadas, 30 jogos distintos),
#    então também serve para escolher as livres. Ver `_jogo_base_rotativo`;
#  - Errar 10 e o Espelho são determinísticos, e a rotação COLAPSA sobre eles.
#    Para um recorte fixo a estratégia devolve sempre o mesmo jogo J. O jogo 2 é
#    (25 - J) mais k dezenas de J; no jogo 3 a única oferta da estratégia dentro
#    do jogo 2 são exatamente essas k, então o jogo 3 reconstrói J e a carteira
#    trava em 2 bilhetes. O app já tem `carteira_deslizante` para dar variedade
#    a elas, variando o recorte em vez do jogo.
# "Errar 10"/"Espelho do Errar 10" repetidos literalmente: `ESTRATEGIAS_DETERMINISTICAS`
# só é definido bem mais abaixo, junto do backtest, e referenciá-lo aqui quebraria o
# import. A checagem de consistência entre os dois conjuntos está logo após aquela
# definição.
ESTRATEGIAS_SEM_ROTATIVO = {"Fechamento Garantido (Cobertura)",
                            "Errar 10", "Espelho do Errar 10",
                            ROTULO_SUPER}

ROTULO_MELHOR = "Melhor Jogo (IA)"

def _jogo_base_rotativo(tipo, frequencia, historico_sets, ultimo, fixas=None,
                        pool=None, historico_analise=None, pesos_modelo=None):
    """Um jogo de 15 dezenas da estratégia `tipo`, incluindo as meta-estratégias.

    `gerar_estrategia_loto` não conhece "Melhor Jogo (IA)": o nome não bate com
    nenhum ramo e cai no `_fallback`, devolvendo um jogo aleatório filtrado com o
    rótulo errado — silenciosamente. Por isso o despacho aqui é explícito.

    `gerar_melhor_jogo_loto` está definido mais abaixo no arquivo; o nome é
    resolvido na chamada, não na definição, então a ordem não importa."""
    if tipo == ROTULO_MELHOR:
        jogo, _nome, _score, _ranking = gerar_melhor_jogo_loto(
            frequencia, historico_sets, ultimo, pool=pool,
            historico_analise=historico_analise, pesos_modelo=pesos_modelo,
        )
        return jogo
    return gerar_estrategia_loto(tipo, frequencia, historico_sets, ultimo,
                                 fixas=fixas, pool=pool,
                                 historico_analise=historico_analise,
                                 pesos_modelo=pesos_modelo)

def _oferta_estrategia(tipo, permitidas, n, frequencia, historico_sets, ultimo,
                       fixas=None, pool=None, historico_analise=None,
                       pesos_modelo=None):
    """Dezenas que a estratégia `tipo` oferece dentro de `permitidas`.

    Os geradores do app não aceitam dezenas fixas — recebem pool e cota e
    devolvem um jogo fechado. Para preservar "a estratégia escolheu", gera-se um
    candidato normal e aproveitam-se as dezenas dele que caem na região
    permitida.

    Devolve a oferta INTEIRA, não `n` dezenas já sorteadas. Medido com 300
    candidatos da Anti-Popular: a oferta tem de 6 a 13 dezenas (moda 9 quando as
    livres são 5, moda 10 quando são 7) e cobre `n` em 300/300 dos casos — ou
    seja, cada chamada do gerador financia ~C(10,7) = 120 escolhas distintas das
    livres. Quem consome deve varrer essas escolhas em vez de gastar uma chamada
    nova por tentativa; sortear uma só e descartar a oferta era o que fazia a
    carteira de 16 dezenas parar em 11 ou 13 jogos de 20 pedidos.

    Se a oferta vier menor que `n` (pool restrito), é completada por amostragem
    ponderada pelo Modelo Ponderado sobre o resto de `permitidas`."""
    perm = sorted(permitidas)
    if n >= len(perm):
        return perm
    cand = _jogo_base_rotativo(tipo, frequencia, historico_sets, ultimo,
                               fixas=fixas, pool=pool,
                               historico_analise=historico_analise,
                               pesos_modelo=pesos_modelo)
    oferta = [d for d in cand if d in permitidas]
    if len(oferta) >= n:
        return sorted(oferta)
    resto = [d for d in perm if d not in oferta]
    falta = min(n - len(oferta), len(resto))
    if falta > 0:
        w = pesos_modelo or PESOS_PONDERADO_PADRAO
        pesos = pesos_ponderados(
            historico_analise or [], ultimo or [],
            w.get("freq", 1.0), w.get("atraso", 1.0), w.get("rep", 1.0),
        )
        oferta = oferta + _amostra_ponderada(resto, [pesos[d] for d in resto], falta)
    return sorted(oferta)

def pool_minimo_rotativo(tam, max_iguais=MAX_IGUAIS_LOTE):
    """`(minimo_teorico, confortavel_medido)` de dezenas no pool para a rotação.

    A rotação força a sobreposição entre jogos CONSECUTIVOS a ser exatamente
    `2*tam - len(pool)`: o jogo seguinte contém as `len(pool) - tam` dezenas que
    o anterior deixou de fora, e o resto vem de dentro dele. Excluir dezenas na
    barra lateral encolhe o pool e ESTREITA a rotação — o efeito é o oposto do
    intuitivo. Acima de `max_iguais` a rotação é impossível por construção, não
    por falta de tentativas.

    O mínimo teórico não é utilizável: nele cada jogo já nasce colado no
    anterior e a corrente morre no terceiro bilhete. Medido com 20 jogos
    pedidos, mediana de 10 seeds (Anti-Popular, com o laço duplo de ofertas):

        pool      25     24     23     22     21     20     19     18
        tam 15  20/20  20/20  20/20  20/20  16/20   6/20   3/20   1/20
        tam 16  20/20  12/20   6/20   4/20   3/20   1/20   1/20   1/20

    Daí os confortáveis serem 22 (cartão de 15) e 25 (cartão de 16) — medidos,
    não derivados: no mesmo `2*tam - len(pool)` o cartão de 16 se sai pior,
    porque dois cartões de 16 já se sobrepõem em 10,24 dezenas na média contra
    9,00 dos de 15, e o teto de 11 fica muito mais perto.
    """
    confortavel = {15: 22, 16: 25}.get(tam, 2 * tam - 7)
    return 2 * tam - max_iguais, confortavel

def gerar_carteira_rotativa(tipo, qtd, frequencia, historico_sets, ultimo, tam=15,
                            fixas=None, pool=None, historico_analise=None,
                            pesos_modelo=None, max_iguais=MAX_IGUAIS_LOTE,
                            tentativas=20, subtentativas=40):
    """Cercamento rotativo. Devolve `(jogos, diag)`.

    RESTRIÇÕES, em ordem de prioridade — as duas primeiras são duras, a terceira
    é melhor esforço:
      1. ineditismo contra o histórico completo (`validar_ineditismo`, < 14 em
         comum com qualquer concurso). Aplicado ao CARTÃO inteiro, o que também
         impede que um cartão de 16 contenha uma aposta simples de 15 com 14 em
         comum com um resultado já sorteado — ver o bloco CARTÃO ESTENDIDO.
      2. `max_iguais` contra TODOS os jogos já no lote, não só o anterior. A
         rotação garante 5 (ou 7) de sobreposição entre CONSECUTIVOS, mas o jogo
         3 reencontra o jogo 1 com 10 + k dezenas em comum, onde k é quanto das
         livres do jogo 3 veio das livres do jogo 2. Sem esta checagem a regra
         dos 12 seria violada já no terceiro jogo.
      3. soma e sequência, só quando `tam == 15`. As fixas da rotação são
         forçadas, então nem sempre existe escolha das livres que caiba na faixa
         de soma — exigir aqui esvaziaria a carteira. Para `tam == 16` os
         limiares não se aplicam (são calibrados sobre concursos de 15 dezenas) e
         não são checados: os jogos 2+ do rotativo são montados direto no tamanho
         final, sem o núcleo de 15 validado que `montar_cartao` preserva.

    `diag` traz `reancoras` (vezes que a rotação encurralou e precisou reiniciar
    de um jogo novo da estratégia) e `relaxados` (cartões aceitos sem passar em
    soma/sequência)."""
    p = set(pool if pool is not None else TODAS)
    checar_forma = (tam == 15)
    jogos = []
    diag = {"reancoras": 0, "relaxados": 0, "livres": None, "fixas": None}

    def nova_ancora():
        """Jogo da estratégia pura, no tamanho pedido.

        `montar_cartao` relaxa o filtro de ineditismo quando o núcleo está
        encurralado (3,3% dos núcleos, medido nos 3.729 concursos): nenhuma das
        dezenas de fora mantém o cartão abaixo de 14 em comum. Aqui há saída
        barata que lá não havia — gerar outro núcleo. Só depois de esgotar as
        tentativas a âncora relaxada é aceita, e o caso entra em `relaxados`."""
        ultimo_cand = None
        for _ in range(tentativas):
            nucleo = _jogo_base_rotativo(tipo, frequencia, historico_sets, ultimo,
                                         fixas=fixas, pool=pool,
                                         historico_analise=historico_analise,
                                         pesos_modelo=pesos_modelo)
            ultimo_cand = montar_cartao(nucleo, tam, historico_analise, ultimo,
                                        pool=pool, pesos_modelo=pesos_modelo,
                                        historico_sets=historico_sets)
            if validar_ineditismo(ultimo_cand, historico_sets):
                return ultimo_cand
        diag["relaxados"] += 1
        return ultimo_cand

    while len(jogos) < qtd:
        if not jogos:
            jogos.append(nova_ancora())
            continue

        ant = set(jogos[-1])
        fixas_rot = p - ant
        livres = tam - len(fixas_rot)
        diag["fixas"], diag["livres"] = len(fixas_rot), livres
        if livres <= 0 or livres > len(ant):
            break   # pool restrito demais para a rotação caber no tamanho pedido

        novo = relaxado = None
        # Laço duplo: o externo paga uma chamada do gerador e ganha uma OFERTA de
        # ~10 dezenas dentro do jogo anterior; o interno varre as escolhas das
        # livres dentro dessa mesma oferta, a custo quase zero. Antes só uma
        # escolha era testada por chamada, e a carteira de 16 dezenas parava em
        # 11 a 17 jogos de 20 pedidos. Ver `_oferta_estrategia`.
        for _ in range(tentativas):
            oferta = _oferta_estrategia(
                tipo, ant, livres, frequencia, historico_sets, ultimo,
                fixas=fixas, pool=pool, historico_analise=historico_analise,
                pesos_modelo=pesos_modelo,
            )
            # Oferta do tamanho exato das livres não admite variação: uma volta
            # só, e o laço externo busca outra oferta.
            voltas = subtentativas if len(oferta) > livres else 1
            for _ in range(voltas):
                picks = (random.sample(oferta, livres) if len(oferta) > livres
                         else list(oferta))
                cand = sorted(fixas_rot | set(picks))
                if len(cand) != tam:
                    continue
                if not validar_ineditismo(cand, historico_sets):
                    continue
                if any(len(set(cand) & set(j)) > max_iguais for j in jogos):
                    continue
                if not checar_forma or (validar_soma(cand) and validar_sequencia(cand)
                                        and validar_proporcao_142857(cand)):
                    novo = cand
                    break
                if relaxado is None:
                    relaxado = cand
            if novo is not None:
                break
        if novo is None and relaxado is not None:
            novo = relaxado
            diag["relaxados"] += 1
        if novo is None:
            # Rotação encurralada: nenhuma escolha das livres respeita as duas
            # restrições duras. Reancora num jogo novo da estratégia em vez de
            # devolver menos jogos do que o usuário pediu.
            reancora = None
            for _ in range(tentativas):
                c = nova_ancora()
                if all(len(set(c) & set(j)) <= max_iguais for j in jogos):
                    reancora = c
                    break
            if reancora is None:
                break
            diag["reancoras"] += 1
            jogos.append(reancora)
            continue
        jogos.append(novo)
    return jogos, diag

# ── SUPERESTRATÉGIA (todas as regras ao mesmo tempo) ──────────────────────────
# As estratégias do app são GERADORAS, não validadoras: cada uma tem a própria
# receita de montar o jogo, e não existe `validar_inversao_suprema()`. Para exigir
# que um jogo satisfaça todas ao mesmo tempo, cada receita foi convertida na regra
# que ela produz. Duas fusões foram necessárias:
#
#   1. Inversão Suprema (6 ausentes) e Cercamento 7/8 (7 ausentes) são
#      MUTUAMENTE EXCLUSIVAS — um jogo tem um único número de dezenas ausentes do
#      último concurso. Medido: 0 jogos em 60.000 satisfazem as duas. Viraram um
#      só mostrador que reveza 6 e 7 entre os jogos do lote.
#   2. Rastreio Ciclo 3 exige as frias dos últimos 3 concursos; Equilíbrio IA
#      exige as mesmas frias MAIS 7 ou 8 ímpares. Medido: o Ciclo 3 não barrava
#      um único jogo que o Equilíbrio já não barrasse (6.849 -> 6.849) — era
#      redundante por completo. Viraram a regra das frias, sempre exigida, mais
#      um segundo mostrador que reveza 7 e 8 ímpares.
#
# Ranking Frequência e Modelo Ponderado ficam de fora: não impõem nada, apenas
# ponderam a amostragem. Fixas de Ouro, Fechamento de Dezenas e Fechamento
# Garantido também, por dependerem de dezenas escolhidas à mão.
#
# VIABILIDADE MEDIDA (120.000 jogos aleatórios, histórico completo):
#     ausentes  ímpares   sobrevivem   ~1 em
#         6        7        0,563%      178
#         6        8        0,634%      158
#         7        7        0,466%      215
#         7        8        0,604%      166
# As quatro combinações existem. Em 120 concursos com 5 jogos cada: zero falhas.
#
# DESEMPENHO MEDIDO — walk-forward em 150 concursos reais, 3 jogos por concurso:
#     SuperEstratégia  8,9956 acertos (ep 0,0582)
#     aleatório puro   9,0533 acertos (ep 0,0586)
#     diferença pareada -0,0578 (ep 0,0862, t = -0,67)
# Empate técnico, como a matemática exige: escolher uniformemente dentro de um
# subconjunto A não muda a probabilidade, porque |A| se cancela (ver a prova no
# docstring de `validar_ineditismo`). Empilhar seis regras não aumenta a chance
# de acertar em nada. O que muda é o perfil: exigir popularidade zero mais cinco
# restrições produz o jogo menos jogado que este app sabe montar, o que reduz a
# divisão do prêmio em caso de acerto. É o único efeito real.
SUPER_AUSENTES  = (6, 7)   # Inversão Suprema / Cercamento 7/8, revezando
SUPER_IMPARES   = (7, 8)   # as duas metades do Equilíbrio IA, revezando


def mostradores_super(i):
    """`(n_ausentes, n_impares)` do i-ésimo jogo do lote.

    Os dois mostradores revezam em passos diferentes — o dos ausentes a cada
    jogo, o dos ímpares a cada dois — para que as quatro combinações apareçam
    antes de qualquer uma repetir."""
    return SUPER_AUSENTES[i % 2], SUPER_IMPARES[(i // 2) % 2]


def gerar_super_estrategia(qtd, frequencia, historico_sets, ultimo, tam=15, pool=None,
                           historico_analise=None, pesos_modelo=None,
                           tentativas=150000):
    """Devolve `(jogos, diag)`. Cada jogo passa por seis porteiros, na ordem do
    mais barato e mais seletivo para o mais caro.

    `diag` traz `funil` (quantas reprovações por porteiro), `mostradores` (o par
    usado em cada jogo), `frias` (as dezenas frias do momento) e `relaxados`
    (jogos aceitos sem o porteiro anti-popular, quando nada estrito apareceu).
    """
    p = set(pool if pool is not None else TODAS)
    p_list = sorted(p)
    base = historico_analise if historico_analise is not None else historico_sets
    ult = set(ultimo or [])
    frias = (p - (historico_sets[-1] | historico_sets[-2] | historico_sets[-3])
             if len(historico_sets) >= 3 else set())
    n_frias = min(3, len(frias))
    assins = set(assinaturas_cores(base)) if base else set()

    jogos = []
    diag = {"funil": Counter(), "mostradores": [], "relaxados": 0,
            "frias": sorted(frias), "tentativas": [],
            "assinaturas": len(assins)}
    if len(p_list) < 15:
        return jogos, diag

    vistos = set()
    for i in range(qtd):
        n_aus, n_imp = mostradores_super(i)
        diag["mostradores"].append((n_aus, n_imp))
        achou = relaxado = None
        achou_nuc = relaxado_nuc = None
        gastas = 0
        for _ in range(tentativas):
            gastas += 1
            j = sorted(random.sample(p_list, 15))
            js = set(j)
            if len(js - ult) != n_aus:
                diag["funil"]["cerco (6 ou 7 ausentes)"] += 1; continue
            if sum(1 for x in j if x % 2) != n_imp:
                diag["funil"]["ímpares (7 ou 8)"] += 1; continue
            if len(js & frias) < n_frias:
                diag["funil"]["frias dos últimos 3"] += 1; continue
            if assins and tuple(sum(1 for n in j if n % 10 == f)
                                for f in FINAIS_ORDEM) not in assins:
                diag["funil"]["assinatura de cores"] += 1; continue
            if tuple(j) in vistos:
                diag["funil"]["repetido no lote"] += 1; continue
            if not validar_jogo_loto(j, historico_sets):
                diag["funil"]["filtros base"] += 1; continue
            popular = indice_popularidade(j, historico_sets)[0] != 0
            cartao = montar_cartao(j, tam, historico_analise, ultimo, pool=pool,
                                   pesos_modelo=pesos_modelo,
                                   historico_sets=historico_sets)
            if len(cartao) > 15 and not validar_ineditismo(cartao, historico_sets):
                # `montar_cartao` relaxa o ineditismo quando o núcleo está
                # encurralado — 3,3% dos núcleos, medido nos 3.729 concursos:
                # nenhuma das dezenas de fora mantém o cartão abaixo de 14 em
                # comum. Aqui há saída barata que lá não havia: procurar outro
                # núcleo, já que o laço está justamente fazendo isso.
                diag["funil"]["ineditismo do cartão estendido"] += 1
                continue
            if popular:
                diag["funil"]["anti-popular (popularidade 0)"] += 1
                if relaxado is None:
                    relaxado, relaxado_nuc = cartao, j
                continue
            achou, achou_nuc = cartao, j
            break
        if achou is None:
            # Nada estrito apareceu: o anti-popular é o porteiro mais caro e o
            # menos essencial (não muda a chance, só a divisão do prêmio), então
            # é o único que se relaxa. Sem candidato nem relaxado, o lote para.
            if relaxado is None:
                break
            achou, achou_nuc = relaxado, relaxado_nuc
            diag["relaxados"] += 1
        diag["tentativas"].append(gastas)
        vistos.add(tuple(achou_nuc))
        jogos.append(achou)
    return jogos, diag

# ── JOGO MÚLTIPLO ───────────────────────────────────────────────────────────────
ESTRATEGIAS_MULTIPLO = [
    "Anti-Popular",
    "Inversão Suprema",
    "Cercamento 7/8",
    "Equilíbrio IA 2026",
    "Ranking Frequência",
    "Rastreio Ciclo 3",
    "Padrão de Cores",
    "Modelo Ponderado",
]
N_ESTRATEGIAS_MULTIPLO = len(ESTRATEGIAS_MULTIPLO)

CORES_ESTRATEGIA = {
    "Anti-Popular":         "FFD6D6",
    "Inversão Suprema":     "D6E6FF",
    "Cercamento 7/8":       "D6FFDA",
    "Equilíbrio IA 2026":   "FFF3D6",
    "Ranking Frequência":   "EAD6FF",
    "Rastreio Ciclo 3":     "D6FFF6",
    "Padrão de Cores":      "FFE3C9",
    "Modelo Ponderado":     "D9D9D9",
    "Errar 10":             "E8E0FF",
    "Espelho do Errar 10":  "C9F0E3",
}

# Errar 10 e seu espelho ficam fora do Jogo Múltiplo e do Melhor Jogo: são
# instrumentos de medição do modelo de ausência, não sugestões de aposta.
ESTRATEGIAS_BACKTEST = ESTRATEGIAS_MULTIPLO + ["Errar 10", "Espelho do Errar 10"]

def gerar_jogo_multiplo(qtd_por_estrategia, frequencia, historico_sets, ultimo, pool=None,
                        historico_analise=None, pesos_modelo=None):
    """Gera `qtd_por_estrategia` jogos de CADA estratégia de ESTRATEGIAS_MULTIPLO,
    em blocos agrupados (todos os jogos de uma estratégia antes de passar para a
    próxima — sem intercalar). Total = qtd_por_estrategia * N_ESTRATEGIAS_MULTIPLO.
    Cada jogo é validado contra o histórico + os jogos já gerados neste lote
    (evita repetir a mesma combinação dentro do próprio múltiplo)."""
    jogos = []
    sets_lote = list(historico_sets)
    for tipo in ESTRATEGIAS_MULTIPLO:
        for _ in range(qtd_por_estrategia):
            jogo = None
            for _ in range(20):
                candidato = gerar_estrategia_loto(
                    tipo, frequencia, historico_sets, ultimo, pool=pool,
                    historico_analise=historico_analise, pesos_modelo=pesos_modelo,
                )
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
    n_bolas = max((len(j) for j, _ in resultado_multiplo), default=15)
    ws.append([f"Bola{i}" for i in range(1, n_bolas + 1)] + ["Estrategia"])
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
def gerar_melhor_jogo_loto(frequencia, historico_sets, ultimo, pool=None,
                           historico_analise=None, pesos_modelo=None):
    candidatos = []
    for tipo in ESTRATEGIAS_MULTIPLO:
        jogo = gerar_estrategia_loto(
            tipo, frequencia, historico_sets, ultimo, pool=pool,
            historico_analise=historico_analise, pesos_modelo=pesos_modelo,
        )
        score = pontuar_jogo_loto(jogo, historico_sets, frequencia)
        candidatos.append((jogo, tipo, score))
    candidatos.sort(key=lambda x: x[2])  # menor popularidade primeiro
    ranking = [(nome, score) for (_, nome, score) in candidatos]
    jogo_best, nome_best, score_best = candidatos[0]
    return jogo_best, nome_best, score_best, ranking

# ── SIMULAÇÃO ──────────────────────────────────────────────────────────────────
def simular_ate_acertar(resultado_alvo, min_acertos, frequencia, pool,
                        max_tentativas, historico_sets, ultimo,
                        estrategia="Aleatório Ponderado (Rápido)",
                        historico_analise=None, pesos_modelo=None):
    """Retorna (tentativas, jogo_vencedor, diag).

    `diag` mede o comportamento da estratégia durante a busca:
      - gerados:     jogos válidos produzidos;
      - distintos:   quantos deles eram combinações diferentes (cobertura real);
      - hist:        Counter de acertos → quantos jogos tiveram cada nº de acertos;
      - max_acertos: melhor acerto atingido, mesmo abaixo do alvo.
    Uma estratégia com `distintos` muito abaixo de `gerados` está presa num
    subespaço pequeno e nunca alcança o alvo, por mais tentativas que faça."""
    alvo = set(resultado_alvo)
    p = sorted(pool if pool is not None else TODAS)
    diag = {"gerados": 0, "distintos": 0, "hist": Counter(), "max_acertos": 0}
    vistos = set()

    def registrar(jogo):
        """Contabiliza o jogo no diagnóstico e devolve seus acertos."""
        vistos.add(tuple(jogo))
        acertos = len(set(jogo) & alvo)
        diag["gerados"] += 1
        diag["hist"][acertos] += 1
        if acertos > diag["max_acertos"]:
            diag["max_acertos"] = acertos
        return acertos

    def fechar(tent, jogo):
        diag["distintos"] = len(vistos)
        return tent, jogo, diag

    if len(p) < 15:
        return fechar(max_tentativas, None)

    if estrategia != "Aleatório Ponderado (Rápido)":
        for tent in range(1, max_tentativas + 1):
            jogo = gerar_estrategia_loto(
                estrategia, frequencia,
                historico_sets=[],   # desabilita ineditismo para performance
                ultimo=ultimo,
                pool=pool,
                historico_analise=historico_analise,
                pesos_modelo=pesos_modelo,
            )
            if registrar(jogo) >= min_acertos:
                return fechar(tent, jogo)
        return fechar(max_tentativas, None)

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

    # `max_tentativas` conta JOGOS VÁLIDOS, não sorteios: um jogo reprovado nos
    # filtros não é uma tentativa de acerto e não pode consumir o orçamento —
    # senão o total vira ~35% do que a tela promete. `limite_sorteios` é só a
    # trava contra loop infinito caso os filtros rejeitem quase tudo.
    validos = sorteios = 0
    limite_sorteios = max_tentativas * 20
    while validos < max_tentativas and sorteios < limite_sorteios:
        sorteios += 1
        jogo = _sorteia()
        if jogo is None or len(jogo) != 15:
            continue
        if not validar_soma(jogo) or not validar_sequencia(jogo):
            continue
        if not validar_proporcao_142857(jogo):
            continue
        validos += 1
        if registrar(jogo) >= min_acertos:
            return fechar(validos, jogo)
    return fechar(validos, None)

# ── BACKTEST WALK-FORWARD ──────────────────────────────────────────────────────
# Estratégias cujo resultado muda conforme o recorte de análise. As demais só
# olham o último concurso (ou nada do histórico), então rodá-las por janela seria
# repetir o mesmo experimento com rótulos diferentes.
ESTRATEGIAS_SENSIVEIS_JANELA = {
    "Ranking Frequência", "Padrão de Cores", "Modelo Ponderado",
    "Errar 10", "Espelho do Errar 10",
}
# Estratégias sem sorteio interno: dado o mesmo recorte e o mesmo último
# concurso, devolvem sempre o MESMO jogo. Chamá-las N vezes devolve N cópias, e
# N linhas idênticas no backtest mantêm média e desvio mas multiplicam o tamanho
# da amostra, encolhendo o erro-padrão por sqrt(N) sem uma única observação nova
# (t = +3,10 com 1 jogo por concurso viraria t = +5,37 com 3, artefato puro de
# contagem). Por isso o backtest NÃO as repete: pede uma CARTEIRA de
# `jogos_por_concurso` recortes deslizantes disjuntos, que são jogos de verdade
# diferentes. A "Janela" da série passa a ser o tamanho de cada recorte da
# carteira; recorte "Tudo" não define carteira e roda como jogo único.
ESTRATEGIAS_DETERMINISTICAS = {"Errar 10", "Espelho do Errar 10"}
# `ESTRATEGIAS_SEM_ROTATIVO` repete estes dois nomes literalmente porque é
# definido antes daqui; se um for renomeado, esta checagem estoura no import.
assert ESTRATEGIAS_DETERMINISTICAS <= ESTRATEGIAS_SEM_ROTATIVO
BASELINE_ALEATORIO = "Aleatório (baseline)"

def _rotulo_janela(janela):
    return "Tudo" if not janela else f"Últimos {janela}"

def backtest_walkforward(historico_sets, estrategias, janelas, n_concursos=30,
                         jogos_por_concurso=3, pool=None, pesos_modelo=None,
                         hist_ineditismo=200, progresso=None):
    """Backtest honesto: para cada um dos últimos `n_concursos`, gera jogos usando
    SOMENTE os concursos anteriores a ele e mede os acertos contra o resultado
    real daquele concurso. Nenhuma informação futura entra na geração.

    `hist_ineditismo` trunca quantos concursos passados entram no filtro de
    ineditismo — que é O(n) por candidato e domina o tempo. Nunca houve no
    histórico real dois concursos com 14+ dezenas em comum, então truncar altera
    o tempo de execução, não o resultado.

    Retorna uma lista de dicts (uma linha por jogo gerado)."""
    total = len(historico_sets)
    n = min(int(n_concursos), total - 1)
    if n < 1:
        return []

    tarefas = []
    for est in estrategias:
        if est in ESTRATEGIAS_SENSIVEIS_JANELA:
            tarefas.extend((est, jn) for jn in janelas)
        else:
            tarefas.append((est, None))
    if not tarefas:
        return []

    p_list = sorted(pool if pool is not None else TODAS)
    resultados = []
    passos, feito = n * len(tarefas), 0

    for k in range(n):
        i = total - n + k
        passado = historico_sets[:i]
        alvo = historico_sets[i]
        ultimo = sorted(passado[-1])
        hist_ined = passado[-hist_ineditismo:] if hist_ineditismo else passado
        cache_freq = {}

        for est, jn in tarefas:
            base = passado[-jn:] if jn else passado
            if jn not in cache_freq:
                cache_freq[jn] = calcular_frequencia(base)
            freq = cache_freq[jn]

            rotulo_jn = (_rotulo_janela(jn) if jn else
                         ("—" if est not in ESTRATEGIAS_SENSIVEIS_JANELA else "Tudo"))

            if est in ESTRATEGIAS_DETERMINISTICAS:
                # Carteira de recortes deslizantes disjuntos: `jn` vira o tamanho
                # de cada janela. Sem `jn` não há carteira a definir — jogo único.
                if jn:
                    jogos_conc = [j for j, _ in carteira_deslizante(
                        hist_ined, ultimo, jogos_por_concurso, pool=pool,
                        tamanho=jn, passo=jn,
                        inverter=(est == "Espelho do Errar 10"),
                        base_recortes=passado,   # janelas vêm do passado inteiro
                    )]
                else:
                    jogos_conc = [gerar_estrategia_loto(
                        est, freq, hist_ined, ultimo, pool=pool,
                        historico_analise=base, pesos_modelo=pesos_modelo)]
            elif est == BASELINE_ALEATORIO:
                jogos_conc = [sorted(random.sample(p_list, 15)) if len(p_list) >= 15
                              else p_list for _ in range(jogos_por_concurso)]
            else:
                jogos_conc = [gerar_estrategia_loto(
                    est, freq, hist_ined, ultimo, pool=pool,
                    historico_analise=base, pesos_modelo=pesos_modelo)
                    for _ in range(jogos_por_concurso)]

            for jogo in jogos_conc:
                resultados.append({
                    "Estratégia": est,
                    "Janela": rotulo_jn,
                    "Concurso": i,
                    "Acertos": len(set(jogo) & alvo),
                })

            feito += 1
            if progresso:
                progresso(feito / passos, f"Concurso {k + 1}/{n} — {est}")

    return resultados

# Probabilidades hipergeométricas exatas das duas caudas extremas (15 de 25).
# Errar 10 (acertar 5) é 3.003x mais provável que acertar 15 — por isso é a
# única ponta da distribuição que um histórico de milhares de concursos
# consegue medir com alguma potência estatística.
P_TEORICO_ERRAR10 = comb(15, 5) * comb(10, 10) / comb(25, 15)   # 0,0919%
P_TEORICO_15      = 1 / comb(25, 15)                            # 0,0000306%

def resumir_backtest(resultados):
    """Agrega o backtest por (Estratégia, Janela): média, desvio e as duas caudas.
    A média é o número que quase não se move (esperado ~9,0 por hipergeométrica).
    As caudas são onde uma estratégia pode diferir: a de cima (% 13+ / 14+ / 15)
    e a de baixo (% ≤6 e % =5, o 'errou 10'), simétricas em dificuldade — quem
    prevê as 10 ausentes prevê tão bem quanto quem prevê as 15 sorteadas."""
    if not resultados:
        return pd.DataFrame()
    df = pd.DataFrame(resultados)
    linhas = []
    for (est, jn), g in df.groupby(["Estratégia", "Janela"], sort=False):
        ac = g["Acertos"]
        n = len(ac)
        linhas.append({
            "Estratégia": est,
            "Janela": jn,
            "Jogos": n,
            "Média": round(ac.mean(), 3),
            "Desvio": round(ac.std(ddof=0), 3),
            "Mín": int(ac.min()),
            "Máx": int(ac.max()),
            "% =5 (errou 10)": round(100 * (ac == 5).sum() / n, 3),
            "% 6-": round(100 * (ac <= 6).sum() / n, 2),
            "% 11+": round(100 * (ac >= 11).sum() / n, 2),
            "% 12+": round(100 * (ac >= 12).sum() / n, 2),
            "% 13+": round(100 * (ac >= 13).sum() / n, 2),
            "% 14+": round(100 * (ac >= 14).sum() / n, 2),
            "% 15":  round(100 * (ac == 15).sum() / n, 2),
        })
    return pd.DataFrame(linhas).sort_values(
        ["% 13+", "Média"], ascending=False
    ).reset_index(drop=True)

def resumir_carteiras(resultados):
    """Agrega por concurso ANTES de agregar por série: para cada concurso, pega o
    MELHOR jogo daquela carteira. É a métrica que decide quando se compra N
    bilhetes de uma vez — ninguém leva o prêmio da média, leva o do melhor
    bilhete. A média de acertos fica em 9,0 para qualquer estratégia e não
    distingue nada; o melhor-da-carteira distingue, porque depende de quanto os
    bilhetes se sobrepõem entre si (carteira concentrada acerta e erra junto)."""
    if not resultados:
        return pd.DataFrame()
    df = pd.DataFrame(resultados)
    por_conc = (df.groupby(["Estratégia", "Janela", "Concurso"])["Acertos"]
                  .agg(["max", "min", "size"]).reset_index())
    linhas = []
    for (est, jn), g in por_conc.groupby(["Estratégia", "Janela"], sort=False):
        linhas.append({
            "Estratégia": est,
            "Janela": jn,
            "Concursos": len(g),
            "Jogos/carteira": int(g["size"].median()),
            "Melhor médio": round(g["max"].mean(), 3),
            "Pior médio": round(g["min"].mean(), 3),
            "Carteiras com 13+": int((g["max"] >= 13).sum()),
            "Carteiras com 14+": int((g["max"] >= 14).sum()),
        })
    return pd.DataFrame(linhas).sort_values(
        "Melhor médio", ascending=False
    ).reset_index(drop=True)

# ── RENDER ─────────────────────────────────────────────────────────────────────
def render_volante(jogo):
    """Dezenas selecionadas pintadas com a cor oficial da bola (final do número)."""
    jogo_set = set(jogo)
    html = '<div class="volante">'
    for n in range(1, 26):
        if n in jogo_set:
            bg, fg = CORES_HEX[n % 10]
            html += (f'<div class="dezena" style="background-color:{bg};'
                     f'color:{fg};border:none;font-weight:bold;">{n:02d}</div>')
        else:
            html += f'<div class="dezena">{n:02d}</div>'
    html += '</div>'
    return html

def info_jogo(jogo):
    pares   = sum(1 for x in jogo if x % 2 == 0)
    impares = len(jogo) - pares
    soma    = sum(jogo)
    n_mold  = len(set(jogo) & MOLDURA)
    p = perfil_cores(jogo)
    zeradas  = sum(1 for f in FINAIS_ORDEM if p[f] == 0)
    duasmais = sum(1 for f in FINAIS_ORDEM if p[f] >= 2)
    # `validar_cores` foi calibrado sobre concursos de 15 dezenas. Num cartão de
    # 16 a distribuição por cor desloca e o selo reprovaria quase tudo sem que
    # isso signifique nada — melhor não exibir do que exibir errado.
    padrao_ok = ("✔" if validar_cores(jogo) else "✖") if len(jogo) == 15                 else "n/d (calibrado p/ 15)"
    n_carr = len(set(jogo) & GRUPO_LOTOFACIL_CARROSSEL)
    n_excl = len(set(jogo) & GRUPO_LOTOFACIL_EXCLUIDOS_369)
    prefixo = "" if len(jogo) == 15 else f"{len(jogo)} dezenas | "
    return (f"{prefixo}Soma: {soma} | Par/Ímpar: {pares}/{impares} | Moldura: {n_mold}/16 | "
            f"Cores 2+: {duasmais} · Zeradas: {zeradas} · Padrão {padrao_ok} | "
            f"Carrossel 142857: {n_carr}/{n_excl}")

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

# ── Sidebar 2: Base de Análise (recorte) ──────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("2. Base de Análise")

_OPCOES_JANELA = [30, 50, 100, 200, 500, 0]
janela_analise = st.sidebar.select_slider(
    "Recorte para estatística",
    options=_OPCOES_JANELA,
    value=0,
    format_func=lambda j: "Histórico completo" if j == 0 else f"Últimos {j} concursos",
    help="Define de onde saem frequência, atraso, assinaturas de cor, fixas e pool "
         "automáticos. O ineditismo continua checado contra o histórico inteiro.",
)

# Recorte é sufixo do histórico: análise usa a janela, ineditismo usa tudo.
historico_analise = (
    historico_sets[-janela_analise:] if (janela_analise and historico_sets) else historico_sets
)
if historico_sets:
    frequencia     = calcular_frequencia(historico_analise)
    quentes_global = top_quentes(frequencia, 10)
    st.sidebar.caption(
        f"Analisando **{len(historico_analise)}** de {len(historico_sets)} concursos."
    )
    if janela_analise and len(historico_analise) < janela_analise:
        st.sidebar.caption("⚠️ Histórico menor que a janela — usando tudo o que há.")

# ── Sidebar 3: Configurar Jogo ────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("3. Configurar Jogo")

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
    help=f"Em 'Jogo Múltiplo' este valor é por estratégia "
         f"(total = valor × {N_ESTRATEGIAS_MULTIPLO})."
)

tam_cartao = st.sidebar.radio(
    "Dezenas por cartão", TAMANHOS_CARTAO, horizontal=True,
    format_func=lambda t: f"{t} dezenas",
    help="A estratégia sempre gera o núcleo de 15 e passa pelos filtros "
         "calibrados. Em 16, uma dezena a mais é acrescentada depois pelo score "
         "do Modelo Ponderado (frequência + atraso + repetição).",
)
if tam_cartao > 15:
    _mult = custo_cartao(tam_cartao)
    st.sidebar.caption(
        f"Cada cartão de {tam_cartao} equivale a **{_mult} apostas simples** "
        f"({brl(_mult * PRECO_JOGO_SIMPLES)}). Com {qtd_jogos} cartão(ões): "
        f"**{brl(qtd_jogos * _mult * PRECO_JOGO_SIMPLES)}**."
    )
    st.sidebar.caption(
        "⚠️ A chance de 15 sobe exatamente o mesmo fator do custo — o retorno "
        "esperado por real é idêntico ao de apostas simples. O ganho é de "
        "concentração: acertar 15 num cartão de 16 arrasta quinze 14 junto."
    )

# ── Sidebar 4: Estratégia ─────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("4. Escolher Estratégia")

ROTULO_MULTIPLO = f"Jogo Múltiplo ({N_ESTRATEGIAS_MULTIPLO} Estratégias)"

estrategia = st.sidebar.selectbox("Estratégia", [
    "Anti-Popular (Recomendado)",
    "Melhor Jogo (IA)",
    ROTULO_MULTIPLO,
    ROTULO_SUPER,
    "Modelo Ponderado",
    "Inversão Suprema",
    "Cercamento 7/8",
    "Fixas de Ouro",
    "Equilíbrio IA 2026",
    "Ranking Frequência",
    "Fechamento de Dezenas",
    "Fechamento Garantido (Cobertura)",
    "Rastreio Ciclo 3",
    "Padrão de Cores",
    "Errar 10",
    "Espelho do Errar 10",
])

# Fechamento Garantido é um sistema de cobertura: os jogos saem do set cover sobre
# o pool, não de um núcleo que se possa estender. E a garantia verificada por
# `gerar_fechamento_garantido` é uma afirmação sobre jogos de 15 — estender cada
# um para 16 a invalidaria sem recalcular a cobertura.
ESTRATEGIAS_SEM_CARTAO_ESTENDIDO = {"Fechamento Garantido (Cobertura)"}
tam_cartao_ef = 15 if estrategia in ESTRATEGIAS_SEM_CARTAO_ESTENDIDO else tam_cartao
if tam_cartao > 15 and tam_cartao_ef == 15:
    st.sidebar.info(
        f"**{estrategia}** ignora o cartão de {tam_cartao} dezenas: a garantia de "
        "cobertura só vale para jogos de 15."
    )

# ── Minha Estratégia: acopla o cercamento rotativo à estratégia escolhida ─────
# Motivo da incompatibilidade, por estratégia — genérico confundiria: o Melhor
# Jogo e o Fechamento Garantido não têm jogo único para ancorar, enquanto Errar
# 10 e o Espelho têm, mas a rotação colapsa sobre eles.
MOTIVO_SEM_ROTATIVO = {
    ROTULO_SUPER:
        "já é uma estratégia de carteira: ela reveza os próprios mostradores entre "
        "os jogos. Sobrepor o cercamento rotativo brigaria com esse revezamento.",
    ROTULO_MULTIPLO:
        "já gera blocos de várias estratégias em paralelo; rotacionar entre elas "
        "misturaria as âncoras e nenhum jogo cercaria o anterior de verdade.",
    "Fechamento Garantido (Cobertura)":
        "devolve um conjunto fechado calculado por set cover — trocar qualquer jogo "
        "quebra a garantia de cobertura.",
    "Errar 10":
        "é determinística: para um recorte fixo devolve sempre o mesmo jogo, e a "
        "rotação colapsa no terceiro bilhete (ele reconstrói o primeiro). Use a "
        "carteira por recortes deslizantes, que varia o recorte em vez do jogo.",
    "Espelho do Errar 10":
        "é determinística: para um recorte fixo devolve sempre o mesmo jogo, e a "
        "rotação colapsa no terceiro bilhete (ele reconstrói o primeiro). Use a "
        "carteira por recortes deslizantes, que varia o recorte em vez do jogo.",
}
_pode_rotativo = (estrategia not in ESTRATEGIAS_SEM_ROTATIVO
                  and estrategia != ROTULO_MULTIPLO)

# `disabled=True` não zera o valor guardado do widget: sem este reset, marcar o
# toggle numa estratégia compatível e depois trocar para uma incompatível deixa
# o checkbox MARCADO e cinza — o usuário lê "ligado" numa estratégia que ignora
# a rotação, e ao voltar para uma compatível ela reativa sozinha. Forçar False
# antes de instanciar o widget faz o toggle aparecer desmarcado e exige um
# clique novo e deliberado para religar.
_KEY_ROT = "usar_rotativo"
st.session_state.setdefault(_KEY_ROT, False)
_desligado_a_forca = False
if not _pode_rotativo and st.session_state.get(_KEY_ROT):
    st.session_state[_KEY_ROT] = False
    _desligado_a_forca = True

usar_rotativo = st.sidebar.checkbox(
    "🔄 Usar Minha Estratégia (cercamento rotativo)",
    key=_KEY_ROT,
    disabled=not _pode_rotativo,
    help="Jogo 1 sai da estratégia escolhida. Cada jogo seguinte FIXA as dezenas "
         "que o anterior deixou de fora e deixa a estratégia escolher o restante "
         "dentro do jogo anterior. Não altera a chance de prêmio grande: reduz a "
         "variância da carteira, eliminando o cenário em que todos os bilhetes "
         "vão mal no mesmo sorteio.",
)

if not _pode_rotativo:
    _motivo = MOTIVO_SEM_ROTATIVO.get(estrategia, "não tem um jogo único para "
                                                  "ancorar a rotação.")
    if _desligado_a_forca:
        st.sidebar.warning(
            f"Minha Estratégia foi **desligada**: **{estrategia}** {_motivo}"
        )
    else:
        st.sidebar.caption(f"Minha Estratégia não se aplica: **{estrategia}** {_motivo}")
elif usar_rotativo:
    _livres_rot = tam_cartao_ef - (25 - tam_cartao_ef)
    st.sidebar.caption(
        f"Cada jogo fixa **{25 - tam_cartao_ef}** dezenas do complemento do anterior; "
        f"**{estrategia}** escolhe as outras **{_livres_rot}**. Sobreposição entre "
        f"consecutivos: {_livres_rot}. Nenhum par de jogos passa de "
        f"{MAX_IGUAIS_LOTE} dezenas em comum."
    )
    _pool_rot = len(pool_disponivel) if pool_disponivel is not None else 25
    _min_rot, _conf_rot = pool_minimo_rotativo(tam_cartao_ef)
    _ov_forcada = 2 * tam_cartao_ef - _pool_rot
    if _pool_rot < _min_rot:
        st.sidebar.error(
            f"**Rotação impossível com {_pool_rot} dezenas no pool.** Ela força "
            f"{_ov_forcada} dezenas em comum entre jogos consecutivos, acima do "
            f"limite de {MAX_IGUAIS_LOTE}. Excluir dezenas ESTREITA a rotação: cada "
            f"jogo tem de conter as {_pool_rot - tam_cartao_ef} que o anterior "
            f"deixou de fora, e quanto menos sobram, mais os jogos se parecem. "
            f"Use no mínimo **{_min_rot}** dezenas para cartão de {tam_cartao_ef} "
            f"(o confortável é {_conf_rot})."
        )
    elif _pool_rot < _conf_rot:
        st.sidebar.warning(
            f"**Pool de {_pool_rot} dezenas aperta a rotação** ({_ov_forcada} em "
            f"comum entre consecutivos, limite {MAX_IGUAIS_LOTE}). Medido com 20 "
            f"jogos pedidos: pool 22 entrega 20 com cartão de 15, mas 21 entrega 16 "
            f"e 20 entrega 6; com cartão de 16 só o pool cheio entrega 20, e 24 já "
            f"cai para 12. Espere menos jogos do que pediu — reduza as exclusões "
            f"para ter **{_conf_rot}** dezenas ou mais."
        )
    if qtd_jogos < 2:
        st.sidebar.warning("A rotação precisa de 2 jogos ou mais — com 1 jogo o "
                           "resultado é o da estratégia pura.")
    elif qtd_jogos > 10:
        st.sidebar.caption(
            f"⚠️ Medido: o ganho no melhor bilhete cai de +0,146 acerto com 3 jogos "
            f"para +0,006 com 20 (cartão de 15). Com {qtd_jogos} jogos o efeito da "
            "rotação é pequeno — a carteira já cobre o espaço por tamanho. Em cartão "
            "de 16 a rotação também reancora muito nesse volume (11 de 20 jogos "
            "medidos), porque o limite de dezenas em comum fecha o espaço."
        )

# Pesos do Modelo Ponderado (usados também no Múltiplo, Melhor Jogo e Painel)
with st.sidebar.expander("⚖️ Pesos do Modelo Ponderado", expanded=(estrategia == "Modelo Ponderado")):
    st.caption(
        "Cada sinal é normalizado em 0–1 antes de ser pesado. "
        "Frequência e atraso são opostos por construção: pesar os dois é escolher "
        "onde ficar entre dezenas quentes e dezenas frias."
    )
    w_freq   = st.slider("Frequência no recorte", 0.0, 3.0, 1.0, 0.1)
    w_atraso = st.slider("Atraso atual",          0.0, 3.0, 1.0, 0.1)
    w_rep    = st.slider("Repetiu no último",     0.0, 3.0, 1.0, 0.1)
pesos_modelo = {"freq": w_freq, "atraso": w_atraso, "rep": w_rep}

# Carteira por recortes deslizantes (só para as estratégias determinísticas)
if estrategia in ESTRATEGIAS_DETERMINISTICAS:
    with st.sidebar.expander("🎯 Carteira por recortes deslizantes", expanded=True):
        st.caption(
            "Esta estratégia devolve um único jogo por recorte. Para pedir vários "
            "bilhetes, cada um sai de uma janela diferente do histórico, recuando."
        )
        carteira_tam = st.slider("Concursos por janela", 20, 200, JANELA_CARTEIRA_TAM, 5)
        carteira_passo = st.slider(
            "Passo entre janelas", 1, 200, carteira_tam, 1,
            help="Igual ao tamanho da janela = janelas disjuntas (recomendado). "
                 "Menor que o tamanho faz as janelas se sobreporem, os jogos saírem "
                 "quase iguais e o melhor bilhete da carteira piorar — medido em "
                 "400 concursos: passo 5 numa janela de 30 custa 0,22 acerto no "
                 "melhor bilhete (t = -4,55) contra jogos aleatórios.",
        )
        _max_j = len(janelas_deslizantes(len(historico_sets), 999,
                                         carteira_tam, carteira_passo)) if historico_sets else 0
        st.caption(f"Histórico atual comporta **{_max_j}** janelas nessa configuração.")
else:
    carteira_tam, carteira_passo = JANELA_CARTEIRA_TAM, JANELA_CARTEIRA_TAM

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

# ── Sidebar 5: Painel Completo ────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("5. Painel Completo")
st.sidebar.caption("1 jogo por estratégia. Fixas e pool escolhidos automaticamente pelo recorte.")
btn_painel = st.sidebar.button("Gerar Painel Completo (Auto)")

# ── Sidebar 6: Simulação ──────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("6. Simulação de Eficiência")

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

_opcoes_sim = ["Aleatório Ponderado (Rápido)"] + ESTRATEGIAS_MULTIPLO
estrategia_sim_sel = st.sidebar.selectbox(
    "Estratégia da simulação:", _opcoes_sim,
    help="'Aleatório Ponderado' é mais rápido. As demais usam a lógica completa da estratégia."
)
st.sidebar.caption(
    "Sempre com jogos de 15 dezenas: o número de tentativas até acertar mede a "
    "estratégia, e cartões de tamanhos diferentes não são comparáveis nessa métrica."
)
btn_simular = st.sidebar.button("🔬 Iniciar Simulação")

# ── Sidebar 7: Backtest Walk-Forward ──────────────────────────────────────────
st.sidebar.divider()
st.sidebar.header("7. Backtest Walk-Forward")
st.sidebar.caption(
    "Mede acertos reais: para cada concurso passado, gera jogos usando só o que "
    "existia antes dele e confere contra o resultado que saiu."
)

bt_estrategias = st.sidebar.multiselect(
    "Estratégias a testar",
    options=[BASELINE_ALEATORIO] + ESTRATEGIAS_BACKTEST,
    default=[BASELINE_ALEATORIO, "Modelo Ponderado", "Padrão de Cores",
             "Errar 10", "Espelho do Errar 10"],
    help="Errar 10 aposta nas 15 dezenas com maior chance estimada de ficarem "
         "ausentes; o Espelho é o complemento das 10 primeiras. Rode os dois "
         "junto com o baseline — a diferença entre eles é a medida do sinal.",
)
bt_janelas_sel = st.sidebar.multiselect(
    "Recortes a comparar",
    options=_OPCOES_JANELA,
    default=[30, 50, 0],
    format_func=lambda j: "Histórico completo" if j == 0 else f"Últimos {j}",
    help="Só afeta Ranking Frequência, Padrão de Cores, Modelo Ponderado, "
         "Errar 10 e Espelho do Errar 10 — as demais não leem o recorte.",
)
bt_n_concursos = st.sidebar.number_input(
    "Concursos avaliados", min_value=5, max_value=300, value=30, step=5,
    help="Os N concursos mais recentes do arquivo."
)
bt_jogos = st.sidebar.number_input(
    "Jogos por concurso", min_value=1, max_value=20, value=3, step=1
)
st.sidebar.caption(
    "Sempre com jogos de 15 dezenas. Comparar um cartão de 16 com o baseline "
    "aleatório de 15 é inválido — um cartão maior acerta mais por construção, e "
    "não por estratégia. A comparação teria de ser por real apostado."
)
btn_backtest = st.sidebar.button("📊 Rodar Backtest")

# ── MAIN: Gerar Jogos ─────────────────────────────────────────────────────────
if btn_gerar:
    for _k in ["_sim_media_val", "_sim_estrategia", "_sim_min_acertos", "_jogo_media",
               "_conf_alvo_ok"]:
        st.session_state.pop(_k, None)

    estrategia_exec = "Anti-Popular" if estrategia.startswith("Anti-Popular") else estrategia

    if estrategia == ROTULO_MULTIPLO:
        _total_multiplo = qtd_jogos * N_ESTRATEGIAS_MULTIPLO
        st.header(f"Resultados: {estrategia} — {qtd_jogos} por estratégia ({_total_multiplo} no total)")
    elif estrategia in ESTRATEGIAS_DETERMINISTICAS:
        st.header(f"Resultados: {estrategia} — 1 jogo (estratégia determinística)")
    else:
        st.header(f"Resultados: {estrategia} — {qtd_jogos} jogo(s)")

    if historico_sets:
        st.caption(
            f"Base de análise: **{_rotulo_janela(janela_analise)}** "
            f"({len(historico_analise)} concursos) · ineditismo checado contra os "
            f"{len(historico_sets)} do arquivo."
        )

    if tam_cartao_ef > 15:
        _mult = custo_cartao(tam_cartao_ef)
        st.info(
            f"**Cartões de {tam_cartao_ef} dezenas.** Núcleo de 15 gerado e filtrado "
            f"pela estratégia; a {tam_cartao_ef}ª dezena vem do score do Modelo "
            f"Ponderado. Cada cartão = {_mult} apostas simples "
            f"({brl(_mult * PRECO_JOGO_SIMPLES)}) e vale {_mult}× a chance de 15 — "
            "retorno esperado por real inalterado, ganho apenas de concentração. "
            "O índice de popularidade usa limiares calibrados para 15 dezenas."
        )

    if acumulada_info > 0:
        st.warning(f"🔥 Lotofácil ACUMULADA há {acumulada_info} concurso(s)!")

    jogos_gerados = []

    _rotativo_ativo = usar_rotativo and _pode_rotativo and qtd_jogos > 1
    _super_ativa    = (estrategia == ROTULO_SUPER)

    if estrategia == "Melhor Jogo (IA)" and not _rotativo_ativo:
        with st.spinner("Analisando todas as estratégias..."):
            jogo_best, nome_best, score_best, ranking = gerar_melhor_jogo_loto(
                frequencia, historico_sets, ultimo_resultado, pool=pool_disponivel,
                historico_analise=historico_analise, pesos_modelo=pesos_modelo,
            )
        # O ranking por popularidade compara os núcleos de 15 — é ele que escolhe
        # a estratégia. A extensão para 16 vem depois, sobre o vencedor.
        jogo_best = montar_cartao(
            jogo_best, tam_cartao_ef, historico_analise, ultimo_resultado,
            pool=pool_disponivel, pesos_modelo=pesos_modelo,
            historico_sets=historico_sets,
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

    elif estrategia == ROTULO_MULTIPLO:
        _total_multiplo = qtd_jogos * N_ESTRATEGIAS_MULTIPLO
        if _total_multiplo > 90:
            st.warning(f"{_total_multiplo} jogos no total — geração/renderização pode demorar.")
        with st.spinner(f"Gerando {qtd_jogos} jogo(s) de cada uma das {N_ESTRATEGIAS_MULTIPLO} estratégias ({_total_multiplo} no total)..."):
            resultado_multiplo = gerar_jogo_multiplo(
                qtd_jogos, frequencia, historico_sets, ultimo_resultado, pool=pool_disponivel,
                historico_analise=historico_analise, pesos_modelo=pesos_modelo,
            )
        # (cartão, núcleo, estratégia): o ineditismo dentro do lote já foi checado
        # sobre os núcleos em `gerar_jogo_multiplo`; a extensão é aplicada depois.
        _lote = [
            (montar_cartao(_n, tam_cartao_ef, historico_analise, ultimo_resultado,
                           pool=pool_disponivel, pesos_modelo=pesos_modelo,
                           historico_sets=historico_sets), _n, _t)
            for _n, _t in resultado_multiplo
        ]
        st.caption(
            f"Blocos agrupados (sem intercalar), {qtd_jogos} por estratégia: "
            + " → ".join(ESTRATEGIAS_MULTIPLO)
        )
        _tipo_atual = None
        cols = st.columns(3)
        for i, (jogo, _nucleo, tipo) in enumerate(_lote):
            if tipo != _tipo_atual:
                st.subheader(tipo)
                cols = st.columns(3)
                _tipo_atual = tipo
                _idx_bloco = 0
            pop, motivos = indice_popularidade(jogo, historico_sets)
            # Curva medida sobre o núcleo de 15: a média esperada de ~9 acertos
            # contra o histórico é um número de jogo de 15, não de cartão de 16.
            curva_segura = validar_curva_acertos(_nucleo, historico_sets)
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

        xlsx_bytes = exportar_multiplo_xlsx([(j, t) for j, _n, t in _lote])
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

    elif _super_ativa:
        with st.spinner(f"Gerando {qtd_jogos} jogo(s) que passem em todas as regras..."):
            _sup, _sdiag = gerar_super_estrategia(
                qtd_jogos, frequencia, historico_sets, ultimo_resultado,
                tam=tam_cartao_ef, pool=pool_disponivel,
                historico_analise=historico_analise, pesos_modelo=pesos_modelo,
            )
        st.info(
            "**Seis porteiros ao mesmo tempo.** Cada jogo é sorteado e só passa se "
            "satisfizer todas as regras: o cerco (6 ou 7 dezenas fora do último "
            "concurso), as frias dos últimos 3, a contagem de ímpares (7 ou 8), uma "
            "assinatura de cores já vista, os filtros base e popularidade zero. Os "
            "dois mostradores revezam entre os jogos, cobrindo as quatro "
            "combinações antes de repetir."
        )
        if _sdiag["frias"]:
            st.caption(
                f"Frias dos últimos 3 concursos: "
                + " · ".join(f"{n:02d}" for n in _sdiag["frias"])
                + f" — o porteiro exige {min(3, len(_sdiag['frias']))} delas."
            )
        else:
            st.caption("Nenhuma dezena ficou fora dos últimos 3 concursos: o porteiro "
                       "das frias não exige nada neste momento.")
        if _sdiag["assinaturas"] < 60:
            st.warning(
                f"**Recorte estreito.** O porteiro das cores só aceita assinaturas já "
                f"vistas, e o recorte atual oferece apenas **{_sdiag['assinaturas']}** "
                "assinaturas distintas. Medido: com o histórico completo (1.889 "
                "assinaturas) um jogo sai em ~245 sorteios; com os últimos 30 "
                "concursos (20 assinaturas), em ~16.400. Aumente o recorte em "
                "**2. Base de Análise** se a geração demorar."
            )
        if len(_sup) < qtd_jogos:
            st.warning(
                f"Gerados **{len(_sup)}** de {qtd_jogos}: as regras não deixaram "
                "candidato sobrar. Reduza a quantidade ou as dezenas excluídas."
            )
        if _sdiag["relaxados"]:
            st.warning(
                f"{_sdiag['relaxados']} jogo(s) aceito(s) com popularidade acima de "
                "zero: nenhum candidato estrito apareceu. O anti-popular é o único "
                "porteiro que se relaxa — ele não muda a chance de acertar, só a "
                "divisão do prêmio."
            )

        cols = st.columns(3)
        for i, jogo in enumerate(_sup):
            _aus, _imp = _sdiag["mostradores"][i]
            pop, motivos = indice_popularidade(jogo, historico_sets)
            jogos_gerados.append(jogo)
            with cols[i % 3]:
                st.markdown(f"**Jogo {i + 1}**")
                st.caption(f"Mostradores: **{_aus}** ausentes · **{_imp}** ímpares")
                st.markdown(render_volante(jogo), unsafe_allow_html=True)
                st.caption(info_jogo(jogo))
                st.write(f"Popularidade: {pop:.0f} (menor = melhor)")
                if motivos:
                    st.caption("⚠️ " + "; ".join(motivos))
                st.divider()

        if _sdiag["funil"]:
            _tot_rej = sum(_sdiag["funil"].values())
            _linhas_funil = [
                {"Porteiro": k, "Jogos barrados": v,
                 "% das reprovações": f"{100 * v / _tot_rej:.1f}%"}
                for k, v in _sdiag["funil"].most_common()
            ]
            with st.expander(f"Ver o funil — {_tot_rej:,} jogos sorteados e descartados"):
                st.dataframe(pd.DataFrame(_linhas_funil), use_container_width=True,
                             hide_index=True)
                if _sdiag["tentativas"]:
                    _md = sum(_sdiag["tentativas"]) / len(_sdiag["tentativas"])
                    st.caption(
                        f"Média de **{_md:,.0f}** sorteios até um jogo passar em tudo "
                        f"(pior: {max(_sdiag['tentativas']):,}). Medido no histórico "
                        "completo, as quatro combinações de mostradores aprovam entre "
                        "0,47% e 0,63% dos jogos — cerca de 1 em 160 a 1 em 215."
                    )
        st.caption(
            "Empilhar as seis regras **não aumenta a chance de acertar**: escolher "
            "uniformemente dentro de um subconjunto A mantém a probabilidade em "
            "1/C(25,15), porque |A| se cancela. Medido em 150 concursos reais, "
            "walk-forward: 8,9956 acertos contra 9,0533 do palpite aleatório "
            "(diferença −0,0578, t = −0,67). O ganho real é outro — este é o jogo "
            "menos popular que o app sabe montar, o que reduz a divisão do prêmio."
        )

    elif _rotativo_ativo:
        with st.spinner(f"Gerando carteira rotativa de {qtd_jogos} jogos com "
                        f"{estrategia_exec}..."):
            _rot, _diag = gerar_carteira_rotativa(
                estrategia_exec, qtd_jogos, frequencia, historico_sets,
                ultimo_resultado, tam=tam_cartao_ef, fixas=fixas,
                pool=pool_disponivel, historico_analise=historico_analise,
                pesos_modelo=pesos_modelo,
            )
        _liv = _diag["livres"] if _diag["livres"] is not None else tam_cartao_ef
        if estrategia_exec == ROTULO_MELHOR:
            st.caption(
                "Com **Melhor Jogo (IA)** a cada passo as 8 estratégias são geradas "
                "de novo e vence a de menor popularidade. Medido em 30 chamadas: 30 "
                "jogos distintos, e **Anti-Popular venceu as 30** — a pontuação do "
                "Melhor Jogo é o próprio índice de popularidade, que é o que a "
                "Anti-Popular minimiza por construção. Na prática a carteira sai "
                "muito parecida com escolher Anti-Popular direto."
            )
        st.info(
            f"**Minha Estratégia sobre {estrategia_exec}.** Jogo 1 é a estratégia "
            f"pura. Cada jogo seguinte fixa as **{_diag['fixas']}** dezenas que o "
            f"anterior deixou de fora e {estrategia_exec} escolhe as outras "
            f"**{_liv}** dentro dele. Nenhum par de jogos tem mais de "
            f"{MAX_IGUAIS_LOTE} dezenas em comum."
        )
        if len(_rot) < qtd_jogos:
            st.warning(
                f"Gerados **{len(_rot)}** de {qtd_jogos} jogos: a rotação esgotou as "
                f"combinações que respeitam o limite de {MAX_IGUAIS_LOTE} dezenas em "
                "comum. Reduza a quantidade de jogos."
            )
        if _diag["reancoras"]:
            st.warning(
                f"A rotação reiniciou **{_diag['reancoras']}** vez(es): não havia "
                f"escolha das {_liv} livres que respeitasse ao mesmo tempo o "
                "ineditismo contra o histórico e o limite de dezenas em comum. "
                "Nesses pontos o jogo veio da estratégia pura, e a rotação "
                "recomeçou dali."
            )
        if _diag["relaxados"]:
            st.caption(
                f"{_diag['relaxados']} jogo(s) aceito(s) fora da faixa de soma ou do "
                "limite de consecutivas: as dezenas fixas da rotação são forçadas e "
                "nem sempre existe escolha das livres que caiba nos dois filtros. "
                "Ineditismo e limite de dezenas em comum foram respeitados sempre."
            )
        if tam_cartao_ef > 15:
            st.caption(
                "Cartão de 16: soma e sequência não são checados nos jogos 2+ — os "
                "limiares são calibrados sobre concursos de 15 dezenas e a rotação "
                "monta o cartão direto no tamanho final, sem núcleo de 15."
            )

        cols = st.columns(3)
        for i, jogo in enumerate(_rot):
            pop, motivos = indice_popularidade(jogo, historico_sets)
            jogos_gerados.append(jogo)
            with cols[i % 3]:
                st.markdown(f"**Jogo {i + 1}**")
                if i:
                    _ov_ant = len(set(jogo) & set(_rot[i - 1]))
                    st.caption(f"Cerca o jogo {i} · {_ov_ant} dezenas em comum com ele")
                else:
                    st.caption(f"Âncora — {estrategia_exec} pura")
                st.markdown(render_volante(jogo), unsafe_allow_html=True)
                st.caption(info_jogo(jogo))
                st.write(f"Popularidade: {pop:.0f} (menor = melhor)")
                if motivos:
                    st.caption("⚠️ " + "; ".join(motivos))
                st.divider()

        if len(_rot) > 1:
            _pares = [len(set(a) & set(b)) for a, b in combinations(_rot, 2)]
            _cob = len(set().union(*[set(j) for j in _rot]))
            _dupla = len(set(_rot[0]) | set(_rot[1]))
            st.caption(
                f"Sobreposição entre pares: média **{sum(_pares) / len(_pares):.2f}**, "
                f"máxima **{max(_pares)}** (limite {MAX_IGUAIS_LOTE}) — referência de "
                f"{len(_rot)} cartões independentes de {tam_cartao_ef} dezenas: "
                f"{tam_cartao_ef ** 2 / 25:.2f}. Os dois primeiros jogos cobrem "
                f"**{_dupla}/25** dezenas; a carteira inteira cobre **{_cob}/25**."
            )
            st.caption(
                "O ganho desta estratégia está em cortar o pior caso, não em subir o "
                "teto: medido em 90.000 sorteios (cartão 15, 5 jogos), a carteira "
                "rotativa nunca faz 8 ou menos no melhor bilhete (0,0000% contra "
                "0,4611% de uma carteira independente) e derruba o 'melhor = 9' de "
                "12,31% para 5,73%. Já P(melhor ≥ 14) fica em +0,003 pp (z = +0,52), "
                "ou seja, a chance de prêmio grande não muda."
            )

    elif estrategia_exec in ESTRATEGIAS_DETERMINISTICAS and qtd_jogos > 1:
        # Determinística: repetir a chamada devolveria N cópias do mesmo bilhete.
        # Cada jogo sai de um recorte deslizante diferente — janelas DISJUNTAS,
        # ver `carteira_deslizante` para a medição que fixa esse passo.
        with st.spinner(f"Gerando carteira de {qtd_jogos} jogos por recortes deslizantes..."):
            _carteira = carteira_deslizante(
                historico_sets, ultimo_resultado, qtd_jogos,
                pool=pool_disponivel, tamanho=carteira_tam, passo=carteira_passo,
                inverter=(estrategia_exec == "Espelho do Errar 10"),
            )
        # `deterministico=True`: para um recorte fixo o bilhete tem de ser único,
        # senão dois cliques com a mesma configuração devolvem cartões diferentes
        # e a estratégia deixa de ser determinística.
        _carteira = [
            (montar_cartao(_j, tam_cartao_ef, historico_analise, ultimo_resultado,
                           pool=pool_disponivel, pesos_modelo=pesos_modelo,
                           deterministico=True, historico_sets=historico_sets), _jan)
            for _j, _jan in _carteira
        ]
        _n_uteis = len(_carteira)
        _distintos = len({tuple(j) for j, _ in _carteira})
        st.info(
            f"**{estrategia_exec} é determinística** — para um recorte fixo existe um "
            f"único ranking de ausência, logo um único jogo. Cada bilhete abaixo usa um "
            f"recorte diferente: **{carteira_tam} concursos, passo {carteira_passo}**, "
            f"recuando no histórico. {_distintos} jogos distintos em {_n_uteis}."
        )
        if _n_uteis < qtd_jogos:
            st.warning(
                f"Histórico de {len(historico_sets)} concursos só comporta **{_n_uteis}** "
                f"janelas de {carteira_tam} com passo {carteira_passo} (pedidos: {qtd_jogos}). "
                "Reduza o passo ou o tamanho da janela para obter mais jogos — mas leia o "
                "aviso sobre passo curto abaixo."
            )
        if carteira_passo < carteira_tam:
            st.warning(
                f"**Passo {carteira_passo} menor que a janela {carteira_tam}**: janelas "
                f"consecutivas compartilham {100 * (carteira_tam - carteira_passo) / carteira_tam:.0f}% "
                "dos concursos, os jogos saem quase iguais e a carteira concentra. "
                "Medido em 400 concursos: com passo 5 numa janela de 30, o **melhor** "
                "bilhete da carteira cai de 11,665 para 11,447 acertos contra 50 jogos "
                "aleatórios (t = −4,55). Os bilhetes acertam e erram juntos. "
                "Com passo ≥ 30 o efeito some."
            )
        cols = st.columns(3)
        for i, (jogo, (_ini, _fim)) in enumerate(_carteira):
            pop, motivos = indice_popularidade(jogo, historico_sets)
            jogos_gerados.append(jogo)
            with cols[i % 3]:
                st.markdown(f"**Jogo {i + 1}**")
                st.caption(f"Recorte: concursos {_ini + 1}–{_fim} do arquivo")
                st.markdown(render_volante(jogo), unsafe_allow_html=True)
                st.caption(info_jogo(jogo))
                st.write(f"Popularidade: {pop:.0f} (menor = melhor)")
                if motivos:
                    st.caption("⚠️ " + "; ".join(motivos))
                st.divider()
        if _carteira:
            _js = [j for j, _ in _carteira]
            _ov = [len(set(a) & set(b)) for x, a in enumerate(_js) for b in _js[x + 1:]]
            if _ov:
                _ref_ov = 9.00 * tam_cartao_ef / 15
                st.caption(
                    f"Sobreposição média entre os bilhetes: "
                    f"**{sum(_ov) / len(_ov):.2f}/{tam_cartao_ef}** — referência de "
                    f"50 cartões aleatórios do mesmo tamanho: {_ref_ov:.2f}. Acima "
                    "disso a carteira está concentrada e o melhor bilhete piora."
                )

    else:
        _det = estrategia_exec in ESTRATEGIAS_DETERMINISTICAS
        cols = st.columns(3)
        for i in range(qtd_jogos):
            with st.spinner(f"Gerando jogo {i + 1}..."):
                nucleo = gerar_estrategia_loto(
                    estrategia_exec, frequencia, historico_sets,
                    ultimo_resultado, fixas=fixas, pool=pool_disponivel,
                    historico_analise=historico_analise, pesos_modelo=pesos_modelo,
                )
            jogo = montar_cartao(
                nucleo, tam_cartao_ef, historico_analise, ultimo_resultado,
                pool=pool_disponivel, pesos_modelo=pesos_modelo, deterministico=_det,
                historico_sets=historico_sets,
            )
            pop, motivos = indice_popularidade(jogo, historico_sets)
            curva_segura = validar_curva_acertos(nucleo, historico_sets)
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
        # Persistido para a seção de conferência, que também hospeda o download:
        # dentro deste ramo o botão morreria no primeiro rerun.
        st.session_state["_conf_jogos"] = [list(j) for j in jogos_gerados]
        st.session_state["_conf_origem"] = (
            f"{len(jogos_gerados)} jogo(s) de **{estrategia}**"
            + (" com cercamento rotativo" if _rotativo_ativo else "")
            + f" · cartão de {tam_cartao_ef} dezenas"
        )
        st.session_state["_conf_arquivo"] = "jogos_lotofacil.csv"

# ── MAIN: Painel Completo ─────────────────────────────────────────────────────
elif btn_painel:
    for _k in ["_sim_media_val", "_sim_estrategia", "_sim_min_acertos", "_jogo_media",
               "_conf_alvo_ok"]:
        st.session_state.pop(_k, None)

    st.header(f"Painel Completo — 1 cartão de {tam_cartao} dezenas por estratégia")

    if acumulada_info > 0:
        st.warning(f"🔥 Lotofácil ACUMULADA há {acumulada_info} concurso(s)!")

    if historico_sets:
        st.caption(
            f"Base de análise: **{_rotulo_janela(janela_analise)}** "
            f"({len(historico_analise)} concursos)."
        )

    fixas_auto = auto_fixas_loto(historico_analise) if historico_analise else []
    pool_auto  = auto_pool_loto(historico_analise)  if historico_analise else list(range(1, 21))

    estrategias_painel = [
        ("Anti-Popular",          [],         "Minimiza divisão do prêmio"),
        ("Inversão Suprema",      [],         ""),
        ("Cercamento 7/8",        [],         ""),
        ("Fixas de Ouro",         fixas_auto, f"Fixas auto: {[f'{n:02d}' for n in fixas_auto]}" if fixas_auto else ""),
        ("Equilíbrio IA 2026",    [],         ""),
        ("Ranking Frequência",    [],         ""),
        ("Fechamento de Dezenas", pool_auto,  f"Pool auto: {len(pool_auto)} dezenas"),
        ("Rastreio Ciclo 3",      [],         ""),
        ("Padrão de Cores",       [],         "Assinatura de cores do recorte"),
        ("Modelo Ponderado",      [],         f"Pesos f/a/r: {w_freq:g} / {w_atraso:g} / {w_rep:g}"),
        ("Errar 10",              [],         "As 15 com maior chance estimada de NÃO sair"),
        ("Espelho do Errar 10",   [],         "Complemento das 10 previstas ausentes"),
    ]

    painel_jogos = []
    cols = st.columns(3)
    for idx, (nome, params, info_str) in enumerate(estrategias_painel):
        with st.spinner(f"Gerando: {nome}..."):
            nucleo = gerar_estrategia_loto(
                nome, frequencia, historico_sets,
                ultimo_resultado, fixas=params, pool=pool_disponivel,
                historico_analise=historico_analise, pesos_modelo=pesos_modelo,
            )
        jogo = montar_cartao(
            nucleo, tam_cartao, historico_analise, ultimo_resultado,
            pool=pool_disponivel, pesos_modelo=pesos_modelo,
            deterministico=(nome in ESTRATEGIAS_DETERMINISTICAS),
            historico_sets=historico_sets,
        )
        pop, motivos = indice_popularidade(jogo, historico_sets)
        curva_segura = validar_curva_acertos(nucleo, historico_sets)
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
            if nome in ("Errar 10", "Espelho do Errar 10"):
                # Sobre o núcleo: "errar 10" é uma afirmação sobre um jogo de 15
                # dezenas — num cartão de 16 a cobertura sobe por construção.
                _cob, _esp = diagnostico_errar_dez(
                    nucleo, historico_analise, ultimo_resultado, pool=pool_disponivel)
                st.caption(
                    f"Cobre {_cob}/10 das dezenas de maior escore de ausência · "
                    f"espalhamento do escore: {_esp:.3f} "
                    "*(0,000 = modelo sem nada a dizer; o ranking vira desempate por número)*"
                )
            st.caption(
                f"Distopia de Acertos: {'Foge dos 79% (Seguro)' if curva_segura else 'Risco de 8-10 pontos'} "
                "*(indicador estatístico, não altera a chance real — sorteios são independentes)*"
            )
            st.divider()

    st.session_state["_conf_jogos"] = [list(j) for j in painel_jogos]
    st.session_state["_conf_origem"] = (
        f"Painel Completo — {len(painel_jogos)} jogos, 1 por estratégia "
        f"· cartão de {tam_cartao} dezenas"
    )
    st.session_state["_conf_arquivo"] = "painel_lotofacil.csv"

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

        # ── O alvo é alcançável? ─────────────────────────────────────────────
        # Um jogo que acerta N dezenas do alvo herda a estrutura dele (soma e
        # sequências ficam próximas). Logo, um alvo reprovado nos filtros
        # costuma arrastar junto os jogos que o acertariam — e o ciclo zera sem
        # que nada esteja errado com a estratégia. Estimado por amostragem dos
        # jogos vencedores, ponderada pela distribuição hipergeométrica.
        _fora_alvo = sorted(set(range(1, 26)) - set(alvo_sim))
        _ks        = list(range(min_acertos_sim, 16))
        _pesos_k   = [comb(15, k) * comb(10, 15 - k) for k in _ks]
        _n_amostra = 3000
        _ok_amostra = 0
        for _ in range(_n_amostra):
            _k = random.choices(_ks, weights=_pesos_k, k=1)[0]
            _j = sorted(random.sample(alvo_sim, _k) + random.sample(_fora_alvo, 15 - _k))
            if (validar_soma(_j) and validar_sequencia(_j)
                    and validar_proporcao_142857(_j)):
                _ok_amostra += 1
        _viab = _ok_amostra / _n_amostra
        _alvo_passa = (validar_soma(alvo_sim) and validar_sequencia(alvo_sim)
                       and validar_proporcao_142857(alvo_sim))

        if _viab == 0:
            st.error(
                f"**Alvo inalcançável.** Nenhum jogo com {min_acertos_sim}+ acertos "
                f"contra este alvo passa nos filtros (soma {SOMA_MIN}–{SOMA_MAX}, "
                f"máx. {MAX_CONSECUTIVAS} consecutivas, carrossel 142857 entre "
                f"{CARROSSEL_LOTO_FAIXA_15[0]} e {CARROSSEL_LOTO_FAIXA_15[1]}). "
                f"A simulação vai zerar por construção, não por falha da estratégia."
            )
        elif _viab < 0.30:
            st.warning(
                f"**Alvo difícil.** Só ~{_viab * 100:.0f}% dos jogos vencedores passam "
                f"nos filtros (soma={sum(alvo_sim)}, "
                f"alvo {'aprovado' if _alvo_passa else 'REPROVADO'} nos próprios filtros). "
                f"A chance efetiva por jogo cai para ~1 em "
                f"{round(1 / (prob * _viab)):,} se prob > 0."
                if prob else "Alvo difícil."
            )
        else:
            st.caption(
                f"Viabilidade do alvo: **{_viab * 100:.0f}%** dos jogos vencedores "
                f"passam nos filtros (soma={sum(alvo_sim)})."
            )

        st.divider()
        progress_bar      = st.progress(0, text="Iniciando...")
        placeholder_tabela = st.empty()

        resultados_sim = []
        diags_sim      = []
        for ciclo in range(1, int(n_ciclos_sim) + 1):
            progress_bar.progress(
                (ciclo - 1) / int(n_ciclos_sim),
                text=f"Ciclo {ciclo}/{int(n_ciclos_sim)}..."
            )
            t0 = time.time()
            tentativas, jogo_venc, diag = simular_ate_acertar(
                alvo_sim, min_acertos_sim, frequencia,
                pool_disponivel, int(max_tent_sim),
                historico_sets, ultimo_resultado, estrategia_sim_sel,
                historico_analise=historico_analise, pesos_modelo=pesos_modelo,
            )
            elapsed_ms = round((time.time() - t0) * 1000)
            diags_sim.append(diag)

            if jogo_venc:
                acertos  = len(set(jogo_venc) & set(alvo_sim))
                jogo_str = "  ".join(f"{n:02d}" for n in jogo_venc)
                encontrou = "✅"
            else:
                acertos  = 0
                jogo_str = "—"
                encontrou = "❌ limite"

            _ger = diag["gerados"] or 1
            resultados_sim.append({
                "Ciclo":            ciclo,
                "Tentativas":       tentativas,
                "Resultado":        encontrou,
                "Acertos":          acertos,
                "Jogos gerados":    diag["gerados"],
                "Jogos distintos":  diag["distintos"],
                "% distintos":      f"{diag['distintos'] / _ger * 100:.1f}%",
                "Melhor acerto":    diag["max_acertos"],
                "Jogo vencedor":    jogo_str,
                "Tempo (ms)":       elapsed_ms,
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

        # ── Diagnóstico de cobertura ─────────────────────────────────────────
        st.divider()
        st.subheader("🔎 Diagnóstico da Estratégia")
        st.caption(
            "Mostra se a estratégia realmente varre o espaço de jogos ou fica presa "
            "num subespaço pequeno. Filtro não aumenta a chance de acertar — só "
            "encolhe o espaço que a busca consegue alcançar."
        )

        hist_total = Counter()
        for _d in diags_sim:
            hist_total.update(_d["hist"])
        total_ger = sum(_d["gerados"] for _d in diags_sim)
        total_dis = sum(_d["distintos"] for _d in diags_sim)

        if not total_ger:
            st.warning("Nenhum jogo válido foi gerado — verifique o pool de dezenas.")
        else:
            pct_dis  = total_dis / total_ger * 100
            media_ac = sum(k * v for k, v in hist_total.items()) / total_ger
            melhor   = max(_d["max_acertos"] for _d in diags_sim)

            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Jogos gerados", f"{total_ger:,}")
            d2.metric("Jogos distintos", f"{total_dis:,}", f"{pct_dis:.1f}% do total",
                      delta_color="off")
            d3.metric("Média de acertos", f"{media_ac:.2f}".replace(".", ","),
                      "teórico 9,00", delta_color="off")
            d4.metric("Melhor acerto atingido", melhor)

            # Distribuição observada vs. hipergeométrica (15 de 25, 15 sorteadas)
            linhas_dist = []
            for k in range(5, 16):
                obs = hist_total.get(k, 0)
                teo = comb(15, k) * comb(10, 15 - k) / comb(25, 15)
                linhas_dist.append({
                    "Acertos":     k,
                    "Jogos":       obs,
                    "% observado": f"{obs / total_ger * 100:.4f}%",
                    "% teórico":   f"{teo * 100:.4f}%",
                    "Esperado":    round(teo * total_ger, 2),
                })
            st.dataframe(pd.DataFrame(linhas_dist),
                         use_container_width=True, hide_index=True)

            if pct_dis < 50:
                st.error(
                    f"**Cobertura travada.** Só {pct_dis:.1f}% dos jogos gerados eram "
                    f"combinações diferentes — a estratégia repete o mesmo punhado de "
                    f"jogos. Mais tentativas não ajudam: o alvo pode estar fora do "
                    f"subespaço que ela alcança."
                )
            elif abs(media_ac - 9.0) > 0.15:
                st.warning(
                    f"**Viés detectado.** Média de acertos {media_ac:.2f} contra 9,00 "
                    f"teórico. A estratégia (ou o pool restrito) está deslocando a "
                    f"distribuição em relação ao sorteio uniforme."
                )
            else:
                st.info(
                    f"**Sem travamento.** {pct_dis:.1f}% de jogos distintos e média "
                    f"{media_ac:.2f} ≈ 9,00 teórico: a estratégia se comporta como "
                    f"sorteio uniforme. Não acertar o alvo é resultado do limite de "
                    f"tentativas, não de falha na geração."
                )

        if tent_list:
            st.session_state["_sim_media_val"]   = media_val
            st.session_state["_sim_estrategia"]  = estrategia_sim_sel
            st.session_state["_sim_min_acertos"] = min_acertos_sim
            st.session_state.pop("_jogo_media", None)

# ── MAIN: Backtest Walk-Forward ───────────────────────────────────────────────
elif btn_backtest:
    for _k in ["_sim_media_val", "_sim_estrategia", "_sim_min_acertos", "_jogo_media"]:
        st.session_state.pop(_k, None)

    if not historico_sets:
        st.error("Faça o upload do Excel da Lotofácil antes de rodar o backtest.")
    elif not bt_estrategias:
        st.error("Selecione ao menos uma estratégia.")
    elif len(historico_sets) <= int(bt_n_concursos):
        st.error(
            f"Histórico tem {len(historico_sets)} concursos — insuficiente para avaliar "
            f"{int(bt_n_concursos)} (é preciso haver passado antes de cada um)."
        )
    else:
        _janelas = bt_janelas_sel or [0]
        _sensiveis = [e for e in bt_estrategias if e in ESTRATEGIAS_SENSIVEIS_JANELA]
        _fixos     = [e for e in bt_estrategias if e not in ESTRATEGIAS_SENSIVEIS_JANELA]
        _n_series  = len(_sensiveis) * len(_janelas) + len(_fixos)
        # Séries determinísticas rendem 1 jogo por concurso, não `bt_jogos`.
        _det = [e for e in bt_estrategias if e in ESTRATEGIAS_DETERMINISTICAS]
        _n_series_det = len([e for e in _det if e in ESTRATEGIAS_SENSIVEIS_JANELA]) * len(_janelas) \
                        + len([e for e in _det if e not in ESTRATEGIAS_SENSIVEIS_JANELA])
        _total_jogos = ((_n_series - _n_series_det) * int(bt_jogos) + _n_series_det) \
                       * int(bt_n_concursos)

        st.header("📊 Backtest Walk-Forward")
        st.caption(
            f"{int(bt_n_concursos)} concursos × {_n_series} série(s) "
            f"= **{_total_jogos:,} jogos** conferidos contra resultados reais."
        )
        if _n_series_det:
            st.caption(
                f"{_n_series_det} série(s) determinística(s) — {', '.join(sorted(set(_det)))} — "
                f"geram **1 jogo por concurso** em vez de {int(bt_jogos)}: elas devolvem "
                "sempre o mesmo jogo para um dado recorte, e repetir a linha encolheria "
                "o erro-padrão sem acrescentar informação."
            )
        st.info(
            "Cada jogo é gerado usando **apenas** os concursos anteriores ao que está "
            "sendo conferido — nenhuma informação do futuro entra na geração."
        )
        if _total_jogos > 5_000:
            st.warning(f"{_total_jogos:,} jogos — pode levar alguns minutos.")

        barra = st.progress(0.0, text="Iniciando...")
        t0 = time.time()
        linhas_bt = backtest_walkforward(
            historico_sets,
            estrategias=bt_estrategias,
            janelas=_janelas,
            n_concursos=int(bt_n_concursos),
            jogos_por_concurso=int(bt_jogos),
            pool=pool_disponivel,
            pesos_modelo=pesos_modelo,
            progresso=lambda f, t: barra.progress(min(f, 1.0), text=t),
        )
        barra.progress(1.0, text=f"Concluído em {time.time() - t0:.1f}s")

        resumo = resumir_backtest(linhas_bt)
        if resumo.empty:
            st.error("Backtest não produziu resultados.")
        else:
            st.subheader("Resumo por Estratégia e Recorte")
            st.dataframe(resumo, use_container_width=True, hide_index=True)

            _esperado = 15 * 15 / 25   # média hipergeométrica: 9,0 acertos
            _melhor = resumo.iloc[0]
            _base = resumo[resumo["Estratégia"] == BASELINE_ALEATORIO]

            c1, c2, c3 = st.columns(3)
            c1.metric("Média esperada (teórica)", f"{_esperado:.2f}")
            c2.metric(
                "Melhor média observada",
                f"{resumo['Média'].max():.3f}",
                delta=f"{resumo['Média'].max() - _esperado:+.3f} vs teórico",
            )
            c3.metric(
                "Maior % de 13+",
                f"{_melhor['% 13+']:.2f}%",
                help=f"{_melhor['Estratégia']} · {_melhor['Janela']}",
            )

            st.markdown(
                f"**Leitura**: a coluna *Média* deve ficar colada em "
                f"{_esperado:.2f} para todas as linhas — é o valor forçado pela "
                "distribuição hipergeométrica e nenhuma estratégia o move, porque "
                "os sorteios são independentes. Diferenças de décimos aí são ruído "
                "amostral. O que **pode** diferir de verdade é a cauda "
                "(*% 13+*, *% 14+*): filtros e pesos concentram os jogos numa região "
                "menor do espaço, o que muda a variância, não a média."
            )
            if not _base.empty:
                st.caption(
                    f"Baseline aleatório nesta rodada: média {_base['Média'].iloc[0]:.3f}, "
                    f"% 13+ = {_base['% 13+'].iloc[0]:.2f}%. Compare toda estratégia "
                    "contra esta linha — vantagem só é real se sobreviver a repetições "
                    "do backtest com mais concursos e mais jogos."
                )

            # ── Cauda de baixo: errar 10 ────────────────────────────────────
            _obs_e10 = sum(1 for r in linhas_bt if r["Acertos"] == 5)
            _n_bt    = len(linhas_bt)
            _esp_e10 = P_TEORICO_ERRAR10 * _n_bt
            st.markdown("**Cauda de baixo — errar 10 (acertar exatamente 5)**")
            e1, e2, e3 = st.columns(3)
            e1.metric("Ocorrências observadas", _obs_e10)
            e2.metric("Esperado por acaso", f"{_esp_e10:.2f}",
                      f"{P_TEORICO_ERRAR10 * 100:.4f}% por jogo", delta_color="off")
            e3.metric("Quão raro é um 15", f"1 em {1 / P_TEORICO_15:,.0f}".replace(",", "."),
                      f"errar 10 é {P_TEORICO_ERRAR10 / P_TEORICO_15:,.0f}x mais provável"
                      .replace(",", "."), delta_color="off")
            st.caption(
                "Errar 10 exige que as 10 dezenas ausentes do sorteio estejam todas "
                "dentro do jogo — é acertar quais 10 não saem, o mesmo problema de "
                "previsão virado do avesso. Como acontece ~3.003x mais que um 15, é a "
                "única ponta da distribuição que este backtest tem potência para medir. "
                f"Nesta rodada precisaria de bem mais que {int(_esp_e10) + 1} ocorrências "
                "em muitas réplicas independentes para não ser ruído."
            )
            if {"Errar 10", "Espelho do Errar 10"} <= set(bt_estrategias):
                st.warning(
                    "**Não leia a diferença entre Errar 10 e Espelho como sinal.** "
                    "Este backtest reestima o modelo a cada concurso, então o escore "
                    "de ausência absorve os próprios alvos do período testado e o par "
                    "aparece separado mesmo quando não há nada a prever. Medido: "
                    "gap +0,1555 (t = +3,10) nos dados reais, mas o mesmo procedimento "
                    "sobre histórico embaralhado já devolve t médio +2,09 — e com o "
                    "modelo congelado (treina num terço, testa em outro) o gap cai para "
                    "+0,0008 (t = +0,01). Controles independentes confirmam: "
                    "sobreposição lag-1 = 8,97 contra 9,00 esperado (t = -1,54) e "
                    "χ² de uniformidade das marginais = 24,95 com 24 gl. "
                    "Não há dependência entre concursos para explorar."
                )

            if int(bt_jogos) > 1:
                st.subheader("Melhor Jogo da Carteira")
                st.caption(
                    f"Cada concurso gera uma carteira de {int(bt_jogos)} jogos. "
                    "Aqui a agregação pega o **melhor bilhete de cada carteira** antes de "
                    "tirar a média — é o que decide quando se compra vários jogos de uma "
                    "vez. A média de acertos fica em 9,0 para todas as séries e não "
                    "distingue nada; esta coluna distingue, porque depende de quanto os "
                    "bilhetes se sobrepõem entre si."
                )
                st.dataframe(resumir_carteiras(linhas_bt),
                             use_container_width=True, hide_index=True)
                st.caption(
                    "Compare contra a linha do baseline aleatório. Carteira que fica "
                    "**abaixo** dele está concentrada — bilhetes parecidos demais, que "
                    "acertam e erram juntos."
                )

            st.subheader("Distribuição de Acertos")
            _df_bt = pd.DataFrame(linhas_bt)
            _df_bt["Série"] = _df_bt["Estratégia"] + " · " + _df_bt["Janela"]
            _dist = (
                _df_bt.groupby(["Série", "Acertos"]).size()
                .unstack(fill_value=0).sort_index(axis=1)
            )
            _dist_pct = (100 * _dist.T / _dist.sum(axis=1)).T.round(2)
            st.dataframe(_dist_pct, use_container_width=True)
            st.caption("Percentual de jogos por número de acertos, em cada série.")

            st.download_button(
                "⬇️ Baixar backtest detalhado (CSV)",
                _df_bt.to_csv(index=False).encode("utf-8"),
                "backtest_lotofacil.csv",
                "text/csv",
            )

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

        with st.expander("🎨 Análise de Cores das Bolas (final do número)"):
            st.caption(
                "Cor da bola é definida pelo final do número: "
                "1=Vermelha · 2=Amarela · 3=Verde · 4=Marrom · 5=Azul · "
                "6=Rosa · 7=Preta · 8=Cinza · 9=Laranja · 0=Branca"
            )
            n_hist = len(historico_sets)
            linhas_cores = []
            for f in FINAIS_ORDEM:
                grupo = DEZENAS_POR_COR[f]
                cnts = [sum(1 for n in s if n % 10 == f) for s in historico_sets]
                media = sum(cnts) / n_hist
                dist = Counter(cnts)
                linhas_cores.append({
                    "Cor": NOME_COR[f],
                    "Dezenas": " ".join(f"{n:02d}" for n in grupo),
                    "Média/concurso": round(media, 2),
                    "Esperado": round(len(grupo) * 15 / 25, 2),
                    "% zerada": f"{100 * dist.get(0, 0) / n_hist:.1f}%",
                    "% completa": f"{100 * dist.get(len(grupo), 0) / n_hist:.1f}%",
                })
            st.dataframe(pd.DataFrame(linhas_cores), use_container_width=True, hide_index=True)
            pct_padrao = 100 * sum(1 for s in historico_sets if validar_cores(s)) / n_hist
            st.caption(
                f"**Padrão dominante**: finais 1–5 com 1–3 dezenas, no máximo 2 cores zeradas "
                f"e 4–6 cores com 2+ dezenas → cobre **{pct_padrao:.1f}%** do histórico. "
                "A estratégia **Padrão de Cores** gera jogos dentro desse perfil "
                "(amostrando assinaturas reais do recorte)."
            )

        with st.expander(f"⚖️ Sinais do Modelo Ponderado — {_rotulo_janela(janela_analise)}"):
            _at = atrasos_atuais(historico_analise)
            _pesos_atuais = pesos_ponderados(
                historico_analise, ultimo_resultado, w_freq, w_atraso, w_rep
            )
            _soma_pesos = sum(_pesos_atuais.values())
            _ult_set = set(ultimo_resultado)
            _tab = pd.DataFrame([{
                "Dezena":     f"{d:02d}",
                "Frequência": frequencia[d],
                "% no recorte": round(100 * frequencia[d] / max(len(historico_analise), 1), 1),
                "Atraso":     _at[d],
                "Saiu no último": "sim" if d in _ult_set else "não",
                "Peso":       round(_pesos_atuais[d], 3),
                "Chance rel.": f"{100 * _pesos_atuais[d] / _soma_pesos:.2f}%",
            } for d in range(1, 26)]).sort_values("Peso", ascending=False)
            st.dataframe(_tab, use_container_width=True, hide_index=True)
            st.caption(
                f"Pesos atuais — frequência **{w_freq:g}**, atraso **{w_atraso:g}**, "
                f"repetição **{w_rep:g}** (ajuste na lateral). "
                f"Maior atraso no recorte: **{max(_at.values())}** concursos. "
                "'Chance rel.' é a probabilidade de a dezena ser a próxima escolhida "
                "no início da amostragem, não a chance de ela ser sorteada pela Caixa."
            )

    elif "_sim_media_val" not in st.session_state:
        st.markdown("""
        ### Como usar
        1. **Upload**: Arraste o Excel da Lotofácil na lateral esquerda
           *(Colunas: Concurso · Data Sorteio · Bola1–Bola15 · Ganhadores 15 acertos)*
        2. **Base de análise**: Escolha o recorte (últimos 30/50/100… ou tudo)
        3. **Configure**: Escolha a quantidade de jogos e exclua números se desejar
        4. **Estratégia**: Selecione a lógica de geração desejada
        5. **Gere**: Clique em **Gerar Jogos** ou **Painel Completo**
        6. **Meça**: Use o **Backtest Walk-Forward** para comparar estratégias e
           recortes contra resultados reais

        ### Filtros aplicados automaticamente
        | Filtro | Regra |
        |--------|-------|
        | Soma | Entre 180 e 220 |
        | Sequência | No máximo 4 números consecutivos |
        | Ineditismo | Sem 14+ dezenas em comum com qualquer resultado histórico |

        ### Base de Análise (Recorte) 🔍
        Frequência, atraso, assinaturas de cor, fixas e pool automáticos passam a
        ser calculados só sobre os últimos N concursos. Recorte curto muda o perfil
        dos jogos e aumenta a variância — **não** a média de acertos, que é fixada
        em 9,0 pela distribuição hipergeométrica. Use o backtest para ver o efeito
        real na cauda (13+ acertos) em vez de confiar na intuição.

        ### Estratégia Modelo Ponderado ⚖️
        Score por dezena = `w_freq × frequência` + `w_atraso × atraso` +
        `w_rep × saiu no último`, cada sinal normalizado em 0–1, com amostragem
        proporcional ao score. Os três pesos são ajustáveis na lateral.

        ### Estratégia Padrão de Cores 🎨
        Cor da bola = final do número (1=Vermelha, 2=Amarela, 3=Verde, 4=Marrom,
        5=Azul, 6=Rosa, 7=Preta, 8=Cinza, 9=Laranja, 0=Branca).
        A estratégia amostra assinaturas de cores reais do recorte e monta jogos
        dentro do perfil dominante: finais 1–5 com 1–3 dezenas, no máximo 2 cores
        zeradas e 4–6 cores com 2+ dezenas.
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
                    historico_analise=historico_analise,
                    pesos_modelo=pesos_modelo,
                )
        st.session_state["_jogo_media"] = _jogo

    if st.session_state.get("_jogo_media"):
        _jm = st.session_state["_jogo_media"]
        st.success(f"Jogo da posição **#{_cap:,}**: {' · '.join(f'{n:02d}' for n in _jm)}")
        st.markdown(render_volante(_jm), unsafe_allow_html=True)
        st.caption(info_jogo(_jm))

# ── CONFERÊNCIA DOS JOGOS GERADOS ─────────────────────────────────────────────
# Os jogos vivem em `st.session_state["_conf_jogos"]`, não em variável local: o
# Streamlit reexecuta o script a cada interação, então ao clicar em "Conferir" o
# `btn_gerar` já é False e os jogos gerados teriam sido perdidos. Por isso o
# download também mora aqui — dentro do ramo de geração ele desapareceria no
# primeiro clique de conferência.
FAIXAS_PREMIO = {15: "🏆 15 pontos", 14: "🥈 14 pontos", 13: "🥉 13 pontos",
                 12: "✅ 12 pontos", 11: "✅ 11 pontos"}
FAIXA_MINIMA_PREMIO = 11        # a Lotofácil não paga abaixo de 11 acertos

def parse_alvo_conferencia(texto, n=15):
    """`(dezenas, erro)`. Aceita qualquer separador não numérico — vírgula,
    espaço, ponto-e-vírgula, hífen, barra, tabulação — porque o resultado
    normalmente vem colado de sites com formatos diferentes."""
    nums = [int(p) for p in re.split(r"\D+", texto.strip()) if p]
    if not nums:
        return [], "Digite as dezenas do resultado."
    fora = sorted({d for d in nums if not 1 <= d <= 25})
    if fora:
        return [], f"Fora da faixa 1–25: {', '.join(f'{d:02d}' for d in fora)}."
    rep = sorted({d for d in nums if nums.count(d) > 1})
    if rep:
        return [], f"Dezena repetida: {', '.join(f'{d:02d}' for d in rep)}."
    if len(nums) != n:
        return [], f"São necessárias {n} dezenas — você informou {len(nums)}."
    return sorted(nums), ""

def faixas_do_cartao(jogo, alvo):
    """`(faixas, acertos)` — quantas apostas simples do cartão fazem cada
    pontuação, e a sobreposição do cartão com o alvo.

    Cartão de 15 é uma aposta simples só. Cartão de 16 são as C(16,15) = 16
    apostas obtidas removendo uma dezena: se `d` das sorteadas caem no cartão,
    omitir uma sorteada dá `d-1` acertos e omitir uma não sorteada dá `d`, logo
    saem `d` apostas com `d-1` e `16-d` com `d`. É isso que paga — o número de
    acertos do cartão, sozinho, não diz quanto ele rendeu."""
    js, al = set(jogo), set(alvo)
    d = len(js & al)
    if len(js) <= 15:
        return Counter({d: 1}), d
    return Counter(len((js - {om}) & al) for om in js), d

st.divider()
_conf_jogos = st.session_state.get("_conf_jogos") or []

if _conf_jogos:
    st.header("🔍 Conferir os jogos gerados")
    if st.session_state.get("_conf_origem"):
        st.caption(st.session_state["_conf_origem"])

    _df_conf = pd.DataFrame(_conf_jogos)
    st.download_button(
        "⬇️ Baixar Jogos (CSV)",
        _df_conf.to_csv(index=False, header=False).encode("utf-8"),
        st.session_state.get("_conf_arquivo", "jogos_lotofacil.csv"),
        "text/csv", key="_dl_conf",
    )

    _txt_alvo = st.text_input(
        "Resultado alvo (15 dezenas)",
        key="_conf_alvo_txt",
        placeholder="01,02,03,04,05,06,07,08,09,10,11,12,13,14,15",
        help="Cole o resultado oficial. Qualquer separador serve.",
    )
    if st.button("🔍 Conferir", key="_btn_conferir"):
        _alvo_novo, _erro_alvo = parse_alvo_conferencia(_txt_alvo)
        if _erro_alvo:
            st.error(_erro_alvo)
            st.session_state.pop("_conf_alvo_ok", None)
        else:
            st.session_state["_conf_alvo_ok"] = _alvo_novo

    _alvo = st.session_state.get("_conf_alvo_ok")
    if _alvo:
        st.write("**Resultado alvo:** " + " · ".join(f"{n:02d}" for n in _alvo))

        _linhas, _premiadas_tot = [], Counter()
        _tem_16 = any(len(j) > 15 for j in _conf_jogos)
        for _i, _jogo in enumerate(_conf_jogos):
            _faixas, _d = faixas_do_cartao(_jogo, _alvo)
            _pag = sorted((k for k in _faixas if k >= FAIXA_MINIMA_PREMIO), reverse=True)
            _premiadas_tot += Counter({k: _faixas[k] for k in _pag})
            _linha = {
                "Jogo": _i + 1,
                "Dezenas": " · ".join(f"{n:02d}" for n in sorted(_jogo)),
                "Acertos": _d,
                "Prêmio": FAIXAS_PREMIO.get(_pag[0], "—") if _pag else "—",
            }
            if _tem_16:
                _linha["Apostas simples premiadas"] = (
                    " + ".join(f"{_faixas[k]}×{k} pontos" for k in _pag) if _pag else "—"
                )
            _linhas.append(_linha)

        st.dataframe(pd.DataFrame(_linhas), use_container_width=True, hide_index=True)

        _acertos = [len(set(j) & set(_alvo)) for j in _conf_jogos]
        _c1, _c2, _c3, _c4 = st.columns(4)
        _c1.metric("Melhor bilhete", max(_acertos))
        _c2.metric("Média dos acertos", f"{sum(_acertos) / len(_acertos):.2f}")
        _c3.metric("Apostas premiadas", sum(_premiadas_tot.values()))
        _c4.metric("Jogos conferidos", len(_conf_jogos))

        if _premiadas_tot:
            st.success("🎉 " + " · ".join(
                f"{_premiadas_tot[k]} aposta(s) com **{k} pontos**"
                for k in sorted(_premiadas_tot, reverse=True)))
        else:
            st.info("Nenhuma aposta premiada — a Lotofácil paga a partir de 11 acertos.")

        # Referência honesta: a média esperada é fixada pela hipergeométrica
        # (tam × 15 / 25) e não depende de estratégia nenhuma. Sem ela, 9 acertos
        # num cartão de 16 parece normal quando está abaixo da média.
        _refs = sorted({len(j) for j in _conf_jogos})
        _txt_ref = " · ".join(f"cartão de {t}: {t * 15 / 25:.2f}" for t in _refs)
        st.caption(
            f"Média esperada de qualquer cartão, por hipergeométrica — {_txt_ref}. "
            "É o piso de comparação: acima disso pode ser sorte, abaixo não é azar. "
            "Um concurso isolado não mede estratégia — o desvio-padrão é ~1,2 acerto "
            "e detectar uma vantagem de 0,10 acerto exige 576 concursos."
        )
        with st.expander("Ver os volantes marcados contra o alvo"):
            st.caption("Cada volante pinta apenas as dezenas do jogo que saíram no "
                       "resultado; as que erraram vêm listadas abaixo dele.")
            _cols_conf = st.columns(3)
            for _i, _jogo in enumerate(_conf_jogos):
                _bateram = sorted(set(_jogo) & set(_alvo))
                _erraram = sorted(set(_jogo) - set(_alvo))
                with _cols_conf[_i % 3]:
                    st.markdown(f"**Jogo {_i + 1}** — {len(_bateram)} acertos")
                    st.markdown(render_volante(_bateram), unsafe_allow_html=True)
                    if _erraram:
                        st.caption("Erraram: "
                                   + " · ".join(f"{n:02d}" for n in _erraram))
                    else:
                        st.caption("Todas as dezenas do jogo saíram.")
                    st.divider()
    elif not _txt_alvo:
        st.caption("Cole o resultado acima e clique em **Conferir** para ver os "
                   "acertos de cada jogo.")

# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Aviso: Este software é uma ferramenta de análise estatística. "
    "Loterias são jogos de azar e não há garantia de lucro. Jogue com responsabilidade."
)