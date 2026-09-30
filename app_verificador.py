import streamlit as st
import pandas as pd
import re
from collections import Counter

st.set_page_config(
    page_title="Verificador de Resultados — Loterias Pro",
    page_icon="🔍",
    layout="wide",
)

st.markdown("""
<style>
.main { background-color: #0e1117; color: white; }
.stButton>button { width: 100%; border-radius: 5px; height: 3em;
                   background-color: #ff4b4b; color: white; }
</style>
""", unsafe_allow_html=True)


# (dezenas por jogo, maior dezena do volante) por loteria.
REGRAS_TIPO = {"lotofacil": (15, 25), "megasena": (6, 60), "quina": (5, 80)}
ROTULO_TIPO = {"lotofacil": "Lotofácil", "megasena": "Mega-Sena", "quina": "Quina"}

# Uma linha da planilha da Caixa não é um jogo: além das bolas ela traz o número
# do concurso, a data, os ganhadores e os rateios. Varrer a linha inteira atrás
# de números fazia o verificador montar jogos como
# `1, 4, 5, 17, 30, 33, 41, 52, 2016` — o 1 é o concurso, o 2016 é o ano da data
# e os rateios entram como dezenas. Por isso a planilha da Caixa é reconhecida
# pelo cabeçalho e só as colunas das bolas são lidas.
RE_COLUNA_BOLA = re.compile(r"^\s*(bola|dezena|n[úu]mero)\s*0*\d+\s*$", re.I)


def _colunas_bolas(df):
    """Colunas de dezenas de uma planilha com cabeçalho (Bola1…BolaN)."""
    cols = [c for c in df.columns if RE_COLUNA_BOLA.match(str(c))]
    def _ordem(c):
        m = re.search(r"(\d+)\s*$", str(c))
        return int(m.group(1)) if m else 0
    return sorted(cols, key=_ordem)


def _tipo_por_tamanho(n):
    if n <= 5:
        return "quina"
    if n <= 14:
        return "megasena"
    return "lotofacil"


def _linhas_para_jogos(linhas):
    """`linhas` é uma lista de listas de inteiros. Devolve `(jogos, tipo, diag)`.

    O tipo sai do tamanho MAIS COMUM das linhas, não da média: uma linha
    estragada no meio do arquivo deslocava a média e trocava a loteria inteira.
    Depois do tipo definido, cada linha precisa ter o tamanho certo e as dezenas
    dentro do volante — o resto é descartado e contado em `diag`."""
    diag = {"ignoradas_tamanho": 0, "ignoradas_faixa": 0, "total_lidas": len(linhas)}
    if not linhas:
        return [], "lotofacil", diag
    tipo = _tipo_por_tamanho(Counter(len(l) for l in linhas).most_common(1)[0][0])
    n_dez, maior = REGRAS_TIPO[tipo]
    jogos = []
    for nums in linhas:
        if len(nums) != n_dez:
            diag["ignoradas_tamanho"] += 1
            continue
        if len(set(nums)) != n_dez or any(not 1 <= d <= maior for d in nums):
            diag["ignoradas_faixa"] += 1
            continue
        jogos.append(sorted(nums))
    return jogos, tipo, diag


def parse_arquivo_jogos(file):
    """`(jogos, tipo, diag)`. `diag["fonte"]` diz se veio de uma planilha de
    histórico da Caixa (colunas Bola1…BolaN) ou de linhas soltas de jogos."""
    nome = file.name.lower()
    linhas, fonte, rotulos = [], "linhas", []

    if nome.endswith(".csv"):
        content = file.read().decode("utf-8", errors="ignore")
        file.seek(0)
        for linha in content.splitlines():
            if not linha.strip():
                continue
            nums = []
            for p in re.split(r"[;,\t]", linha):
                try:
                    nums.append(int(float(p.strip())))
                except (ValueError, TypeError):
                    pass
            if nums:
                linhas.append(nums)
    else:
        df_h = pd.read_excel(file, header=0)
        file.seek(0)
        cols = _colunas_bolas(df_h)
        if len(cols) >= 5:
            # Planilha da Caixa (ou qualquer uma com cabeçalho de bolas).
            fonte = "historico"
            validas = df_h.dropna(subset=cols)
            for _, row in validas.iterrows():
                try:
                    linhas.append([int(float(row[c])) for c in cols])
                except (ValueError, TypeError):
                    continue
            col_conc = next((c for c in df_h.columns
                             if str(c).strip().lower().startswith("concurso")), None)
            if col_conc is not None:
                rotulos = [str(v) for v in validas[col_conc].tolist()]
        else:
            df_j = pd.read_excel(file, header=None)
            for _, row in df_j.iterrows():
                nums = []
                for val in row:
                    try:
                        nums.append(int(float(val)))
                    except (ValueError, TypeError):
                        pass
                if nums:
                    linhas.append(nums)

    jogos, tipo, diag = _linhas_para_jogos(linhas)
    diag["fonte"] = fonte
    # Os rótulos só continuam válidos se nenhuma linha tiver sido descartada.
    diag["rotulos"] = rotulos if len(rotulos) == len(jogos) else []
    return jogos, tipo, diag


# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.header("1. Upload dos Jogos")
arq = st.sidebar.file_uploader(
    "Arquivo com seus jogos (CSV ou Excel)",
    type=["csv", "xlsx"],
    help=(
        "CSV: uma linha por jogo, números separados por vírgula.\n"
        "Excel: uma linha por jogo, um número por célula (sem cabeçalho), OU a "
        "planilha de resultados da Caixa (com colunas Bola1…BolaN).\n\n"
        "Detecção automática: 5 → Quina · 6 a 14 → Mega-Sena · ≥ 15 → Lotofácil"
    ),
)

jogos, tipo, diag = [], "lotofacil", {}
rotulos = []

if arq:
    try:
        jogos, tipo, diag = parse_arquivo_jogos(arq)
        rotulos = diag.get("rotulos") or []
        if jogos:
            st.sidebar.success(f"✅ {len(jogos)} jogo(s) carregado(s)")
            st.sidebar.info(f"Tipo detectado: **{ROTULO_TIPO[tipo]}**")
            if diag.get("fonte") == "historico":
                st.sidebar.caption(
                    "Planilha de resultados da Caixa reconhecida: só as colunas das "
                    "bolas foram lidas. Cada linha é um concurso, e o resultado que "
                    "você digitar será comparado com todos eles."
                )
            _desc = diag.get("ignoradas_tamanho", 0) + diag.get("ignoradas_faixa", 0)
            if _desc:
                st.sidebar.warning(
                    f"{_desc} linha(s) descartada(s): "
                    f"{diag.get('ignoradas_tamanho', 0)} sem as "
                    f"{REGRAS_TIPO[tipo][0]} dezenas de {ROTULO_TIPO[tipo]} e "
                    f"{diag.get('ignoradas_faixa', 0)} com dezena repetida ou fora "
                    f"da faixa 1–{REGRAS_TIPO[tipo][1]}."
                )
        else:
            st.sidebar.error(
                "Nenhum jogo válido encontrado. O arquivo deve ter uma linha por "
                "jogo (5, 6 ou 15 dezenas) ou ser a planilha da Caixa."
            )
    except Exception as e:
        st.sidebar.error(f"Erro ao ler arquivo: {e}")

# ── Main ───────────────────────────────────────────────────────────────────────
st.title("🔍 Verificador de Resultados")

if not jogos:
    st.info("Faça upload do arquivo com seus jogos na lateral esquerda.")
    st.markdown("""
### Formato aceito

**CSV** — uma linha por jogo, números separados por vírgula:
```
1,5,12,23,45,60
3,7,11,22,38,55
```

**Excel** — uma linha por jogo, um número por célula (sem cabeçalho):

| A | B | C | D | E | F |
|---|---|---|---|---|---|
| 1 | 5 | 12 | 23 | 45 | 60 |
| 3 | 7 | 11 | 22 | 38 | 55 |

**Planilha da Caixa** — também é aceita direto: se o arquivo tiver colunas
`Bola1`…`BolaN`, só elas são lidas, e cada concurso vira uma linha para conferir
contra o resultado que você digitar.

**Detecção automática do tipo:**
- 5 números por jogo → **Quina**
- 6 a 14 números por jogo → **Mega-Sena**
- 15 ou mais números por jogo → **Lotofácil**

Linhas com dezena repetida, fora da faixa do volante ou com quantidade diferente
da loteria detectada são descartadas, e a lateral informa quantas.
""")
else:
    label_tipo = ROTULO_TIPO[tipo]
    nums_por_jogo, maior_dezena = REGRAS_TIPO[tipo]

    _rot = "concurso(s) do histórico" if diag.get("fonte") == "historico" else "jogo(s)"
    st.subheader(f"🎲 {label_tipo} — {len(jogos)} {_rot}")

    placeholder = {
        "lotofacil": "01,02,03,04,05,06,07,08,09,10,11,12,13,14,15",
        "megasena": "01,02,03,04,05,06",
        "quina": "01,02,03,04,05",
    }[tipo]
    resultado_str = st.text_input(
        f"Resultado oficial ({nums_por_jogo} números separados por vírgula):",
        key="verif_resultado",
        placeholder=placeholder,
    )

    # Mesmo parser dos outros apps: qualquer separador, e valida faixa, repetidas
    # e quantidade antes de conferir — um resultado com 5 dezenas na Mega-Sena
    # produziria uma tabela de acertos silenciosamente errada.
    resultado_oficial = []
    erro_parse = False
    if resultado_str:
        nums = [int(x) for x in re.split(r"\D+", resultado_str.strip()) if x]
        fora = sorted({d for d in nums if not 1 <= d <= maior_dezena})
        reps = sorted({d for d in nums if nums.count(d) > 1})
        if not nums:
            st.error("Digite as dezenas do resultado.")
            erro_parse = True
        elif fora:
            st.error(f"Fora da faixa 1–{maior_dezena}: "
                     + ", ".join(f"{d:02d}" for d in fora) + ".")
            erro_parse = True
        elif reps:
            st.error("Dezena repetida: " + ", ".join(f"{d:02d}" for d in reps) + ".")
            erro_parse = True
        elif len(nums) != nums_por_jogo:
            st.error(f"{label_tipo} sorteia {nums_por_jogo} dezenas — você informou "
                     f"{len(nums)}.")
            erro_parse = True
        else:
            resultado_oficial = sorted(nums)

    st.divider()

    if resultado_oficial and not erro_parse:
        resultado_set = set(resultado_oficial)
        st.write(f"**Resultado:** {' · '.join(f'{n:02d}' for n in sorted(resultado_oficial))}")

        dados = []
        for i, jogo in enumerate(jogos):
            acertos = len(set(jogo) & resultado_set)
            if tipo == "lotofacil":
                if acertos == 15:
                    premio = "🏆 15 pontos"
                elif acertos == 14:
                    premio = "🥈 14 pontos"
                elif acertos == 13:
                    premio = "🥉 13 pontos"
                elif acertos == 12:
                    premio = "✅ 12 pontos"
                elif acertos == 11:
                    premio = "✅ 11 pontos"
                else:
                    premio = "—"
            elif tipo == "quina":
                if acertos == 5:
                    premio = "🏆 Quina"
                elif acertos == 4:
                    premio = "🥈 Quadra"
                elif acertos == 3:
                    premio = "🥉 Terno"
                elif acertos == 2:
                    premio = "✅ Duque"
                else:
                    premio = "—"
            else:
                if acertos == 6:
                    premio = "🏆 Sena"
                elif acertos == 5:
                    premio = "🥈 Quina"
                elif acertos == 4:
                    premio = "🥉 Quadra"
                else:
                    premio = "—"
            dados.append({
                "Jogo": rotulos[i] if rotulos else i + 1,
                "Dezenas": " · ".join(f"{n:02d}" for n in sorted(jogo)),
                "Acertos": acertos,
                "Prêmio": premio,
            })

        df_verif = pd.DataFrame(dados)
        st.dataframe(df_verif, use_container_width=True, hide_index=True)

        premiados = [d for d in dados if d["Prêmio"] != "—"]
        if premiados:
            st.success(f"🎉 {len(premiados)} jogo(s) premiado(s)!")
        else:
            st.info("Nenhum jogo premiado neste resultado.")

        _ac = [d["Acertos"] for d in dados]
        _c1, _c2, _c3 = st.columns(3)
        _c1.metric("Melhor jogo", max(_ac))
        _c2.metric("Média dos acertos", f"{sum(_ac) / len(_ac):.2f}")
        _c3.metric("Jogos conferidos", len(_ac))
        st.caption(
            "Média esperada de qualquer jogo, por hipergeométrica: "
            f"{nums_por_jogo * nums_por_jogo / maior_dezena:.2f}. É o piso de "
            "comparação — acima disso pode ser sorte, abaixo não é azar."
        )

    else:
        dados = [
            {"Jogo": i + 1, "Dezenas": " · ".join(f"{n:02d}" for n in sorted(j))}
            for i, j in enumerate(jogos)
        ]
        st.dataframe(pd.DataFrame(dados), use_container_width=True, hide_index=True)
        if not resultado_str:
            st.caption("⬆️ Digite o resultado oficial acima para ver os acertos.")

st.markdown("---")
st.caption(
    "Aviso: Este software é uma ferramenta de análise estatística. "
    "Loterias são jogos de azar e não há garantia de lucro. Jogue com responsabilidade."
)
