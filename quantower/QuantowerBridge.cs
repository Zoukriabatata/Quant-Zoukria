// QuantowerBridge.cs — Indicateur Quantower
// Equivalent de RithmicBridge.cs (NinjaTrader) pour Quantower + Rithmic
// Ecrit C:\tmp\mnq_live.json a chaque tick/bougie M1
// Python/Streamlit lit ce fichier pour afficher le signal live
//
// INSTALLATION :
//   1. Compile en DLL (voir Quantower_Setup dans l'app)
//   2. Copie QuantowerBridge.dll dans Scripts\Indicators\
//   3. Ajoute l'indicateur sur le chart MNQ M1
//   4. Verifie que C:\tmp\mnq_live.json est cree

using System;
using System.IO;
using System.Text;
using System.Globalization;
using System.Threading;
using TradingPlatform.BusinessLayer;

public class QuantowerBridge : Indicator
{
    private const string OUTPUT_FILE = @"C:\tmp\mnq_live.json";
    private static readonly CultureInfo IC = CultureInfo.InvariantCulture;

    private volatile string _pendingJson = null;
    private Thread          _writerThread;
    private volatile bool   _running     = false;

    public QuantowerBridge() : base()
    {
        Name           = "Quantower Bridge";
        SeparateWindow = false;
    }

    protected override void OnInit()
    {
        if (!Directory.Exists(@"C:\tmp"))
            Directory.CreateDirectory(@"C:\tmp");

        _running      = true;
        _writerThread = new Thread(WriterLoop)
        {
            IsBackground = true,
            Name         = "QTBridgeWriter"
        };
        _writerThread.Start();
    }

    protected override void OnUpdate(UpdateArgs args)
    {
        if (this.Count < 5) return;
        _pendingJson = BuildJson();
    }

    protected override void OnClear()
    {
        _running = false;
        _writerThread?.Join(2000);
    }

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
                    File.WriteAllText(tmpFile, json, new UTF8Encoding(false));
                    File.Copy(tmpFile, OUTPUT_FILE, overwrite: true);
                }
                catch { }
            }
            Thread.Sleep(200);
        }
    }

    private string BuildJson()
    {
        var    sb  = new StringBuilder(16384);
        string now = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", IC);

        sb.Append('{');
        sb.Append("\"updated\":\"").Append(now).Append("\",");
        sb.Append("\"last_bar\":").Append(BarToJson(1)).Append(',');
        sb.Append("\"live_bar\":").Append(BarToJson(0, true)).Append(',');

        int  count = Math.Min(120, this.Count - 2);
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

    private string BarToJson(int offset, bool isLive = false)
    {
        var    item = (HistoryItemBar)this.HistoricalData[offset];
        string iso  = item.TimeLeft.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ", IC);
        string live = isLive ? ",\"live\":true" : "";
        return string.Format(IC,
            "{{\"time\":\"{0}\",\"open\":{1:F2},\"high\":{2:F2},\"low\":{3:F2},\"close\":{4:F2},\"volume\":{5:F0}{6}}}",
            iso, (double)item.Open, (double)item.High, (double)item.Low, (double)item.Close, (double)item.Volume, live);
    }
}
