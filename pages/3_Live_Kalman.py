"""
Page Live Kalman OU — redirige vers le live standalone.
Sur Streamlit Cloud, affiche un message. En local, charge le live.
"""
import streamlit as st
import os

st.set_page_config(page_title="Live Kalman", page_icon="LK", layout="wide")

is_cloud = os.environ.get("STREAMLIT_SHARING_MODE") or not os.path.exists(r"C:\Users\ryadb")

if is_cloud:
    st.title("Live Kalman OU — MNQ")
    st.warning(
        "Le mode live necessite TWS (IBKR) en local.\n\n"
        "Lance en local avec:\n"
        "```\nstreamlit run live_kalman.py\n```"
    )
    st.markdown("---")
    st.markdown("### Comment trader")
    st.markdown("""
    1. Ouvrir **TWS** (IBKR, port 7497)
    2. Lancer `streamlit run live_kalman.py`
    3. Cliquer **Demarrer**
    4. Attendre le signal: **LONG** ou **SHORT**
    5. Executer sur **Apex** avec les niveaux affiches
    6. **1 trade max par session**

    ### Logique du signal
    | Composant | Methode |
    |---|---|
    | **Signal** | Prix sort de la bande Kalman OU (k=1.0σ) |
    | **TP** | Retour au fair value Kalman |
    | **SL** | ATR x 1.5 (dynamique) |
    | **Filtre** | GARCH regime (skip HIGH vol) |
    | **Data** | IBKR TWS (CME L1, $1.55/mois) |
    """)
else:
    st.title("Live Kalman OU — MNQ")
    st.info("Lance le live avec: `streamlit run live_kalman.py`")
    st.markdown("Le live necessite TWS ouvert en arriere-plan.")
