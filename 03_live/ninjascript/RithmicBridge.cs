using System;
using System.IO;
using System.Text;
using System.Globalization;
using System.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class RithmicBridge : Indicator
    {
        private const string OUTPUT_FILE = @"C:\tmp\mnq_live.json";
        private static readonly CultureInfo IC = CultureInfo.InvariantCulture;

        // Thread background — jamais de File I/O sur le thread NinjaTrader
        private volatile string _pendingJson = null;
        private Thread          _writerThread;
        private volatile bool   _running     = false;
        private DateTime        _lastBuild   = DateTime.MinValue;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description              = "Rithmic Bridge MNQ M1 vers mnq_live.json";
                Name                     = "RithmicBridge";
                Calculate                = Calculate.OnPriceChange;
                IsOverlay                = true;
                DisplayInDataBox         = false;
                DrawOnPricePanel         = false;
                IsSuspendedWhileInactive = false;
                ScaleJustification       = NinjaTrader.Gui.Chart.ScaleJustification.Right;
            }
            else if (State == State.DataLoaded)
            {
                if (!Directory.Exists(@"C:\tmp"))
                    Directory.CreateDirectory(@"C:\tmp");

                _running      = true;
                _writerThread = new Thread(WriterLoop)
                {
                    IsBackground = true,
                    Name         = "RithmicBridgeWriter"
                };
                _writerThread.Start();
            }
            else if (State == State.Terminated)
            {
                _running = false;
                _writerThread?.Join(2000);
                _writerThread = null;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 2) return;

            // Throttle : construit le JSON max 1x/seconde — zéro I/O ici
            DateTime now = DateTime.UtcNow;
            if ((now - _lastBuild).TotalMilliseconds < 1000) return;
            _lastBuild   = now;
            _pendingJson = BuildJson();
        }

        // ── Thread background : seul responsable du disque ──────────────
        private void WriterLoop()
        {
            string tmpFile = OUTPUT_FILE + ".tmp";
            while (_running)
            {
                string json = _pendingJson;
                if (json != null)
                {
                    _pendingJson = null;
                    try
                    {
                        File.WriteAllText(tmpFile, json, new UTF8Encoding(false));  // BOM false — JSON pur UTF8
                        File.Copy(tmpFile, OUTPUT_FILE, overwrite: true);
                    }
                    catch { }
                }
                Thread.Sleep(200);
            }
        }

        // ── Construction JSON — uniquement lecture de données prix ───────
        private string BuildJson()
        {
            StringBuilder sb  = new StringBuilder(16384);
            string        now = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", IC);

            sb.Append('{');
            sb.Append("\"updated\":\"").Append(now).Append("\",");
            sb.Append("\"last_bar\":").Append(BarToJson(1)).Append(',');
            sb.Append("\"live_bar\":").Append(BarToJson(0, true)).Append(',');

            int  count = Math.Min(120, CurrentBar - 1);
            bool first = true;
            sb.Append("\"bars\":[");
            for (int i = count; i >= 1; i--)
            {
                if (!first) sb.Append(',');
                sb.Append(BarToJson(i));
                first = false;
            }
            sb.Append("]}");
            return sb.ToString();
        }

        private string BarToJson(int idx, bool isLive = false)
        {
            DateTime dt   = Time[idx].ToUniversalTime();
            string   iso  = dt.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", IC);
            string   o    = Open[idx].ToString("F2", IC);
            string   h    = High[idx].ToString("F2", IC);
            string   l    = Low[idx].ToString("F2", IC);
            string   c    = Close[idx].ToString("F2", IC);
            string   v    = Volume[idx].ToString("F0", IC);
            string   live = isLive ? ",\"live\":true" : "";
            return string.Format(IC,
                "{{\"time\":\"{0}\",\"open\":{1},\"high\":{2},\"low\":{3},\"close\":{4},\"volume\":{5}{6}}}",
                iso, o, h, l, c, v, live);
        }
    }
}
