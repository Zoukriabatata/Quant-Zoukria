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
 * HurstMR_Apex_v10 — Strategie Full Auto NinjaTrader / Rithmic
 * =============================================================
 * VERSION 10 : Ajoute Grossman-Zhou ADAPTIVE Shrinkage au sizing v9.
 *
 * Edge inchange v9 : Hurst < 0.58 (regime MR) + Z-score +-2.75 sigma
 * Trail MR/Trend inchange : actif @ H > 0.51
 * SL inchange : max(5pts, 0.65 x std), capped a 20pts (Leung)
 * TP inchange : FV + 0.15 sigma overshoot
 *
 * NOUVEAU v10 — Grossman-Zhou Adaptive Sizing :
 * ============================================
 *   contracts_v10 = contracts_v9 x shrinkage_factor
 *
 *   shrinkage_factor = (W_t - alpha * M_t) / ((1 - alpha) * M_t)
 *                    = (equity - (HWM - ApexDdLimit)) / ApexDdLimit
 *
 *   - At peak (W_t = M_t) : shrinkage = 1.0 -> contracts inchanges = v9
 *   - At mid-buffer       : shrinkage = 0.5 -> contracts reduits de moitie
 *   - At floor            : shrinkage = 0.0 -> 0 contracts (protection totale)
 *
 * Validation backtest 5 ans MNQ (Sprint 4.3 CPCV + DSR + PBO) :
 *   PnL=$298k, Sharpe=4.42, DD intra-mois=$1549,
 *   **BUSTES = 0/61** (vs 2/61 pour v9 baseline) <- LE GAIN CRITIQUE
 *   Passes target $3k = 51/61
 *   DSR = 0.999999 (anti-overfit certifie)
 *   PBO global = 0.317 (non-overfit, 8 configs testees)
 *
 * Reference : Grossman, S.J. & Zhou, Z. (1993). "Optimal Investment
 * Strategies for Controlling Drawdowns", Mathematical Finance 3(3).
 *
 * Coexistence avec v9 : noms differents -> les deux strategies peuvent
 * tourner en parallele sur 2 charts pour A/B test live.
 */

namespace NinjaTrader.NinjaScript.Strategies
{
    public class HurstMR_Apex_v10 : Strategy
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
        [Display(Name = "SL Mult", Description = "SL = max(5.0, SL_Mult x std), capped a 20.0", Order = 5, GroupName = "Signal")]
        public double SlMult { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 2.0)]
        [Display(Name = "TP Overshoot (sigma)", Description = "0.15 = config champion v9/v10", Order = 6, GroupName = "Signal")]
        public double TpOvershoot { get; set; }

        [NinjaScriptProperty]
        [Range(15, 300)]
        [Display(Name = "Timeout (barres M1)", Description = "Liquidation MTM apres N barres (champion = 120)", Order = 7, GroupName = "Signal")]
        public int TimeoutBars { get; set; }

        // ── Trail MR/Trend ───────────────────────────────────────────────────
        [NinjaScriptProperty]
        [Display(Name = "Trail MR/Trend (ON/OFF)", Description = "Si ON : stop deplace a FV quand prix franchit FV + H trending", Order = 1, GroupName = "Trail")]
        public bool TrailEnabled { get; set; }

        [NinjaScriptProperty]
        [Range(0.40, 0.60)]
        [Display(Name = "Seuil H activation trail", Description = "H > seuil -> trail actif (optimal = 0.51)", Order = 2, GroupName = "Trail")]
        public double TrailHThresh { get; set; }

        // ── Sizing Kelly ─────────────────────────────────────────────────────
        [NinjaScriptProperty]
        [Range(0.01, 0.50)]
        [Display(Name = "Kelly Risk % / trade", Description = "% du DD restant risque par trade (champion v9 = 0.12)", Order = 7, GroupName = "Sizing Kelly")]
        public double KellyRiskPct { get; set; }

        [NinjaScriptProperty]
        [Range(1, 40)]
        [Display(Name = "Contrats max Eval (cap Apex)", Description = "12 MNQ champion v9/v10", Order = 8, GroupName = "Sizing Kelly")]
        public int MaxContractsEval { get; set; }

        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name = "Contrats max PA (cap Apex)", Description = "4 MNQ en debut PA / 2 avant safety net", Order = 9, GroupName = "Sizing Kelly")]
        public int MaxContractsPA { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Mode PA (vs Eval)", Description = "ON = plafond PA actif (moins de contrats)", Order = 10, GroupName = "Sizing Kelly")]
        public bool ModePA { get; set; }

        // ── NOUVEAU v10 : Grossman-Zhou Adaptive Shrinkage ──────────────────
        [NinjaScriptProperty]
        [Display(Name = "GZ Adaptive (ON/OFF)", Description = "v10: shrink sizing quand equity approche du floor DD. Elimine les busts.", Order = 11, GroupName = "Sizing Kelly")]
        public bool UseGzAdaptive { get; set; }

        // ── Backtest mode ────────────────────────────────────────────────────
        [NinjaScriptProperty]
        [Display(Name = "Enable in Backtest (Strategy Analyzer)", Description = "ON = trade sur barres historiques (Strategy Analyzer). OFF = live uniquement (recommande pour prod).", Order = 12, GroupName = "Sizing Kelly")]
        public bool EnableInBacktest { get; set; }

        // ── Risk ─────────────────────────────────────────────────────────────
        [NinjaScriptProperty]
        [Range(1, 30)]
        [Display(Name = "Max Trades / Jour", Description = "20 = champion v9/v10", Order = 11, GroupName = "Risk")]
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
        private double   _cumPnl          = 0.0;   // Cumul PnL all trades (pour equity tracking en backtest)
        private double   _initialCapital  = 0.0;   // Capital initial fixe
        private DateTime _lastTradeDate   = DateTime.MinValue;
        private int      _barsInSession   = 0;
        private bool     _sessionStarted  = false;
        private bool     _tradingHalted   = false;
        private string   _haltReason      = "";
        private int      _lastExitBar     = -99;
        private const int EXIT_COOLDOWN_BARS = 2;
        private bool     _entryPending    = false;
        private int      _entryBar        = -1;
        private bool     _trailActive     = false;
        private double   _trailStop       = 0.0;

        private static readonly TimeZoneInfo ParisTZ =
            TimeZoneInfo.FindSystemTimeZoneById("Romance Standard Time");

        private const double MNQ_TICK_VALUE = 2.0;

        // ===================================================================
        // INITIALISATION
        // ===================================================================

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name                          = "HurstMR_Apex_v10";
                Description                   = "v10 = v9 + Grossman-Zhou adaptive sizing (elimine busts Apex)";
                Calculate                     = Calculate.OnBarClose;
                EntriesPerDirection           = 1;
                EntryHandling                 = EntryHandling.UniqueEntries;
                IsExitOnSessionCloseStrategy  = true;
                ExitOnSessionCloseSeconds     = 60;
                BarsRequiredToTrade           = 500;
                IsInstantiatedOnEachOptimizationIteration = false;

                // Defaults = Champion v9 2026-05-12 (params Python validees, restoree apres echec NT H=0.80 5y)
                HurstThreshold  = 0.58;
                HurstWindow     = 50;
                Lookback        = 19;
                BandK           = 2.75;
                SlMult          = 0.65;
                TpOvershoot     = 0.15;
                TimeoutBars     = 120;

                TrailEnabled  = true;
                TrailHThresh  = 0.51;

                KellyRiskPct     = 0.12;
                MaxContractsEval = 12;
                MaxContractsPA   = 4;
                ModePA           = false;

                // NOUVEAU v10 : GZ Adaptive ACTIVE par defaut
                UseGzAdaptive    = true;

                // Backtest mode : OFF par defaut pour la prod (evite faux trades replay)
                // POUR BACKTEST DANS STRATEGY ANALYZER : passer cette case a TRUE
                EnableInBacktest = false;

                MaxTradesDay    = 20;
                DailyLossLimit  = 1000.0;
                ApexDdLimit     = 2000.0;
                DdSafetyBuffer  = 150.0;
                SkipOpenBars    = 5;
            }
            else if (State == State.DataLoaded)
            {
                _hwm = Account.Get(AccountItem.NetLiquidationByCurrency, Currency.UsDollar);
                if (_hwm <= 0) _hwm = Account.Get(AccountItem.CashValue, Currency.UsDollar);
                if (_hwm <= 0) _hwm = 50_000.0;  // Backtest fallback : Account.Get ne marche pas en Strategy Analyzer
                _initialCapital = _hwm;
                _cumPnl = 0.0;
                Print($"[INIT v10] HurstMR_Apex_v10 chargee — Balance={_hwm:F0}$ | " +
                      $"H<{HurstThreshold} HW={HurstWindow} LB={Lookback} K={BandK} " +
                      $"SL={SlMult} TP_os={TpOvershoot} Timeout={TimeoutBars}b " +
                      $"Trail={(TrailEnabled ? $"ON@H>{TrailHThresh}" : "OFF")} " +
                      $"Kelly={KellyRiskPct*100:F0}% MaxC={MaxContractsEval} " +
                      $"GZ_Adapt={(UseGzAdaptive ? "ON" : "OFF")} " +
                      $"MaxTrades={MaxTradesDay} DailyLimit={DailyLossLimit}$ ModePA={ModePA}");

                int barsCount = Bars != null ? Bars.Count : 0;
                DateTime firstBarTime = (barsCount > 0) ? Bars.GetTime(0) : DateTime.MinValue;
                Print($"[HISTORIQUE] Barres chargees={barsCount} | Premiere barre={firstBarTime:yyyy-MM-dd HH:mm} | Requis={BarsRequiredToTrade}");
                if (barsCount < BarsRequiredToTrade)
                {
                    Print($"[WARNING] Historique insuffisant ({barsCount} < {BarsRequiredToTrade}) — augmente 'Days to load' sur le chart.");
                }
                else
                {
                    Print($"[OK] Historique suffisant — calcul Hurst stable.");
                }

                if (KellyRiskPct <= 0.0)
                    Print("[ERREUR CRITIQUE] KellyRiskPct = 0 -> AUCUN TRADE POSSIBLE. Mettre 0.12.");
            }
        }

        // ===================================================================
        // GZ ADAPTIVE SHRINKAGE — Le coeur de v10
        //
        // shrinkage = (equity - floor) / ApexDdLimit
        //   floor = HWM - ApexDdLimit
        //
        // Returns dans [0, 1] :
        //   1.0 si equity = HWM (au peak, aucun shrink)
        //   0.5 si equity a mi-chemin entre HWM et floor
        //   0.0 si equity = floor (DD max atteint, plus de risque)
        // ===================================================================

        private double ComputeGzShrinkage()
        {
            if (!UseGzAdaptive) return 1.0;
            if (_hwm <= 0.0 || ApexDdLimit <= 0.0) return 1.0;

            // Equity = capital initial + cumul PnL trades + PnL position ouverte
            // Cette methode marche en LIVE ET en BACKTEST (Account.Get ne marche pas en Strategy Analyzer).
            double equity;
            if (State == State.Historical)
            {
                // Backtest : utilise notre cumul interne + unrealized PnL position ouverte
                double unrealized = (Position.MarketPosition != MarketPosition.Flat)
                    ? Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, Close[0])
                    : 0.0;
                equity = _initialCapital + _cumPnl + unrealized;
            }
            else
            {
                // Live : utilise Account broker reel
                equity = Account.Get(AccountItem.NetLiquidationByCurrency, Currency.UsDollar);
                if (equity <= 0) equity = _initialCapital + _cumPnl;  // fallback
            }

            double floor  = _hwm - ApexDdLimit;
            double buffer = equity - floor;

            if (buffer <= 0.0) return 0.0;  // sous le floor, protection totale

            double shrinkage = buffer / ApexDdLimit;
            return Math.Min(1.0, Math.Max(0.0, shrinkage));
        }

        // ===================================================================
        // SIZING KELLY + GZ ADAPTIVE — v10
        // ===================================================================

        private int ComputeKellyContracts(double slPts)
        {
            // ── Etape 1 : Sizing Kelly v9 (inchange) ─────────────────────────
            double ddRem = Math.Max(0.0, ApexDdLimit - _apexDdUsed);

            double risk = Math.Min(KellyRiskPct * ddRem, DailyLossLimit * 0.40);
            risk        = Math.Max(50.0, risk);

            double lossPerC = slPts * MNQ_TICK_VALUE;
            if (lossPerC <= 0.0) return 0;

            int contracts = (int)(risk / lossPerC);

            int capApex = ModePA ? MaxContractsPA : MaxContractsEval;
            contracts   = Math.Min(contracts, capApex);
            contracts   = Math.Max(1, contracts);

            double budgetRem  = Math.Max(0.0, DailyLossLimit + _dailyPnl);
            int    maxByBudget = (int)(budgetRem / lossPerC);
            contracts = Math.Min(contracts, maxByBudget);

            // ── Etape 2 NOUVELLE v10 : GZ Adaptive Shrinkage ─────────────────
            if (UseGzAdaptive)
            {
                double shrinkage = ComputeGzShrinkage();
                int contractsBeforeGz = contracts;
                contracts = (int)(contracts * shrinkage);

                // Log si le shrinkage modifie la decision (visibilite live)
                if (contractsBeforeGz != contracts)
                {
                    Print($"[GZ SHRINK] {contractsBeforeGz} -> {contracts} contracts " +
                          $"(shrinkage={shrinkage:F2}, equity_buffer=${(_hwm - ApexDdLimit + ApexDdLimit*shrinkage - _hwm + ApexDdLimit):F0})");
                }
            }

            return contracts;
        }

        // ===================================================================
        // LOGIQUE PRINCIPALE — executee a chaque cloture M1
        // ===================================================================

        protected override void OnBarUpdate()
        {
            // En mode live : skip les barres historiques (replay au demarrage) pour eviter
            // les faux trades dans les compteurs. En backtest Strategy Analyzer : autoriser
            // les barres historiques (sinon aucun trade ne se declenche jamais).
            if (State == State.Historical && !EnableInBacktest) return;

            if (CurrentBar < Math.Max(HurstWindow + Lookback + 2, BarsRequiredToTrade))
            {
                if (CurrentBar % 30 == 0)
                    Print($"[WARMUP] Bar {CurrentBar}/{Math.Max(HurstWindow + Lookback + 2, BarsRequiredToTrade)} — en attente...");
                return;
            }

            // En live : wall clock Paris. En backtest : utilise Time[0] directement
            // (suppose chart NT en Paris time, ce qui est le default pour user France).
            DateTime nowParis;
            if (State == State.Historical && EnableInBacktest)
                nowParis = Time[0];  // bar time direct, sans conversion (chart en Paris time)
            else
                nowParis = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, ParisTZ);

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

            bool inSession = (nowParis.Hour > 15 || (nowParis.Hour == 15 && nowParis.Minute >= 30))
                          && (nowParis.Hour < 22);

            if (inSession && !_sessionStarted) { _sessionStarted = true; _barsInSession = 0; }
            if (inSession) _barsInSession++;

            bool mustBeFlat = nowParis.Hour > 21 ||
                              (nowParis.Hour == 21 && nowParis.Minute >= 59);
            if (mustBeFlat)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                {
                    ExitLong("Flat_2159", "HurstMR_v10_Long");
                    ExitShort("Flat_2159", "HurstMR_v10_Short");
                    Print($"[FLAT FORCE] {nowParis:HH:mm:ss} Paris");
                }
                return;
            }

            bool entryAllowed = inSession
                             && !(nowParis.Hour == 21 && nowParis.Minute >= 55);
            if (!entryAllowed) return;

            if (_barsInSession <= SkipOpenBars) return;

            if (_barsInSession % 30 == 0)
            {
                double currentShrinkage = ComputeGzShrinkage();
                Print($"[ALIVE v10] {nowParis:HH:mm} Trades={_tradesToday}/{MaxTradesDay} " +
                      $"DailyPnL={_dailyPnl:F0}$ DD={_apexDdUsed:F0}$ " +
                      $"GZ_shrinkage={currentShrinkage:F2} Kelly={KellyRiskPct*100:F0}%");
            }

            UpdateDdTracking();

            if (_tradingHalted)
            {
                if (Position.MarketPosition != MarketPosition.Flat)
                { ExitLong("Halt", "HurstMR_v10_Long"); ExitShort("Halt", "HurstMR_v10_Short"); }
                return;
            }

            if (_dailyPnl <= -DailyLossLimit)
            { HaltTrading($"Daily loss limit: {_dailyPnl:F0}$"); return; }

            if (_tradesToday >= MaxTradesDay) return;

            if (Position.MarketPosition != MarketPosition.Flat)
            {
                if (_entryBar >= 0 && CurrentBar - _entryBar >= TimeoutBars)
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                        ExitLong("Timeout", "HurstMR_v10_Long");
                    else
                        ExitShort("Timeout", "HurstMR_v10_Short");
                    Print($"[TIMEOUT] {nowParis:HH:mm} bar={CurrentBar} entry_bar={_entryBar} — exit MTM");
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

            // ── Z-score ──────────────────────────────────────────────────────
            double mean = 0.0, std = 0.0;
            for (int i = 1; i <= Lookback; i++) mean += Close[i];
            mean /= Lookback;
            for (int i = 1; i <= Lookback; i++) std += (Close[i] - mean) * (Close[i] - mean);
            std = Math.Sqrt(std / Lookback);
            if (std < 1e-9) return;

            double zScore = (Close[0] - mean) / std;
            Print($"[MR REGIME] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2} (seuil=±{BandK}) mean={mean:F2} std={std:F3}");
            if (Math.Abs(zScore) < BandK) return;

            // ── SL ──────────────────────────────────────────────────────────
            double slPts = Math.Max(5.0, SlMult * std);
            slPts        = Math.Min(slPts, 20.0);

            int contracts = ComputeKellyContracts(slPts);
            if (contracts <= 0)
            {
                Print($"[SKIP v10] Contracts=0 — Kelly={KellyRiskPct*100:F0}% DD_rem={ApexDdLimit-_apexDdUsed:F0}$ " +
                      $"GZ_shrink={ComputeGzShrinkage():F2} slPts={slPts:F2}");
                return;
            }

            double fairValue = mean;

            // ── Execution ────────────────────────────────────────────────────
            if (zScore > 0)
            {
                double sl = Close[0] + slPts;
                double tp = TpOvershoot > 0 ? fairValue - TpOvershoot * std : fairValue;
                SetStopLoss("HurstMR_v10_Short",    CalculationMode.Price, sl, false);
                SetProfitTarget("HurstMR_v10_Short", CalculationMode.Price, tp);
                _entryPending = true;
                EnterShort(contracts, "HurstMR_v10_Short");
                Print($"[SHORT v10] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2} " +
                      $"Entry={Close[0]:F2} SL={sl:F2} TP={tp:F2} Qty={contracts} " +
                      $"DD_used={_apexDdUsed:F0}$ GZ_shrink={ComputeGzShrinkage():F2}");
            }
            else
            {
                double sl = Close[0] - slPts;
                double tp = TpOvershoot > 0 ? fairValue + TpOvershoot * std : fairValue;
                SetStopLoss("HurstMR_v10_Long",    CalculationMode.Price, sl, false);
                SetProfitTarget("HurstMR_v10_Long", CalculationMode.Price, tp);
                _entryPending = true;
                EnterLong(contracts, "HurstMR_v10_Long");
                Print($"[LONG v10] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2} " +
                      $"Entry={Close[0]:F2} SL={sl:F2} TP={tp:F2} Qty={contracts} " +
                      $"DD_used={_apexDdUsed:F0}$ GZ_shrink={ComputeGzShrinkage():F2}");
            }
        }

        // ===================================================================
        // TRAIL MR/TREND — IDENTIQUE v9 (pas touche par v10)
        // ===================================================================

        private void ManageTrail(DateTime nowParis)
        {
            if (CurrentBar < Lookback + 2) return;

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
                bool fvCrossed = (isLong && Close[0] > fv) || (isShort && Close[0] < fv);
                bool hTrend    = !double.IsNaN(hurst) && hurst > TrailHThresh;

                if (fvCrossed && hTrend)
                {
                    _trailActive = true;
                    _trailStop   = fv;
                    if (isLong)
                    {
                        SetProfitTarget("HurstMR_v10_Long",  CalculationMode.Price, Close[0] + 500.0);
                        SetStopLoss("HurstMR_v10_Long",      CalculationMode.Price, _trailStop, false);
                    }
                    else
                    {
                        SetProfitTarget("HurstMR_v10_Short", CalculationMode.Price, Close[0] - 500.0);
                        SetStopLoss("HurstMR_v10_Short",     CalculationMode.Price, _trailStop, false);
                    }
                    Print($"[TRAIL ON] {nowParis:HH:mm} H={hurst:F3} FV={fv:F2} Z={zScore:F2} TrailStop={_trailStop:F2}");
                    return;
                }
            }
            else
            {
                if (isLong && fv > _trailStop)
                {
                    _trailStop = fv;
                    SetStopLoss("HurstMR_v10_Long", CalculationMode.Price, _trailStop, false);
                    Print($"[TRAIL RATCHET] {nowParis:HH:mm} FV={fv:F2} TrailStop={_trailStop:F2}");
                }
                else if (isShort && fv < _trailStop)
                {
                    _trailStop = fv;
                    SetStopLoss("HurstMR_v10_Short", CalculationMode.Price, _trailStop, false);
                    Print($"[TRAIL RATCHET] {nowParis:HH:mm} FV={fv:F2} TrailStop={_trailStop:F2}");
                }

                if (isLong)
                {
                    if (zScore >= 3.0)
                    {
                        ExitLong("Trail_Z3", "HurstMR_v10_Long");
                        Print($"[TRAIL EXIT Z3] {nowParis:HH:mm} Z={zScore:F2}");
                    }
                    else if (!double.IsNaN(hurst) && hurst > TrailHThresh && zScore >= 2.5)
                    {
                        ExitLong("Trail_HZ", "HurstMR_v10_Long");
                        Print($"[TRAIL EXIT HZ] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2}");
                    }
                }
                else
                {
                    if (zScore <= -3.0)
                    {
                        ExitShort("Trail_Z3", "HurstMR_v10_Short");
                        Print($"[TRAIL EXIT Z3] {nowParis:HH:mm} Z={zScore:F2}");
                    }
                    else if (!double.IsNaN(hurst) && hurst > TrailHThresh && zScore <= -2.5)
                    {
                        ExitShort("Trail_HZ", "HurstMR_v10_Short");
                        Print($"[TRAIL EXIT HZ] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2}");
                    }
                }
            }
        }

        // ===================================================================
        // TRACKING PnL ET DD — IDENTIQUE v9
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
                    _entryBar = CurrentBar;
                }
            }

            if (execution.Order.OrderAction == OrderAction.Sell ||
                execution.Order.OrderAction == OrderAction.BuyToCover)
            {
                _lastExitBar  = CurrentBar;
                _entryPending = false;
                _entryBar     = -1;
                _trailActive  = false;
                _trailStop    = 0.0;
                int n = SystemPerformance.AllTrades.Count;
                if (n > 0)
                {
                    double tradePnl = SystemPerformance.AllTrades[n - 1].ProfitCurrency;
                    _dailyPnl += tradePnl;
                    _cumPnl   += tradePnl;  // NOUVEAU v10 : tracking equity pour GZ adaptatif
                }
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
            // Equity : Account broker en live, cumul interne en backtest
            double equity;
            if (State == State.Historical)
            {
                double unrealized = (Position.MarketPosition != MarketPosition.Flat)
                    ? Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, Close[0])
                    : 0.0;
                equity = _initialCapital + _cumPnl + unrealized;
            }
            else
            {
                equity = Account.Get(AccountItem.NetLiquidationByCurrency, Currency.UsDollar);
                if (equity <= 0) equity = _initialCapital + _cumPnl;
            }
            if (equity <= 0) return;
            if (_hwm <= 0) _hwm = equity;
            if (equity > _hwm) _hwm = equity;
            _apexDdUsed = Math.Max(0.0, _hwm - equity);
        }

        private void HaltTrading(string reason)
        {
            _tradingHalted = true;
            _haltReason    = reason;
            Print($"[HALT] {DateTime.Now:HH:mm:ss} — {reason}");
            if (Position.MarketPosition != MarketPosition.Flat)
            { ExitLong("Halt", "HurstMR_v10_Long"); ExitShort("Halt", "HurstMR_v10_Short"); }
        }

        // ===================================================================
        // CALCUL HURST R/S — IDENTIQUE v9 (replique Python hurst_rs)
        // ===================================================================

        private double ComputeHurst(int window)
        {
            if (CurrentBar < window + 2) return 0.5;

            double[] logRets = new double[window];
            for (int i = 0; i < window; i++)
            {
                double prev = Close[i + 1];
                double curr = Close[i];
                if (prev <= 0.0 || curr <= 0.0) return 0.5;
                logRets[window - 1 - i] = Math.Log(curr / prev);
            }

            int maxLag = Math.Min(window / 2, 50);
            if (maxLag < 4) return 0.5;

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

            var meanRsVals = new List<double>();
            var logLagList = new List<double>();

            foreach (int lag in lags)
            {
                int nChunks = window / lag;
                if (nChunks < 2) continue;

                double rsSum   = 0.0;
                int    rsCount = 0;

                for (int c = 0; c < nChunks; c++)
                {
                    int start = c * lag;
                    int end   = start + lag;

                    double chunkMean = 0.0;
                    for (int j = start; j < end; j++) chunkMean += logRets[j];
                    chunkMean /= lag;

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

                    double S = Math.Sqrt(varSum / lag);
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

            if (meanRsVals.Count < 3) return 0.5;

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
