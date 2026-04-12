"""
Interactive Plotly charts for each learning module.
Called by app_learning.py to inject real visualizations.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm, gaussian_kde

# ── Shared dark theme ──────────────────────────────────────────────
DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(6,6,6,0)",
    plot_bgcolor="rgba(8,8,8,1)",
    font=dict(color="#888", size=12, family="JetBrains Mono"),
    margin=dict(t=44, b=36, l=48, r=20),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor="rgba(255,255,255,0.05)",
        borderwidth=1,
        font=dict(color="#555", size=11),
    ),
)
# Axis style appliqué individuellement par chart (ne pas mettre dans DARK
# pour éviter les conflits quand une fonction passe xaxis/yaxis explicitement)
AXIS = dict(
    gridcolor="rgba(255,255,255,0.04)",
    linecolor="#1a1a1a",
    tickfont=dict(color="#444", size=11),
    title_font=dict(color="#555", size=11),
    zeroline=False,
)
TEAL    = "#3CC4B7"
CYAN    = "#00e5ff"
MAGENTA = "#ff00e5"
GREEN   = "#00ff88"
RED     = "#ff3366"
YELLOW  = "#ffd600"
ORANGE  = "#ff9100"
WHITE_50 = "rgba(255,255,255,0.4)"


# ===================================================================
# 01 — TIME SERIES
# ===================================================================

# ===================================================================
# 00b — RETAIL VS INSTITUTIONAL
# ===================================================================

def retail_market_making_sim():
    """Simulate market-maker collecting spread vs price risk."""
    np.random.seed(42)
    n = 200
    mid = 100 + np.cumsum(np.random.normal(0, 0.1, n))
    spread = 0.20
    bid, ask = mid - spread / 2, mid + spread / 2

    pos = 0
    pnl = np.zeros(n)
    for i in range(n):
        trade = np.random.choice(["buy", "sell", "none"], p=[0.35, 0.35, 0.30])
        gain = spread / 2 if trade != "none" else 0
        if trade == "buy":
            pos += 1
        elif trade == "sell":
            pos -= 1
        price_impact = -pos * (mid[i] - mid[i - 1]) if i > 0 else 0
        pnl[i] = gain + price_impact

    cum_pnl = np.cumsum(pnl)

    fig = make_subplots(rows=1, cols=2, subplot_titles=["Bid / Ask / Mid", "P&L du Market-Maker"])
    fig.add_trace(go.Scatter(y=ask, line=dict(color=RED, width=1), name="Ask"), row=1, col=1)
    fig.add_trace(go.Scatter(y=mid, line=dict(color=WHITE_50, width=1, dash="dot"), name="Mid"), row=1, col=1)
    fig.add_trace(go.Scatter(y=bid, line=dict(color=GREEN, width=1), name="Bid"), row=1, col=1)
    fig.add_trace(go.Bar(y=pnl, marker_color=[GREEN if p > 0 else RED for p in pnl], showlegend=False, opacity=0.4), row=1, col=2)
    fig.add_trace(go.Scatter(y=cum_pnl, line=dict(color=CYAN, width=3), name="Cum PnL"), row=1, col=2)
    fig.update_layout(height=380, title="Market-Making : collecter le spread (sell-side)", **DARK)
    return fig


def retail_adverse_selection():
    """Show informed vs uninformed trader concept."""
    np.random.seed(42)
    n = 300
    # Uninformed: random, net 0
    uninformed_pnl = np.cumsum(np.random.normal(0, 50, n))
    # Informed (with edge): positive drift
    informed_pnl = np.cumsum(np.random.normal(15, 50, n))
    # MM against informed: negative
    mm_vs_informed = np.cumsum(np.random.normal(-12, 40, n))

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=uninformed_pnl, line=dict(color=WHITE_50, width=2), name="Trader non-informe (bruit)"))
    fig.add_trace(go.Scatter(y=informed_pnl, line=dict(color=GREEN, width=3), name="Trader INFORME (toi avec pipeline)"))
    fig.add_trace(go.Scatter(y=mm_vs_informed, line=dict(color=RED, width=2, dash="dot"), name="MM face au trader informe"))
    fig.add_hline(y=0, line_dash="dash", line_color=WHITE_50, opacity=0.3)
    fig.update_layout(height=400, title="Adverse Selection : avec ton pipeline TU es le trader informe",
                      xaxis_title="Trades", yaxis_title="PnL cumule ($)", **DARK)
    return fig


# ===================================================================
# 01 — TIME SERIES
# ===================================================================

def ts_decomposition():
    """Show trend + seasonality + noise = observed price."""
    np.random.seed(42)
    t = np.arange(300)
    trend = 0.05 * t + 100
    season = 3 * np.sin(2 * np.pi * t / 30)
    noise = np.random.normal(0, 1.5, len(t))
    observed = trend + season + noise

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        subplot_titles=["📈 Trend", "🔄 Saisonnalite", "🎲 Bruit (Noise)", "👁️ Ce que tu vois (Observed)"],
        vertical_spacing=0.06,
    )
    fig.add_trace(go.Scatter(x=t, y=trend, line=dict(color=CYAN, width=2), name="Trend"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=season, line=dict(color=MAGENTA, width=2), name="Saison"), row=2, col=1)
    fig.add_trace(go.Scatter(x=t, y=noise, line=dict(color=WHITE_50, width=1), name="Bruit"), row=3, col=1)
    fig.add_trace(go.Scatter(x=t, y=observed, line=dict(color=GREEN, width=2), name="Observed"), row=4, col=1)
    fig.update_layout(height=650, showlegend=False, title="Decomposition d'une Time Series", **DARK)
    return fig


def ts_moving_averages():
    """Compare MA(5), MA(20), EMA(0.1) on noisy price."""
    np.random.seed(7)
    n = 200
    price = 100 + np.cumsum(np.random.normal(0.02, 1, n))

    def ma(arr, w):
        out = np.full(len(arr), np.nan)
        for i in range(w - 1, len(arr)):
            out[i] = arr[i - w + 1: i + 1].mean()
        return out

    def ema(arr, alpha):
        out = np.zeros(len(arr))
        out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
        return out

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=price, mode="lines", line=dict(color=WHITE_50, width=1), name="Prix brut"))
    fig.add_trace(go.Scatter(y=ma(price, 5), mode="lines", line=dict(color=CYAN, width=2), name="MA(5) — reactif"))
    fig.add_trace(go.Scatter(y=ma(price, 20), mode="lines", line=dict(color=MAGENTA, width=2), name="MA(20) — lisse"))
    fig.add_trace(go.Scatter(y=ema(price, 0.1), mode="lines", line=dict(color=GREEN, width=2, dash="dot"), name="EMA(α=0.1)"))
    fig.update_layout(
        height=400, title="Filtrage : MA vs EMA",
        xaxis_title="Temps", yaxis_title="Prix", **DARK,
    )
    return fig


def ts_forecast_cone():
    """Random walk forecast with expanding uncertainty cone."""
    np.random.seed(42)
    n_hist = 100
    n_fwd = 50
    price = 100 + np.cumsum(np.random.normal(0, 1, n_hist))
    last = price[-1]
    sigma = np.std(np.diff(price))

    t_fwd = np.arange(n_hist, n_hist + n_fwd)
    forecast = np.full(n_fwd, last)
    upper_1 = last + sigma * np.sqrt(np.arange(1, n_fwd + 1))
    lower_1 = last - sigma * np.sqrt(np.arange(1, n_fwd + 1))
    upper_2 = last + 2 * sigma * np.sqrt(np.arange(1, n_fwd + 1))
    lower_2 = last - 2 * sigma * np.sqrt(np.arange(1, n_fwd + 1))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(n_hist)), y=price, line=dict(color=CYAN, width=2), name="Historique"))
    # 95% band
    fig.add_trace(go.Scatter(x=list(t_fwd) + list(t_fwd[::-1]), y=list(upper_2) + list(lower_2[::-1]),
                             fill="toself", fillcolor="rgba(255,0,229,0.1)", line=dict(width=0), name="95% IC"))
    # 68% band
    fig.add_trace(go.Scatter(x=list(t_fwd) + list(t_fwd[::-1]), y=list(upper_1) + list(lower_1[::-1]),
                             fill="toself", fillcolor="rgba(0,229,255,0.15)", line=dict(width=0), name="68% IC"))
    fig.add_trace(go.Scatter(x=list(t_fwd), y=forecast, line=dict(color=YELLOW, width=2, dash="dash"), name="Forecast"))
    fig.add_vline(x=n_hist, line_dash="dot", line_color="white", opacity=0.5)
    fig.update_layout(height=400, title="Prevision : le cone d'incertitude GRANDIT", xaxis_title="Temps", yaxis_title="Prix", **DARK)
    return fig


# ===================================================================
# 02 — CENTRAL LIMIT THEOREM
# ===================================================================

def clt_dice_demo():
    """Show how averaging N dice rolls converges to a bell curve."""
    np.random.seed(42)
    n_sims = 10000
    fig = make_subplots(rows=2, cols=2, subplot_titles=[
        "1 de (uniforme)", "2 des (triangle)",
        "5 des (presque cloche)", "30 des (gaussienne !)"
    ], vertical_spacing=0.15)

    for idx, n_dice in enumerate([1, 2, 5, 30]):
        row, col = divmod(idx, 2)
        means = np.mean(np.random.randint(1, 7, (n_sims, n_dice)), axis=1)
        fig.add_trace(go.Histogram(
            x=means, nbinsx=40, histnorm="probability density",
            marker_color=CYAN, opacity=0.7, name=f"{n_dice} de(s)",
            showlegend=False,
        ), row=row + 1, col=col + 1)
        # Overlay normal fit
        x_fit = np.linspace(means.min(), means.max(), 200)
        y_fit = norm.pdf(x_fit, means.mean(), means.std())
        fig.add_trace(go.Scatter(
            x=x_fit, y=y_fit, mode="lines", line=dict(color=MAGENTA, width=2),
            showlegend=False,
        ), row=row + 1, col=col + 1)

    fig.update_layout(height=550, title="CLT : la moyenne converge vers une gaussienne", **DARK)
    return fig


def clt_trading_confidence():
    """Show confidence interval shrinking with more trades."""
    np.random.seed(42)
    mu_true = 8  # edge = 8$ per trade
    sigma = 60
    trade_counts = np.arange(10, 501, 5)

    ci_upper = mu_true + 2 * sigma / np.sqrt(trade_counts)
    ci_lower = mu_true - 2 * sigma / np.sqrt(trade_counts)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(trade_counts) + list(trade_counts[::-1]),
        y=list(ci_upper) + list(ci_lower[::-1]),
        fill="toself", fillcolor="rgba(0,229,255,0.2)", line=dict(width=0),
        name="Intervalle de confiance 95%"
    ))
    fig.add_trace(go.Scatter(x=trade_counts, y=np.full_like(trade_counts, mu_true, dtype=float),
                             line=dict(color=GREEN, width=2), name="Ton edge reel (+8$)"))
    fig.add_hline(y=0, line_dash="dash", line_color=RED, opacity=0.7, annotation_text="Zero (pas d'edge)")
    # Mark where CI excludes 0
    n_signif = int(np.ceil((2 * sigma / mu_true) ** 2))
    fig.add_vline(x=n_signif, line_dash="dot", line_color=YELLOW,
                  annotation_text=f"Edge confirme a n={n_signif}", annotation_position="top right")
    fig.update_layout(
        height=400, title="Plus de trades = plus de certitude",
        xaxis_title="Nombre de trades", yaxis_title="Estimation de l'edge ($)", **DARK,
    )
    return fig


# ===================================================================
# 02b — ASYMPTOTICS
# ===================================================================

def asymp_lln_convergence():
    """Show mean converging to true value as n grows."""
    np.random.seed(42)
    mu_true = 8.0
    sigma = 80.0
    max_n = 2000
    trades = np.random.normal(mu_true, sigma, max_n)
    running_mean = np.cumsum(trades) / np.arange(1, max_n + 1)
    ns = np.arange(1, max_n + 1)
    upper = mu_true + 2 * sigma / np.sqrt(ns)
    lower = mu_true - 2 * sigma / np.sqrt(ns)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(ns) + list(ns[::-1]), y=list(upper) + list(lower[::-1]),
        fill="toself", fillcolor="rgba(0,229,255,0.1)", line=dict(width=0),
        name="IC 95%",
    ))
    fig.add_trace(go.Scatter(x=ns, y=running_mean, mode="lines",
                             line=dict(color=CYAN, width=2), name="Moyenne empirique"))
    fig.add_hline(y=mu_true, line_dash="dash", line_color=GREEN, annotation_text=f"mu = {mu_true}$")
    fig.update_layout(
        height=420, title="Loi des Grands Nombres : la moyenne converge",
        xaxis_title="Nombre de trades (n)", yaxis_title="Moyenne ($)", **DARK,
    )
    return fig


def asymp_convergence_speed():
    """Show error ~ 1/sqrt(n) curve."""
    ns = np.arange(10, 5001)
    sigma = 80.0
    se = sigma / np.sqrt(ns)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ns, y=se, mode="lines", line=dict(color=MAGENTA, width=3),
                             name="Erreur standard = sigma/sqrt(n)"))
    # Annotations for key points
    for n_mark, label in [(25, "n=25"), (100, "n=100"), (400, "n=400"), (2500, "n=2500")]:
        se_val = sigma / np.sqrt(n_mark)
        fig.add_trace(go.Scatter(x=[n_mark], y=[se_val], mode="markers+text",
                                 marker=dict(color=YELLOW, size=10),
                                 text=[f"  {label}: {se_val:.1f}$"], textposition="middle right",
                                 textfont=dict(color=YELLOW, size=12), showlegend=False))

    fig.add_annotation(x=3000, y=10, text="x4 trades = erreur / 2", font=dict(color=WHITE_50, size=12),
                       showarrow=False)
    fig.update_layout(
        height=400, title="Vitesse de convergence : 1/sqrt(n)",
        xaxis_title="Nombre de trades", yaxis_title="Erreur standard ($)", **DARK,
    )
    return fig


def asymp_sharpe_uncertainty():
    """Show Sharpe ratio confidence interval vs sample size."""
    sharpe_obs = 1.2
    ns = np.arange(20, 1001)
    se_sharpe = np.sqrt((1 + sharpe_obs ** 2 / 2) / ns)
    upper = sharpe_obs + 2 * se_sharpe
    lower = sharpe_obs - 2 * se_sharpe

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(ns) + list(ns[::-1]), y=list(upper) + list(lower[::-1]),
        fill="toself", fillcolor="rgba(255,0,229,0.15)", line=dict(width=0),
        name="IC 95% du Sharpe",
    ))
    fig.add_trace(go.Scatter(x=ns, y=np.full_like(ns, sharpe_obs, dtype=float),
                             line=dict(color=CYAN, width=2), name=f"Sharpe observe = {sharpe_obs}"))
    fig.add_hline(y=0, line_dash="dash", line_color=RED, annotation_text="Sharpe = 0 (pas d'edge)")
    fig.add_hline(y=0.5, line_dash="dot", line_color=YELLOW, opacity=0.5, annotation_text="Sharpe = 0.5 (faible)")

    # Mark where lower CI > 0
    n_signif = ns[lower > 0][0] if any(lower > 0) else ns[-1]
    fig.add_vline(x=n_signif, line_dash="dot", line_color=GREEN,
                  annotation_text=f"Sharpe > 0 confirme a n={n_signif}")

    fig.update_layout(
        height=420, title="Incertitude du Sharpe Ratio selon la taille d'echantillon",
        xaxis_title="Nombre de trades", yaxis_title="Sharpe Ratio", **DARK,
    )
    return fig


def asymp_estimator_comparison():
    """Compare convergence of mean, variance, max drawdown."""
    np.random.seed(42)
    mu_true = 5.0
    sigma_true = 50.0
    max_n = 1500
    all_trades = np.random.normal(mu_true, sigma_true, max_n)

    ns = np.arange(20, max_n + 1, 5)
    means, stds, max_dds = [], [], []
    for n in ns:
        subset = all_trades[:n]
        means.append(subset.mean())
        stds.append(subset.std())
        cum = np.cumsum(subset)
        running_max = np.maximum.accumulate(cum)
        dd = running_max - cum
        max_dds.append(dd.max())

    fig = make_subplots(rows=1, cols=3, subplot_titles=[
        "Moyenne (converge)", "Ecart-type (converge)", "Max Drawdown (ne converge PAS)"
    ])
    fig.add_trace(go.Scatter(x=ns, y=means, line=dict(color=CYAN, width=2), showlegend=False), row=1, col=1)
    fig.add_hline(y=mu_true, line_dash="dash", line_color=GREEN, row=1, col=1)

    fig.add_trace(go.Scatter(x=ns, y=stds, line=dict(color=MAGENTA, width=2), showlegend=False), row=1, col=2)
    fig.add_hline(y=sigma_true, line_dash="dash", line_color=GREEN, row=1, col=2)

    fig.add_trace(go.Scatter(x=ns, y=max_dds, line=dict(color=RED, width=2), showlegend=False), row=1, col=3)
    fig.add_annotation(x=max_n * 0.7, y=max(max_dds) * 0.5, text="Grandit toujours !",
                       font=dict(color=RED, size=13), showarrow=False, row=1, col=3)

    fig.update_layout(height=380, title="Consistance : tous les estimateurs ne convergent pas", **DARK)
    return fig


# ===================================================================
# 03b — MONTE CARLO
# ===================================================================

def mc_dice_convergence():
    """Show mean of dice rolls converging to 3.5."""
    np.random.seed(42)
    n = 5000
    rolls = np.random.randint(1, 7, n)
    cum_mean = np.cumsum(rolls) / np.arange(1, n + 1)

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=cum_mean, mode="lines", line=dict(color=CYAN, width=2), name="Moyenne empirique"))
    fig.add_hline(y=3.5, line_dash="dash", line_color=GREEN, annotation_text="E[X] = 3.5")
    fig.update_layout(height=380, title="Monte Carlo : la moyenne du de converge vers 3.5",
                      xaxis_title="Nombre de lancers", yaxis_title="Moyenne", xaxis_type="log", **DARK)
    return fig


def mc_wealth_paths():
    """Simulate wealth paths for a casino game."""
    np.random.seed(42)
    n_paths, n_steps = 200, 100
    start = 10000
    target = 15000

    fig = go.Figure()
    wins = 0
    for _ in range(n_paths):
        w = np.zeros(n_steps + 1)
        w[0] = start
        for t in range(n_steps):
            roll = np.random.randint(1, 7)
            if roll % 2 == 1:
                payout = 1000 if np.random.random() < 0.6 else -500
            else:
                payout = -500 if np.random.random() < 0.5 else 1000
            w[t + 1] = w[t] - 325 + payout
            if w[t + 1] <= 0:
                w[t + 1:] = 0
                break
            if w[t + 1] >= target:
                w[t + 1:] = w[t + 1]
                wins += 1
                break
        color = GREEN if w[-1] >= target else RED if w[-1] <= 0 else WHITE_50
        fig.add_trace(go.Scatter(y=w, mode="lines", line=dict(color=color, width=0.8), opacity=0.3, showlegend=False))

    fig.add_hline(y=target, line_dash="dash", line_color=YELLOW, annotation_text=f"Target 15k (atteint {wins}/{n_paths})")
    fig.add_hline(y=0, line_dash="dash", line_color=RED, opacity=0.5)
    fig.update_layout(height=420, title=f"Monte Carlo : {n_paths} parcours de richesse",
                      xaxis_title="Nombre de parties", yaxis_title="Capital ($)", **DARK)
    return fig


def mc_precision():
    """Show how precision improves with sqrt(n)."""
    np.random.seed(42)
    true_ev = 325
    ns = [10, 50, 100, 500, 1000, 5000]
    n_trials = 200

    fig = go.Figure()
    for i, n in enumerate(ns):
        estimates = []
        for _ in range(n_trials):
            results = []
            for _ in range(n):
                roll = np.random.randint(1, 7)
                if roll % 2 == 1:
                    payout = 1000 if np.random.random() < 0.6 else -500
                else:
                    payout = -500 if np.random.random() < 0.5 else 1000
                results.append(payout)
            estimates.append(np.mean(results))
        fig.add_trace(go.Box(y=estimates, name=f"n={n}", marker_color=CYAN, line_color=CYAN, boxmean=True))

    fig.add_hline(y=true_ev, line_dash="dash", line_color=GREEN, annotation_text=f"Vraie EV = {true_ev}$")
    fig.update_layout(height=420, title="Plus de simulations = estimation plus precise",
                      yaxis_title="EV estimee ($)", **DARK)
    return fig


# ===================================================================
# 03 — ERGODICITY
# ===================================================================

def ergo_ensemble_illusion():
    """Show ensemble average vs individual paths — most lose despite positive EV."""
    np.random.seed(123)
    n_steps = 50
    n_paths = 100

    fig = go.Figure()
    final_values = []
    for i in range(n_paths):
        flips = np.random.choice([1.5, 0.6], n_steps)
        path = 1000 * np.cumprod(flips)
        final_values.append(path[-1])
        color = GREEN if path[-1] > 1000 else RED
        fig.add_trace(go.Scatter(
            y=np.concatenate([[1000], path]), mode="lines",
            line=dict(width=0.7, color=color), opacity=0.35,
            showlegend=False,
        ))

    # Ensemble average (EV line)
    ev_line = 1000 * (1.05 ** np.arange(n_steps + 1))
    fig.add_trace(go.Scatter(
        y=ev_line, mode="lines", line=dict(color=YELLOW, width=3, dash="dash"),
        name=f"Moyenne d'ensemble (EV = +5%/tour)",
    ))
    fig.add_hline(y=1000, line_dash="dot", line_color=WHITE_50, opacity=0.4)

    n_losers = sum(1 for v in final_values if v < 1000)
    pct_losers = n_losers / n_paths * 100

    fig.update_layout(
        height=500,
        title=f"L'illusion de l'EV : {pct_losers:.0f}% des parcours PERDENT malgre EV = +5%",
        yaxis_title="Capital ($)", yaxis_type="log",
        xaxis_title="Tours",
        annotations=[dict(
            x=n_steps * 0.7, y=np.log10(ev_line[-1]) * 0.5,
            text=f"<b>{pct_losers:.0f}% en rouge = perdants</b><br>L'EV jaune monte,<br>mais TOI tu es probablement en rouge",
            showarrow=False, font=dict(color="white", size=13),
            bgcolor="rgba(255,51,102,0.3)", bordercolor=RED,
        )],
        **DARK,
    )
    return fig


def ergo_multiplicative_vs_additive():
    """Show how multiplicative process diverges from EV."""
    np.random.seed(42)
    n_steps = 200
    n_paths = 50

    fig = make_subplots(rows=1, cols=2, subplot_titles=[
        "Additif (ergodique) : +50 / -40",
        "Multiplicatif (NON ergodique) : +50% / -40%"
    ])

    for path in range(n_paths):
        flips = np.random.choice([1, -1], n_steps)
        # Additive
        add_gains = np.where(flips == 1, 50, -40)
        add_path = 1000 + np.cumsum(add_gains)
        fig.add_trace(go.Scatter(y=add_path, mode="lines", line=dict(width=0.5, color=CYAN), opacity=0.3,
                                 showlegend=False), row=1, col=1)
        # Multiplicative
        mult_gains = np.where(flips == 1, 1.5, 0.6)
        mult_path = 1000 * np.cumprod(mult_gains)
        fig.add_trace(go.Scatter(y=mult_path, mode="lines", line=dict(width=0.5, color=MAGENTA), opacity=0.3,
                                 showlegend=False), row=1, col=2)

    # Expected value line (additive)
    ev_add = 1000 + np.arange(n_steps) * 5  # E = 0.5*50 + 0.5*(-40) = 5 per step
    fig.add_trace(go.Scatter(y=ev_add, mode="lines", line=dict(color=YELLOW, width=3, dash="dash"),
                             name="E[V] = +5$/tour"), row=1, col=1)
    # Expected value line (multiplicative) - geometric growth
    ev_mult = 1000 * (0.95 ** np.arange(n_steps))  # geometric mean = sqrt(1.5*0.6) - 1 ≈ -5%
    fig.add_trace(go.Scatter(y=ev_mult, mode="lines", line=dict(color=RED, width=3, dash="dash"),
                             name="Croissance reelle = -5%/tour"), row=1, col=2)

    fig.update_yaxes(title="Capital ($)", row=1, col=1)
    fig.update_yaxes(title="Capital ($)", type="log", row=1, col=2)
    fig.update_xaxes(title="Tours", row=1, col=1)
    fig.update_xaxes(title="Tours", row=1, col=2)
    fig.update_layout(height=500, title="Additif = stable | Multiplicatif = ruine (meme EV !)", **DARK)
    return fig


def ergo_kelly_sizing():
    """Show growth rate vs bet fraction (Kelly curve)."""
    p = 0.55
    b = 1.5
    f = np.linspace(0, 1, 200)
    # g(f) = p * log(1 + b*f) + (1-p) * log(1 - f)
    with np.errstate(divide="ignore", invalid="ignore"):
        g = p * np.log(1 + b * f) + (1 - p) * np.log(1 - f)
        g[f >= 1] = np.nan

    f_kelly = (p * b - (1 - p)) / b
    g_kelly = p * np.log(1 + b * f_kelly) + (1 - p) * np.log(1 - f_kelly)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=f, y=g, mode="lines", line=dict(color=CYAN, width=3), name="Taux de croissance"))
    fig.add_hline(y=0, line_dash="dash", line_color=RED, opacity=0.5)
    fig.add_trace(go.Scatter(x=[f_kelly], y=[g_kelly], mode="markers+text",
                             marker=dict(color=GREEN, size=14, symbol="star"),
                             text=[f"  Kelly = {f_kelly:.0%}"], textposition="middle right",
                             textfont=dict(color=GREEN, size=14), name="Kelly optimal"))
    fig.add_trace(go.Scatter(x=[f_kelly / 2], y=[p * np.log(1 + b * f_kelly / 2) + (1 - p) * np.log(1 - f_kelly / 2)],
                             mode="markers+text", marker=dict(color=YELLOW, size=12),
                             text=[f"  Demi-Kelly = {f_kelly / 2:.0%}"], textposition="middle right",
                             textfont=dict(color=YELLOW, size=14), name="Demi-Kelly"))
    # Ruin zone
    f_ruin = f[g < 0]
    if len(f_ruin) > 0:
        fig.add_vrect(x0=f_ruin[0], x1=1, fillcolor="rgba(255,51,102,0.1)", line_width=0,
                      annotation_text="ZONE DE RUINE", annotation_position="top")

    fig.update_layout(
        height=420, title="Kelly Criterion : croissance vs taille de position",
        xaxis_title="Fraction du capital risquee (f)", yaxis_title="Taux de croissance g(f)", **DARK,
    )
    return fig


def ergo_kelly_impact_sim():
    """Simulate equity curves for sub-Kelly, Kelly, and over-Kelly sizing."""
    np.random.seed(7)
    n_steps = 500
    n_paths = 30
    p, b = 0.55, 1.5
    f_kelly = (p * b - (1 - p)) / b  # ~0.25

    fractions = {
        f"Demi-Kelly ({f_kelly/2:.0%})": (f_kelly / 2, GREEN),
        f"Kelly ({f_kelly:.0%})": (f_kelly, CYAN),
        f"Sur-Kelly ({min(f_kelly*2.5, 0.95):.0%})": (min(f_kelly * 2.5, 0.95), RED),
    }

    fig = make_subplots(rows=1, cols=3, subplot_titles=list(fractions.keys()),
                        horizontal_spacing=0.06)

    for col_idx, (label, (f, color)) in enumerate(fractions.items(), 1):
        for _ in range(n_paths):
            wins = np.random.random(n_steps) < p
            gains = np.where(wins, 1 + b * f, 1 - f)
            equity = 1000 * np.cumprod(gains)
            fig.add_trace(go.Scatter(
                y=equity, mode="lines",
                line=dict(width=0.8, color=color), opacity=0.4,
                showlegend=False,
            ), row=1, col=col_idx)
        # Median path
        all_paths = []
        for _ in range(200):
            wins = np.random.random(n_steps) < p
            gains = np.where(wins, 1 + b * f, 1 - f)
            all_paths.append(1000 * np.cumprod(gains))
        median_path = np.median(all_paths, axis=0)
        fig.add_trace(go.Scatter(
            y=median_path, mode="lines",
            line=dict(width=3, color=color, dash="dash"),
            name=f"Mediane {label}", showlegend=True,
        ), row=1, col=col_idx)
        fig.update_yaxes(type="log", title="Capital ($)" if col_idx == 1 else "", row=1, col=col_idx)

    fig.add_hline(y=1000, line_dash="dot", line_color=WHITE_50, opacity=0.3)
    fig.update_layout(
        height=550,
        title="Impact du sizing : sous-Kelly monte lent, Kelly monte fort, sur-Kelly = ruine",
        **DARK,
    )
    return fig


def ergo_variance_drag():
    """Show g = E[r] - sigma²/2 visually."""
    edge = np.linspace(0, 0.10, 100)  # 0 to 10%
    sigmas = [0.05, 0.10, 0.15, 0.20, 0.30]
    colors = [GREEN, CYAN, YELLOW, ORANGE, RED]

    fig = go.Figure()
    for sigma, color in zip(sigmas, colors):
        g = edge - sigma ** 2 / 2
        fig.add_trace(go.Scatter(
            x=edge * 100, y=g * 100, mode="lines",
            line=dict(color=color, width=2),
            name=f"σ = {sigma:.0%}",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.3)
    fig.update_layout(
        height=400, title="g = E[r] − σ²/2 : la volatilite mange ton edge",
        xaxis_title="Edge E[r] (%)", yaxis_title="Croissance reelle g (%)", **DARK,
    )
    return fig


# ===================================================================
# 04 — GARCH
# ===================================================================

def garch_volatility_clustering():
    """Simulate GARCH(1,1) and show volatility clustering."""
    np.random.seed(42)
    n = 500
    alpha0, alpha1, beta1 = 0.00001, 0.12, 0.85
    sigma2 = np.zeros(n)
    returns = np.zeros(n)
    sigma2[0] = alpha0 / (1 - alpha1 - beta1)

    for t in range(1, n):
        sigma2[t] = alpha0 + alpha1 * returns[t - 1] ** 2 + beta1 * sigma2[t - 1]
        returns[t] = np.sqrt(sigma2[t]) * np.random.normal()

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=["Rendements simules (GARCH)", "Volatilite σ(t)"],
                        vertical_spacing=0.08)
    fig.add_trace(go.Scatter(y=returns * 100, mode="lines", line=dict(color=CYAN, width=1), name="Returns %"), row=1, col=1)
    fig.add_trace(go.Scatter(y=np.sqrt(sigma2) * 100, mode="lines", line=dict(color=MAGENTA, width=2), name="σ GARCH"), row=2, col=1)
    fig.add_hline(y=np.sqrt(alpha0 / (1 - alpha1 - beta1)) * 100, line_dash="dash", line_color=YELLOW,
                  row=2, col=1, annotation_text="σ long terme")
    fig.update_yaxes(title="Return (%)", row=1, col=1)
    fig.update_yaxes(title="σ (%)", row=2, col=1)
    fig.update_layout(height=500, title="GARCH(1,1) : le clustering de volatilite", showlegend=False, **DARK)
    return fig


def garch_var_comparison():
    """Naive VaR vs GARCH VaR."""
    np.random.seed(42)
    n = 500
    alpha0, alpha1, beta1 = 0.00001, 0.12, 0.85
    sigma2 = np.zeros(n)
    returns = np.zeros(n)
    sigma2[0] = alpha0 / (1 - alpha1 - beta1)
    for t in range(1, n):
        sigma2[t] = alpha0 + alpha1 * returns[t - 1] ** 2 + beta1 * sigma2[t - 1]
        returns[t] = np.sqrt(sigma2[t]) * np.random.normal()

    naive_var = -np.std(returns) * 1.645 * 100
    garch_var = -np.sqrt(sigma2) * 1.645 * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=returns * 100, mode="lines", line=dict(color=WHITE_50, width=1), name="Returns %"))
    fig.add_hline(y=naive_var, line_dash="dash", line_color=RED, annotation_text="VaR Naive (fixe)")
    fig.add_trace(go.Scatter(y=garch_var, mode="lines", line=dict(color=GREEN, width=2), name="VaR GARCH (dynamique)"))

    # Count breaches
    naive_breach = np.sum(returns * 100 < naive_var) / n * 100
    garch_breach = np.sum(returns * 100 < garch_var) / n * 100

    fig.update_layout(
        height=400,
        title=f"VaR 95% : Naive = {naive_breach:.1f}% breaches vs GARCH = {garch_breach:.1f}% breaches (cible = 5%)",
        xaxis_title="Temps", yaxis_title="Return (%)", **DARK,
    )
    return fig


def garch_step_by_step():
    """Interactive GARCH step-by-step: user sees how a shock propagates."""
    alpha0, alpha1, beta1 = 0.00001, 0.10, 0.85
    sigma2_lt = alpha0 / (1 - alpha1 - beta1)

    # Day 0: normal, Day 1: shock of -4%, then calm days
    days = 30
    shocks = np.zeros(days)
    shocks[0] = 0.005  # small move
    shocks[5] = -0.04  # big shock at day 5
    # rest = 0

    sigma2 = np.zeros(days)
    sigma2[0] = sigma2_lt
    for t in range(1, days):
        sigma2[t] = alpha0 + alpha1 * shocks[t - 1] ** 2 + beta1 * sigma2[t - 1]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(range(days)), y=shocks * 100, marker_color=[RED if s < -0.01 else CYAN for s in shocks],
                         name="Choc (%)", opacity=0.5))
    fig.add_trace(go.Scatter(x=list(range(days)), y=np.sqrt(sigma2) * 100, mode="lines+markers",
                             line=dict(color=MAGENTA, width=3), name="σ GARCH (%)"))
    fig.add_hline(y=np.sqrt(sigma2_lt) * 100, line_dash="dot", line_color=YELLOW, annotation_text="σ long-terme")
    fig.add_annotation(x=5, y=abs(shocks[5]) * 100, text="CHOC -4% !", font=dict(color=RED, size=14), showarrow=True,
                       arrowhead=2, arrowcolor=RED)
    fig.update_layout(height=420, title="Un choc se propage puis s'efface (mean reversion)",
                      xaxis_title="Jour", yaxis_title="%", **DARK)
    return fig


# ===================================================================
# 04b — TRADING METRICS
# ===================================================================

def metrics_winrate_trap():
    """Show 3 strategies: 100% WR (flat), 99% WR (blowup), 40% WR (profitable)."""
    np.random.seed(42)
    n = 300

    # A: 100% WR, tiny gains
    a = 100000 + np.cumsum(np.random.uniform(0.5, 1.5, n))
    # B: 99% WR, one blowup
    b_gains = np.random.uniform(5, 15, n)
    b_gains[200] = -3000
    b = 100000 + np.cumsum(b_gains)
    # C: 40% WR, profitable
    c_trades = np.where(np.random.random(n) < 0.4, np.random.uniform(100, 300, n), np.random.uniform(-50, -20, n))
    c = 100000 + np.cumsum(c_trades)

    fig = make_subplots(rows=1, cols=3, subplot_titles=[
        "100% WR (+0.003%)", "99% WR (blowup)", "40% WR (profitable)"
    ])
    fig.add_trace(go.Scatter(y=a, line=dict(color=GREEN, width=2), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(y=b, line=dict(color=MAGENTA, width=2), showlegend=False), row=1, col=2)
    fig.add_trace(go.Scatter(y=c, line=dict(color=CYAN, width=2), showlegend=False), row=1, col=3)
    fig.update_layout(height=350, title="Le winrate MENT : 40% WR peut battre 100% WR", **DARK)
    return fig


def metrics_stability_test():
    """Show stable vs unstable strategy: backtest vs live."""
    np.random.seed(42)
    n_bt, n_live = 400, 200

    # Stable
    r1_bt = np.random.normal(0.001, 0.01, n_bt)
    r1_live = np.random.normal(0.0008, 0.011, n_live)
    eq1 = np.concatenate([100000 * np.exp(np.cumsum(r1_bt)), 100000 * np.exp(np.cumsum(r1_bt))[-1] * np.exp(np.cumsum(r1_live))])

    # Unstable
    r2_bt = np.random.normal(0.001, 0.01, n_bt)
    r2_live = np.random.normal(-0.0005, 0.02, n_live)
    eq2_bt = 100000 * np.exp(np.cumsum(r2_bt))
    eq2_live = eq2_bt[-1] * np.exp(np.cumsum(r2_live))
    eq2 = np.concatenate([eq2_bt, eq2_live])

    fig = make_subplots(rows=1, cols=2, subplot_titles=["STABLE (edge reel)", "INSTABLE (overfitting)"])
    x = list(range(len(eq1)))
    fig.add_trace(go.Scatter(x=x[:n_bt], y=eq1[:n_bt], line=dict(color=CYAN, width=2), name="Backtest"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x[n_bt:], y=eq1[n_bt:], line=dict(color=GREEN, width=2), name="Live"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x[:n_bt], y=eq2[:n_bt], line=dict(color=CYAN, width=2), showlegend=False), row=1, col=2)
    fig.add_trace(go.Scatter(x=x[n_bt:], y=eq2[n_bt:], line=dict(color=RED, width=2), name="Live (effondrement)"), row=1, col=2)
    fig.add_vline(x=n_bt, line_dash="dot", line_color="white", opacity=0.5)
    fig.update_layout(height=380, title="STABILITE = la seule metrique qui compte", **DARK)
    return fig


def metrics_random_walk_best():
    """Show best of 1000 random walks has great metrics but is pure luck."""
    np.random.seed(42)
    n_paths, n_steps = 500, 300
    paths = np.zeros((n_paths, n_steps))
    paths[:, 0] = 100

    for i in range(n_paths):
        r = np.random.normal(0, 0.02, n_steps - 1)
        paths[i, 1:] = 100 * np.exp(np.cumsum(r))

    finals = paths[:, -1]
    best = np.argmax(finals)

    fig = go.Figure()
    for i in range(n_paths):
        fig.add_trace(go.Scatter(y=paths[i], mode="lines", line=dict(color=CYAN, width=0.3), opacity=0.08, showlegend=False))
    fig.add_trace(go.Scatter(y=paths[best], mode="lines", line=dict(color=YELLOW, width=3), name=f"Meilleur : +{(finals[best]/100-1)*100:.0f}%"))
    fig.add_hline(y=100, line_dash="dash", line_color=WHITE_50)
    fig.add_annotation(x=n_steps * 0.6, y=paths[best].max() * 0.9,
                       text="EV = 0 pour TOUS<br>Le 'meilleur' = pure chance",
                       font=dict(color=RED, size=14), showarrow=False)
    fig.update_layout(height=420, title="500 random walks (EV=0) : le meilleur a l'air genial... mais c'est du hasard",
                      xaxis_title="Jours", yaxis_title="Valeur", **DARK)
    return fig


# ===================================================================
# 05 — HMM
# ===================================================================

def hmm_regime_distributions():
    """Show 3 regime distributions with different mean/std."""
    x = np.linspace(-0.08, 0.08, 500)
    regimes = [
        ("Bull (Low Vol)", 0.001, 0.015, GREEN, "rgba(0,255,136,0.15)"),
        ("Sideways (Med Vol)", 0.0, 0.025, YELLOW, "rgba(255,214,0,0.15)"),
        ("Bear (High Vol)", -0.005, 0.045, RED, "rgba(255,51,102,0.15)"),
    ]

    fig = go.Figure()
    for name, mu, sigma, color, fill in regimes:
        y = norm.pdf(x, mu, sigma)
        fig.add_trace(go.Scatter(x=x * 100, y=y, mode="lines", fill="tozeroy",
                                 line=dict(color=color, width=2),
                                 fillcolor=fill, name=name))
    fig.update_layout(height=400, title="Distributions de rendement par regime",
                      xaxis_title="Rendement (%)", yaxis_title="Densite", **DARK)
    return fig


def hmm_regime_price_colored():
    """Simulate price colored by hidden regime."""
    np.random.seed(42)
    n = 500
    # Transition matrix
    A = np.array([[0.97, 0.02, 0.01],
                  [0.03, 0.94, 0.03],
                  [0.02, 0.03, 0.95]])
    mus = [0.001, 0.0, -0.003]
    sigmas = [0.008, 0.015, 0.03]
    colors_map = [GREEN, YELLOW, RED]
    regime_names = ["Bull", "Sideways", "Bear"]

    state = 0
    states = [state]
    returns = []
    for _ in range(n - 1):
        state = np.random.choice(3, p=A[state])
        states.append(state)
        returns.append(np.random.normal(mus[state], sigmas[state]))

    price = 100 * np.exp(np.cumsum([0] + returns))
    states = np.array(states)

    fig = go.Figure()
    for s in range(3):
        mask = states == s
        y_masked = np.where(mask, price, np.nan)
        fig.add_trace(go.Scatter(
            y=y_masked, mode="lines", line=dict(color=colors_map[s], width=2),
            name=regime_names[s], connectgaps=False,
        ))

    fig.update_layout(height=400, title="Prix colore par regime cache (HMM)",
                      xaxis_title="Temps", yaxis_title="Prix", **DARK)
    return fig


def hmm_transition_heatmap():
    """Visualize a transition matrix as a heatmap."""
    A = np.array([[0.96, 0.03, 0.01],
                  [0.04, 0.91, 0.05],
                  [0.01, 0.07, 0.92]])
    labels = ["Low Vol", "Med Vol", "High Vol"]

    fig = go.Figure(go.Heatmap(
        z=A, x=labels, y=labels,
        colorscale=[[0, "rgba(17,17,17,1)"], [0.5, CYAN], [1, MAGENTA]],
        text=np.round(A * 100, 1).astype(str),
        texttemplate="%{text}%",
        textfont=dict(size=16, color="white"),
        showscale=False,
    ))
    fig.update_layout(
        height=380, title="Matrice de Transition (% de chance de passer d'un etat a l'autre)",
        xaxis_title="Vers →", yaxis_title="Depuis ↓", yaxis=dict(autorange="reversed"), **DARK,
    )
    return fig


# ===================================================================
# 05b — REGIME SWITCHING
# ===================================================================

def regime_bayesian_filtering():
    """Simulate Bayesian regime filtering on live bars."""
    np.random.seed(42)
    n = 200
    # Simulate vol regimes
    A = np.array([[0.95, 0.04, 0.01], [0.05, 0.90, 0.05], [0.01, 0.04, 0.95]])
    mus_r = [0.005, 0.015, 0.035]
    sigs_r = [0.002, 0.005, 0.010]
    state = 0
    states, vols, posteriors = [], [], []
    post = np.array([0.8, 0.15, 0.05])

    for t in range(n):
        state = np.random.choice(3, p=A[state])
        states.append(state)
        vol = max(0.001, np.random.normal(mus_r[state], sigs_r[state]))
        vols.append(vol)
        # Bayesian filter
        prior = A.T @ post
        lik = np.array([norm.pdf(vol, mus_r[r], sigs_r[r]) for r in range(3)])
        post = prior * lik
        post /= post.sum()
        posteriors.append(post.copy())

    posteriors = np.array(posteriors)
    states = np.array(states)
    colors_map = {0: GREEN, 1: YELLOW, 2: RED}

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=["Volatilite par barre (colore par regime)", "Probabilite posterieure"],
                        vertical_spacing=0.08)
    for s, name in [(0, "LOW"), (1, "MED"), (2, "HIGH")]:
        mask = states == s
        y = np.where(mask, vols, np.nan)
        fig.add_trace(go.Scatter(y=y, mode="markers", marker=dict(color=colors_map[s], size=4),
                                 name=name, connectgaps=False), row=1, col=1)

    fig.add_trace(go.Scatter(y=posteriors[:, 0], line=dict(color=GREEN, width=2), name="P(LOW)"), row=2, col=1)
    fig.add_trace(go.Scatter(y=posteriors[:, 1], line=dict(color=YELLOW, width=2), name="P(MED)"), row=2, col=1)
    fig.add_trace(go.Scatter(y=posteriors[:, 2], line=dict(color=RED, width=2), name="P(HIGH)"), row=2, col=1)
    fig.update_yaxes(title="Vol", row=1, col=1)
    fig.update_yaxes(title="Proba", range=[0, 1], row=2, col=1)
    fig.update_layout(height=500, title="Filtrage bayesien en temps reel : regime switching", **DARK)
    return fig


# ===================================================================
# 05c — HAWKES
# ===================================================================

def hawkes_intensity():
    """Simulate Hawkes process intensity with clustering."""
    np.random.seed(42)
    n = 200
    mu_base, alpha, beta_h = 0.2, 0.4, 0.8
    dt = 1.0

    lam = np.zeros(n + 1)
    N_count = np.zeros(n + 1)
    lam[0] = mu_base

    for t in range(1, n + 1):
        dN = np.random.poisson(lam[t - 1] * dt)
        N_count[t] = N_count[t - 1] + dN
        lam[t] = mu_base + (lam[t - 1] - mu_base) * np.exp(-beta_h * dt) + alpha * dN

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=["Intensite lambda(t) — self-exciting", "Events cumules N(t)"],
                        vertical_spacing=0.08)
    fig.add_trace(go.Scatter(y=lam, line=dict(color=MAGENTA, width=2), name="lambda(t)"), row=1, col=1)
    fig.add_hline(y=mu_base, line_dash="dash", line_color=WHITE_50, row=1, col=1, annotation_text=f"mu={mu_base}")
    fig.add_trace(go.Scatter(y=N_count, line=dict(color=CYAN, width=2), name="N(t)"), row=2, col=1)
    fig.update_yaxes(title="lambda", row=1, col=1)
    fig.update_yaxes(title="N(t)", row=2, col=1)
    fig.update_layout(height=500, title="Hawkes Process : les events provoquent d'autres events", **DARK)
    return fig


def hawkes_vs_poisson():
    """Compare Poisson (no clustering) vs Hawkes (clustering) returns."""
    np.random.seed(42)
    n = 300
    sigma_diff, sigma_J = 0.01, 0.04
    lam_fixed = 0.15
    mu_base, alpha, beta_h = 0.06, 0.3, 0.5

    dW = np.random.normal(0, sigma_diff, n)
    R_std, R_hwk = np.zeros(n), np.zeros(n)
    lam_h = mu_base

    for t in range(n):
        dN_std = np.random.poisson(lam_fixed)
        j_std = np.sum(np.random.normal(0, sigma_J, dN_std)) if dN_std > 0 else 0
        R_std[t] = dW[t] + j_std

        dN_hwk = np.random.poisson(lam_h)
        j_hwk = np.sum(np.random.normal(0, sigma_J, dN_hwk)) if dN_hwk > 0 else 0
        R_hwk[t] = dW[t] + j_hwk
        lam_h = mu_base + (lam_h - mu_base) * np.exp(-0.5) + alpha * dN_hwk

    fig = make_subplots(rows=1, cols=2, subplot_titles=["Poisson (pas de clustering)", "Hawkes (clustering)"])
    fig.add_trace(go.Scatter(y=R_std * 100, mode="lines", line=dict(color=CYAN, width=1), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(y=R_hwk * 100, mode="lines", line=dict(color=MAGENTA, width=1), showlegend=False), row=1, col=2)

    from scipy.stats import kurtosis as kurt_fn
    k_std = kurt_fn(R_std)
    k_hwk = kurt_fn(R_hwk)
    fig.add_annotation(x=150, y=max(R_std) * 80, text=f"Kurtosis = {k_std:.1f}", font=dict(color=CYAN, size=13), showarrow=False, row=1, col=1)
    fig.add_annotation(x=150, y=max(R_hwk) * 80, text=f"Kurtosis = {k_hwk:.1f}", font=dict(color=MAGENTA, size=13), showarrow=False, row=1, col=2)
    fig.update_layout(height=380, title="Poisson vs Hawkes : les clusters changent tout", **DARK)
    return fig


# ===================================================================
# 06 — KALMAN FILTER
# ===================================================================

def kalman_filter_demo():
    """Full Kalman filter on noisy VIX-like signal."""
    np.random.seed(42)
    n = 200
    # True signal: mean-reverting OU process
    true_val = np.zeros(n)
    true_val[0] = 18
    kappa, theta, sigma_ou = 0.1, 18, 1.5
    for t in range(1, n):
        true_val[t] = true_val[t - 1] + kappa * (theta - true_val[t - 1]) + sigma_ou * np.random.normal()

    # Inject regime change
    true_val[120:] += 8

    # Noisy observations
    R_noise = 4.0
    obs = true_val + np.random.normal(0, np.sqrt(R_noise), n)

    # Kalman Filter
    F = 0.95  # AR(1) decay
    B = (1 - F) * theta
    Q = 2.0
    R = R_noise

    x_est = np.zeros(n)
    P_est = np.zeros(n)
    K_hist = np.zeros(n)
    x_est[0] = obs[0]
    P_est[0] = 5.0

    for t in range(1, n):
        # Predict
        x_pred = F * x_est[t - 1] + B
        P_pred = F ** 2 * P_est[t - 1] + Q
        # Innovation
        innov = obs[t] - x_pred
        # Adaptive: inflate P on shock
        if innov ** 2 > 9 * (P_pred + R):
            P_pred += 50
        # Update
        K = P_pred / (P_pred + R)
        x_est[t] = x_pred + K * innov
        P_est[t] = (1 - K) * P_pred
        K_hist[t] = K

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=["Signal : vrai vs observe vs filtre Kalman", "Kalman Gain K(t)"],
                        row_heights=[0.7, 0.3], vertical_spacing=0.08)

    # Confidence band
    upper = x_est + 2 * np.sqrt(P_est)
    lower = x_est - 2 * np.sqrt(P_est)
    t_arr = list(range(n))
    fig.add_trace(go.Scatter(x=t_arr + t_arr[::-1], y=list(upper) + list(lower[::-1]),
                             fill="toself", fillcolor="rgba(0,229,255,0.12)", line=dict(width=0),
                             name="IC 95%", showlegend=True), row=1, col=1)

    fig.add_trace(go.Scatter(y=obs, mode="markers", marker=dict(color=WHITE_50, size=3), name="Observations (bruitees)"), row=1, col=1)
    fig.add_trace(go.Scatter(y=true_val, mode="lines", line=dict(color=YELLOW, width=1, dash="dot"), name="Vrai signal (cache)"), row=1, col=1)
    fig.add_trace(go.Scatter(y=x_est, mode="lines", line=dict(color=CYAN, width=3), name="Estimation Kalman"), row=1, col=1)

    fig.add_trace(go.Scatter(y=K_hist, mode="lines", line=dict(color=ORANGE, width=2), name="Gain K"), row=2, col=1)
    fig.add_vline(x=120, line_dash="dot", line_color=RED, annotation_text="Regime change", row=1, col=1)
    fig.add_vline(x=120, line_dash="dot", line_color=RED, row=2, col=1)

    fig.update_yaxes(title="Valeur", row=1, col=1)
    fig.update_yaxes(title="K", range=[0, 1], row=2, col=1)
    fig.update_layout(height=550, title="Kalman Filter adaptatif avec regime change", **DARK)
    return fig


def kalman_gain_explained():
    """Show how K changes with R."""
    P = 2.0
    R_range = np.linspace(0.1, 20, 200)
    K = P / (P + R_range)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=R_range, y=K, mode="lines", line=dict(color=CYAN, width=3), name="K = P/(P+R)"))
    fig.add_hline(y=0.5, line_dash="dot", line_color=WHITE_50)
    fig.add_annotation(x=1, y=0.85, text="R petit → suit les donnees", font=dict(color=GREEN, size=13), showarrow=False)
    fig.add_annotation(x=15, y=0.15, text="R grand → suit le modele", font=dict(color=RED, size=13), showarrow=False)

    fig.update_layout(height=380, title="Le Kalman Gain : a qui faire confiance ?",
                      xaxis_title="R (bruit de mesure)", yaxis_title="Gain K", **DARK)
    return fig


def kalman_R_comparison():
    """Same data, different R values."""
    np.random.seed(42)
    n = 150
    true_sig = np.zeros(n)
    true_sig[0] = 50
    for t in range(1, n):
        true_sig[t] = true_sig[t - 1] + 0.3 * np.random.normal()

    obs = true_sig + np.random.normal(0, 5, n)

    def run_kf(obs, R, Q=0.5):
        x_est = np.zeros(len(obs))
        x_est[0] = obs[0]
        P = 1.0
        for t in range(1, len(obs)):
            P_pred = P + Q
            K = P_pred / (P_pred + R)
            x_est[t] = x_est[t - 1] + K * (obs[t] - x_est[t - 1])
            P = (1 - K) * P_pred
        return x_est

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=obs, mode="markers", marker=dict(color=WHITE_50, size=3), name="Observations"))
    fig.add_trace(go.Scatter(y=true_sig, mode="lines", line=dict(color=YELLOW, width=1, dash="dot"), name="Vrai signal"))

    for R, color, label in [(0.5, GREEN, "R=0.5 (reactif)"), (5, CYAN, "R=5 (equilibre)"), (50, RED, "R=50 (lisse)")]:
        fig.add_trace(go.Scatter(y=run_kf(obs, R), mode="lines", line=dict(color=color, width=2), name=label))

    fig.update_layout(height=420, title="Impact de R : reactif vs lisse",
                      xaxis_title="Temps", yaxis_title="Signal", **DARK)
    return fig


# ===================================================================
# 07 — PIPELINE
# ===================================================================

def pipeline_decision_matrix():
    """Visual decision matrix."""
    regimes = ["Low Vol", "Med Vol", "High Vol"]
    signals = ["Signal Faible", "Signal Fort"]

    z = np.array([[0, 100], [0, 50], [0, 0]])
    colors = [[RED, GREEN], [RED, YELLOW], [RED, RED]]
    text = [["NO TRADE", "TRADE 100%"], ["NO TRADE", "TRADE 50%"], ["NO TRADE", "NO TRADE"]]

    fig = go.Figure(go.Heatmap(
        z=z, x=signals, y=regimes,
        colorscale=[[0, "rgba(255,51,102,0.6)"], [0.5, YELLOW], [1, GREEN]],
        text=text, texttemplate="%{text}",
        textfont=dict(size=18, color="white"),
        showscale=False,
    ))
    fig.update_layout(height=350, title="Matrice de Decision : Regime x Signal",
                      yaxis=dict(autorange="reversed"), **DARK)
    return fig


def pipeline_full_simulation():
    """Full pipeline: GARCH + HMM + Kalman → decision."""
    np.random.seed(42)
    n = 300

    # Simulate regimes
    A = np.array([[0.97, 0.02, 0.01], [0.03, 0.94, 0.03], [0.02, 0.03, 0.95]])
    state = 0
    states = [state]
    for _ in range(n - 1):
        state = np.random.choice(3, p=A[state])
        states.append(state)
    states = np.array(states)

    # Simulate returns per regime
    mus = [0.001, 0.0, -0.002]
    sigmas_regime = [0.008, 0.015, 0.035]
    returns = np.array([np.random.normal(mus[s], sigmas_regime[s]) for s in states])

    # GARCH sigma
    alpha0, alpha1, beta1 = 0.00001, 0.12, 0.85
    garch_sig2 = np.zeros(n)
    garch_sig2[0] = 0.0002
    for t in range(1, n):
        garch_sig2[t] = alpha0 + alpha1 * returns[t - 1] ** 2 + beta1 * garch_sig2[t - 1]

    # Fake absorption signal
    absorption_raw = np.random.normal(0.5, 0.3, n)
    absorption_raw[states == 0] += 0.3  # stronger in bull
    absorption_raw = np.clip(absorption_raw, 0, 1)

    # Kalman on absorption
    x_est = np.zeros(n)
    x_est[0] = 0.5
    P = 0.1
    for t in range(1, n):
        Q = 0.01 + 0.1 * np.sqrt(garch_sig2[t])
        R = 0.3 if states[t] == 2 else 0.1 if states[t] == 0 else 0.2
        P_pred = P + Q
        K = P_pred / (P_pred + R)
        x_est[t] = x_est[t - 1] + K * (absorption_raw[t] - x_est[t - 1])
        P = (1 - K) * P_pred

    # Decisions
    threshold = 0.6
    decisions = np.zeros(n)
    for t in range(n):
        if x_est[t] > threshold and states[t] == 0:
            decisions[t] = 1.0
        elif x_est[t] > threshold and states[t] == 1:
            decisions[t] = 0.5
        else:
            decisions[t] = 0.0

    price = 100 * np.exp(np.cumsum(returns))

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                        subplot_titles=[
                            "Prix + Regime (couleur)",
                            "σ GARCH",
                            "Signal Absorption (brut vs Kalman)",
                            "Decision de Trading (taille)",
                        ], vertical_spacing=0.06, row_heights=[0.3, 0.2, 0.3, 0.2])

    colors_map = {0: GREEN, 1: YELLOW, 2: RED}
    for s, name in [(0, "Bull"), (1, "Side"), (2, "Bear")]:
        mask = states == s
        y_m = np.where(mask, price, np.nan)
        fig.add_trace(go.Scatter(y=y_m, mode="lines", line=dict(color=colors_map[s], width=2),
                                 name=name, connectgaps=False, showlegend=True), row=1, col=1)

    fig.add_trace(go.Scatter(y=np.sqrt(garch_sig2) * 100, line=dict(color=MAGENTA, width=2),
                             name="σ GARCH", showlegend=False), row=2, col=1)

    fig.add_trace(go.Scatter(y=absorption_raw, mode="markers", marker=dict(color=WHITE_50, size=2),
                             name="Absorption brut", showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(y=x_est, line=dict(color=CYAN, width=3),
                             name="Absorption Kalman", showlegend=False), row=3, col=1)
    fig.add_hline(y=threshold, line_dash="dash", line_color=YELLOW, row=3, col=1)

    fig.add_trace(go.Bar(y=decisions * 100,
                         marker_color=[GREEN if d == 1 else YELLOW if d == 0.5 else "rgba(50,50,50,0.3)" for d in decisions],
                         name="Taille (%)", showlegend=False), row=4, col=1)

    fig.update_yaxes(title="Prix", row=1, col=1)
    fig.update_yaxes(title="σ %", row=2, col=1)
    fig.update_yaxes(title="Signal", row=3, col=1)
    fig.update_yaxes(title="Taille %", row=4, col=1)
    fig.update_layout(height=800, title="Pipeline complet : GARCH + HMM + Kalman → Decision", **DARK)
    return fig


# ===================================================================
# 06b — KALMAN MEAN REVERSION
# ===================================================================

def ou_mean_reversion_sim():
    """Simulate OU process and show mean reversion + bands."""
    np.random.seed(42)
    n = 400
    mu, theta, sigma = 100.0, 0.05, 1.2
    dt = 1.0
    X = np.zeros(n)
    X[0] = 106.0
    for t in range(1, n):
        X[t] = X[t-1] + theta * (mu - X[t-1]) * dt + sigma * np.random.randn() * np.sqrt(dt)

    stat_dev = sigma / np.sqrt(2 * theta)

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=X, mode="lines", line=dict(color=CYAN, width=2), name="Prix (OU)"))
    fig.add_hline(y=mu, line_dash="dash", line_color=GREEN, annotation_text="mu = 100 (vraie moyenne)")
    fig.add_hline(y=mu + stat_dev, line_dash="dot", line_color=RED, opacity=0.5, annotation_text="mu + sigma_stat")
    fig.add_hline(y=mu - stat_dev, line_dash="dot", line_color=GREEN, opacity=0.5)
    fig.add_annotation(x=50, y=106, text="Depart haut (106)", font=dict(color=YELLOW, size=12), showarrow=True, arrowcolor=YELLOW)
    fig.update_layout(height=420, title="Processus OU : le prix est tire vers mu comme un elastique",
                      xaxis_title="Temps", yaxis_title="Prix", **DARK)
    return fig


def kalman_vs_fixed_mean():
    """Compare Kalman adaptive mean vs fixed sample mean for trading."""
    np.random.seed(42)
    n = 300
    mu_true = 100.0
    theta, sigma = 0.05, 1.2
    dt = 1.0

    X = np.zeros(n)
    X[0] = 105.0
    for t in range(1, n):
        X[t] = X[t-1] + theta * (mu_true - X[t-1]) * dt + sigma * np.random.randn() * np.sqrt(dt)

    # Fixed mean from first 30 bars (biased)
    fixed_mean = np.mean(X[:30])

    # Kalman filter
    phi = np.exp(-theta * dt)
    Q = sigma**2 * (1 - phi**2)
    R = 2.0
    x_kf = np.zeros(n)
    x_kf[0] = X[0]
    P = 1.0
    for t in range(1, n):
        x_pred = phi * x_kf[t-1] + (1 - phi) * mu_true
        P_pred = phi**2 * P + Q
        K = P_pred / (P_pred + R)
        x_kf[t] = x_pred + K * (X[t] - x_pred)
        P = (1 - K) * P_pred

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=X, mode="lines", line=dict(color=WHITE_50, width=1), name="Prix"))
    fig.add_hline(y=fixed_mean, line_dash="dash", line_color=RED,
                  annotation_text=f"Moyenne fixe (30 bars) = {fixed_mean:.1f} -- BIAISEE")
    fig.add_trace(go.Scatter(y=x_kf, mode="lines", line=dict(color=CYAN, width=3), name="Kalman (adaptatif)"))
    fig.add_hline(y=mu_true, line_dash="dot", line_color=GREEN, opacity=0.5, annotation_text=f"Vraie mu = {mu_true}")

    fig.update_layout(height=420, title="Moyenne fixe (biaisee) vs Kalman adaptatif",
                      xaxis_title="Temps", yaxis_title="Prix", **DARK)
    return fig


def mean_reversion_trap():
    """Show equity curve bleeding from biased mean vs Kalman-based."""
    np.random.seed(42)
    n_est, n_trade = 30, 300
    n_total = n_est + n_trade
    mu_true, theta, sigma = 100.0, 0.05, 1.2
    dt = 1.0

    X = np.zeros(n_total)
    X[0] = 106.0
    for t in range(1, n_total):
        X[t] = X[t-1] + theta * (mu_true - X[t-1]) * dt + sigma * np.random.randn() * np.sqrt(dt)

    est_mu = np.mean(X[:n_est])
    stat_dev = sigma / np.sqrt(2 * theta)
    band = 0.8 * stat_dev
    upper_bad = est_mu + band
    lower_bad = est_mu - band

    # Kalman
    phi = np.exp(-theta * dt)
    Q = sigma**2 * (1 - phi**2)
    R = 2.0
    x_kf = X[0]
    P = 1.0
    kf_means = []
    for t in range(n_total):
        x_pred = phi * x_kf + (1 - phi) * mu_true
        P_pred = phi**2 * P + Q
        K = P_pred / (P_pred + R)
        x_kf = x_pred + K * (X[t] - x_pred)
        P = (1 - K) * P_pred
        kf_means.append(x_kf)

    # Trading sim: biased vs kalman
    def trade_sim(prices, means, band_w):
        pos = 0
        pnl = []
        cum = 0
        for i in range(1, len(prices)):
            m = means[i] if hasattr(means, '__getitem__') and len(means) > 1 else means
            m_val = m if isinstance(m, (int, float)) else float(m)
            profit = pos * (prices[i] - prices[i-1])
            cum += profit
            pnl.append(cum)
            if pos == 0:
                if prices[i] > m_val + band_w:
                    pos = -1
                elif prices[i] < m_val - band_w:
                    pos = 1
            elif pos == 1 and prices[i] >= m_val:
                pos = 0
            elif pos == -1 and prices[i] <= m_val:
                pos = 0
        return pnl

    prices_trade = X[n_est:]
    pnl_bad = trade_sim(prices_trade, [est_mu]*len(prices_trade), band)
    kf_trade = kf_means[n_est:]
    pnl_kf = trade_sim(prices_trade, kf_trade, band)

    fig = make_subplots(rows=1, cols=2, subplot_titles=[
        f"Equity : moyenne fixe ({est_mu:.1f}, biaisee)", "Equity : Kalman adaptatif"
    ])
    fig.add_trace(go.Scatter(y=pnl_bad, mode="lines", line=dict(color=RED, width=2), name="Biased"), row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color=WHITE_50, row=1, col=1)
    fig.add_trace(go.Scatter(y=pnl_kf, mode="lines", line=dict(color=GREEN, width=2), name="Kalman"), row=1, col=2)
    fig.add_hline(y=0, line_dash="dash", line_color=WHITE_50, row=1, col=2)
    fig.update_layout(height=380, title="Le piege : estimation biaisee = PnL qui descend", showlegend=False, **DARK)
    return fig


# ===================================================================
# 25 — HURST MR
# ===================================================================

def hurst_regime_spectrum():
    """Visual H spectrum: MR zone / Random Walk / Trend zone."""
    fig = go.Figure()

    # Colored zones
    zones = [
        (0.00, 0.45, "rgba(0,255,136,0.18)",  "rgba(0,255,136,0.6)"),
        (0.45, 0.55, "rgba(255,214,0,0.12)",  "rgba(255,214,0,0.5)"),
        (0.55, 1.00, "rgba(255,51,102,0.15)", "rgba(255,51,102,0.6)"),
    ]
    for x0, x1, fill, line_c in zones:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=0, y1=1,
                      fillcolor=fill, line=dict(width=0), layer="below")

    # Gradient bar
    h_vals = np.linspace(0, 1, 200)
    colors = []
    for h in h_vals:
        if h < 0.45:
            r = int(0 + h / 0.45 * 255)
            colors.append(f"rgb({r},255,136)")
        elif h < 0.55:
            colors.append("rgb(255,214,0)")
        else:
            r = int(255)
            g = int(max(0, 51 + (1 - h) / 0.45 * 80))
            colors.append(f"rgb({r},{g},102)")

    fig.add_trace(go.Bar(
        x=h_vals, y=[0.45] * len(h_vals),
        marker_color=colors, marker_line_width=0,
        width=0.005, base=0.275, showlegend=False,
        hoverinfo="skip",
    ))

    # Labels sous la barre
    labels = [
        (0.225, 0.12, GREEN,  "MEAN REVERSION", "H < 0.45", "TON EDGE"),
        (0.500, 0.12, YELLOW, "RANDOM WALK",    "H = 0.5",  "pas d'edge"),
        (0.775, 0.12, RED,    "TRENDING",       "H > 0.55", "ne pas trader MR"),
    ]
    for x, y, color, title, sub, note in labels:
        fig.add_annotation(x=x, y=0.55, text=f"<b>{title}</b>",
                           showarrow=False, font=dict(color=color, size=13,
                           family="JetBrains Mono"), xanchor="center")
        fig.add_annotation(x=x, y=0.38, text=sub,
                           showarrow=False, font=dict(color=color, size=11,
                           family="JetBrains Mono"), xanchor="center")
        fig.add_annotation(x=x, y=0.22, text=f"<i>{note}</i>",
                           showarrow=False, font=dict(color="#555", size=10,
                           family="JetBrains Mono"), xanchor="center")

    # Seuil 0.45
    fig.add_shape(type="line", x0=0.45, x1=0.45, y0=0.0, y1=0.75,
                  line=dict(color=TEAL, width=2, dash="dot"))
    fig.add_annotation(x=0.45, y=0.80, text="Seuil 0.45",
                       showarrow=False, font=dict(color=TEAL, size=10,
                       family="JetBrains Mono"), xanchor="center")

    # Axe H
    tick_vals = [0, 0.1, 0.2, 0.3, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    fig.update_layout(
        height=200,
        title=dict(text="Spectre de l'Exposant de Hurst H", font=dict(size=13, color="#aaa")),
        xaxis=dict(range=[0, 1], tickvals=tick_vals,
                   ticktext=[str(v) for v in tick_vals],
                   tickfont=dict(color="#555", size=10, family="JetBrains Mono"),
                   gridcolor="#111", title="H", zeroline=False),
        yaxis=dict(visible=False, range=[0, 1]),
        **{**DARK, "margin": dict(t=50, b=40, l=40, r=20)},
    )
    return fig


def hurst_session_visual():
    """Side-by-side: trending session vs mean-reverting session."""
    np.random.seed(42)
    n = 80

    # Trending: fBm H=0.75
    trend_path = _fbm_ar1(n, H=0.73, seed=7)

    # MR: fBm H=0.2 + rolling bands
    mr_path = _fbm_ar1(n, H=0.22, seed=13)
    lb = 20
    mu_r  = np.array([mr_path[max(0, i-lb):i].mean() if i >= lb else np.nan for i in range(n)])
    std_r = np.array([mr_path[max(0, i-lb):i].std()  if i >= lb else np.nan for i in range(n)])
    upper_r = mu_r + 2.0 * std_r
    lower_r = mu_r - 2.0 * std_r

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["SESSION TRENDING — H > 0.5 (NE PAS TRADER)",
                         "SESSION MEAN-REVERTING — H < 0.45 (TON EDGE)"],
        horizontal_spacing=0.10,
    )

    # Trending side
    fig.add_trace(go.Scatter(y=trend_path, mode="lines",
                             line=dict(color=RED, width=2), name="Prix"), row=1, col=1)
    # Arrows showing momentum
    for i in range(10, n - 10, 15):
        if trend_path[i+5] > trend_path[i]:
            fig.add_annotation(x=i+3, y=trend_path[i+3],
                               ax=i, ay=trend_path[i],
                               xref="x", yref="y", axref="x", ayref="y",
                               showarrow=True, arrowhead=2, arrowwidth=2,
                               arrowcolor=RED, row=1, col=1)

    # MR side
    fig.add_trace(go.Scatter(y=upper_r, line=dict(color="rgba(255,51,102,0.4)", dash="dot", width=1.5),
                             name="+2σ", showlegend=False), row=1, col=2)
    fig.add_trace(go.Scatter(y=lower_r, line=dict(color="rgba(0,255,136,0.4)", dash="dot", width=1.5),
                             fill="tonexty", fillcolor="rgba(60,196,183,0.04)",
                             name="-2σ", showlegend=False), row=1, col=2)
    fig.add_trace(go.Scatter(y=mu_r, line=dict(color=TEAL, width=1.5, dash="dash"),
                             name="Fair Value", showlegend=False), row=1, col=2)
    fig.add_trace(go.Scatter(y=mr_path, mode="lines",
                             line=dict(color=GREEN, width=2), name="Prix MR"), row=1, col=2)

    fig.update_layout(
        height=380,
        showlegend=False,
        **{**DARK, "margin": dict(t=60, b=30, l=40, r=20)},
    )
    fig.update_annotations(font=dict(size=11, family="JetBrains Mono"))
    return fig

def _davies_harte_batch(N, H, n_paths, seed=42):
    """Generate n_paths fBm via Davies-Harte (vectorized, exact algorithm from Lec 25)."""
    np.random.seed(seed)
    # Autocovariance of fGn: gamma(0)=1, gamma(k)=0.5*(|k+1|^{2H}-2k^{2H}+|k-1|^{2H})
    k = np.arange(N + 1, dtype=float)
    gamma = np.zeros(N + 1)
    gamma[0] = 1.0
    gamma[1:] = 0.5 * ((k[1:] + 1) ** (2*H) - 2 * k[1:] ** (2*H) + (k[1:] - 1) ** (2*H))
    # Circulant embedding
    M = 2 * N
    c = np.concatenate([gamma, gamma[N-1:0:-1]])
    L = np.maximum(np.fft.fft(c).real, 0)   # eigenvalues (non-negative)
    sqrtL = np.sqrt(L)
    # Random arrays for all paths at once
    X0 = np.random.normal(0, 1, n_paths)
    XN = np.random.normal(0, 1, n_paths)
    Xk = np.random.normal(0, 1, (N - 1, n_paths))
    Yk = np.random.normal(0, 1, (N - 1, n_paths))
    Z = np.zeros((M, n_paths), dtype=np.complex128)
    Z[0] = sqrtL[0] * X0
    Z[N] = sqrtL[N] * XN
    for ki in range(1, N):
        Z[ki]   = sqrtL[ki] / np.sqrt(2) * (Xk[ki-1] + 1j * Yk[ki-1])
        Z[M-ki] = np.conj(Z[ki])
    fGn = np.fft.ifft(Z, axis=0).real[:N] * np.sqrt(M)   # (N, n_paths)
    fbm = np.cumsum(fGn, axis=0)                           # (N, n_paths)
    return fbm.T   # (n_paths, N)


def hurst_covariance_heatmap():
    """Empirical vs Theoretical Covariance of fBm — Davies-Harte (Lec 25)."""
    N, H, n_paths = 64, 0.25, 600

    paths = _davies_harte_batch(N, H, n_paths, seed=42)   # (n_paths, N)

    # Empirical covariance (N x N)
    emp_cov = np.cov(paths.T)

    # Theoretical covariance: Cov(B_H(t), B_H(s)) = 0.5*(t^{2H}+s^{2H}-|t-s|^{2H})
    t = np.arange(1, N + 1, dtype=float)
    ti, tj = np.meshgrid(t, t)
    theo_cov = 0.5 * (ti ** (2*H) + tj ** (2*H) - np.abs(ti - tj) ** (2*H))

    rmse = float(np.sqrt(np.mean((emp_cov - theo_cov) ** 2)))

    tick_vals = list(range(0, N, 6))
    tick_text = [str(v) for v in tick_vals]

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["Empirical Covariance", "Theoretical Covariance"],
        horizontal_spacing=0.12,
    )
    common = dict(colorscale="Viridis", zmin=0, showscale=True)
    fig.add_trace(go.Heatmap(z=emp_cov,  name="Empirical",
                              colorbar=dict(x=0.44, len=0.9, thickness=12,
                                            tickfont=dict(color="#555", size=9)),
                              **common), row=1, col=1)
    fig.add_trace(go.Heatmap(z=theo_cov, name="Theoretical",
                              colorbar=dict(x=1.00, len=0.9, thickness=12,
                                            tickfont=dict(color="#555", size=9)),
                              **common), row=1, col=2)

    for col in [1, 2]:
        fig.update_xaxes(tickvals=tick_vals, ticktext=tick_text,
                         tickfont=dict(color="#444", size=9), row=1, col=col)
        fig.update_yaxes(tickvals=tick_vals, ticktext=tick_text,
                         tickfont=dict(color="#444", size=9), row=1, col=col)

    fig.update_layout(
        height=480,
        title=dict(
            text=f"fBm H={H} — Empirical vs Theoretical Covariance  (RMSE = {rmse:.4f})",
            font=dict(size=12, color="#aaa"),
        ),
        **{**DARK, "margin": dict(t=60, b=30, l=40, r=60)},
    )
    return fig


def _fbm_ar1(n, H, seed=42):
    """Approximate fBm via AR(1) with exact lag-1 autocorrelation of fGn."""
    np.random.seed(seed)
    phi = 2 ** (2 * H - 1) - 1          # lag-1 autocorr of fGn (exact formula)
    z = np.random.randn(n)
    eps = np.zeros(n)
    eps[0] = z[0]
    for i in range(1, n):
        eps[i] = phi * eps[i - 1] + z[i] * np.sqrt(max(1 - phi ** 2, 1e-9))
    return 100 + np.cumsum(eps)


def hurst_fbm_paths():
    """Compare 3 fBm paths: H=0.2 (MR), H=0.5 (RW), H=0.7 (Trend)."""
    n = 200
    cases = [
        (0.2, GREEN,   "H = 0.2 — Anti-persistant (Mean Reversion) ← TON EDGE"),
        (0.5, YELLOW,  "H = 0.5 — Random Walk (pas de memoire)"),
        (0.7, RED,     "H = 0.7 — Persistant (Trending)"),
    ]
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        subplot_titles=[c[2] for c in cases],
        vertical_spacing=0.08,
    )
    for row, (H, color, label) in enumerate(cases, 1):
        y = _fbm_ar1(n, H, seed=row * 7)
        fig.add_trace(go.Scatter(
            y=y, mode="lines", line=dict(color=color, width=1.8),
            name=label, showlegend=False,
        ), row=row, col=1)
        # Add rolling mean for H=0.2 to show MR property
        if H == 0.2:
            w = 30
            mu = np.array([np.mean(y[max(0, i-w):i]) if i >= w else np.nan for i in range(n)])
            fig.add_trace(go.Scatter(
                y=mu, mode="lines", line=dict(color=TEAL, width=1.5, dash="dash"),
                name="Moyenne rolling", showlegend=False,
            ), row=row, col=1)
    fig.update_layout(
        height=600,
        title="Exposant de Hurst H — Impact visuel sur le prix",
        **DARK,
    )
    return fig


def hurst_rs_analysis():
    """R/S log-log plot showing slope = H for different regimes."""
    np.random.seed(42)
    n = 2000
    lags = [5, 8, 12, 20, 30, 50, 80, 120, 200]

    def compute_rs(series, lag):
        chunks = [series[i:i+lag] for i in range(0, len(series)-lag+1, lag)]
        rs_vals = []
        for c in chunks:
            if len(c) < 4:
                continue
            std = np.std(c)
            if std > 0:
                devs = np.cumsum(c - np.mean(c))
                rs_vals.append((devs.max() - devs.min()) / std)
        return np.mean(rs_vals) if rs_vals else np.nan

    cases = [
        (0.2, GREEN,  "H=0.2 (MR)"),
        (0.5, YELLOW, "H=0.5 (RW)"),
        (0.7, RED,    "H=0.7 (Trend)"),
    ]

    fig = go.Figure()
    for H, color, label in cases:
        series = np.diff(_fbm_ar1(n + 1, H, seed=99))
        rs = [compute_rs(series, lag) for lag in lags]
        valid = [(lags[i], rs[i]) for i in range(len(lags)) if not np.isnan(rs[i])]
        if len(valid) < 3:
            continue
        lx = np.log([v[0] for v in valid])
        ly = np.log([v[1] for v in valid])
        slope = np.polyfit(lx, ly, 1)[0]
        fig.add_trace(go.Scatter(
            x=lx, y=ly, mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=6, color=color),
            name=f"{label} (pente mesurée={slope:.2f})",
        ))
    fig.add_annotation(
        x=2.5, y=1.8,
        text="Pente = H\n← plus la pente est faible, plus le marche est MR",
        showarrow=False, font=dict(color=TEAL, size=10),
        bgcolor="rgba(0,0,0,0.5)",
    )
    fig.update_layout(
        height=420,
        title="Analyse R/S (Rescaled Range) — La pente = H",
        xaxis_title="log(tau) — taille de la fenetre",
        yaxis_title="log(R/S)",
        **DARK,
    )
    return fig


def hurst_mr_strategy():
    """Simulate the actual Hurst_MR strategy: OU process + bands + signals."""
    np.random.seed(42)
    n = 120   # 2h de barres M1

    # OU process (mean reverting par construction)
    theta, mu_ref, sigma_ou = 0.08, 24200.0, 8.0
    price = np.zeros(n)
    price[0] = mu_ref
    for i in range(1, n):
        price[i] = price[i-1] + theta * (mu_ref - price[i-1]) + np.random.randn() * sigma_ou

    LOOKBACK = 30
    BAND_K = 2.5
    means = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    for i in range(LOOKBACK, n):
        w = price[i - LOOKBACK:i]
        m, s = w.mean(), w.std()
        means[i] = m
        upper[i] = m + BAND_K * s
        lower[i] = m - BAND_K * s

    long_x, long_y, short_x, short_y = [], [], [], []
    tp_x, tp_y = [], []
    in_trade = None
    for i in range(LOOKBACK + 5, n):
        if np.isnan(means[i]):
            continue
        z = (price[i] - means[i]) / (price[i - LOOKBACK:i].std() or 1)
        if in_trade is None:
            if z < -BAND_K:
                long_x.append(i); long_y.append(price[i]); in_trade = ("long", i, means[i])
            elif z > BAND_K:
                short_x.append(i); short_y.append(price[i]); in_trade = ("short", i, means[i])
        else:
            direction, entry_i, tp_level = in_trade
            hit_tp = (direction == "long" and price[i] >= tp_level) or \
                     (direction == "short" and price[i] <= tp_level)
            if hit_tp:
                tp_x.append(i); tp_y.append(price[i]); in_trade = None

    x = list(range(n))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=upper, line=dict(color="rgba(255,51,102,0.5)", dash="dot", width=1.5),
                             name=f"+{BAND_K}σ (SHORT zone)"))
    fig.add_trace(go.Scatter(x=x, y=lower, line=dict(color="rgba(0,255,136,0.5)", dash="dot", width=1.5),
                             fill="tonexty", fillcolor="rgba(60,196,183,0.04)",
                             name=f"-{BAND_K}σ (LONG zone)"))
    fig.add_trace(go.Scatter(x=x, y=means, line=dict(color=TEAL, width=1.5, dash="dash"),
                             name="Fair Value (TP)"))
    fig.add_trace(go.Scatter(x=x, y=price, line=dict(color=YELLOW, width=2), name="MNQ M1"))
    if long_x:
        fig.add_trace(go.Scatter(x=long_x, y=[y * 0.9995 for y in long_y],
                                 mode="markers+text", text=["LONG"]*len(long_x),
                                 textposition="bottom center", textfont=dict(color=GREEN, size=9),
                                 marker=dict(symbol="triangle-up", size=14, color=GREEN),
                                 name="Signal LONG"))
    if short_x:
        fig.add_trace(go.Scatter(x=short_x, y=[y * 1.0005 for y in short_y],
                                 mode="markers+text", text=["SHORT"]*len(short_x),
                                 textposition="top center", textfont=dict(color=RED, size=9),
                                 marker=dict(symbol="triangle-down", size=14, color=RED),
                                 name="Signal SHORT"))
    if tp_x:
        fig.add_trace(go.Scatter(x=tp_x, y=tp_y,
                                 mode="markers", marker=dict(symbol="x", size=10, color=TEAL,
                                                              line=dict(color="white", width=1)),
                                 name="TP touche"))
    fig.update_layout(
        height=450,
        title="Hurst_MR — Strategie complete (session simule, H=0.2)",
        xaxis_title="Barres M1",
        yaxis_title="Prix MNQ",
        **DARK,
    )
    return fig


def hurst_edge_stats():
    """Simulate many sessions: show win-rate and PnL by H value."""
    np.random.seed(0)

    H_vals, pnl_vals, mr_vals, wr_vals = [], [], [], []
    for _ in range(300):
        H = np.random.uniform(0.25, 0.65)
        base_wr = 0.70 - 0.80 * (H - 0.25)   # wr: 70% at H=0.25, 30% at H=0.65
        n_trades = np.random.randint(2, 8)
        pnl = 0.0
        for _ in range(n_trades):
            win = np.random.rand() < base_wr
            pnl += (np.random.uniform(0.5, 2.5) if win else -np.random.uniform(0.5, 1.5))
        H_vals.append(H); pnl_vals.append(pnl)
        mr_vals.append(H < 0.45); wr_vals.append(base_wr)

    H_arr  = np.array(H_vals)
    pnl_arr = np.array(pnl_vals)
    mr_arr  = np.array(mr_vals)
    wr_arr  = np.array(wr_vals)

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["PnL par session vs H", "Win-rate moyen par regime"])

    # Scatter PnL vs H
    colors = [GREEN if r else RED for r in mr_arr]
    fig.add_trace(go.Scatter(
        x=H_arr, y=pnl_arr,
        mode="markers",
        marker=dict(color=colors, size=6, opacity=0.7),
        showlegend=False,
    ), row=1, col=1)
    fig.add_vline(x=0.45, line_dash="dash", line_color=TEAL, row=1, col=1)
    fig.add_annotation(x=0.45, y=pnl_arr.max() * 0.9,
                       text="Seuil 0.45", showarrow=True, arrowhead=1,
                       font=dict(color=TEAL, size=10), row=1, col=1)

    # Bar chart: avg win-rate MR vs Trend
    mr_wr = wr_arr[mr_arr].mean() * 100
    tr_wr = wr_arr[~mr_arr].mean() * 100
    fig.add_trace(go.Bar(
        x=["H < 0.45 (MR)", "H >= 0.45 (Trend)"],
        y=[mr_wr, tr_wr],
        marker_color=[GREEN, RED],
        text=[f"{mr_wr:.0f}%", f"{tr_wr:.0f}%"],
        textposition="outside",
        showlegend=False,
    ), row=1, col=2)
    fig.add_hline(y=50, line_dash="dash", line_color=YELLOW, annotation_text="50%", row=1, col=2)

    fig.update_layout(height=420, title="Edge Hurst_MR — PnL et win-rate par regime", **DARK)
    return fig


# ===================================================================
# 05d — GMM STICKY REGIME
# ===================================================================

def gmm_three_regimes():
    """Distribution des |returns| avec 3 composantes GMM."""
    np.random.seed(42)
    n_per = 2000
    sigs = [0.0005, 0.0015, 0.0040]
    labels = ["LOW (vol faible)", "MED (vol moyenne)", "HIGH (vol forte)"]
    colors = [TEAL, YELLOW, RED]
    x = np.linspace(0, 0.012, 400)
    fig = go.Figure()
    for sig, lbl, col in zip(sigs, labels, colors):
        pdf = np.exp(-0.5 * (x / sig) ** 2) / (sig * np.sqrt(2 * np.pi))
        fig.add_trace(go.Scatter(x=x, y=pdf, mode="lines", name=lbl,
                                 line=dict(color=col, width=2),
                                 fill="tozeroy",
                                 fillcolor=col.replace("#", "rgba(") + ",0.06)".replace("rgba(#", "rgba(")
                                 if col.startswith("#") else col))
    # Reformat fill with proper rgba
    fig.data[0].fillcolor = "rgba(60,196,183,0.06)"
    fig.data[1].fillcolor = "rgba(255,214,0,0.06)"
    fig.data[2].fillcolor = "rgba(255,51,102,0.06)"
    fig.update_layout(
        **DARK, height=340,
        title="GMM — 3 distributions de |returns| MNQ",
        xaxis=dict(**AXIS, title="|return| (log)"),
        yaxis=dict(**AXIS, title="Densite"),
    )
    return fig


def gmm_sticky_effect():
    """Regime brut vs regime sticky — effet lissant."""
    np.random.seed(7)
    n = 200
    # Regime bruité : alterne LOW/MED/HIGH
    raw = np.random.choice([0, 1, 2], size=n, p=[0.55, 0.30, 0.15])
    # Sticky : on reste en LOW tant que <5 barres consécutives non-LOW
    smoothed = raw.copy()
    streak = 0
    for i in range(1, n):
        if smoothed[i-1] == 0:
            if raw[i] != 0:
                streak += 1
                if streak < 5:
                    smoothed[i] = 0
                else:
                    streak = 0
            else:
                streak = 0
        else:
            streak = 0

    color_map = {0: TEAL, 1: YELLOW, 2: RED}
    t = np.arange(n)
    fig = make_subplots(rows=2, cols=1, subplot_titles=["Regime brut (oscille)", "Regime sticky (stable)"],
                        vertical_spacing=0.12)
    for row, arr in [(1, raw), (2, smoothed)]:
        colors_arr = [color_map[v] for v in arr]
        fig.add_trace(go.Bar(x=t, y=np.ones(n), marker_color=colors_arr,
                             showlegend=(row == 1), name="Regime",
                             marker_line_width=0), row=row, col=1)
    for row in [1, 2]:
        fig.update_yaxes(showticklabels=False, row=row, col=1)

    # Légende manuelle
    for lbl, col in [("LOW", TEAL), ("MED", YELLOW), ("HIGH", RED)]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                                 marker=dict(color=col, size=10, symbol="square"),
                                 name=lbl, showlegend=True))
    fig.update_layout(**DARK, height=340, title="Effet sticky_window=5 — stabilisation des regimes",
                      xaxis=dict(**AXIS, title="Barre"),
                      xaxis2=dict(**AXIS, title="Barre"))
    return fig


# ===================================================================
# 06c — DEMI-VIE OU
# ===================================================================

def halflife_phi_table():
    """Demi-vie en fonction de phi — courbe + zone valide."""
    phis = np.linspace(0.50, 0.999, 300)
    hls = -np.log(2) / np.log(phis)
    fig = go.Figure()
    # Zone valide (HL < 60)
    valid_mask = hls < 60
    fig.add_trace(go.Scatter(
        x=phis[valid_mask], y=hls[valid_mask],
        mode="lines", line=dict(color=TEAL, width=3), name="Zone valide (HL<60)"
    ))
    fig.add_trace(go.Scatter(
        x=phis[~valid_mask], y=hls[~valid_mask],
        mode="lines", line=dict(color=RED, width=2, dash="dot"), name="Trop lent"
    ))
    fig.add_hline(y=60, line=dict(color=YELLOW, dash="dash", width=1),
                  annotation_text="Seuil 60 barres", annotation_position="right")
    # Points remarquables
    for phi_pt, label in [(0.90, "phi=0.90\n7 barres"), (0.95, "phi=0.95\n14 barres"),
                           (0.98, "phi=0.98\n34 barres"), (0.99, "phi=0.99\n69 barres")]:
        hl_pt = -np.log(2) / np.log(phi_pt)
        fig.add_trace(go.Scatter(
            x=[phi_pt], y=[hl_pt], mode="markers+text",
            marker=dict(color=WHITE_50, size=9, symbol="circle"),
            text=[f"  {hl_pt:.0f}b"], textposition="middle right",
            showlegend=False,
        ))
    fig.update_layout(
        **DARK, height=360,
        title="Demi-vie OU en fonction de phi (AR1)",
        xaxis=dict(**AXIS, title="phi (persistance AR1)", range=[0.49, 1.0]),
        yaxis=dict(**AXIS, title="Demi-vie (barres M1)", range=[0, 150]),
    )
    return fig


def halflife_reversion_paths():
    """Simulation de reversion à différentes vitesses (phi=0.90/0.95/0.99)."""
    np.random.seed(3)
    n = 80
    t = np.arange(n)
    start_dev = 3.0   # prix à 3σ de FV
    phis = [0.90, 0.95, 0.99]
    cols = [TEAL, YELLOW, RED]
    lbls = ["phi=0.90 — rapide", "phi=0.95 — normal", "phi=0.99 — lent"]
    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color=WHITE_50, dash="dash", width=1),
                  annotation_text="Fair Value")
    fig.add_hline(y=2.5, line=dict(color=YELLOW, dash="dot", width=1),
                  annotation_text="Bande +2.5σ")
    for phi, col, lbl in zip(phis, cols, lbls):
        path = np.zeros(n)
        path[0] = start_dev
        for i in range(1, n):
            path[i] = phi * path[i-1] + np.random.normal(0, 0.15)
        fig.add_trace(go.Scatter(x=t, y=path, mode="lines", name=lbl,
                                 line=dict(color=col, width=2)))
    fig.update_layout(
        **DARK, height=340,
        title="Reversion vers FV — 3 vitesses (signal entre a la barre 0)",
        xaxis=dict(**AXIS, title="Barres M1 apres le signal"),
        yaxis=dict(**AXIS, title="Deviation (sigma)"),
    )
    return fig


# ===================================================================
# 06d — CONFIRMATION DE REVERSION
# ===================================================================

def confirmation_scenario():
    """Deux scenarios : avec et sans confirmation."""
    np.random.seed(12)
    n = 40
    t = np.arange(n)

    # Scenario 1 : prix va plus loin avant de revenir (sans confirmation → loss)
    path_no = np.zeros(n)
    path_no[:5] = np.linspace(0, 3.5, 5)
    path_no[5:15] = np.linspace(3.5, 4.2, 10)   # continue de monter (SL)
    path_no[15:] = np.linspace(4.2, 0.5, 25)     # revient trop tard

    # Scenario 2 : prix confirme et revient vite (avec confirmation → win)
    path_ok = np.zeros(n)
    path_ok[:5] = np.linspace(0, 3.5, 5)
    path_ok[5] = 3.2          # barre de confirmation : deja en reversion
    path_ok[6:] = np.linspace(3.0, 0.2, n - 6) + np.random.normal(0, 0.15, n - 6)

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["SANS confirmation — SL souvent touche",
                                        "AVEC confirmation — TP atteint"])
    # Scenario sans confirmation
    for i, (path, col_line) in enumerate([(path_no, RED), (path_ok, TEAL)], 1):
        fig.add_trace(go.Scatter(x=t, y=path, mode="lines",
                                 line=dict(color=col_line, width=2), showlegend=False), row=1, col=i)
        fig.add_hline(y=2.5, line=dict(color=YELLOW, dash="dash", width=1),
                      annotation_text="Signal k=2.5σ", row=1, col=i)
        fig.add_hline(y=0, line=dict(color=WHITE_50, dash="dot", width=1),
                      annotation_text="FV (TP)", row=1, col=i)

    # Marqueurs entrée
    fig.add_trace(go.Scatter(
        x=[5], y=[path_no[5]], mode="markers",
        marker=dict(color=RED, size=12, symbol="x"),
        name="Entree sans confirm", showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=[6], y=[path_ok[6]], mode="markers",
        marker=dict(color=TEAL, size=12, symbol="triangle-up"),
        name="Entree avec confirm", showlegend=False,
    ), row=1, col=2)

    fig.update_layout(**DARK, height=340,
                      title="Confirmation de reversion — impact sur le timing d'entree")
    for col in [1, 2]:
        fig.update_xaxes(dict(**AXIS, title="Barres apres detection"), row=1, col=col)
        fig.update_yaxes(dict(**AXIS, title="Deviation (sigma)"), row=1, col=col)
    return fig


def confirmation_winrate_impact():
    """Bar chart : WR et EV avec/sans confirmation."""
    categories = ["Sans confirmation", "Avec confirmation"]
    wr_vals = [42, 52]
    ev_vals = [10.3, 18.4]
    trades = [1095, 876]

    fig = make_subplots(rows=1, cols=3,
                        subplot_titles=["Win Rate (%)", "EV par trade (pts)", "Nb trades/an"])
    colors_pair = [RED, TEAL]
    for col, (vals, fmt) in enumerate([(wr_vals, "{:.0f}%"), (ev_vals, "{:.1f}"), (trades, "{:.0f}")], 1):
        fig.add_trace(go.Bar(
            x=categories, y=vals,
            marker_color=colors_pair,
            text=[fmt.format(v) for v in vals],
            textposition="outside",
            showlegend=False,
        ), row=1, col=col)
    fig.update_layout(**DARK, height=320,
                      title="Impact du filtre confirmation sur l'edge (backtest 5 ans MNQ)")
    for col in [1, 2, 3]:
        fig.update_yaxes(dict(**AXIS), row=1, col=col)
        fig.update_xaxes(dict(**AXIS), row=1, col=col)
    return fig


# ===================================================================
# 08 — KELLY CRITERION
# ===================================================================

def kelly_sizing_curve():
    """Fraction Kelly optimale en fonction du WR et du ratio R:R."""
    wrs = np.linspace(0.30, 0.70, 200)
    rr_ratios = [1.5, 2.0, 2.5, 3.0]
    cols_kelly = [RED, YELLOW, TEAL, GREEN]
    fig = go.Figure()
    for rr, col in zip(rr_ratios, cols_kelly):
        # Kelly = p - (1-p)/b   où b = gain/loss ratio
        k = wrs - (1 - wrs) / rr
        k = np.clip(k, 0, 1)
        fig.add_trace(go.Scatter(x=wrs * 100, y=k * 100, mode="lines",
                                 name=f"R:R = {rr:.1f}",
                                 line=dict(color=col, width=2)))
    # Marquer position Hurst_MR (WR=52%, RR~2.5)
    k_hurst = 0.52 - 0.48 / 2.5
    fig.add_trace(go.Scatter(
        x=[52], y=[k_hurst * 100],
        mode="markers+text",
        marker=dict(color=WHITE_50, size=14, symbol="star"),
        text=["  Hurst_MR\n  validé"],
        textfont=dict(color=WHITE_50, size=10),
        showlegend=False,
    ))
    fig.add_vline(x=50, line=dict(color=WHITE_50, dash="dot", width=1),
                  annotation_text="WR=50%")
    fig.update_layout(
        **DARK, height=360,
        title="Fraction Kelly (%) — WR vs ratio gain/perte",
        xaxis=dict(**AXIS, title="Win Rate (%)"),
        yaxis=dict(**AXIS, title="Kelly optimal (% du capital)"),
    )
    return fig


def kelly_fractional_growth():
    """Croissance du capital selon la fraction f du Kelly (f=full/half/quarter)."""
    np.random.seed(42)
    n_trades = 300
    wr = 0.52
    rr = 2.5
    k_full = wr - (1 - wr) / rr
    fractions = [k_full, k_full / 2, k_full / 4, 0.01]
    labels = ["Full Kelly", "Half Kelly", "Quarter Kelly", "1% fixe"]
    cols_f = [RED, YELLOW, TEAL, GREEN]

    outcomes = np.where(np.random.rand(n_trades) < wr, 1, -1 / rr)
    fig = go.Figure()
    for f, lbl, col in zip(fractions, labels, cols_f):
        capital = np.ones(n_trades + 1)
        for i, r in enumerate(outcomes):
            mult = 1 + f * r if r > 0 else 1 - f / rr
            capital[i + 1] = capital[i] * (1 + f * r)
        fig.add_trace(go.Scatter(
            y=capital, mode="lines", name=lbl,
            line=dict(color=col, width=2)
        ))
    fig.update_layout(
        **DARK, height=340,
        title=f"Croissance capital — fractions Kelly (WR={wr:.0%}, R:R={rr})",
        xaxis=dict(**AXIS, title="Trades"),
        yaxis=dict(**AXIS, title="Capital (normalise)"),
    )
    return fig


# ===================================================================
# 09 — BACKTESTING PITFALLS
# ===================================================================

def pitfall_lookahead_bias():
    """Simulation : strategie avec et sans look-ahead bias."""
    np.random.seed(8)
    n = 100
    t = np.arange(n)
    # Prix aléatoire
    price = 100 + np.cumsum(np.random.normal(0, 1, n))
    # Signal SANS bias : moyenne sur passé seulement
    ma_true = np.array([price[max(0, i-20):i].mean() if i > 0 else price[0] for i in range(n)])
    # Signal AVEC look-ahead : utilise les 10 prochaines barres aussi
    ma_biased = np.array([price[max(0, i-10):min(n, i+10)].mean() for i in range(n)])

    equity_clean = np.zeros(n)
    equity_biased = np.zeros(n)
    pos_clean = pos_biased = 0
    for i in range(1, n):
        sig_c = 1 if price[i-1] > ma_true[i-1] else -1
        sig_b = 1 if price[i-1] > ma_biased[i-1] else -1
        ret = price[i] - price[i-1]
        equity_clean[i] = equity_clean[i-1] + sig_c * ret
        equity_biased[i] = equity_biased[i-1] + sig_b * ret

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=equity_biased, name="Avec look-ahead bias",
                             line=dict(color=GREEN, width=2)))
    fig.add_trace(go.Scatter(x=t, y=equity_clean, name="Reel (sans bias)",
                             line=dict(color=RED, width=2)))
    fig.add_hline(y=0, line=dict(color=WHITE_50, dash="dot", width=1))
    fig.update_layout(
        **DARK, height=320,
        title="Look-ahead bias — l'equity parfaite qui disparait en live",
        xaxis=dict(**AXIS, title="Trades"),
        yaxis=dict(**AXIS, title="P&L cumule"),
    )
    return fig


def pitfall_overfitting_curves():
    """In-sample parfait vs out-of-sample catastrophique."""
    np.random.seed(5)
    n = 200
    split = 100
    t = np.arange(n)
    # Vrai processus : léger drift positif
    true_returns = np.random.normal(0.05, 1.0, n)
    # Overfit in-sample : optimise sur les 100 premières barres (parait parfait)
    equity_is = np.cumsum(np.abs(true_returns[:split]))  # toujours positif (triché)
    # OOS : performance réelle aléatoire
    equity_oos = np.cumsum(true_returns[split:])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t[:split], y=equity_is, name="In-sample (optimise)",
                             line=dict(color=GREEN, width=2)))
    fig.add_trace(go.Scatter(x=t[split:], y=equity_oos + equity_is[-1],
                             name="Out-of-sample (reel)",
                             line=dict(color=RED, width=2)))
    fig.add_vline(x=split, line=dict(color=YELLOW, dash="dash", width=2),
                  annotation_text="  Split IS/OOS", annotation_position="top right")
    fig.add_hline(y=0, line=dict(color=WHITE_50, dash="dot", width=1))
    fig.update_layout(
        **DARK, height=320,
        title="Overfitting — curve-fitted in-sample vs reel en OOS",
        xaxis=dict(**AXIS, title="Barres"),
        yaxis=dict(**AXIS, title="P&L cumule"),
    )
    return fig


# ===================================================================
# 09b — PROFITABLE VS TRADABLE
# ===================================================================

def tradable_slippage_impact():
    """Impact du slippage sur le profit factor selon le nb de trades."""
    slip_range = np.linspace(0, 3.0, 100)  # pts de slippage par trade
    avg_trade_pnl = 6.0    # gain moyen par trade avant slippage (pts)
    n_trades = 1095

    pf_raw = 2.03
    fig = go.Figure()
    # PF degradé par slippage
    pf_adj = np.clip(pf_raw - slip_range / avg_trade_pnl * pf_raw, 0.5, pf_raw)
    fig.add_trace(go.Scatter(
        x=slip_range, y=pf_adj,
        mode="lines", line=dict(color=TEAL, width=2), name="PF ajuste slippage"
    ))
    fig.add_hline(y=1.0, line=dict(color=RED, dash="dash", width=1),
                  annotation_text="PF=1 (breakeven)")
    fig.add_hline(y=1.5, line=dict(color=YELLOW, dash="dot", width=1),
                  annotation_text="PF=1.5 (min viable)")
    fig.add_vline(x=0.5, line=dict(color=GREEN, dash="dot", width=1),
                  annotation_text="  0.5pts (MNQ typique)")
    fig.update_layout(
        **DARK, height=320,
        title="Slippage vs Profit Factor — quand la strategie devient non-tradable",
        xaxis=dict(**AXIS, title="Slippage par trade (pts MNQ)"),
        yaxis=dict(**AXIS, title="Profit Factor", range=[0.5, 2.2]),
    )
    return fig


def tradable_regime_drift():
    """Walk-forward : performance par fenêtre de 6 mois — détection de drift."""
    np.random.seed(21)
    n_windows = 10
    windows = [f"W{i+1}" for i in range(n_windows)]
    # Simulate: bon régime pendant 6 fenêtres, drift ensuite
    pfs = np.array([2.1, 2.3, 1.9, 2.0, 2.2, 1.8, 1.4, 1.1, 0.9, 0.8])
    shs = np.array([2.4, 2.6, 2.1, 2.3, 2.5, 1.9, 1.5, 1.0, 0.7, 0.5])

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["Profit Factor par fenetre 6 mois",
                                        "Sharpe par fenetre 6 mois"])
    colors_wf = [GREEN if p > 1.5 else YELLOW if p > 1.0 else RED for p in pfs]
    fig.add_trace(go.Bar(x=windows, y=pfs, marker_color=colors_wf,
                         text=[f"{p:.1f}" for p in pfs],
                         textposition="outside", showlegend=False), row=1, col=1)
    fig.add_hline(y=1.5, line=dict(color=YELLOW, dash="dash", width=1), row=1, col=1)

    colors_sh = [GREEN if s > 1.5 else YELLOW if s > 1.0 else RED for s in shs]
    fig.add_trace(go.Bar(x=windows, y=shs, marker_color=colors_sh,
                         text=[f"{s:.1f}" for s in shs],
                         textposition="outside", showlegend=False), row=1, col=2)
    fig.add_hline(y=1.5, line=dict(color=YELLOW, dash="dash", width=1), row=1, col=2)

    fig.update_layout(
        **DARK, height=340,
        title="Walk-forward — detection de drift du regime (re-optimisation necessaire apres W6)",
    )
    return fig


# ── Chart registry ──────────────────────────────────────────────────
CHARTS = {
    "00b_retail_vs_institutional.md": [
        ("Market-Making sim", retail_market_making_sim),
        ("Adverse Selection", retail_adverse_selection),
    ],
    "01_time_series.md": [
        ("Decomposition", ts_decomposition),
        ("Moving Averages vs EMA", ts_moving_averages),
        ("Cone de prevision", ts_forecast_cone),
    ],
    "02_central_limit_theorem.md": [
        ("Des vers Gaussienne (CLT)", clt_dice_demo),
        ("Confiance vs Nb de trades", clt_trading_confidence),
    ],
    "02b_asymptotics.md": [
        ("LGN : convergence de la moyenne", asymp_lln_convergence),
        ("Vitesse 1/sqrt(n)", asymp_convergence_speed),
        ("Incertitude du Sharpe", asymp_sharpe_uncertainty),
        ("Consistance des estimateurs", asymp_estimator_comparison),
    ],
    "03b_monte_carlo.md": [
        ("Convergence du de", mc_dice_convergence),
        ("Parcours de richesse", mc_wealth_paths),
        ("Precision vs n", mc_precision),
    ],
    "03_ergodicity.md": [
        ("g = E[r] - sigma2/2", ergo_variance_drag),
        ("Kelly Criterion", ergo_kelly_sizing),
    ],
    "04_garch.md": [
        ("Clustering de volatilite", garch_volatility_clustering),
        ("Propagation d un choc", garch_step_by_step),
        ("VaR Naive vs GARCH", garch_var_comparison),
    ],
    "04b_trading_metrics.md": [
        ("Piege du winrate", metrics_winrate_trap),
        ("Test de stabilite", metrics_stability_test),
        ("Random walks : le hasard a l air bon", metrics_random_walk_best),
    ],
    "05_hidden_markov_models.md": [
        ("Distributions par regime", hmm_regime_distributions),
        ("Prix colore par regime", hmm_regime_price_colored),
        ("Matrice de transition", hmm_transition_heatmap),
    ],
    "05b_regime_switching.md": [
        ("Filtrage bayesien live", regime_bayesian_filtering),
    ],
    "05c_hawkes.md": [
        ("Hawkes : intensite self-exciting", hawkes_intensity),
        ("Poisson vs Hawkes", hawkes_vs_poisson),
    ],
    "06_kalman_filter.md": [
        ("Kalman Filter complet", kalman_filter_demo),
        ("Le Gain K explique", kalman_gain_explained),
        ("Impact de R", kalman_R_comparison),
    ],
    "06b_kalman_mean_reversion.md": [
        ("OU Process : mean reversion", ou_mean_reversion_sim),
        ("Kalman vs Fixed Mean", kalman_vs_fixed_mean),
        ("Le piege du biais", mean_reversion_trap),
    ],
    "07_pipeline_integration.md": [
        ("Matrice de decision", pipeline_decision_matrix),
        ("Pipeline complet", pipeline_full_simulation),
    ],
    "25_hurst_mr.md": [
        ("Empirical vs Theoretical Covariance fBm", hurst_covariance_heatmap),
        ("Edge stats — PnL et win-rate par regime", hurst_edge_stats),
    ],
    "05d_gmm_regime.md": [
        ("3 regimes GMM — distributions des |returns|", gmm_three_regimes),
        ("Effet sticky_window — stabilisation des regimes", gmm_sticky_effect),
    ],
    "06c_halflife_ou.md": [
        ("Demi-vie vs phi — zone valide", halflife_phi_table),
        ("Reversion a 3 vitesses (phi=0.90/0.95/0.99)", halflife_reversion_paths),
    ],
    "06d_confirmation_reversal.md": [
        ("Confirmation — 2 scenarios (avec/sans)", confirmation_scenario),
        ("Impact winrate/EV du filtre confirmation", confirmation_winrate_impact),
    ],
    "08_kelly_criterion.md": [
        ("Kelly optimal — WR vs ratio gain/perte", kelly_sizing_curve),
        ("Croissance capital — fractions du Kelly", kelly_fractional_growth),
    ],
    "09_backtesting_pitfalls.md": [
        ("Look-ahead bias — equity parfaite vs reelle", pitfall_lookahead_bias),
        ("Overfitting — in-sample vs out-of-sample", pitfall_overfitting_curves),
    ],
    "09b_profitable_vs_tradable.md": [
        ("Slippage vs Profit Factor", tradable_slippage_impact),
        ("Walk-forward — detection de drift", tradable_regime_drift),
    ],
}

# Inline charts: injected directly in markdown content via <!-- CHART:name --> markers
INLINE_CHARTS = {
    "ergo_ensemble_illusion": ergo_ensemble_illusion,
    "ergo_multiplicative_vs_additive": ergo_multiplicative_vs_additive,
    "ergo_kelly_impact_sim": ergo_kelly_impact_sim,
    # Hurst MR — inline dans les tabs
    "hurst_regime_spectrum":    hurst_regime_spectrum,
    "hurst_session_visual":     hurst_session_visual,
    "hurst_fbm_paths":          hurst_fbm_paths,
    "hurst_covariance_heatmap": hurst_covariance_heatmap,
    "hurst_rs_analysis":        hurst_rs_analysis,
    "hurst_mr_strategy":        hurst_mr_strategy,
}
