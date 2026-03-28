import streamlit as st

st.set_page_config(page_title="Quant Maths", page_icon="QM", layout="wide")

st.title("QUANT MATHS")
st.markdown("### Systeme de trading quantitatif MNQ")

st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### Etude")
    st.markdown(
        "Roadmap d'apprentissage : Time Series, CLT, GARCH, HMM, "
        "Kalman Filter, Pipeline integration."
    )
    st.markdown("*Disponible sur Cloud et en local*")

with col2:
    st.markdown("### Backtest Kalman")
    st.markdown(
        "Backtest Kalman OU Mean Reversion sur donnees Databento MNQ. "
        "46.8% WR, PF 3.48, +10.2% return."
    )
    st.markdown("*Local uniquement (donnees Databento)*")

with col3:
    st.markdown("### Live Kalman")
    st.markdown(
        "Signal live Kalman OU via IBKR TWS. "
        "Fair value, bandes, entry/SL/TP en temps reel."
    )
    st.markdown("*Local uniquement (TWS requis)*")

st.markdown("---")
st.markdown("### Architecture")
st.code("""
Signal:  Kalman OU Mean Reversion (prix hors bande k x sigma_stat)
TP:      Retour au fair value Kalman
SL:      ATR x 1.5 (dynamique, max 15 pts)
Filtre:  GARCH regime (skip HIGH vol)
Sizing:  Apex-safe (max 2 contracts, daily loss limit $400)
Data:    IBKR TWS (CME L1, $1.55/mois)
""", language="text")

st.markdown("---")
st.caption("Utilise la sidebar pour naviguer entre les pages.")
