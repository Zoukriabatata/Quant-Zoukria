import streamlit as st
from auth import is_authenticated, login_sidebar

st.set_page_config(
    page_title="Quant Maths",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

login_sidebar()

pages_public = [
    st.Page("pages/7_Etude.py",   title="Étude",        icon="🎓", default=True),
    st.Page("pages/8_Library.py", title="Bibliothèque", icon="📚"),
]

pages_home = [
    st.Page("pages/_home.py", title="Accueil", icon="⚡"),
]

pages_live = [
    st.Page("pages/3_Live_Signal.py",   title="MNQ Live",   icon="📡"),
    st.Page("pages/Crypto_Live_SOL.py", title="SOL Live",   icon="🟢"),
]

pages_analyse = [
    st.Page("pages/5_Backtest.py",    title="Backtest",     icon="📊"),
    st.Page("pages/6_Multi_Model.py", title="Multi Model",  icon="🤖"),
    st.Page("pages/Crypto_Swing.py",  title="Crypto Swing", icon="🔮"),
]

pages_gestion = [
    st.Page("pages/4_Journal.py",      title="Journal",      icon="📋"),
    st.Page("pages/2_Session_Prep.py", title="Session Prep", icon="🎯"),
    st.Page("pages/9_BTC_DCA.py",      title="BTC DCA",      icon="🟡"),
]

pages_setup = [
    st.Page("pages/1_Demarrage.py", title="Démarrage",  icon="🚀"),
    st.Page("pages/Apex_Rules.py",  title="Apex Rules", icon="📋"),
]

if is_authenticated():
    pg = st.navigation({
        "": pages_home,
        "Live": pages_live,
        "Analyse": pages_analyse,
        "Gestion": pages_gestion,
        "Setup": pages_setup,
        "Public": pages_public,
    })
else:
    pg = st.navigation(pages_public)

pg.run()
