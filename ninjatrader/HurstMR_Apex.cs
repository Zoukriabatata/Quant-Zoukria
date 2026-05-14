#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Strategies;
#endregion

/*
 * HurstMR_Apex — Strategie Full Auto NinjaTrader / Rithmic
 * =========================================================
 * Edge    : Hurst < 0.53 (regime MR confirme) + Z-score +-3sigma (entree)
 * TP      : Fair Value = rolling mean 30 barres
 * SL      : max(3.0, 0.75 x std), capped a 20.0
 * Cible   : Apex Trader Funding $50k EOD
 *
 * SIZING : Kelly fractionnel cappe Apex (identique au backtest)
 *   contracts = min(MAX_APEX, int(RiskPct x DD_restant / (SL_pts x TickValue)))
 *   - Agressif en debut de challenge (DD intact = plus de contrats)
 *   - Conservateur si DD se remplit (moins de contrats = protection automatique)
 *   - Cap dur : 6 MNQ eval / 4 MNQ PA / configurable
 *
 * Backtest valide (JSON 2026-04-20) :
 *   PF=1.88 x Sharpe=3.13 x MaxDD=3.81% x WR=30.0% x 1530 trades / 5 ans
 *   PnL total backtest Kelly pur : ~$145,751
 *   Params : H=0.53 x win=60 x lb=30 x k=3.0 x sl=0.75 x tp=0.0 x slip=0.5
 *
 * Regles Apex integrees :
 *   - Flat obligatoire a 21h59 Paris (15h59 NY)
 *   - Pas de nouvelle entree apres 21h55 Paris
 *   - Daily loss limit $1,000 -> arret immediat
 *   - Max 5 trades/jour
 *   - Safety net DD : buffer < $150 vs seuil Apex -> arret
 *   - Anti double-position native NinjaTrader
 *
 * LOGIQUE IDENTIQUE BACKTEST (backtest_hurst.py) :
 *   - Hurst : 12 lags log-espaces [4..min(window/2,50)], methode chunks, ddof=0
 *   - Z-score : fenetre [Close[1]..Close[Lookback]] (barre courante EXCLUE)
 *   - SL : max(3.0, SlMult x std), min(..., 20.0)
 *   - Tick value : $2 par point MNQ
 */

namespace NinjaTrader.NinjaScript.Strategies
{
    public class HurstMR_Apex : Strategy
    {
        // ===================================================================
        // PARAMETRES — modifiables depuis l'UI NinjaTrader
        // ===================================================================

        // ── Signal ──────────────────────────────────────────────────────────
        [NinjaScriptProperty]
        [Range(0.01, 1.0)]
        [Display(Name = "Hurst Seuil", Description = "H < seuil -> regime MR", Order = 1, GroupName = "Signal")]
        public double HurstThreshold { get; set; }

        [NinjaScriptProperty]
        [Range(20, 200)]
        [Display(Name = "Hurst Window (barres)", Description = "Fenetre rolling Hurst R/S", Order = 2, GroupName = "Signal")]
        public int HurstWindow { get; set; }

        [NinjaScriptProperty]
        [Range(10, 100)]
        [Display(Name = "Lookback Bandes (barres)", Description = "Fenetre rolling mean/std", Order = 3, GroupName = "Signal")]
        public int Lookback { get; set; }

        [NinjaScriptProperty]
        [Range(1.0, 5.0)]
        [Display(Name = "Band K (sigma)", Description = "Seuil Z-score entree", Order = 4, GroupName = "Signal")]
        public double BandK { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 3.0)]
        [Display(Name = "SL Mult", Description = "SL = max(3.0, SL_Mult x std), capped a 20.0", Order = 5, GroupName = "Signal")]
        public double SlMult { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 2.0)]
        [Display(Name = "TP Overshoot (sigma)", Description = "0 = fair value pure · 0.50 = config champion", Order = 6, GroupName = "Signal")]
        public double TpOvershoot { get; set; }

        [NinjaScriptProperty]
        [Range(15, 300)]
        [Display(Name = "Timeout (barres M1)", Description = "Liquidation mark-to-market si ni TP ni SL touche apres N barres (champion = 120)", Order = 7, GroupName = "Signal")]
        public int TimeoutBars { get; set; }

        // ── Trail MR/Trend ───────────────────────────────────────────────────
        [NinjaScriptProperty]
        [Display(Name = "Trail MR/Trend (ON/OFF)", Description = "Si ON : stop deplace a FV quand prix franchit FV + H trending", Order = 1, GroupName = "Trail")]
        public bool TrailEnabled { get; set; }

        [NinjaScriptProperty]
        [Range(0.40, 0.60)]
        [Display(Name = "Seuil H activation trail", Description = "H > seuil → regime trending → trail actif (optimal backtest = 0.45)", Order = 2, GroupName = "Trail")]
        public double TrailHThresh { get; set; }

        // ── Sizing Kelly ─────────────────────────────────────────────────────
        [NinjaScriptProperty]
        [Range(0.01, 0.50)]
        [Display(Name = "Kelly Risk % / trade", Description = "% du DD restant risque par trade (champion v9 = 0.12 → DD 2.49%)", Order = 7, GroupName = "Sizing Kelly")]
        public double KellyRiskPct { get; set; }

        [NinjaScriptProperty]
        [Range(1, 40)]
        [Display(Name = "Contrats max Eval (cap Apex)", Description = "12 MNQ champion v9 · Apex permet jusqu'a 40", Order = 8, GroupName = "Sizing Kelly")]
        public int MaxContractsEval { get; set; }

        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Contrats max PA (cap Apex)", Description = "4 MNQ en debut PA / 2 avant safety net", Order = 9, GroupName = "Sizing Kelly")]
        public int MaxContractsPA { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Mode PA (vs Eval)", Description = "ON = plafond PA actif (moins de contrats)", Order = 10, GroupName = "Sizing Kelly")]
        public bool ModePA { get; set; }

        // ── Backtest mode (Strategy Analyzer) ────────────────────────────────
        [NinjaScriptProperty]
        [Display(Name = "Enable in Backtest (Strategy Analyzer)", Description = "ON = trade sur barres historiques. OFF = live uniquement (defaut pour prod).", Order = 11, GroupName = "Sizing Kelly")]
        public bool EnableInBacktest { get; set; }

        // ── Risk ─────────────────────────────────────────────────────────────
        [NinjaScriptProperty]
        [Range(1, 30)]
        [Display(Name = "Max Trades / Jour", Description = "20 = champion v9", Order = 11, GroupName = "Risk")]
        public int MaxTradesDay { get; set; }

        [NinjaScriptProperty]
        [Range(100, 2000)]
        [Display(Name = "Daily Loss Limit ($)", Order = 12, GroupName = "Risk")]
        public double DailyLossLimit { get; set; }

        [NinjaScriptProperty]
        [Range(1000, 5000)]
        [Display(Name = "Apex DD Limit ($)", Description = "Trailing DD EOD Apex — $2,000 pour $50k", Order = 13, GroupName = "Risk")]
        public double ApexDdLimit { get; set; }

        [NinjaScriptProperty]
        [Range(50, 500)]
        [Display(Name = "DD Safety Buffer ($)", Description = "Arret si (ApexDdLimit - DD_utilise) < buffer", Order = 14, GroupName = "Risk")]
        public double DdSafetyBuffer { get; set; }

        // ── Filtres ──────────────────────────────────────────────────────────
        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Skip Open Barres", Order = 15, GroupName = "Filtres")]
        public int SkipOpenBars { get; set; }

        // ===================================================================
        // VARIABLES INTERNES
        // ===================================================================

        private int      _tradesToday     = 0;
        private double   _dailyPnl        = 0.0;
        private double   _hwm             = 0.0;
        private double   _apexDdUsed      = 0.0;
        private DateTime _lastTradeDate   = DateTime.MinValue;
        private int      _barsInSession   = 0;
        private bool     _sessionStarted  = false;
        private bool     _tradingHalted   = false;
        private string   _haltReason      = "";
        private int      _lastExitBar     = -99;
        private const int EXIT_COOLDOWN_BARS = 2;
        private bool     _entryPending    = false;
        private int      _entryBar        = -1;     // Barre d'entree pour calcul timeout
        private bool     _trailActive     = false;
        private double   _trailStop       = 0.0;

        private static readonly TimeZoneInfo ParisTZ =
            TimeZoneInfo.FindSystemTimeZoneById("Romance Standard Time");

        private const double MNQ_TICK_VALUE = 2.0;   // $2 par point MNQ

        // ===================================================================
        // INITIALISATION
        // ===================================================================

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name                          = "HurstMR_Apex";
                Description                   = "Hurst Mean-Reversion Full Auto — Apex $50k — Kelly sizing";
                Calculate                     = Calculate.OnBarClose;
                EntriesPerDirection           = 1;
                EntryHandling                 = EntryHandling.UniqueEntries;
                IsExitOnSessionCloseStrategy  = true;
                ExitOnSessionCloseSeconds     = 60;
                BarsRequiredToTrade           = 500;   // raise de 90 -> 500 (anti-divergence Hurst entre postes)
                IsInstantiatedOnEachOptimizationIteration = false;

                // Valeurs par defaut — Champion v9 2026-05-12 (JSON params_20260512_2324, WF valide)
                // Backtest 5 ans : PF 2.29 / WR 42.64% / Sharpe 4.82 / DD 2.49% / 3030 trades / +$303,306
                // WF OOS : PF 5.17 / Sharpe 3.34 / Calmar 95.50 / 78% fenetres rentables / 60/60 mois positifs
                // Theoreme Leung respecte : SL elargi (0.65 + min 5pts) + TP raccourci (0.15)
                // Champion v9 2026-05-12 (Python validee, restoree apres test H=0.80 echec en NT 5y)
                HurstThreshold  = 0.58;
                HurstWindow     = 50;
                Lookback        = 19;
                BandK           = 2.75;
                SlMult          = 0.65;
                TpOvershoot     = 0.15;
                TimeoutBars     = 120;

                TrailEnabled  = true;
                TrailHThresh  = 0.51;

                // Kelly v9 : Risk 12% + Plafond 12 contrats
                KellyRiskPct     = 0.12;  // hausse de 0.09 -> 0.12
                MaxContractsEval = 12;    // hausse de 6 -> 12 (Apex permet jusqu'a 40)
                MaxContractsPA   = 4;
                ModePA           = false;

                // Backtest mode : OFF par defaut (= comportement v9 historique inchange).
                // POUR BACKTEST STRATEGY ANALYZER : passer cette case a TRUE.
                EnableInBacktest = false;

                MaxTradesDay    = 20;     // hausse de 15 -> 20
                DailyLossLimit  = 1000.0;
                ApexDdLimit     = 2000.0;
                DdSafetyBuffer  = 150.0;
                SkipOpenBars    = 5;
            }
            else if (State == State.DataLoaded)
            {
                _hwm = Account.Get(AccountItem.NetLiquidationByCurrency, Currency.UsDollar);
                if (_hwm <= 0) _hwm = Account.Get(AccountItem.CashValue, Currency.UsDollar);
                Print($"[INIT] HurstMR_Apex chargee — Balance={_hwm:F0}$ | " +
                      $"H<{HurstThreshold} HW={HurstWindow} LB={Lookback} K={BandK} " +
                      $"SL={SlMult} TP_os={TpOvershoot} Timeout={TimeoutBars}b " +
                      $"Trail={(TrailEnabled ? $"ON@H>{TrailHThresh}" : "OFF")} " +
                      $"Kelly={KellyRiskPct*100:F0}% MaxC={MaxContractsEval} " +
                      $"MaxTrades={MaxTradesDay} DailyLimit={DailyLossLimit}$ ModePA={ModePA}");

                // Diagnostic anti-divergence Hurst — verifie que l'historique charge est suffisant
                int barsCount = Bars != null ? Bars.Count : 0;
                DateTime firstBarTime = (barsCount > 0) ? Bars.GetTime(0) : DateTime.MinValue;
                Print($"[HISTORIQUE] Barres chargees={barsCount} | Premiere barre={firstBarTime:yyyy-MM-dd HH:mm} | Requis={BarsRequiredToTrade}");
                if (barsCount < BarsRequiredToTrade)
                {
                    Print($"[WARNING] Historique insuffisant ({barsCount} < {BarsRequiredToTrade}) — augmente 'Days to load' sur le chart pour garantir la coherence Hurst entre postes.");
                }
                else
                {
                    Print($"[OK] Historique suffisant — calcul Hurst stable et reproductible.");
                }

                if (KellyRiskPct <= 0.0)
                    Print("[ERREUR CRITIQUE] KellyRiskPct = 0 → AUCUN TRADE POSSIBLE. Mettre 0.12 dans les parametres.");
            }
        }

        // ===================================================================
        // SIZING KELLY — identique logique backtest Python
        // ===================================================================

        private int ComputeKellyContracts(double slPts)
        {
            double ddRem = Math.Max(0.0, ApexDdLimit - _apexDdUsed);

            // Budget risque = min(KellyRiskPct x ddRem, 40% du daily limit)
            double risk = Math.Min(KellyRiskPct * ddRem, DailyLossLimit * 0.40);
            risk        = Math.Max(50.0, risk);  // plancher $50 identique backtest

            double lossPerC = slPts * MNQ_TICK_VALUE;
            if (lossPerC <= 0.0) return 0;

            int contracts = (int)(risk / lossPerC);

            int capApex = ModePA ? MaxContractsPA : MaxContractsEval;
            contracts   = Math.Min(contracts, capApex);
            contracts   = Math.Max(1, contracts);

            double budgetRem  = Math.Max(0.0, DailyLossLimit + _dailyPnl);
            int    maxByBudget = (int)(budgetRem / lossPerC);
            contracts = Math.Min(contracts, maxByBudget);

            return contracts;
        }

        // ===================================================================
        // LOGIQUE PRINCIPALE — executee a chaque cloture M1
        // ===================================================================

        protected override void OnBarUpdate()
        {
            // En live : skip historiques (replay au demarrage). En backtest Strategy Analyzer :
            // autoriser les historiques (sinon aucun trade ne se declenche).
            if (State == State.Historical && !EnableInBacktest) return;

            if (CurrentBar < Math.Max(HurstWindow + Lookback + 2, BarsRequiredToTrade))
            {
                if (CurrentBar % 30 == 0)
                    Print($"[WARMUP] Bar {CurrentBar}/{Math.Max(HurstWindow + Lookback + 2, BarsRequiredToTrade)} — en attente...");
                return;
            }

            // En live : wall clock Paris. En backtest : utilise le timestamp de la barre.
            // Time[0] est dans la timezone du chart NT (typiquement Paris si user France,
            // ou NY si chart configure en Eastern). On NE convertit PAS : on assume que
            // le chart est dans la meme TZ que la session check (Paris).
            DateTime nowParis;
            if (State == State.Historical && EnableInBacktest)
                nowParis = Time[0];  // utilise bar time direct, suppose chart en Paris time
            else
                nowParis = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, ParisTZ);

            // ── Reset journalier ────────────────────────────────────────────
            DateTime today = nowParis.Date;
            if (today != _lastTradeDate)
            {
                _tradesToday    = 0;
                _dailyPnl       = 0.0;
                _tradingHalted  = false;
                _haltReason     = "";
                _barsInSession  = 0;
                _sessionStarted = false;
                _lastTradeDate  = today;
                _entryPending   = false;
                _lastExitBar    = -99;
                _trailActive    = false;
                _trailStop      = 0.0;
            }

            // ── Debut de session (15h30 Paris = 9h30 NY) ───────────────────
            bool inSession = (nowParis.Hour > 15 || (nowParis.Hour == 15 && nowParis.Minute >= 30))
                          && (nowParis.Hour < 22);

            if (inSession && !_sessionStarted) { _sessionStarted = true; _barsInSession = 0; }
            if (inSession) _barsInSession++;

            // ── FLAT FORCE a 21h59 Paris ────────────────────────────────────
            bool mustBeFlat = nowParis.Hour > 21 ||
                              (nowParis.Hour == 21 && nowParis.Minute >= 59);
            if (mustBeFlat)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    ExitLong("Flat_2159", "HurstMR_Long");
                    ExitShort("Flat_2159", "HurstMR_Short");
                    Print($"[FLAT FORCE] {nowParis:HH:mm:ss} Paris");
                }
                return;
            }

            // ── Stop entrees a 21h55 Paris ──────────────────────────────────
            bool entryAllowed = inSession
                             && !(nowParis.Hour == 21 && nowParis.Minute >= 55);
            if (!entryAllowed) return;

            // ── Warmup session ───────────────────────────────────────────────
            if (_barsInSession <= SkipOpenBars) return;

            // ── Heartbeat toutes les 30 barres pour confirmer activite ────────
            if (_barsInSession % 30 == 0)
                Print($"[ALIVE] {nowParis:HH:mm} Trades={_tradesToday}/{MaxTradesDay} " +
                      $"DailyPnL={_dailyPnl:F0}$ DD={_apexDdUsed:F0}$ Kelly={KellyRiskPct*100:F0}%");

            // ── Mise a jour DD Apex ──────────────────────────────────────────
            UpdateDdTracking();

            // ── Verifications risque ─────────────────────────────────────────
            if (_tradingHalted)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                { ExitLong("Halt", "HurstMR_Long"); ExitShort("Halt", "HurstMR_Short"); }
                return;
            }

            if (_dailyPnl <= -DailyLossLimit)
            { HaltTrading($"Daily loss limit: {_dailyPnl:F0}$"); return; }

            if (_tradesToday >= MaxTradesDay) return;

            // DD cumulatif : suivi informatif uniquement — pas de halt (identique logique backtest intraday)

            if (Position.MarketPosition != MarketPosition.Flat)
            {
                // Timeout — liquidation mark-to-market si trade trop long
                if (_entryBar >= 0 && CurrentBar - _entryBar >= TimeoutBars)
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                        ExitLong("Timeout", "HurstMR_Long");
                    else
                        ExitShort("Timeout", "HurstMR_Short");
                    Print($"[TIMEOUT] {nowParis:HH:mm} bar={CurrentBar} entry_bar={_entryBar} (>{TimeoutBars} barres) — exit MTM");
                    return;
                }
                if (TrailEnabled) ManageTrail(nowParis);
                return;
            }
            if (_entryPending) return;
            if (CurrentBar - _lastExitBar < EXIT_COOLDOWN_BARS) return;

            // ── Signal Hurst ─────────────────────────────────────────────────
            double hurst = ComputeHurst(HurstWindow);
            Print($"[SIGNAL] {nowParis:HH:mm} H={hurst:F3} (seuil={HurstThreshold}) Close={Close[0]:F2}");
            if (double.IsNaN(hurst) || hurst >= HurstThreshold) return;

            // ── Z-score — fenetre [Close[1]..Close[Lookback]], barre courante EXCLUE
            // Identique Python : w = closes[i - lb : i]  (i exclusif)
            double mean = 0.0, std = 0.0;
            for (int i = 1; i <= Lookback; i++) mean += Close[i];
            mean /= Lookback;
            for (int i = 1; i <= Lookback; i++) std += (Close[i] - mean) * (Close[i] - mean);
            std = Math.Sqrt(std / Lookback);  // ddof=0 identique Python ndarray.std()
            if (std < 1e-9) return;

            double zScore = (Close[0] - mean) / std;  // Close[0] = barre courante
            Print($"[MR REGIME] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2} (seuil=±{BandK}) mean={mean:F2} std={std:F3}");
            if (Math.Abs(zScore) < BandK) return;

            // ── Calcul SL v9 — SL min 5pts (theoreme Leung : SL large + TP raccourci 0.15)
            // Backtest 5 ans avec SL min 5pts : PF 2.29 / WR 42.64% / DD 2.49%
            // Bonus : resout le bug de rejet broker en marche rapide
            double slPts = Math.Max(5.0, SlMult * std);
            slPts        = Math.Min(slPts, 20.0);

            int contracts = ComputeKellyContracts(slPts);
            if (contracts <= 0)
            {
                Print($"[SKIP] Contracts=0 — KellyRiskPct={KellyRiskPct*100:F0}% DD_rem={ApexDdLimit-_apexDdUsed:F0}$ slPts={slPts:F2} budget={DailyLossLimit+_dailyPnl:F0}$");
                return;
            }

            double fairValue = mean;

            // ── Execution ────────────────────────────────────────────────────
            if (zScore > 0)
            {
                // Prix > upper band -> SHORT vers fair value
                double sl = Close[0] + slPts;
                double tp = TpOvershoot > 0 ? fairValue - TpOvershoot * std : fairValue;
                SetStopLoss("HurstMR_Short",    CalculationMode.Price, sl, false);
                SetProfitTarget("HurstMR_Short", CalculationMode.Price, tp);
                _entryPending = true;
                EnterShort(contracts, "HurstMR_Short");
                Print($"[SHORT] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2} " +
                      $"Entry={Close[0]:F2} SL={sl:F2} TP={tp:F2} Qty={contracts} " +
                      $"DD_used={_apexDdUsed:F0}$ Kelly={KellyRiskPct*100:F0}%");
            }
            else
            {
                // Prix < lower band -> LONG vers fair value
                double sl = Close[0] - slPts;
                double tp = TpOvershoot > 0 ? fairValue + TpOvershoot * std : fairValue;
                SetStopLoss("HurstMR_Long",    CalculationMode.Price, sl, false);
                SetProfitTarget("HurstMR_Long", CalculationMode.Price, tp);
                _entryPending = true;
                EnterLong(contracts, "HurstMR_Long");
                Print($"[LONG] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2} " +
                      $"Entry={Close[0]:F2} SL={sl:F2} TP={tp:F2} Qty={contracts} " +
                      $"DD_used={_apexDdUsed:F0}$ Kelly={KellyRiskPct*100:F0}%");
            }
        }

        // ===================================================================
        // TRAIL MR/TREND — replique exacte de la logique backtest Python
        //
        // Activation : prix franchit FV ET H > TrailHThresh
        // Trail actif : SL ratchete a FV (monte si LONG, descend si SHORT)
        // Sortie explicite : Z >= 3.0 (oppose) | H > seuil + Z >= 2.5
        // ===================================================================

        private void ManageTrail(DateTime nowParis)
        {
            if (CurrentBar < Lookback + 2) return;

            // Calcul FV, std et Z courant — identique boucle interne backtest Python
            double mean = 0.0, std = 0.0;
            for (int i = 1; i <= Lookback; i++) mean += Close[i];
            mean /= Lookback;
            for (int i = 1; i <= Lookback; i++) std += (Close[i] - mean) * (Close[i] - mean);
            std = Math.Sqrt(std / Lookback);
            if (std < 1e-9) return;

            double fv     = mean;
            double zScore = (Close[0] - fv) / std;
            double hurst  = ComputeHurst(HurstWindow);

            bool isLong  = Position.MarketPosition == MarketPosition.Long;
            bool isShort = Position.MarketPosition == MarketPosition.Short;

            if (!_trailActive)
            {
                // Condition activation : prix a franchi FV ET H trending
                bool fvCrossed = (isLong && Close[0] > fv) || (isShort && Close[0] < fv);
                bool hTrend    = !double.IsNaN(hurst) && hurst > TrailHThresh;

                if (fvCrossed && hTrend)
                {
                    _trailActive = true;
                    _trailStop   = fv;
                    // Supprimer le TP fixe (prix tres eloigne) + placer SL a FV
                    if (isLong)
                    {
                        SetProfitTarget("HurstMR_Long",  CalculationMode.Price, Close[0] + 500.0);
                        SetStopLoss("HurstMR_Long",      CalculationMode.Price, _trailStop, false);
                    }
                    else
                    {
                        SetProfitTarget("HurstMR_Short", CalculationMode.Price, Close[0] - 500.0);
                        SetStopLoss("HurstMR_Short",     CalculationMode.Price, _trailStop, false);
                    }
                    Print($"[TRAIL ON] {nowParis:HH:mm} H={hurst:F3} FV={fv:F2} Z={zScore:F2} TrailStop={_trailStop:F2}");
                    return;
                }
                // Trail pas encore actif → TP/SL fixes geres par NT, rien a faire
            }
            else
            {
                // Trail actif — ratchet le stop dans la direction favorable
                if (isLong && fv > _trailStop)
                {
                    _trailStop = fv;
                    SetStopLoss("HurstMR_Long", CalculationMode.Price, _trailStop, false);
                    Print($"[TRAIL RATCHET] {nowParis:HH:mm} FV={fv:F2} TrailStop={_trailStop:F2}");
                }
                else if (isShort && fv < _trailStop)
                {
                    _trailStop = fv;
                    SetStopLoss("HurstMR_Short", CalculationMode.Price, _trailStop, false);
                    Print($"[TRAIL RATCHET] {nowParis:HH:mm} FV={fv:F2} TrailStop={_trailStop:F2}");
                }

                // Sorties explicites — identique Python :
                // LONG  : z >= 3.0  |  H > seuil + z >= 2.5
                // SHORT : z <= -3.0 |  H > seuil + z <= -2.5
                if (isLong)
                {
                    if (zScore >= 3.0)
                    {
                        ExitLong("Trail_Z3", "HurstMR_Long");
                        Print($"[TRAIL EXIT Z3] {nowParis:HH:mm} Z={zScore:F2} Prix={Close[0]:F2} Stop={_trailStop:F2}");
                    }
                    else if (!double.IsNaN(hurst) && hurst > TrailHThresh && zScore >= 2.5)
                    {
                        ExitLong("Trail_HZ", "HurstMR_Long");
                        Print($"[TRAIL EXIT HZ] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2} Stop={_trailStop:F2}");
                    }
                }
                else
                {
                    if (zScore <= -3.0)
                    {
                        ExitShort("Trail_Z3", "HurstMR_Short");
                        Print($"[TRAIL EXIT Z3] {nowParis:HH:mm} Z={zScore:F2} Prix={Close[0]:F2} Stop={_trailStop:F2}");
                    }
                    else if (!double.IsNaN(hurst) && hurst > TrailHThresh && zScore <= -2.5)
                    {
                        ExitShort("Trail_HZ", "HurstMR_Short");
                        Print($"[TRAIL EXIT HZ] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2} Stop={_trailStop:F2}");
                    }
                }
            }
        }

        // ===================================================================
        // TRACKING PnL ET DD
        // ===================================================================

        protected override void OnExecutionUpdate(Execution execution, string executionId,
            double price, int quantity, MarketPosition marketPosition,
            string orderId, DateTime time)
        {
            if (execution.Order.OrderAction == OrderAction.SellShort ||
                execution.Order.OrderAction == OrderAction.Buy)
            {
                if (_entryPending)
                {
                    _entryPending = false;
                    _tradesToday++;
                    _entryBar = CurrentBar;   // Marquer la barre d'entree pour timeout
                }
            }

            if (execution.Order.OrderAction == OrderAction.Sell ||
                execution.Order.OrderAction == OrderAction.BuyToCover)
            {
                _lastExitBar  = CurrentBar;
                _entryPending = false;
                _entryBar     = -1;          // Reset timeout tracker
                _trailActive  = false;
                _trailStop    = 0.0;
                int n = SystemPerformance.AllTrades.Count;
                if (n > 0)
                    _dailyPnl += SystemPerformance.AllTrades[n - 1].ProfitCurrency;
            }
        }

        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice,
            int quantity, int filled, double averageFillPrice,
            OrderState orderState, DateTime time, ErrorCode error, string comment)
        {
            if (orderState == OrderState.Rejected)
            {
                Print($"[ORDRE REJETE] {order.Name} action={order.OrderAction} " +
                      $"qty={quantity} erreur={error} commentaire={comment}");
                _entryPending = false;
                _lastExitBar  = CurrentBar;
            }
        }

        private void UpdateDdTracking()
        {
            // NetLiquidationByCurrency inclut le PnL unrealized — confirme par test Rithmic
            double equity = Account.Get(AccountItem.NetLiquidationByCurrency, Currency.UsDollar);
            if (equity <= 0) return;  // Compte pas encore charge — evite HALT spurieux au demarrage
            if (_hwm <= 0) _hwm = equity;  // Reinit si DataLoaded a recupere une valeur nulle
            if (equity > _hwm) _hwm = equity;
            _apexDdUsed = Math.Max(0.0, _hwm - equity);
        }

        private void HaltTrading(string reason)
        {
            _tradingHalted = true;
            _haltReason    = reason;
            Print($"[HALT] {DateTime.Now:HH:mm:ss} — {reason}");
            if (Position.MarketPosition != MarketPosition.Flat)
            { ExitLong("Halt", "HurstMR_Long"); ExitShort("Halt", "HurstMR_Short"); }
        }

        // ===================================================================
        // CALCUL HURST R/S — replique exacte de hurst_rs() dans backtest_hurst.py
        //
        // Python reference :
        //   lags = np.unique(np.round(np.exp(np.linspace(log(4), log(min(n//2,50)), 12))).astype(int))
        //   for lag in lags:
        //       n_chunks = n // lag
        //       if n_chunks < 2: continue
        //       mat  = ts[:n_chunks * lag].reshape(n_chunks, lag)
        //       mean = mat.mean(axis=1, keepdims=True)
        //       devs = np.cumsum(mat - mean, axis=1)
        //       R    = devs.max(axis=1) - devs.min(axis=1)
        //       S    = mat.std(axis=1, ddof=0)
        //       rs_vals.append(float((R[mask] / S[mask]).mean()))
        //   return np.polyfit(np.log(lags[:len(rs_vals)]), np.log(rs_vals), 1)[0]
        // ===================================================================

        private double ComputeHurst(int window)
        {
            if (CurrentBar < window + 2) return 0.5;

            // Construire la serie de log-returns chronologique (index 0 = plus ancien)
            double[] logRets = new double[window];
            for (int i = 0; i < window; i++)
            {
                double prev = Close[i + 1];
                double curr = Close[i];
                if (prev <= 0.0 || curr <= 0.0) return 0.5;
                logRets[window - 1 - i] = Math.Log(curr / prev);
            }

            // 12 lags log-espaces entre 4 et min(window/2, 50) — identique Python
            int maxLag = Math.Min(window / 2, 50);
            if (maxLag < 4) return 0.5;

            // Generer les 12 lags log-espaces et les dedupliquer (equiv. np.unique)
            var lagSet = new HashSet<int>();
            for (int k = 0; k < 12; k++)
            {
                double t      = (k == 0) ? 0.0 : (double)k / 11.0;
                double lagDbl = Math.Round(Math.Exp(Math.Log(4) + t * (Math.Log(maxLag) - Math.Log(4))));
                int    lagInt = (int)lagDbl;
                if (lagInt >= 4) lagSet.Add(lagInt);
            }
            int[] lags = new int[lagSet.Count];
            lagSet.CopyTo(lags);
            Array.Sort(lags);

            var meanRsVals = new List<double>();  // R/S moyen par lag (lineaire)
            var logLagList = new List<double>();  // log(lag)

            foreach (int lag in lags)
            {
                int nChunks = window / lag;
                if (nChunks < 2) continue;

                // Moyenne R/S sur les nChunks segments non-chevauchants
                double rsSum   = 0.0;
                int    rsCount = 0;

                for (int c = 0; c < nChunks; c++)
                {
                    int start = c * lag;
                    int end   = start + lag;

                    // Moyenne du chunk
                    double chunkMean = 0.0;
                    for (int j = start; j < end; j++) chunkMean += logRets[j];
                    chunkMean /= lag;

                    // Deviation cumulee, range R et ecart-type S (ddof=0)
                    double cumDev = 0.0;
                    double maxDev = double.MinValue;
                    double minDev = double.MaxValue;
                    double varSum = 0.0;

                    for (int j = start; j < end; j++)
                    {
                        cumDev += logRets[j] - chunkMean;
                        if (cumDev > maxDev) maxDev = cumDev;
                        if (cumDev < minDev) minDev = cumDev;
                        varSum += (logRets[j] - chunkMean) * (logRets[j] - chunkMean);
                    }

                    double S = Math.Sqrt(varSum / lag);  // ddof=0 identique Python
                    if (S > 1e-10)
                    {
                        rsSum += (maxDev - minDev) / S;
                        rsCount++;
                    }
                }

                if (rsCount > 0)
                {
                    meanRsVals.Add(rsSum / rsCount);
                    logLagList.Add(Math.Log(lag));
                }
            }

            // Besoin d'au moins 3 points valides pour la regression (identique Python)
            if (meanRsVals.Count < 3) return 0.5;

            // Regression log-log : pente = exposant Hurst
            var logRsList = new List<double>(meanRsVals.Count);
            foreach (double rs in meanRsVals) logRsList.Add(Math.Log(rs));

            return Math.Max(0.0, Math.Min(1.0, LinearSlope(logLagList, logRsList)));
        }

        private double LinearSlope(List<double> x, List<double> y)
        {
            int    n     = x.Count;
            double sumX  = 0, sumY = 0, sumXY = 0, sumX2 = 0;
            for (int i = 0; i < n; i++)
            { sumX += x[i]; sumY += y[i]; sumXY += x[i]*y[i]; sumX2 += x[i]*x[i]; }
            double denom = n * sumX2 - sumX * sumX;
            if (Math.Abs(denom) < 1e-12) return 0.5;
            return (n * sumXY - sumX * sumY) / denom;
        }
    }
}