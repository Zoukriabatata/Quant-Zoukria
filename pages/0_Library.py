"""
Bibliothèque — Quant Guild Library (Roman Paolucci)
Catalogue de tous les cours avec catégories, liens YouTube et GitHub.
"""
import streamlit as st

st.set_page_config(page_title="Bibliothèque Quant", page_icon="QM", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
[data-testid="stAppViewContainer"] { background: #060606; }
[data-testid="stSidebar"] { background: #0a0a0a; border-right: 1px solid #1a1a1a; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { display: none; }
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #3CC4B7; border-radius: 2px; }
[data-testid="stSidebarNavLink"] {
    display:block; padding:0.6rem 1.2rem; margin:2px 8px; border-radius:6px;
    font-family:'JetBrains Mono',monospace; font-size:0.75rem; letter-spacing:0.08em;
    color:#555 !important; text-decoration:none !important;
    transition:background 0.15s,color 0.15s; border:1px solid transparent;
}
[data-testid="stSidebarNavLink"]:hover { background:#111 !important; color:#ccc !important; border-color:#1a1a1a; }
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background:rgba(60,196,183,0.08) !important; color:#3CC4B7 !important; border-color:rgba(60,196,183,0.2);
}
.lec-card {
    background: #0a0a0a; border: 1px solid #1a1a1a; border-radius: 8px;
    padding: 0.8rem 1rem; margin: 4px 0; display: flex; align-items: center;
    gap: 1rem; transition: border-color 0.15s;
}
.lec-card:hover { border-color: #333; }
.lec-card.studied { border-left: 3px solid #3CC4B7; }
.lec-num {
    font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
    color: #444; min-width: 36px; text-align: right; flex-shrink: 0;
}
.lec-title { color: #ccc; font-size: 0.85rem; flex: 1; }
.lec-title.studied { color: #fff; font-weight: 600; }
.lec-tag {
    font-family: 'JetBrains Mono', monospace; font-size: 0.6rem;
    padding: 2px 7px; border-radius: 4px; white-space: nowrap;
}
.tag-ml    { background: rgba(255,0,229,0.12); color: #ff00e5; }
.tag-stats { background: rgba(0,229,255,0.10); color: #00e5ff; }
.tag-risk  { background: rgba(255,214,0,0.10); color: #ffd600; }
.tag-vol   { background: rgba(255,145,0,0.10); color: #ff9100; }
.tag-trade { background: rgba(60,196,183,0.10); color: #3CC4B7; }
.tag-mind  { background: rgba(255,51,102,0.10); color: #ff3366; }
.tag-opt   { background: rgba(0,255,136,0.10); color: #00ff88; }
.cat-header {
    font-family: 'JetBrains Mono', monospace; font-size: 0.65rem;
    font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase;
    margin: 1.5rem 0 0.5rem; padding: 0.3rem 0;
    border-bottom: 1px solid #1a1a1a;
}
</style>
""", unsafe_allow_html=True)

# ── Lectures — (num, titre, youtube_id_or_None, github_slug, tags, covered_module)
# tags: trade=trading systems, stats=proba/stats, ml=machine learning,
#       risk=risk/performance, vol=volatilité, mind=mindset, opt=options
# covered_module = None si pas encore dans l'étude

GH_BASE = "https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2025%20Video%20Lectures"
GH_BASE_26 = "https://github.com/romanmichaelpaolucci/Quant-Guild-Library/tree/main/2026%20Video%20Lectures"

LECTURES = [
    # ── 2025 ──────────────────────────────────────────────────────
    (1,  "Inverse Transform Method for Generating Random Variables", None, "1.%20Inverse%20Transform%20Method%20for%20Generating%20Random%20Variables", ["stats"], None),
    (2,  "Control Variates for Variance Reduction",                  None, "2.%20Control%20Variates%20for%20Variance%20Reduction", ["stats"], None),
    (3,  "How to Make & Lose Money Trading",                         None, "3.%20How%20to%20Make%20%26%20Lose%20Money%20Trading", ["mind"], None),
    (4,  "Analyzing Trading Strategy Performance Over Time",         None, "4.%20Analyzing%20Trading%20Strategy%20Performance%20Over%20Time", ["risk"], None),
    (6,  "How to Trade with the Black-Scholes Model",                None, "6.%20How%20to%20Trade%20with%20the%20Black-Scholes%20Model", ["opt"], None),
    (7,  "Martingale Volatility Trading",                            None, "7.%20Martingale%20Volatility%20Trading", ["vol", "risk"], None),
    (9,  "Delta Hedging and Black-Scholes Prices",                   None, "9.%20Delta%20Hedging%20and%20Black-Scholes%20Prices", ["opt"], None),
    (11, "Managing Option Portfolios with Black-Scholes Greeks",      None, "11.%20Managing%20Option%20Portfolios%20with%20Black-Scholes%20Greeks", ["opt"], None),
    (13, "Can AI Learn Black-Scholes",                               None, "13.%20Can%20AI%20Learn%20Black-Scholes", ["ml", "opt"], None),
    (14, "Quant Investing for Beginners",                            None, "14.%20Quant%20Investing%20for%20Beginners", ["trade"], None),
    (15, "How to Build an AI Trading Bot in Python",                 None, "15.%20How%20to%20Build%20an%20AI%20Trading%20Bot%20in%20Python", ["ml", "trade"], None),
    (16, "Information and Stock Price Prediction",                   None, "16.%20Information%20and%20Stock%20Price%20Prediction", ["ml"], None),
    (17, "Analyzing Stock Returns with PCA",                         None, "17.%20Analyzing%20Stock%20Returns%20with%20PCA", ["ml", "stats"], None),
    (18, "Why Quant Traders Care About Pricing",                     None, "18.%20Why%20Quant%20Traders%20Care%20About%20Pricing", ["opt", "mind"], None),
    (19, "Monte Carlo Simulation and Black-Scholes for Pricing",     None, "19.%20Monte%20Carlo%20Simulation%20and%20Black-Scholes%20for%20Pricing%20Options", ["opt", "stats"], None),
    (20, "Why Portfolio Optimization Doesn't Work",                  None, "20.%20Why%20Portfolio%20Optimization%20Doesn%27t%20Work", ["risk", "mind"], None),
    (21, "Expected Stock Returns Don't Exist",                       None, "21.%20Expected%20Stock%20Returns%20Don%27t%20Exist", ["stats", "mind"], None),
    (22, "How to Trade",                                             None, "22.%20How%20to%20Trade", ["trade", "mind"], None),
    (23, "How to Trade Option Implied Volatility",                   None, "23.%20How%20to%20Trade%20Option%20Implied%20Volatility", ["vol", "opt"], None),
    (24, "Trading with Violated Model Assumptions",                  None, "24.%20Trading%20with%20Violated%20Model%20Assumptions", ["trade", "mind"], None),
    (25, "Simulating Fractional Brownian Motion — Davies-Harte",     None, "25.%20How%20to%20Simulate%20Fractional%20Brownian%20Motion%20via%20Davies-Harte", ["stats"], None),
    (26, "Is Quant Trading Gambling",                                None, "26.%20Is%20Quant%20Trading%20Gambling%20-%20Roulette%2C%20Poker%2C%20and%20Trading", ["mind", "risk"], None),
    (28, "Gambler's Ruin Problem in Quant Trading",                  None, "28.%20Gambler%27s%20Ruin%20Problem%20in%20Quant%20Trading", ["risk", "stats"], None),
    (29, "Ito's Lemma Clearly Explained",                            None, "29.%20Ito%27s%20Lemma%20Clearly%20and%20Visually%20Explained", ["stats"], None),
    (30, "Trading with the Black-Scholes Implied Volatility Surface", None, "30.%20Trading%20with%20the%20Black-Scholes%20Implied%20Volatility%20Surface", ["vol", "opt"], None),
    (31, "Ito Integration Clearly Explained",                        None, "31.%20Ito%20Integration%20Clearly%20and%20Visually%20Explained", ["stats"], None),
    (32, "How to Price Exotic Options",                              None, "32.%20How%20to%20Price%20Exotic%20Options", ["opt"], None),
    (33, "Why Monte Carlo Simulation Works",                         "-4sf43SLL3A", "33.%20Why%20Monte%20Carlo%20Simulation%20Works", ["stats"], "03b_monte_carlo.md"),
    (34, "How to Trade with an Edge",                                None, "34.%20How%20to%20Trade%20with%20an%20Edge", ["trade", "risk"], None),
    (35, "What Does AI Actually Learn",                              None, "35.%20What%20Does%20AI%20Actually%20Learn", ["ml"], None),
    (36, "How to Trade with the Kelly Criterion",                    None, "36.%20How%20to%20Trade%20with%20the%20Kelly%20Criterion", ["risk", "trade"], "08_kelly_criterion.md"),
    (37, "Stochastic Differential Equations for Quant Finance",      None, "37.%20Stochastic%20Differential%20Equations%20for%20Quant%20Finance", ["stats"], None),
    (38, "Finite Differences Option Pricing",                        None, "38.%20Finite%20Differences%20Option%20Pricing%20for%20Quant%20Finance", ["opt"], None),
    (39, "Heston Stochastic Volatility Model and FFT",               None, "39.%20Heston%20Stochastic%20Volatility%20Model%20and%20Fast%20Fourier%20Transforms", ["vol", "opt"], None),
    (40, "Quant Trader on Retail vs Institutional Trading",          "j1XAcdEHzbU", "40.%20Quant%20Trader%20on%20Retail%20vs%20Institutional%20Trading", ["mind"], "00b_retail_vs_institutional.md"),
    (43, "How to Trade Implied Volatility Crush",                    None, "43.%20How%20to%20Trade%20Implied%20Volatility%20Crush", ["vol", "opt"], None),
    (44, "Time Series Analysis for Quant Finance",                   "JwqjuUnR8OY", "44.%20Time%20Series%20Analysis%20for%20Quant%20Finance", ["stats", "trade"], "01_time_series.md"),
    (46, "Is Trading Luck or Skill",                                 None, "46.%20Is%20Trading%20Luck%20or%20Skill%20-%20Quant%20Debunks%20Trading%20Gurus%20with%20Math", ["mind", "risk"], None),
    (47, "Master Volatility with ARCH & GARCH Models",               "iImtlBRcczA", "47.%20Master%20Volatility%20with%20ARCH%20%26%20GARCH%20Models", ["vol", "trade"], "04_garch.md"),
    (48, "Why Trading Metrics are Misleading",                       "xziwmju7x2s", "48.%20Why%20Trading%20Metrics%20are%20Misleading", ["risk"], "04b_trading_metrics.md"),
    (49, "Markov Chains for Quant Finance",                          None, "49.%20Markov%20Chains%20for%20Quant%20Finance", ["ml", "stats"], None),
    (50, "Why Poker Pros Make the Best Traders",                     None, "50.%20Why%20Poker%20Pros%20Make%20the%20Best%20Traders", ["mind"], None),
    (51, "Hidden Markov Models for Quant Finance",                   "Bru4Mkr601Q", "51.%20Hidden%20Markov%20Models%20for%20Quant%20Finance", ["ml", "trade"], "05_hidden_markov_models.md"),
    (54, "Quant vs Discretionary Trading",                           None, "54.%20Quant%20vs%20Discretionary%20Trading", ["mind"], None),
    (56, "Quant Busts 3 Trading Myths with Math",                    None, "56.%20Quant%20Busts%203%20Trading%20Myths%20with%20Math", ["mind", "risk"], None),
    (57, "Banks are Just Casinos",                                   None, "57.%20Banks%20are%20Just%20Casinos%20%28Quant%20Explains%20Why%29", ["mind"], None),
    (58, "Why Quant Models Break",                                   None, "58.%20Why%20Quant%20Models%20Break", ["mind", "risk"], None),
    (59, "Brownian Motion for Quant Finance",                        None, "59.%20Brownian%20Motion%20for%20Quant%20Finance", ["stats"], None),
    (60, "Is Trading Gambling — Quant Proves It's Not",              None, "60.%20Is%20Trading%20Gambling%20-%20Quant%20Proves%20It%27s%20Not%20With%20Math", ["mind", "risk"], None),
    (61, "Central Limit Theorem for Quant Finance",                  "q2era-4pnic", "61.%20Central%20Limit%20Theorem%20for%20Quant%20Finance", ["stats"], "02_central_limit_theorem.md"),
    (63, "Neural Networks for Quant Finance",                        None, "63.%20Neural%20Networks%20for%20Quant%20Finance", ["ml"], None),
    (65, "Natural Language Processing for Quant Finance",            None, "65.%20Natural%20Language%20Processing%20for%20Quant%20Finance", ["ml"], None),
    (67, "How Physics Proved the Black-Scholes Model",               None, "67.%20How%20Physics%20Accidentally%20Proved%20the%20Black-Scholes%20Model", ["opt", "stats"], None),
    (69, "Quant Explains Algorithmic Market-Making",                 None, "69.%20Quant%20Explains%20Algorithmic%20Market-Making", ["trade"], None),
    (71, "Markov Property for Quant Finance",                        None, "71.%20Markov%20Property%20for%20Quant%20Finance", ["ml", "stats"], None),
    (72, "Markov Chain Regime Switching Bot Part 1",                 "mais1dsB_1g", "72.%20How%20to%20Build%20a%20Markov%20Chain%20Regime%20Switching%20Bot%20in%20Python%20%28IBKR%29%20Part%201", ["ml", "trade"], "05b_regime_switching.md"),
    (74, "Markov Chain Regime Switching Bot Part 2",                 "mais1dsB_1g", "74.%20How%20to%20Build%20a%20Markov%20Chain%20Regime%20Switching%20Bot%20in%20Python%20%28IBKR%29%20Part%202", ["ml", "trade"], "05b_regime_switching.md"),
    (75, "Profitable Backtesting with Poker",                        None, "75.%20Quant%20Explains%20Backtesting%20with%20Poker", ["trade", "risk"], None),
    (77, "Profitable vs Tradable — Why Most Strategies Fail Live",   None, "77.%20Profitable%20vs%20Tradable%20-%20Why%20Most%20Strategies%20Fail%20Live", ["trade", "risk"], "09b_profitable_vs_tradable.md"),

    # ── 2026 ──────────────────────────────────────────────────────
    (78, "Trader Skill or Market Luck — Quant Explains Alpha",       None, None, ["risk", "mind"], None),
    (80, "The 5 Papers That Built Modern Quant Finance",             None, None, ["stats", "mind"], None),
    (81, "Why Most Traders Lose — Ergodicity for Quant Trading",     "dryV1qJYUw8", None, ["risk", "stats"], "03_ergodicity.md"),
    (82, "Poisson Processes for Quant Finance",                      None, None, ["stats"], None),
    (83, "Quant Explains Risk-Neutral Option Pricing",               None, None, ["opt"], None),
    (85, "Quant Derives Volterra Process Discretization",            None, None, ["stats"], None),
    (87, "How a Quant Trades in 3 Minutes",                          None, None, ["trade", "mind"], None),
    (88, "How a Quant Manages a Portfolio",                          None, None, ["risk"], None),
    (89, "Black-Scholes Implied Volatility in 3 Minutes",            None, None, ["vol", "opt"], None),
    (91, "How Goldman Sachs Prices Variance Swaps",                  None, None, ["vol", "opt"], None),
    (92, "Kalman Filter for Quant Finance",                          "zVJY_oaVh-0", None, ["ml", "stats", "trade"], "06_kalman_filter.md"),
    (93, "Non-Stationarity and Why Market Timing Fails",             None, None, ["stats", "mind"], None),
    (94, "Hawkes Processes for Quant Finance",                       "BotPHbWFRUA", None, ["stats", "trade"], "05c_hawkes.md"),
    (95, "Trading Mean Reversion with Kalman Filters",               "BuPil7nXvMU", None, ["trade", "ml"], "06b_kalman_mean_reversion.md"),
    (96, "I Bet You've Never Found Alpha",                           None, None, ["risk", "mind"], None),
    (97, "3 Backtesting Pitfalls That Ruin Your Strategy",           None, None, ["trade", "risk"], "09_backtesting_pitfalls.md"),
    (98, "How to Get Historical Market Data with IBKR",              None, None, ["trade"], None),
    (100,"Black-Litterman vs Mean-Variance Portfolio Optimization",  None, None, ["risk"], None),
    (101,"Stop Using the Sharpe Ratio Until You Watch This",         None, None, ["risk"], None),
    (103,"Quant Finance in 3 Minutes",                               None, None, ["mind"], None),
]

# Modules couverts dans l'étude
ETUDE_MODULES = {lec[5] for lec in LECTURES if lec[5]}

TAG_META = {
    "trade": ("TRADING", "tag-trade"),
    "stats": ("STATS", "tag-stats"),
    "ml":    ("ML/IA", "tag-ml"),
    "risk":  ("RISK", "tag-risk"),
    "vol":   ("VOL", "tag-vol"),
    "mind":  ("MINDSET", "tag-mind"),
    "opt":   ("OPTIONS", "tag-opt"),
}

CATEGORIES = {
    "SIGNAL & MEAN REVERSION": ["trade", "ml"],       # primary tags
    "RISK & PERFORMANCE":       ["risk"],
    "PROBABILITÉ & STATS":      ["stats"],
    "VOLATILITÉ":               ["vol"],
    "MACHINE LEARNING":         ["ml"],
    "OPTIONS":                  ["opt"],
    "MINDSET & MARCHÉ":         ["mind"],
}

CAT_COLORS = {
    "SIGNAL & MEAN REVERSION": "#3CC4B7",
    "RISK & PERFORMANCE":      "#ffd600",
    "PROBABILITÉ & STATS":     "#00e5ff",
    "VOLATILITÉ":              "#ff9100",
    "MACHINE LEARNING":        "#ff00e5",
    "OPTIONS":                 "#00ff88",
    "MINDSET & MARCHÉ":        "#ff3366",
}

# ── Header ──────────────────────────────────────────────────────────
st.markdown("""
<div style="padding: 1.5rem 0 0.5rem; border-bottom: 1px solid #1a1a1a; margin-bottom: 1.5rem;">
    <div style="font-family:'JetBrains Mono',monospace; font-size:0.65rem;
                letter-spacing:0.2em; color:#3CC4B7; text-transform:uppercase;">
        QUANT GUILD LIBRARY — Roman Paolucci
    </div>
    <div style="font-size:1.8rem; font-weight:700; color:#fff; letter-spacing:-0.02em; margin-top:0.3rem;">
        Bibliothèque
    </div>
</div>
""", unsafe_allow_html=True)

# ── Filters ─────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
with col_f1:
    search = st.text_input("Rechercher", placeholder="kalman, kelly, GARCH...", label_visibility="collapsed")
with col_f2:
    tag_filter = st.selectbox(
        "Catégorie",
        options=["Tout", "TRADING", "RISK", "STATS", "ML/IA", "VOL", "OPTIONS", "MINDSET"],
        label_visibility="collapsed",
    )
with col_f3:
    only_studied = st.toggle("Déjà étudié", value=False)

tag_map = {"TRADING": "trade", "RISK": "risk", "STATS": "stats",
           "ML/IA": "ml", "VOL": "vol", "OPTIONS": "opt", "MINDSET": "mind"}

# ── Stats bar ───────────────────────────────────────────────────────
n_studied = sum(1 for lec in LECTURES if lec[5])
n_total   = len(LECTURES)

st.markdown(f"""
<div style="display:flex; gap:1rem; margin:0.5rem 0 1.5rem; align-items:center;">
    <div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:#888;">
        <span style="color:#3CC4B7; font-weight:700;">{n_studied}</span> / {n_total} cours couverts dans l'étude
    </div>
    <div style="flex:1; background:#1a1a1a; border-radius:4px; height:4px; overflow:hidden;">
        <div style="width:{n_studied/n_total*100:.0f}%; background:#3CC4B7; height:100%; border-radius:4px;"></div>
    </div>
    <div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:#444;">
        {n_studied/n_total*100:.0f}%
    </div>
</div>
""", unsafe_allow_html=True)

# ── Filter logic ────────────────────────────────────────────────────
def matches(lec):
    num, title, yt, gh, tags, module = lec
    if only_studied and not module:
        return False
    if tag_filter != "Tout":
        wanted = tag_map[tag_filter]
        if wanted not in tags:
            return False
    if search:
        q = search.lower()
        if q not in title.lower() and q not in str(num):
            return False
    return True

filtered = [lec for lec in LECTURES if matches(lec)]

# ── Render ──────────────────────────────────────────────────────────
def lec_html(lec):
    num, title, yt, gh, tags, module = lec
    is_studied = module is not None

    # Number
    num_html = f'<div class="lec-num">#{num}</div>'

    # Title
    title_cls = "lec-title studied" if is_studied else "lec-title"
    title_html = f'<div class="{title_cls}">{title}'
    if is_studied:
        title_html += ' <span style="color:#3CC4B7; font-size:0.7rem;">✓ Étude</span>'
    title_html += '</div>'

    # Tags
    tag_html = '<div style="display:flex; gap:4px;">'
    for t in tags:
        label, cls = TAG_META[t]
        tag_html += f'<span class="lec-tag {cls}">{label}</span>'
    tag_html += '</div>'

    # Links
    links_html = '<div style="display:flex; gap:8px; flex-shrink:0;">'
    if yt:
        links_html += (
            f'<a href="https://youtu.be/{yt}" target="_blank" '
            f'style="font-family:JetBrains Mono,monospace; font-size:0.65rem; '
            f'background:#ff0000; color:#fff; padding:3px 8px; border-radius:4px; '
            f'text-decoration:none;">▶ YT</a>'
        )
    # GitHub link only for 2025 lectures (gh != None)
    if gh:
        year_base = GH_BASE if num <= 77 else GH_BASE_26
        gh_url = f"{year_base}/{gh}"
        links_html += (
            f'<a href="{gh_url}" target="_blank" '
            f'style="font-family:JetBrains Mono,monospace; font-size:0.65rem; '
            f'background:#1a1a1a; color:#888; padding:3px 8px; border-radius:4px; '
            f'text-decoration:none; border:1px solid #333;">GH</a>'
        )
    links_html += '</div>'

    card_cls = "lec-card studied" if is_studied else "lec-card"
    return (
        f'<div class="{card_cls}">'
        f'{num_html}{title_html}{tag_html}{links_html}'
        f'</div>'
    )

if not filtered:
    st.markdown(
        '<div style="color:#444; font-family:JetBrains Mono,monospace; '
        'font-size:0.8rem; padding:2rem; text-align:center;">Aucun cours trouvé.</div>',
        unsafe_allow_html=True,
    )
else:
    html_out = "".join(lec_html(lec) for lec in filtered)
    st.markdown(html_out, unsafe_allow_html=True)

# ── Legend ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="font-family:'JetBrains Mono',monospace; font-size:0.65rem; color:#444;
            display:flex; gap:1.5rem; flex-wrap:wrap;">
    <span><span style="color:#3CC4B7;">✓ Étude</span> = module dans la page Étude</span>
    <span><span style="color:#ff0000;">▶ YT</span> = lien YouTube confirmé</span>
    <span><span style="color:#888;">GH</span> = code source GitHub</span>
    <span><a href="https://github.com/romanmichaelpaolucci/Quant-Guild-Library" target="_blank"
             style="color:#3CC4B7; text-decoration:none;">→ Dépôt complet</a></span>
</div>
""", unsafe_allow_html=True)
