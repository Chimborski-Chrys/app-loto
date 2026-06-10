import streamlit as st
import pandas as pd

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


def parse_arquivo_jogos(file):
    nome = file.name.lower()
    jogos = []
    if nome.endswith(".csv"):
        content = file.read().decode("utf-8", errors="ignore")
        file.seek(0)
        for linha in content.splitlines():
            linha = linha.strip()
            if not linha:
                continue
            nums = []
            for p in linha.split(","):
                p = p.strip()
                try:
                    n = int(float(p))
                    if n > 0:
                        nums.append(n)
                except (ValueError, TypeError):
                    pass
            if len(nums) >= 4:
                jogos.append(nums)
    else:
        df_j = pd.read_excel(file, header=None)
        for _, row in df_j.iterrows():
            nums = []
            for val in row:
                try:
                    n = int(float(val))
                    if n > 0:
                        nums.append(n)
                except (ValueError, TypeError):
                    pass
            if len(nums) >= 4:
                jogos.append(nums)
    if not jogos:
        return [], "lotofacil"
    avg_len = sum(len(j) for j in jogos) / len(jogos)
    tipo = "megasena" if avg_len < 15 else "lotofacil"
    return jogos, tipo


# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.header("1. Upload dos Jogos")
arq = st.sidebar.file_uploader(
    "Arquivo com seus jogos (CSV ou Excel)",
    type=["csv", "xlsx"],
    help=(
        "CSV: uma linha por jogo, números separados por vírgula.\n"
        "Excel: uma linha por jogo, um número por célula (sem cabeçalho).\n\n"
        "Detecção automática: < 15 números → Mega-Sena · ≥ 15 → Lotofácil"
    ),
)

jogos = []
tipo = "lotofacil"

if arq:
    try:
        jogos, tipo = parse_arquivo_jogos(arq)
        if jogos:
            label = "Lotofácil" if tipo == "lotofacil" else "Mega-Sena"
            st.sidebar.success(f"✅ {len(jogos)} jogo(s) carregado(s)")
            st.sidebar.info(f"Tipo detectado: **{label}**")
        else:
            st.sidebar.error("Nenhum jogo encontrado no arquivo.")
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

**Detecção automática do tipo:**
- Menos de 15 números por jogo → **Mega-Sena**
- 15 ou mais números por jogo → **Lotofácil**
""")
else:
    label_tipo = "Lotofácil" if tipo == "lotofacil" else "Mega-Sena"
    nums_por_jogo = 15 if tipo == "lotofacil" else 6

    st.subheader(f"🎲 {label_tipo} — {len(jogos)} jogo(s) carregado(s)")

    placeholder = (
        "01,02,03,04,05,06,07,08,09,10,11,12,13,14,15"
        if tipo == "lotofacil"
        else "01,02,03,04,05,06"
    )
    resultado_str = st.text_input(
        f"Resultado oficial ({nums_por_jogo} números separados por vírgula):",
        key="verif_resultado",
        placeholder=placeholder,
    )

    resultado_oficial = []
    erro_parse = False
    if resultado_str:
        try:
            partes = [p.strip() for p in resultado_str.split(",") if p.strip()]
            resultado_oficial = [int(p) for p in partes]
        except ValueError:
            st.error("Formato inválido. Use apenas números separados por vírgula.")
            erro_parse = True

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
                "Jogo": i + 1,
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
