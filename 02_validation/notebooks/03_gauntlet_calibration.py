# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#     text_representation:
#       extension: .py
#       format_name: percent
# ---

# %% [markdown]
# # Gauntlet — Calibration known-answer
#
# Lance le gauntlet complet (`run_gauntlet`) sur les 2 hypothèses contrôle :
# **v9 HurstMR** et **EOD reversal**. Les deux sont connues-mortes — elles DOIVENT
# ressortir **NO-GO**. Si l'une sort GO ou CONDITIONAL, le gauntlet est cassé ou mal
# calibré : STOP, investiguer avant de faire confiance à un verdict.
#
# Spec : `docs/superpowers/specs/2026-05-14-gauntlet-validation-design.md` (section Calibration).
#
# **Exécuter depuis la racine du repo** (`python 02_validation/notebooks/03_gauntlet_calibration.py`).
# Charge le CSV Databento MNQ 5 ans (~1.7M lignes) + Hurst rolling — compter plusieurs minutes.

# %%
from __future__ import annotations

import sys
from pathlib import Path

# Console Windows cp1252 ne peut pas imprimer les emojis — forcer UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ce script tourne depuis la racine du repo. 02_validation/ et 01_research/ sur le path.
_REPO_ROOT = Path(".").resolve()
_VALIDATION = _REPO_ROOT / "02_validation"
_RESEARCH = _REPO_ROOT / "01_research"
if not _VALIDATION.is_dir() or not _RESEARCH.is_dir():
    raise RuntimeError(
        f"02_validation/ ou 01_research/ introuvable depuis {_REPO_ROOT}. "
        "Lancer ce script depuis la racine du repo."
    )
for p in (str(_VALIDATION), str(_RESEARCH)):
    if p not in sys.path:
        sys.path.insert(0, p)

from gauntlet.run_gauntlet import run_gauntlet
from gauntlet.calibration.hyp_eod_reversal import HYP_EOD_REVERSAL
from gauntlet.calibration.hyp_v9_hurstmr import HYP_V9_HURSTMR

OUT_BASE = _VALIDATION / "outputs" / "gauntlet"
OUT_BASE.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Lancement du gauntlet sur les 2 contrôles
#
# `run_gauntlet` charge les vraies données, prépare les splits, lance la batterie complète
# (walk-forward, CPCV, DSR, PBO, Monte Carlo, stress test, cycle PA) et agrège le verdict.

# %%
CONTROLS = [HYP_V9_HURSTMR, HYP_EOD_REVERSAL]
verdicts = {}

for hyp in CONTROLS:
    print("=" * 72)
    print(f"GAUNTLET — {hyp.name}")
    print("=" * 72)
    out_dir = OUT_BASE / hyp.name
    verdict = run_gauntlet(hyp, splits=None, out_dir=str(out_dir))
    verdicts[hyp.name] = verdict
    print(f"  verdict     : {verdict.verdict}")
    print(f"  hard fails  : {[c.name for c in verdict.hard_fails]}")
    for c in verdict.criteria:
        mark = "OK " if c.passed else "FAIL"
        print(f"    [{mark}] {c.name:18} = {c.value}")
    print(f"  rapport     : {out_dir / 'gauntlet_report.md'}")
    print()

# %% [markdown]
# ## Vérification known-answer
#
# Les 2 contrôles DOIVENT ressortir NO-GO. C'est le test d'intégration du build.

# %%
for name, verdict in verdicts.items():
    assert verdict.verdict == "NO-GO", (
        f"CALIBRATION ÉCHOUÉE : {name} ressort {verdict.verdict}, attendu NO-GO. "
        f"Le gauntlet est cassé ou mal calibré — investiguer avant de faire confiance "
        f"à un verdict. Hard fails détectés : {[c.name for c in verdict.hard_fails]}"
    )
    print(f"OK — {name} : NO-GO (calibration confirmée)")

print()
print("=" * 72)
print("GAUNTLET CALIBRÉ — les 2 contrôles known-dead ressortent bien NO-GO.")
print("Le gauntlet est prêt à juger une vraie hypothèse de recherche (cycle suivant).")
print("=" * 72)
