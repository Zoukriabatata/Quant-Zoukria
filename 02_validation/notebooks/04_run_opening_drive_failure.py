# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#     text_representation:
#       extension: .py
#       format_name: percent
# ---

# %% [markdown]
# # Gauntlet — Hypothèse #1 : Opening Drive Failure Fade (MNQ)
#
# Lance le gauntlet complet (`run_gauntlet`) sur la première vraie hypothèse de
# recherche d'edge. Contrairement à la calibration, on NE connaît PAS la réponse —
# le gauntlet tranche GO / NO-GO / CONDITIONAL.
#
# Spec : `docs/superpowers/specs/2026-05-15-opening-drive-failure-fade-design.md`
#
# **Exécuter depuis la racine du repo** (`python 02_validation/notebooks/04_run_opening_drive_failure.py`).
# Charge le CSV Databento MNQ 5 ans (~1.7M lignes) — compter plusieurs minutes.

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
from gauntlet.hypotheses.hyp_opening_drive_failure import HYP_OPENING_DRIVE_FAILURE

OUT_DIR = _VALIDATION / "outputs" / "gauntlet" / HYP_OPENING_DRIVE_FAILURE.name
OUT_DIR.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Lancement du gauntlet
#
# `run_gauntlet` charge les vraies données MNQ, prépare les splits, lance la batterie
# (walk-forward, CPCV, DSR, PBO, Monte Carlo, stress test, cycle PA) et agrège le verdict.

# %%
print("=" * 72)
print(f"GAUNTLET — {HYP_OPENING_DRIVE_FAILURE.name}")
print("=" * 72)

verdict = run_gauntlet(HYP_OPENING_DRIVE_FAILURE, splits=None, out_dir=str(OUT_DIR))

print(f"\n  VERDICT     : {verdict.verdict}")
print(f"  hard fails  : {[c.name for c in verdict.hard_fails]}")
print("\n  Critères :")
for c in verdict.criteria:
    mark = "OK  " if c.passed else "FAIL"
    print(f"    [{mark}] {c.name:18} = {c.value}")
print("\n  Caveats :")
for cav in verdict.caveats:
    print(f"    - {cav}")
print("\n  Next steps :")
for step in verdict.next_steps:
    print(f"    - {step}")
print(f"\n  Rapport complet : {OUT_DIR / 'gauntlet_report.md'}")

# %% [markdown]
# ## Lecture du verdict
#
# - **GO** → cross-validation NT8 Strategy Analyzer + sim live ≥ 2 semaines (next steps).
# - **NO-GO / CONDITIONAL** → résultat honnête. Relire les critères échoués, décider :
#   raffiner (ex. news blackout contre le momentum-flip) ou pivoter sur une autre thèse.
#   Vu la prudence de la littérature, un NO-GO est un résultat probable — et c'est le
#   process qui marche, pas un échec.

# %%
print("\nRun terminé. Verdict ci-dessus, rapport détaillé dans le dossier outputs.")
