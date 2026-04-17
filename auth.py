import streamlit as st

_KEY = "_qm_auth"

def is_authenticated() -> bool:
    return st.session_state.get(_KEY, False)

def login_sidebar():
    """Widget login dans la sidebar. Retourne True si authentifié."""
    if is_authenticated():
        st.sidebar.markdown(
            '<div style="font-family:\'JetBrains Mono\',monospace;font-size:.65rem;'
            'color:#10b981;padding:.4rem 0">● SESSION PRIVÉE</div>',
            unsafe_allow_html=True
        )
        if st.sidebar.button("Déconnexion", use_container_width=True, key="_qm_logout"):
            st.session_state[_KEY] = False
            st.rerun()
        return True

    with st.sidebar.expander("🔒 Accès privé"):
        pwd = st.text_input(
            "Mot de passe", type="password",
            placeholder="••••••••", key="_qm_pwd",
            label_visibility="collapsed"
        )
        if st.button("Connexion", use_container_width=True, key="_qm_login"):
            try:
                correct = st.secrets["APP_PASSWORD"]
            except Exception:
                correct = ""
            if pwd and pwd == correct:
                st.session_state[_KEY] = True
                st.rerun()
            elif pwd:
                st.error("Mot de passe incorrect")
    return False
