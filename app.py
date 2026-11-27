import streamlit as st

st.set_page_config(
    page_title="Loterias Pro — IA & Engenharia de Dados",
    page_icon="🎰",
    layout="wide"
)

st.title("🎰 Loterias Pro — IA & Engenharia de Dados")
st.markdown("Bem-vindo ao gerador inteligente de jogos para loterias da Caixa Econômica Federal.")
st.markdown("Escolha um módulo no menu lateral **←** ou clique em um dos atalhos abaixo.")

st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.subheader("🎲 Lotofácil")
    st.write("25 números · escolha 15 · análise histórica e estratégias de fechamento.")
    if st.button("Acessar Lotofácil", use_container_width=True):
        st.switch_page("pages/1_Lotofacil.py")

with col2:
    st.subheader("🎰 Mega Sena")
    st.write("60 números · aposte de 6 a 15 dezenas · 7 estratégias + Melhor Jogo IA.")
    if st.button("Acessar Mega Sena", use_container_width=True):
        st.switch_page("pages/2_Mega_Sena.py")

with col3:
    st.subheader("🎯 Quina")
    st.write("80 números · acerte 5 · 4 métodos de desdobramento e fechamento de ciclo.")
    if st.button("Acessar Quina", use_container_width=True):
        st.switch_page("pages/3_Quina.py")

with col4:
    st.subheader("🔍 Verificador")
    st.write("Confira seus jogos · CSV ou Excel · Lotofácil, Mega-Sena e Quina · acertos por jogo.")
    if st.button("Acessar Verificador", use_container_width=True):
        st.switch_page("pages/4_Verificador.py")

st.divider()
st.caption("Aviso: Este software é uma ferramenta de análise estatística. Loterias são jogos de azar e não há garantia de lucro.")
