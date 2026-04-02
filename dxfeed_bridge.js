/**
 * dxFeed Bridge — stream MNQ M1 candles → C:\tmp\mnq_live.json
 * Usage: node dxfeed_bridge.js
 * Requires: @dxfeed/graal-nodejs-api (bundled avec dx-feed-viewer-ng)
 *
 * Ce script se connecte à 4PropTrader via dxFeed et écrit
 * chaque barre M1 fermée dans un fichier JSON que Python lit.
 */

const path = require("path");
const fs   = require("fs");

// Chemin vers le module dxFeed (dx-feed-viewer-ng)
const DXFEED_MODULE = path.join(
    process.env.LOCALAPPDATA || "C:\\Users\\ryadb\\AppData\\Local",
    "Programs", "dx-feed-viewer-ng", "resources",
    "app.asar.unpacked", "node_modules", "@dxfeed", "graal-nodejs-api"
);

// Credentials (même que ATAS)
const HOST     = process.env.DXFEED_HOST     || "data.4proptrader.com:7300";
const LOGIN    = process.env.DXFEED_LOGIN    || "ryad.bouderga78@gmail.com";
const PASSWORD = process.env.DXFEED_PASSWORD || "69ce550296eb4";

const OUTPUT_FILE = "C:\\tmp\\mnq_live.json";

// Assure que C:\tmp existe
if (!fs.existsSync("C:\\tmp")) fs.mkdirSync("C:\\tmp", { recursive: true });

let DXFeed;
try {
    DXFeed = require(DXFEED_MODULE);
} catch (e) {
    console.error("❌ Module dxFeed introuvable:", DXFEED_MODULE);
    console.error(e.message);
    process.exit(1);
}

console.log("=".repeat(55));
console.log("  dxFeed Bridge — MNQ M1  |  4PropTrader");
console.log("=".repeat(55));
console.log("Host   :", HOST);
console.log("Output :", OUTPUT_FILE);
console.log("");

// Buffer de barres pour la session courante
const barBuffer = [];

async function main() {
    try {
        // Connexion dxFeed
        const endpoint = DXFeed.DXEndpoint.create();
        await endpoint.connect(`${HOST}[login=${LOGIN},password=${PASSWORD}]`);

        console.log("✓ Connecté à dxFeed");

        // Abonnement Candle M1 pour /MNQ (front-month futures)
        const feed       = endpoint.getFeed();
        const sub        = feed.createSubscription(DXFeed.Candle);

        // Symbol format dxFeed : /MNQ{=1m}
        const candleSymbol = DXFeed.CandleSymbol.valueOf("/MNQ{=1m}");
        sub.addSymbols([candleSymbol]);

        console.log("✓ Abonné à /MNQ{=1m}");
        console.log("En attente de barres M1...\n");

        sub.addEventListener((events) => {
            for (const event of events) {
                try {
                    const bar = {
                        time:   new Date(Number(event.time)).toISOString(),
                        open:   Number(event.open),
                        high:   Number(event.high),
                        low:    Number(event.low),
                        close:  Number(event.close),
                        volume: Number(event.volume),
                        count:  Number(event.count || 0),
                    };

                    // Ignore barres invalides
                    if (!bar.close || bar.close <= 0) continue;

                    barBuffer.push(bar);

                    // Garde max 600 barres (session ~10h)
                    if (barBuffer.length > 600) barBuffer.shift();

                    // Écrit dans le fichier JSON
                    const output = {
                        updated:  new Date().toISOString(),
                        last_bar: bar,
                        bars:     barBuffer.slice(-120), // dernière 2h
                    };
                    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2));

                    process.stdout.write(
                        `\r  [${bar.time.slice(11,16)} UTC] close=${bar.close.toFixed(2)}  bars=${barBuffer.length}   `
                    );
                } catch (e) {
                    // Barre incomplète, ignore
                }
            }
        });

    } catch (e) {
        console.error("\n❌ Erreur connexion dxFeed:", e.message);
        console.error("   Vérifier HOST dans .env ou en argument");
        console.error("   Essayer: DXFEED_HOST=demo.dxfeed.com:7300 node dxfeed_bridge.js");
        process.exit(1);
    }
}

main();
