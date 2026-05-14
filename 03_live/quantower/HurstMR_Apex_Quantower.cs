// HurstMR_Apex_Quantower.cs — Strategie Full Auto Quantower.Algo + Rithmic
// Equivalent de HurstMR_Apex.cs (NinjaTrader) pour Quantower
//
// Edge    : Hurst < 0.53 (regime MR confirme) + Z-score +-3sigma (entree)
// TP      : Fair Value = rolling mean 30 barres
// SL      : max(3.0, 0.75 x std), capped a 20.0
// Cible   : Apex Trader Funding $50k EOD
//
// INSTALLATION :
//   1. Compiler ce fichier (voir Quantower Setup dans l'app)
//   2. Copier le DLL dans Scripts\Strategies\
//   3. Strategy Manager → Add → HurstMR_Apex_Quantower
//   4. Lier a ton compte Rithmic Apex sur MNQ M1

using System;
using System.Collections.Generic;
using System.Linq;
using TradingPlatform.BusinessLayer;

public class HurstMR_Apex_Quantower : Strategy
{
    // ── Parametres Signal ────────────────────────────────────────────────────
    [InputParameter("Hurst Seuil (H <)", 0, 0.01, 1.0, 0.01)]
    public double HurstThreshold { get; set; } = 0.53;

    [InputParameter("Hurst Window (barres)", 1, 20, 200, 1)]
    public int HurstWindow { get; set; } = 60;

    [InputParameter("Lookback Bandes (barres)", 2, 10, 100, 1)]
    public int Lookback { get; set; } = 30;

    [InputParameter("Band K (sigma)", 3, 1.0, 5.0, 0.25)]
    public double BandK { get; set; } = 3.0;

    [InputParameter("SL Mult", 4, 0.1, 3.0, 0.05)]
    public double SlMult { get; set; } = 0.75;

    [InputParameter("TP Overshoot (sigma, 0=FV pur)", 5, 0.0, 2.0, 0.1)]
    public double TpOvershoot { get; set; } = 0.0;

    // ── Sizing Kelly ─────────────────────────────────────────────────────────
    [InputParameter("Kelly Risk % / trade", 6, 0.01, 0.50, 0.01)]
    public double KellyRiskPct { get; set; } = 0.10;

    [InputParameter("Contrats max Eval Apex", 7, 1, 10, 1)]
    public int MaxContractsEval { get; set; } = 6;

    [InputParameter("Contrats max PA Apex", 8, 1, 10, 1)]
    public int MaxContractsPA { get; set; } = 4;

    [InputParameter("Mode PA (vs Eval)", 9)]
    public bool ModePA { get; set; } = false;

    // ── Risk ─────────────────────────────────────────────────────────────────
    [InputParameter("Max Trades / Jour", 10, 1, 20, 1)]
    public int MaxTradesDay { get; set; } = 5;

    [InputParameter("Daily Loss Limit ($)", 11, 100, 2000, 100)]
    public double DailyLossLimit { get; set; } = 1000.0;

    [InputParameter("Apex DD Limit ($)", 12, 1000, 5000, 100)]
    public double ApexDdLimit { get; set; } = 2000.0;

    [InputParameter("DD Safety Buffer ($)", 13, 50, 500, 50)]
    public double DdSafetyBuffer { get; set; } = 150.0;

    [InputParameter("Skip Open Barres", 14, 1, 20, 1)]
    public int SkipOpenBars { get; set; } = 5;

    [InputParameter("Symbole (ex: MNQ)", 15)]
    public string SymbolName { get; set; } = "MNQ";

    // ── Variables internes ───────────────────────────────────────────────────
    private Account        _acct;
    private Symbol         _sym;
    private HistoricalData _hd;

    private int      _tradesToday    = 0;
    private double   _dailyPnl       = 0.0;
    private double   _hwm            = 0.0;
    private double   _apexDdUsed     = 0.0;
    private DateTime _lastTradeDate  = DateTime.MinValue;
    private int      _barsInSession  = 0;
    private bool     _sessionStarted = false;
    private bool     _tradingHalted  = false;
    private double   _lastBalance    = 0.0;

    // SL/TP geres manuellement
    private bool   _inPosition  = false;
    private Side   _posSide     = Side.Buy;
    private double _slPrice     = 0.0;
    private double _tpPrice     = 0.0;
    private int    _posQty      = 0;

    private const double MNQ_TICK_VALUE = 2.0;

    private static readonly TimeZoneInfo ParisTZ =
        TimeZoneInfo.FindSystemTimeZoneById("Romance Standard Time");

    // ── Demarrage ────────────────────────────────────────────────────────────
    protected override void OnRun()
    {
        // Selectionne le compte et le symbole
        _acct = Core.Instance.Accounts.FirstOrDefault();
        _sym  = Core.Instance.Symbols.FirstOrDefault(s => s.Name.Contains(SymbolName));

        if (_acct == null || _sym == null)
        {
            Log("ERREUR : compte ou symbole non trouve", StrategyLoggingLevel.Error);
            return;
        }

        _hwm         = _acct.Balance;
        _lastBalance = _hwm;

        // Charge l'historique M1 et s'abonne aux nouvelles barres
        _hd = _sym.GetHistory(new HistoryRequestParameters
        {
            Symbol      = _sym,
            Aggregation = new HistoryAggregationTime(Period.MIN1, HistoryType.Last),
            FromTime    = DateTime.UtcNow.AddDays(-3),
            ToTime      = DateTime.UtcNow,
        });

        _hd.NewHistoryItem += (s, e) =>
        {
            if (e.HistoryItem is HistoryItemBar bar)
                OnNewBar(bar);
        };

        Log($"HurstMR_Apex_Quantower demarree — {_sym.Name} — Balance={_acct.Balance:F0}$ Kelly={KellyRiskPct*100:F0}%",
            StrategyLoggingLevel.Info);
    }

    protected override void OnStop()
    {
        _hd = null;
    }

    // ── Logique principale — executee a chaque cloture M1 ───────────────────
    private void OnNewBar(HistoryItemBar bar)
    {
        int needed = HurstWindow + Lookback + 2;
        if (_hd.Count < needed) return;

        DateTime nowParis = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, ParisTZ);

        // ── Suivi PnL via delta balance ───────────────────────────────────────
        double currentBalance = _acct.Balance;
        if (currentBalance != _lastBalance)
        {
            _dailyPnl    += (currentBalance - _lastBalance);
            _lastBalance  = currentBalance;
        }

        // ── Reset journalier ─────────────────────────────────────────────────
        DateTime today = nowParis.Date;
        if (today != _lastTradeDate)
        {
            _tradesToday    = 0;
            _dailyPnl       = 0.0;
            _tradingHalted  = false;
            _barsInSession  = 0;
            _sessionStarted = false;
            _lastTradeDate  = today;
            _lastBalance    = _acct.Balance;
        }

        // ── Session 15h30 → 22h00 Paris ─────────────────────────────────────
        bool inSession = (nowParis.Hour > 15 || (nowParis.Hour == 15 && nowParis.Minute >= 30))
                      && nowParis.Hour < 22;

        if (inSession && !_sessionStarted) { _sessionStarted = true; _barsInSession = 0; }
        if (inSession) _barsInSession++;

        // ── Gestion SL/TP manuel ─────────────────────────────────────────────
        if (_inPosition)
        {
            double closeNow = (double)bar.Close;
            bool slHit = _posSide == Side.Buy  ? closeNow <= _slPrice : closeNow >= _slPrice;
            bool tpHit = _posSide == Side.Buy  ? closeNow >= _tpPrice : closeNow <= _tpPrice;

            if (slHit || tpHit)
            {
                ClosePosition(slHit ? "SL" : "TP");
                return;
            }
        }

        // ── Flat force a 21h59 Paris ─────────────────────────────────────────
        bool mustBeFlat = nowParis.Hour > 21 ||
                         (nowParis.Hour == 21 && nowParis.Minute >= 59);
        if (mustBeFlat)
        {
            if (_inPosition) ClosePosition("Flat_2159");
            return;
        }

        if (_inPosition) return;

        bool entryAllowed = inSession && !(nowParis.Hour == 21 && nowParis.Minute >= 55);
        if (!entryAllowed) return;
        if (_barsInSession <= SkipOpenBars) return;

        // ── DD tracking ──────────────────────────────────────────────────────
        double equity = _acct.Balance;
        if (equity > _hwm) _hwm = equity;
        _apexDdUsed = Math.Max(0.0, _hwm - equity);

        // ── Verifications risque ─────────────────────────────────────────────
        if (_tradingHalted)                                              return;
        if (_dailyPnl <= -DailyLossLimit)   { HaltTrading("Daily loss limit"); return; }
        if (_tradesToday >= MaxTradesDay)                                return;
        if (_apexDdUsed >= ApexDdLimit - DdSafetyBuffer) { HaltTrading("DD buffer"); return; }

        // ── Signal Hurst ─────────────────────────────────────────────────────
        double hurst = ComputeHurst();
        if (double.IsNaN(hurst) || hurst >= HurstThreshold) return;

        // ── Z-score ──────────────────────────────────────────────────────────
        int    n    = _hd.Count;
        double mean = 0.0, std = 0.0;
        for (int i = 1; i <= Lookback; i++)
        {
            if (_hd[n - 1 - i] is HistoryItemBar b)
                mean += (double)b.Close;
        }
        mean /= Lookback;

        for (int i = 1; i <= Lookback; i++)
        {
            if (_hd[n - 1 - i] is HistoryItemBar b)
                std += ((double)b.Close - mean) * ((double)b.Close - mean);
        }
        std = Math.Sqrt(std / Lookback);
        if (std < 1e-9) return;

        double price  = (double)bar.Close;
        double zScore = (price - mean) / std;
        if (Math.Abs(zScore) < BandK) return;

        // ── Sizing ───────────────────────────────────────────────────────────
        double slPts = Math.Min(Math.Max(3.0, SlMult * std), 20.0);
        int    qty   = ComputeKellyContracts(slPts);
        if (qty <= 0) return;

        double fairValue = mean;
        Side   side      = zScore > 0 ? Side.Sell : Side.Buy;
        double sl        = side == Side.Sell ? price + slPts : price - slPts;
        double tp        = TpOvershoot > 0
            ? (side == Side.Sell ? fairValue - TpOvershoot * std : fairValue + TpOvershoot * std)
            : fairValue;

        // ── Execution ────────────────────────────────────────────────────────
        var result = Core.Instance.PlaceOrder(new PlaceOrderRequestParameters
        {
            Symbol      = _sym,
            Account     = _acct,
            Side        = side,
            Quantity    = qty,
            TimeInForce = TimeInForce.Day,
        });

        if (result?.Status != TradingOperationResultStatus.Failure)
        {
            _inPosition  = true;
            _posSide     = side;
            _slPrice     = sl;
            _tpPrice     = tp;
            _posQty      = qty;
            _tradesToday++;
            Log($"[{side}] {nowParis:HH:mm} H={hurst:F3} Z={zScore:F2} Entry={price:F2} SL={sl:F2} TP={tp:F2} Qty={qty}",
                StrategyLoggingLevel.Trading);
        }
    }

    // ── Fermeture de position ─────────────────────────────────────────────────
    private void ClosePosition(string reason)
    {
        if (!_inPosition) return;

        Side closeSide = _posSide == Side.Buy ? Side.Sell : Side.Buy;
        Core.Instance.PlaceOrder(new PlaceOrderRequestParameters
        {
            Symbol      = _sym,
            Account     = _acct,
            Side        = closeSide,
            Quantity    = _posQty,
            TimeInForce = TimeInForce.Day,
        });

        _inPosition = false;
        Log($"[CLOSE {reason}] Qty={_posQty}", StrategyLoggingLevel.Trading);

        _dailyPnl    += (_acct.Balance - _lastBalance);
        _lastBalance  = _acct.Balance;
    }

    // ── Kelly sizing ─────────────────────────────────────────────────────────
    private int ComputeKellyContracts(double slPts)
    {
        double ddRem = Math.Max(0.0, ApexDdLimit - _apexDdUsed);
        double risk  = Math.Min(KellyRiskPct * ddRem, DailyLossLimit * 0.40);
        risk         = Math.Max(50.0, risk);

        double lossPerC = slPts * MNQ_TICK_VALUE;
        if (lossPerC <= 0.0) return 0;

        int capApex   = ModePA ? MaxContractsPA : MaxContractsEval;
        int contracts = Math.Min((int)(risk / lossPerC), capApex);
        contracts     = Math.Max(1, contracts);

        double budgetRem = Math.Max(0.0, DailyLossLimit + _dailyPnl);
        return Math.Min(contracts, (int)(budgetRem / lossPerC));
    }

    private void HaltTrading(string reason)
    {
        _tradingHalted = true;
        Log($"[HALT] {reason}", StrategyLoggingLevel.Error);
        if (_inPosition) ClosePosition("Halt");
    }

    // ── Hurst R/S ────────────────────────────────────────────────────────────
    private double ComputeHurst()
    {
        int n = _hd.Count;
        if (n < HurstWindow + 2) return 0.5;

        double[] logRets = new double[HurstWindow];
        for (int i = 0; i < HurstWindow; i++)
        {
            var curr = _hd[n - 1 - i] as HistoryItemBar;
            var prev = _hd[n - 2 - i] as HistoryItemBar;
            if (curr == null || prev == null || (double)prev.Close <= 0.0) return 0.5;
            logRets[HurstWindow - 1 - i] = Math.Log((double)curr.Close / (double)prev.Close);
        }

        int maxLag = Math.Min(HurstWindow / 2, 50);
        if (maxLag < 4) return 0.5;

        var lagSet = new HashSet<int>();
        for (int k = 0; k < 12; k++)
        {
            double t      = k == 0 ? 0.0 : (double)k / 11.0;
            double lagDbl = Math.Round(Math.Exp(Math.Log(4) + t * (Math.Log(maxLag) - Math.Log(4))));
            int    lagInt = (int)lagDbl;
            if (lagInt >= 4) lagSet.Add(lagInt);
        }

        int[] lags = lagSet.ToArray();
        Array.Sort(lags);

        var meanRsVals = new List<double>();
        var logLagList = new List<double>();

        foreach (int lag in lags)
        {
            int nChunks = HurstWindow / lag;
            if (nChunks < 2) continue;

            double rsSum = 0.0; int rsCount = 0;
            for (int c = 0; c < nChunks; c++)
            {
                int    start     = c * lag;
                double chunkMean = 0.0;
                for (int j = start; j < start + lag; j++) chunkMean += logRets[j];
                chunkMean /= lag;

                double cumDev = 0.0, maxDev = double.MinValue, minDev = double.MaxValue, varSum = 0.0;
                for (int j = start; j < start + lag; j++)
                {
                    cumDev += logRets[j] - chunkMean;
                    if (cumDev > maxDev) maxDev = cumDev;
                    if (cumDev < minDev) minDev = cumDev;
                    varSum += (logRets[j] - chunkMean) * (logRets[j] - chunkMean);
                }

                double S = Math.Sqrt(varSum / lag);
                if (S > 1e-10) { rsSum += (maxDev - minDev) / S; rsCount++; }
            }

            if (rsCount > 0) { meanRsVals.Add(rsSum / rsCount); logLagList.Add(Math.Log(lag)); }
        }

        if (meanRsVals.Count < 3) return 0.5;

        var logRsList = new List<double>();
        foreach (double rs in meanRsVals) logRsList.Add(Math.Log(rs));
        return Math.Max(0.0, Math.Min(1.0, LinearSlope(logLagList, logRsList)));
    }

    private double LinearSlope(List<double> x, List<double> y)
    {
        int    count = x.Count;
        double sumX  = 0, sumY = 0, sumXY = 0, sumX2 = 0;
        for (int i = 0; i < count; i++)
        { sumX += x[i]; sumY += y[i]; sumXY += x[i]*y[i]; sumX2 += x[i]*x[i]; }
        double denom = count * sumX2 - sumX * sumX;
        if (Math.Abs(denom) < 1e-12) return 0.5;
        return (count * sumXY - sumX * sumY) / denom;
    }
}
