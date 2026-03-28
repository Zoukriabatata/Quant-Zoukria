"""
Page Backtest Kalman OU — redirige vers le backtest standalone.
Sur Streamlit Cloud, affiche un message. En local, charge le backtest.
"""
import streamlit as st
import os

st.set_page_config(page_title="Backtest Kalman", page_icon="BK", layout="wide")

# Detecter si on est sur Streamlit Cloud ou en local
is_cloud = os.environ.get("STREAMLIT_SHARING_MODE") or not os.path.exists(
    r"C:\Users\ryadb\Downloads\GLBX-20260327-P8LBCQVG8R"
)

if is_cloud:
    st.title("Backtest Kalman OU — MNQ")
    st.warning(
        "Le backtest necessite les donnees Databento en local.\n\n"
        "Lance en local avec:\n"
        "```\nstreamlit run backtest_kalman.py\n```"
    )
    st.markdown("---")
    st.markdown("### Derniers resultats du backtest")
    st.markdown("""
    | Metrique | Valeur |
    |---|---|
    | **Winrate** | 46.8% |
    | **Esperance** | +20.5 pts/trade |
    | **Profit Factor** | 3.48 |
    | **Return** | +10.2% (3 mois) |
    | **Max Drawdown** | -0.6% |
    | **Kelly** | 33.3% |
    | **Signal** | Kalman OU (k=1.0σ) |
    | **TP** | Retour au fair value |
    | **SL** | ATR x 1.5 |
    """)
else:
    st.title("Backtest Kalman OU — MNQ")
    st.info("Lance le backtest complet avec: `streamlit run backtest_kalman.py`")
    st.markdown("Ce backtest necessite les fichiers Databento et un traitement lourd. "
                "Il tourne en standalone pour eviter les timeouts.")
