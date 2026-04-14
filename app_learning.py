import streamlit as st

pg = st.navigation([
    st.Page("Accueil.py",              title="Quant Maths",    icon="⚡"),
    st.Page("pages/1_Demarrage.py",    title="Démarrage",      icon="🔌"),
    st.Page("pages/2_Session_Prep.py", title="Session Prep",   icon="🕐"),
    st.Page("pages/3_Live_Signal.py",  title="Live Signal",    icon="📡"),
    st.Page("pages/4_Journal.py",      title="Journal",        icon="📒"),
    st.Page("pages/5_Backtest.py",     title="Backtest",       icon="📊"),
    st.Page("pages/6_Multi_Model.py",  title="Multi-Model",    icon="🤖"),
    st.Page("pages/7_Etude.py",        title="Étude",          icon="🎓"),
    st.Page("pages/8_Library.py",      title="Bibliothèque",   icon="📚"),
    st.Page("pages/9_BTC_DCA.py",      title="BTC DCA",        icon="🪙"),
])
pg.run()
