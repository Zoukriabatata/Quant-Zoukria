"""
Démarrage — Procédure de lancement session MNQ
"""
import streamlit as st
import os, json, time
from pathlib import Path
from datetime import datetime, timezone

st.set_page_config(page_title="Démarrage", page_icon="🚀", layout="wide")
from styles import inject as _inj; _inj()
from streamlit_autorefresh import st_autorefresh
from config import DXFEED_FILE
st_autorefresh(interval=10_000, key="dem_refresh")  # statut bridge toutes les 10s

st.markdown("""
<style>
.block-container { padding-top: 1.5rem; max-width: 860px; }
.step-wrap {
    display: flex; gap: 16px; align-items: flex-start;
    background: var(--bg-surface); border: 1px solid var(--border-default);
    border-radius: var(--r-lg); padding: 1.1rem 1.3rem; margin-bottom: 10px;
    transition: var(--t-fast);
}
.step-wrap:hover { border-color: var(--border-active); }
.step-num {
    min-width: 32px; height: 32px; border-radius: 50%;
    background: var(--grad-primary); color: #fff;
    font-weight: 700; font-size: .85rem;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.step-body { flex: 1; }
.step-title { font-weight: 600; color: var(--text-primary); font-size: .92rem; margin-bottom: .25rem; }
.step-desc  { font-size: .8rem; color: var(--text-muted); line-height: 1.6; }
.step-desc a { color: var(--accent-cyan); text-decoration: none; }
.step-desc a:hover { text-decoration: underline; }
.section-title {
    font-family: 'JetBrains Mono', monospace; font-size: .6rem; font-weight: 700;
    letter-spacing: .18em; color: var(--accent-cyan); text-transform: uppercase;
    margin: 1.8rem 0 .8rem; padding-bottom: .4rem;
    border-bottom: 1px solid var(--border-subtle);
}
.token-result {
    background: rgba(16,185,129,0.06); border: 1px solid rgba(16,185,129,0.25);
    border-radius: var(--r-lg); padding: 1rem 1.3rem; margin-top: .8rem;
}
.token-ok { color: var(--accent-green); font-weight: 700; font-size: .9rem; margin-bottom: .5rem; }
.token-exp { font-size: .75rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }
.token-error {
    background: rgba(239,68,68,0.06); border: 1px solid rgba(239,68,68,0.25);
    border-radius: var(--r-lg); padding: 1rem 1.3rem; margin-top: .8rem;
    color: var(--accent-red); font-size: .85rem;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:.5rem 0 1.5rem; border-bottom:1px solid var(--border-subtle); margin-bottom:1.5rem">
    <div style="font-family:'JetBrains Mono',monospace; font-size:.6rem; letter-spacing:.2em;
                color:var(--accent-cyan); text-transform:uppercase; margin-bottom:.4rem">
        PROCÉDURE · MNQ · SESSION NY
    </div>
    <div style="font-size:1.6rem; font-weight:700; color:var(--text-primary); letter-spacing:-.02em">
        🚀 Démarrage Session
    </div>
    <div style="font-size:.82rem; color:var(--text-muted); margin-top:.3rem">
        Tout ce qu il faut lancer avant 15h30 — dans l ordre
    </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# STATUS BAR — Bridge + Token
# ════════════════════════════════════════════════════════════════════
def _bridge_status():
    """Retourne (actif: bool, age_s: float, price: float)"""
    try:
        p = Path(DXFEED_FILE)
        if not p.exists():
            return False, None, None
        age_s = time.time() - p.stat().st_mtime
        data  = json.loads(p.read_text(encoding="utf-8"))
        bars  = data.get("bars", [])
        price = bars[-1]["close"] if bars else None
        return age_s < 30, age_s, price
    except Exception:
        return False, None, None

def _token_expiry():
    """Lit exp du VOLUMETRIC_JTOKEN dans .env"""
    try:
        import base64
        env_path = Path(__file__).parent.parent / ".env"
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("VOLUMETRIC_JTOKEN="):
                jtoken = line.split("=", 1)[1].strip()
                parts  = jtoken.split(".")
                pad    = len(parts[1]) % 4
                b64    = parts[1] + "=" * (4 - pad if pad else 0)
                payload = json.loads(base64.b64decode(b64).decode())
                exp_dt  = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                now_utc = datetime.now(timezone.utc)
                diff    = exp_dt - now_utc
                return diff.total_seconds(), exp_dt.strftime("%d/%m %H:%M UTC")
    except Exception:
        pass
    return None, None

bridge_ok, bridge_age, bridge_price = _bridge_status()
token_secs, token_exp_str = _token_expiry()

# Bridge pill
if bridge_ok:
    br_cls  = "qm-badge--green"
    br_dot  = "qm-live-dot--green"
    br_txt  = f"Bridge ACTIF · MNQ {bridge_price:.2f}" if bridge_price else "Bridge ACTIF"
else:
    br_cls  = "qm-badge--red"
    br_dot  = "qm-live-dot--red"
    br_txt  = f"Bridge INACTIF" + (f" · dernier tick il y a {bridge_age:.0f}s" if bridge_age else "")

# Token pill
if token_secs is None:
    tk_cls = "qm-badge--amber"
    tk_txt = "Token illisible"
elif token_secs < 0:
    tk_cls = "qm-badge--red"
    tk_txt = "Token EXPIRE"
elif token_secs < 3600:
    tk_cls = "qm-badge--amber"
    tk_txt = f"Token expire dans {int(token_secs/60)} min"
else:
    tk_cls = "qm-badge--green"
    tk_txt = f"Token valide jusqu a {token_exp_str}"

st.markdown(f"""
<div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:1.5rem; align-items:center">
    <span class="qm-badge {br_cls}">
        <span class="qm-live-dot {br_dot}" style="width:6px;height:6px;margin:0 4px 0 0"></span>
        {br_txt}
    </span>
    <span class="qm-badge {tk_cls}">{tk_txt}</span>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# SECTION 1 — TOKEN VOLUMETRIC
# ════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">Étape 1 — Vérifier NinjaTrader + Rithmic</div>', unsafe_allow_html=True)

st.markdown("""
<div class="step-wrap">
    <div class="step-num">1</div>
    <div class="step-body">
        <div class="step-title">Ouvre NinjaTrader 8</div>
        <div class="step-desc">
            Lance NinjaTrader depuis le bureau.<br>
            Vérifie que la connexion <b>Rithmic (Apex)</b> est active (point vert en bas).
        </div>
    </div>
</div>
<div class="step-wrap">
    <div class="step-num">2</div>
    <div class="step-body">
        <div class="step-title">Ouvre le chart MNQ 1 Minute</div>
        <div class="step-desc">
            New → Chart → Instrument <code>MNQM26</code> → Type <code>Minute</code> → Value <code>1</code>
        </div>
    </div>
</div>
<div class="step-wrap">
    <div class="step-num">3</div>
    <div class="step-body">
        <div class="step-title">Vérifie que l indicateur RithmicBridge est actif</div>
        <div class="step-desc">
            Clic droit chart → Indicators → RithmicBridge doit être dans la liste à droite.<br>
            Le fichier <code>C:\\tmp\\mnq_live.json</code> se met à jour automatiquement.
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

url_input = st.text_input(
    "URL Volumetric",
    placeholder="https://webapp.volumetricatrading.com/?popupId=...&jtoken=eyJ...",
    label_visibility="collapsed",
    key="vol_url",
)

jtoken = None
if url_input and "jtoken=" in url_input:
    try:
        # Parse jtoken from URL
        idx_start = url_input.index("jtoken=") + 7
        idx_end   = url_input.find("&", idx_start)
        jtoken    = url_input[idx_start:] if idx_end < 0 else url_input[idx_start:idx_end]

        # Decode expiration
        import base64, json as _json
        parts   = jtoken.split(".")
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = _json.loads(base64.b64decode(payload_b64).decode())
        from datetime import datetime, timezone
        exp_ts  = payload.get("exp", 0)
        exp_dt  = datetime.fromtimestamp(exp_ts, tz=timezone.utc).strftime("%d/%m/%Y à %H:%M UTC")

        st.markdown(f"""
        <div class="token-result">
            <div class="token-ok">Token extrait</div>
            <div class="token-exp">Expire le : {exp_dt}</div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f'<div class="token-error">Impossible d extraire le jtoken — verifie l URL ({e})</div>', unsafe_allow_html=True)
        jtoken = None
elif url_input:
    st.markdown('<div class="token-error">URL invalide — pas de jtoken= trouvé</div>', unsafe_allow_html=True)

st.markdown("""
<div class="step-wrap" style="margin-top:10px">
    <div class="step-num">4</div>
    <div class="step-body">
        <div class="step-title">Lance cette commande dans PowerShell</div>
        <div class="step-desc">Depuis le dossier <code>QUANT MATHS</code></div>
    </div>
</div>
""", unsafe_allow_html=True)

if jtoken:
    cmd_token = f'powershell -File update_jtoken.ps1 "{url_input.strip()}"'
else:
    cmd_token = 'powershell -File update_jtoken.ps1 "<colle ton URL ici>"'

st.code(cmd_token, language="powershell")

# ════════════════════════════════════════════════════════════════════
# SECTION 2 — BRIDGE DXFEED
# ════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">Étape 2 — Lancer Streamlit</div>', unsafe_allow_html=True)

st.markdown("""
<div class="step-wrap">
    <div class="step-num">4</div>
    <div class="step-body">
        <div class="step-title">Lance Streamlit dans un terminal</div>
        <div class="step-desc">
            Depuis le dossier <code>QUANT MATHS</code> dans PowerShell.
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.code("streamlit run Accueil.py", language="powershell")

st.markdown("""
<div class="step-wrap">
    <div class="step-num">5</div>
    <div class="step-body">
        <div class="step-title">Laisse NinjaTrader et le chart ouverts</div>
        <div class="step-desc">
            Le chart MNQ doit rester ouvert toute la session.<br>
            Si tu fermes NinjaTrader, le Live Signal passe en fallback yfinance (~15 min de retard).
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# SECTION 3 — STREAMLIT
# ════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">Étape 3 — Lancer l application Streamlit</div>', unsafe_allow_html=True)

st.markdown("""
<div class="step-wrap">
    <div class="step-num">7</div>
    <div class="step-body">
        <div class="step-title">Ouvre un second terminal PowerShell</div>
        <div class="step-desc">Depuis le dossier <code>QUANT MATHS</code>.</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.code("streamlit run Accueil.py", language="powershell")

st.markdown("""
<div class="step-wrap">
    <div class="step-num">8</div>
    <div class="step-body">
        <div class="step-title">Ouvre le navigateur</div>
        <div class="step-desc">Streamlit s ouvre automatiquement sur <code>http://localhost:8501</code></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
# SECTION 4 — RECAP RAPIDE
# ════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">Récap — ordre des commandes</div>', unsafe_allow_html=True)

st.code("""# 1. Ouvre NinjaTrader → connexion Rithmic verte → chart MNQM26 1min → indicateur RithmicBridge actif

# 2. Terminal — Streamlit
streamlit run Accueil.py""", language="powershell")

# ════════════════════════════════════════════════════════════════════
# SECTION 5 — DEPANNAGE
# ════════════════════════════════════════════════════════════════════
with st.expander("Dépannage"):
    st.markdown("""
**Bridge affiche `Token expired` au démarrage**
→ Le token dans `.env` est expiré. Refais l etape 1-4.

**Bridge affiche `Ticks recus` mais Live Signal dit "Bridge inactif"**
→ Le fichier `C:/tmp/mnq_live.json` n est pas lu. Verifie que `C:/tmp/` existe.

**`node: command not found`**
→ Node.js n est pas installe ou pas dans le PATH. Installe depuis nodejs.org.

**`streamlit: command not found`**
→ Lance depuis l environnement Python avec le venv actif, ou utilise `python -m streamlit run Accueil.py`.

**Le token expire en cours de session**
→ Depuis 2025, les tokens Volumetric expirent toutes les 24h. Le bridge tente un renouvellement automatique mais necessite un nouveau jtoken.
    """)
