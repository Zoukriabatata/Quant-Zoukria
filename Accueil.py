import streamlit as st
from auth import is_authenticated, login_sidebar

st.set_page_config(
    page_title="Quant Maths",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Auth widget sidebar ───────────────────────────────────────────────
login_sidebar()

# ── Définition des pages ──────────────────────────────────────────────
pages_public = [
    st.Page("pages/7_Etude.py",   title="Étude",        icon="🎓", default=True),
    st.Page("pages/8_Library.py", title="Bibliothèque", icon="📚"),
]

pages_private = [
    st.Page("pages/_home.py",          title="Accueil",      icon="⚡"),
    st.Page("pages/3_Live_Signal.py",  title="Live Signal",  icon="⚡"),
    st.Page("pages/5_Backtest.py",     title="Backtest",     icon="📊"),
    st.Page("pages/4_Journal.py",      title="Journal",      icon="📋"),
    st.Page("pages/2_Session_Prep.py", title="Session Prep", icon="🎯"),
    st.Page("pages/6_Multi_Model.py",  title="Multi Model",  icon="🤖"),
    st.Page("pages/9_BTC_DCA.py",      title="BTC DCA",      icon="₿"),
    st.Page("pages/1_Demarrage.py",    title="Démarrage",    icon="🚀"),
    st.Page("pages/Apex_Rules.py",     title="Apex Rules",   icon="○"),
]

# ── Navigation conditionnelle ─────────────────────────────────────────
if is_authenticated():
    pg = st.navigation({
        "Public":  pages_public,
        "Privé":   pages_private,
    })
else:
    pg = st.navigation(pages_public)

pg.run()
