# Sprint 1 — Multi-Backtest v10 Foundation

**Date** : 2026-05-13
**Univers** : MNQ M1 Databento, 1259 jours, 61 mois (avril 2021 → avril 2026)
**Configs testées** : 7 (C0 baseline + 6 combinaisons des 3 hooks Sprint 1)
**Runtime** : 522s (8min42s)

## Modules livrés en TDD strict

| Module | Source académique | Tests | Status |
|--------|-------------------|:---:|:---:|
| Lee-Mykland Jump Detection | Lee & Mykland 2008, RFS 21(6) | 10 ✓ | LIVRÉ |
| HAR-RV Vol Forecast | Corsi 2009, JFE 7(2) | 12 ✓ | LIVRÉ |
| Grossman-Zhou DD Sizing | Grossman & Zhou 1993, Math Finance | 13 ✓ | LIVRÉ |

**35 tests, 100% passing.** Discipline RED → GREEN → REFACTOR respectée.

## Résultats 5 ans MNQ

| Config | PnL | PF | Sharpe | DD max | % mois + | Trades |
|--------|------|------|--------|--------|----------|--------|
| C0 baseline | $323,471 | 2.24 | 3.31 | $2,586 | 96.7% | 3,231 |
| **C1 jump filter** ★ | **$317,782** | **2.27** | **3.45** | **$2,196** | **98.4%** | 3,116 |
| C2 HAR+GZ | $282,999 | 2.19 | 3.06 | $4,282 | 85.2% | 2,539 |
| C3 GZ only | $303,775 | 2.28 | 3.11 | $4,282 | 85.2% | 2,528 |
| C6 jump+HAR+GZ | $306,779 | 2.24 | 3.23 | $3,473 | 88.5% | 2,666 |
| C7 jump+GZ | $324,258 | 2.33 | 3.25 | $3,473 | 88.5% | 2,649 |
| C_S1_full | $306,779 | 2.24 | 3.23 | $3,473 | 88.5% | 2,666 |

★ Gagnant Sprint 1 : C1 jump filter seul.

## Conclusions

### Le jump filter Lee-Mykland est Pareto-dominant
- Sharpe +4.2% (3.31 → 3.45)
- DD -15.1% ($2,586 → $2,196)
- % mois positifs +1.7pt (96.7% → 98.4%)
- PnL -1.8% (acceptable trade-off)

### Le Grossman-Zhou dans sa forme actuelle est CONTRE-PRODUCTIF
- Toutes les configs avec GZ ont DD ≥ $3,473 (vs $2,586 baseline)
- Cause : µ_excess / (γ σ²) ≈ 30 → GZ recommande toujours max_contracts
- GZ est moins conservateur que le sizing v9 natif qui shrink déjà à dd_used > $1000
- **Action Sprint 2** : implémenter la forme adaptative
  `contracts_v10 = contracts_v9 × (W_t - αM_t)/((1-α)M_t)`

### Caveat sur la reproduction v9 baseline
Le C0 baseline ne reproduit pas exactement les chiffres v9 champion (Sharpe 3.31 vs 4.82, DD $2,586 vs $1,245). Hypothèse principale : **différence de définition DD** (global cumsum vs intra-mois). À investiguer en Sprint 1 cleanup.

## Décisions prises

| Item | Décision | Justification |
|------|----------|---------------|
| Lee-Mykland jump filter | **VALIDÉ pour Sprint 4 → prod** | Gain Pareto sur 5y |
| Grossman-Zhou pur | **REJETÉ, à recalibrer** | DD x1.7 vs baseline |
| HAR-RV | **À retester après fix GZ** | Effet non isolable |

## Prochaines étapes

1. **Sprint 1 cleanup** : aligner métrique DD sur définition Apex intra-mois (1-2j)
2. **Sprint 2** : Cartea-Figueroa MRJD + MF-DFA + GZ adaptatif recalibré (3-4j)
3. **Sprint 3** : Copula pairs ES/NQ avec données Databento déjà disponibles (2-3j)
4. **Sprint 4** : Validation CPCV + Deflated Sharpe + PBO sur toutes les configs gagnantes (2j)
