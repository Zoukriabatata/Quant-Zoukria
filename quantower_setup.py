import streamlit as st
from styles import inject as _inj; _inj()

DARK = dict(
    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#050505",
    font=dict(color="#94a3b8", size=11, family="'JetBrains Mono',monospace"),
    margin=dict(t=40, b=30, l=50, r=20),
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.qt-step {
    background:#060606;border:1px solid #111;border-radius:12px;
    padding:1.2rem 1.4rem;margin-bottom:1rem;
    font-family:'JetBrains Mono',monospace;
}
.qt-step-num {
    font-size:.6rem;color:#333;letter-spacing:.2em;
    text-transform:uppercase;margin-bottom:.3rem;
}
.qt-step-title {
    font-size:1rem;font-weight:700;color:#f1f5f9;margin-bottom:.5rem;
}
.qt-step-body {
    font-size:.82rem;color:#6b7280;line-height:1.7;
}
.qt-tip {
    background:rgba(209,213,219,0.04);border-left:3px solid #4b5563;
    border-radius:0 8px 8px 0;padding:.6rem 1rem;
    font-family:'JetBrains Mono',monospace;font-size:.78rem;color:#9ca3af;
    margin:.6rem 0;
}
.qt-warn {
    background:rgba(107,114,128,0.06);border-left:3px solid #9ca3af;
    border-radius:0 8px 8px 0;padding:.6rem 1rem;
    font-family:'JetBrains Mono',monospace;font-size:.78rem;color:#d1d5db;
    margin:.6rem 0;
}
.qt-code {
    background:#0a0a0a;border:1px solid #1a1a1a;border-radius:6px;
    padding:.5rem .8rem;font-family:'JetBrains Mono',monospace;
    font-size:.78rem;color:#d1d5db;margin:.4rem 0;
}
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style='padding:1.2rem 0 .8rem;border-bottom:1px solid #111;margin-bottom:1.4rem'>
    <div style='font-size:.6rem;color:#333;letter-spacing:.25em;
        font-family:JetBrains Mono,monospace;text-transform:uppercase;'>
        QUANTMASTER · GUIDE
    </div>
    <h1 style='font-size:1.8rem;font-weight:700;color:#f1f5f9;margin:.3rem 0 .2rem;'>
        Setup Quantower + Rithmic + Apex
    </h1>
    <p style='color:#4b5563;font-size:.85rem;font-family:JetBrains Mono,monospace;'>
        Guide complet pour débutants — bridge semi-auto + stratégie full auto HURST_MR
    </p>
</div>
""", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "⚙️ Installation Quantower",
    "🔌 Connexion Rithmic + Apex",
    "📡 Bridge Semi-Auto",
    "🤖 Full Auto HURST_MR",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — INSTALLATION QUANTOWER
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    steps = [
        ("ÉTAPE 1", "Télécharger Quantower",
         """Va sur <b style='color:#d1d5db'>quantower.com</b> → Download → installe la version stable.<br>
         Quantower est gratuit pour l'utilisation de base avec un broker connecté."""),

        ("ÉTAPE 2", "Lancer Quantower la première fois",
         """Double-clique sur <b style='color:#d1d5db'>Quantower.exe</b><br>
         Une fenêtre principale s'ouvre avec le <b style='color:#d1d5db'>Control Center</b>.<br>
         C'est depuis là que tu gères tout : connexions, charts, stratégies."""),

        ("ÉTAPE 3", "Installer les plugins nécessaires",
         """Dans le Control Center → <b style='color:#d1d5db'>Settings → Plugins</b><br>
         Installe : <b style='color:#d1d5db'>Algo (Quantower.Algo)</b> — indispensable pour charger les .cs<br>
         Installe : <b style='color:#d1d5db'>Chart</b> si pas déjà présent"""),

        ("ÉTAPE 4", "Ajouter les scripts C# (.cs)",
         """Dans <b style='color:#d1d5db'>Settings → Scripts</b> → Add folder<br>
         Navigue vers le dossier <b style='color:#d1d5db'>quantower/</b> du projet :<br>
         Sélectionne le dossier contenant <code>QuantowerBridge.cs</code> et <code>HurstMR_Apex_Quantower.cs</code><br>
         Quantower compile automatiquement les fichiers C#."""),

        ("ÉTAPE 5", "Vérifier la compilation",
         """Settings → Scripts → tu dois voir :<br>
         ✓ <b style='color:#d1d5db'>QuantowerBridge</b> — Status : Compiled<br>
         ✓ <b style='color:#d1d5db'>HurstMR_Apex_Quantower</b> — Status : Compiled<br>
         Si erreur → vérifie que le plugin Algo est bien installé (étape 3)"""),
    ]

    for num, title, body in steps:
        st.markdown(f"""
        <div class="qt-step">
            <div class="qt-step-num">{num}</div>
            <div class="qt-step-title">{title}</div>
            <div class="qt-step-body">{body}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="qt-tip">
    💡 Quantower ne nécessite pas de licence payante pour utiliser les algos —
    c'est inclus dans la connexion broker. Si Rithmic est connecté (étape suivante),
    tout fonctionne gratuitement.
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — CONNEXION RITHMIC + APEX
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("""
    <div class="qt-warn">
    ⚠️ Tu dois avoir reçu tes credentials Rithmic d'Apex Trader Funding par email
    (username + password + server). Vérifie ton email Apex avant de continuer.
    </div>
    """, unsafe_allow_html=True)

    steps2 = [
        ("ÉTAPE 1", "Ouvrir la connexion broker dans Quantower",
         """Control Center → <b style='color:#d1d5db'>Connections</b> (icône plug en haut)<br>
         Clique sur <b style='color:#d1d5db'>Add connection</b>"""),

        ("ÉTAPE 2", "Sélectionner Rithmic",
         """Dans la liste des brokers → cherche <b style='color:#d1d5db'>Rithmic</b><br>
         Clique dessus → <b style='color:#d1d5db'>Create</b>"""),

        ("ÉTAPE 3", "Entrer tes credentials Apex",
         """<b style='color:#d1d5db'>Username</b> : ton identifiant Apex (reçu par email)<br>
         <b style='color:#d1d5db'>Password</b> : ton mot de passe Rithmic<br>
         <b style='color:#d1d5db'>Server</b> : sélectionne <code>Apex Trader Funding</code> dans la liste<br>
         <b style='color:#d1d5db'>Market Data</b> : Rithmic Paper Trading (eval) ou Rithmic Live (PA)"""),

        ("ÉTAPE 4", "Connecter",
         """Clique <b style='color:#d1d5db'>Connect</b><br>
         Le statut passe à <b style='color:#d1d5db'>Connected</b> (point vert)<br>
         Tu verras ton compte Apex apparaître avec le solde et le DD disponible"""),

        ("ÉTAPE 5", "Ouvrir un chart MNQ",
         """Control Center → <b style='color:#d1d5db'>New Chart</b><br>
         Symbole : tape <code>MNQ</code> → sélectionne <b style='color:#d1d5db'>MNQ (Micro Nasdaq Futures)</b><br>
         Timeframe : <b style='color:#d1d5db'>M1</b> (1 minute)<br>
         Connexion : sélectionne ton compte Rithmic Apex connecté"""),
    ]

    for num, title, body in steps2:
        st.markdown(f"""
        <div class="qt-step">
            <div class="qt-step-num">{num}</div>
            <div class="qt-step-title">{title}</div>
            <div class="qt-step-body">{body}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="qt-tip">
    💡 Le compte Apex sur Rithmic est en <b>Paper Trading</b> pendant l'évaluation —
    c'est normal, les trades sont simulés sur données réelles. En PA (compte financé),
    bascule sur <b>Rithmic Live</b>.
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — BRIDGE SEMI-AUTO
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("""
    <div style='color:#444;font-size:.72rem;font-family:JetBrains Mono,monospace;
    letter-spacing:.1em;text-transform:uppercase;margin-bottom:.8rem;'>
    MODE SEMI-AUTO — Python génère le signal → tu valides l'ordre manuellement dans Quantower
    </div>
    """, unsafe_allow_html=True)

    steps3 = [
        ("ÉTAPE 1", "Charger l'indicateur QuantowerBridge",
         """Sur ton chart MNQ M1 → clique droit → <b style='color:#d1d5db'>Add Indicator</b><br>
         Cherche <b style='color:#d1d5db'>QuantowerBridge</b> → Add<br>
         L'indicateur s'ajoute silencieusement (pas de ligne visible, c'est normal)"""),

        ("ÉTAPE 2", "Vérifier que le fichier JSON est créé",
         """Ouvre l'explorateur Windows → navigue vers <code>C:\\tmp\\</code><br>
         Tu dois voir le fichier <code>mnq_live.json</code> se mettre à jour toutes les secondes<br>
         Si absent → vérifie que Quantower a les droits d'écriture sur <code>C:\\tmp</code>"""),

        ("ÉTAPE 3", "Lancer l'app Python",
         """Dans le terminal depuis le dossier du projet :<br>"""),
    ]

    for num, title, body in steps3:
        st.markdown(f"""
        <div class="qt-step">
            <div class="qt-step-num">{num}</div>
            <div class="qt-step-title">{title}</div>
            <div class="qt-step-body">{body}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="qt-code">streamlit run Accueil.py</div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="qt-step">
        <div class="qt-step-num">ÉTAPE 4</div>
        <div class="qt-step-title">Utiliser le Live Signal</div>
        <div class="qt-step-body">
        Dans l'app → <b style='color:#d1d5db'>📡 MNQ Live</b><br>
        Tu vois en temps réel : signal LONG/SHORT/FLAT, Z-score, Hurst, prix<br>
        Quand le signal s'allume → tu passes l'ordre <b>manuellement</b> dans Quantower<br><br>
        <b style='color:#9ca3af;'>C'est le mode semi-auto : le cerveau est Python, la main est Quantower.</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="qt-tip">
    💡 Avantage semi-auto : tu gardes le contrôle total sur chaque trade.
    Idéal pour apprendre à lire le signal avant de passer en full auto.
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — FULL AUTO HURST_MR
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("""
    <div class="qt-warn">
    ⚠️ Le full auto exécute les ordres sans intervention humaine.
    Assure-toi de bien comprendre les paramètres avant d'activer.
    Commence en paper trading / eval Apex avant de passer en live.
    </div>
    """, unsafe_allow_html=True)

    steps4 = [
        ("ÉTAPE 1", "Ouvrir le Strategy Runner",
         """Control Center → <b style='color:#d1d5db'>Strategies</b> (ou Strategy Runner)<br>
         Clique <b style='color:#d1d5db'>Add Strategy</b>"""),

        ("ÉTAPE 2", "Charger HurstMR_Apex_Quantower",
         """Dans la liste → cherche <b style='color:#d1d5db'>HurstMR_Apex_Quantower</b><br>
         Sélectionne ton compte Rithmic Apex<br>
         Sélectionne le symbole : <b style='color:#d1d5db'>MNQ</b><br>
         Timeframe : <b style='color:#d1d5db'>M1</b>"""),

        ("ÉTAPE 3", "Configurer les paramètres",
         """Les valeurs par défaut sont celles du backtest validé — <b style='color:#d1d5db'>ne change rien</b> sauf :<br>
         • <b>Mode PA</b> : OFF en eval (6 MNQ max), ON en PA (4 MNQ max)<br>
         • <b>Apex DD Limit</b> : $2,000 pour le $50k EOD<br>
         • <b>Daily Loss Limit</b> : $1,000 (règle Apex)"""),

        ("ÉTAPE 4", "Démarrer la stratégie",
         """Clique <b style='color:#d1d5db'>Run</b><br>
         La stratégie démarre et attend l'ouverture de session (15h30 Paris)<br>
         Elle s'arrête et se met FLAT automatiquement à 21h59 Paris<br>
         Tu peux monitorer les trades dans l'onglet <b style='color:#d1d5db'>Trades</b> du Strategy Runner"""),

        ("ÉTAPE 5", "Monitorer depuis l'app Python",
         """La page <b style='color:#d1d5db'>📡 MNQ Live</b> affiche le signal en temps réel<br>
         Tu peux voir si la stratégie est en position, le Z-score actuel, le Hurst<br>
         Les alertes NTFY/Discord sont optionnelles pour le MNQ (le full auto gère tout)"""),
    ]

    for num, title, body in steps4:
        st.markdown(f"""
        <div class="qt-step">
            <div class="qt-step-num">{num}</div>
            <div class="qt-step-title">{title}</div>
            <div class="qt-step-body">{body}</div>
        </div>
        """, unsafe_allow_html=True)

    # Paramètres de référence
    st.divider()
    st.markdown(
        '<div style="color:#444;font-size:.65rem;font-family:JetBrains Mono,monospace;'
        'letter-spacing:.12em;text-transform:uppercase;margin-bottom:.6rem;">'
        'Paramètres validés — backtest 5 ans</div>',
        unsafe_allow_html=True
    )

    params = [
        ("Hurst Seuil",        "0.53",    "Régime mean-reversion confirmé si H < 0.53"),
        ("Hurst Window",       "60 barres", "Fenêtre rolling R/S Analysis"),
        ("Lookback Bandes",    "30 barres", "Fenêtre rolling mean/std pour Z-score"),
        ("Band K",             "3.0 σ",    "Seuil d'entrée — 3 écarts-types"),
        ("SL Mult",            "0.75",     "SL = max(3.0, 0.75 × std), cap 20 pts"),
        ("Kelly Risk %",       "10%",      "% du DD restant risqué par trade"),
        ("Max Contrats Eval",  "6 MNQ",    "Cap Apex en phase évaluation"),
        ("Max Contrats PA",    "4 MNQ",    "Cap Apex en compte financé"),
        ("Max Trades/Jour",    "5",        "Filtre anti-surtrading"),
        ("Daily Loss Limit",   "$1,000",   "Règle Apex — arrêt immédiat si atteint"),
        ("Apex DD Limit",      "$2,000",   "Trailing DD EOD Apex $50k"),
        ("DD Safety Buffer",   "$150",     "Stop si DD utilisé > $1,850"),
    ]

    for param, val, desc in params:
        st.markdown(
            f'<div style="background:#060606;border:1px solid #0d0d0d;border-radius:7px;'
            f'padding:.45rem 1rem;margin-bottom:.25rem;font-family:JetBrains Mono,monospace;'
            f'font-size:.76rem;display:flex;gap:2rem;">'
            f'<span style="color:#94a3b8;min-width:14rem;">{param}</span>'
            f'<span style="color:#f1f5f9;font-weight:700;min-width:7rem;">{val}</span>'
            f'<span style="color:#333;">{desc}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("""
    <div class="qt-tip" style="margin-top:1rem;">
    💡 Performance backtest validée (5 ans walk-forward) :<br>
    PF 1.88 · Sharpe 3.13 · MaxDD 3.81% · WR 30% · 1530 trades<br>
    Ces chiffres sont sur données historiques — le live peut différer.
    </div>
    """, unsafe_allow_html=True)
