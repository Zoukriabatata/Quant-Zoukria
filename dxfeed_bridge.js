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

// Le module api.js utilise process.cwd() sur Windows (bug path.includes avec backslash)
// Fix : changer CWD vers le répertoire du module avant le require
const _origCwd = process.cwd();
process.chdir(DXFEED_MODULE);

let DXFeed;
try {
    DXFeed = require(DXFEED_MODULE);
} catch (e) {
    console.error("❌ Module dxFeed introuvable:", DXFEED_MODULE);
    console.error(e.message);
    process.exit(1);
} finally {
    process.chdir(_origCwd);
}

console.log("=".repeat(55));
console.log("  dxFeed Bridge — MNQ M1  |  4PropTrader");
console.log("=".repeat(55));
console.log("Host   :", HOST);
console.log("Output :", OUTPUT_FILE);
console.log("");

// Buffer de barres pour la session courante
const barBuffer = [];

function main() {
    try {
        // API : new Endpoint(url), connect(callback), createSubscription(eventType)
        const url      = `${HOST}[login=${LOGIN},password=${PASSWORD}]`;
        const endpoint = new DXFeed.Endpoint(url);
        // Abonnement créé avant connect (dxFeed bufferise jusqu'à connexion)
        const sub = endpoint.createSubscription("Candle");
        sub.addSymbols(["/MNQ{=1m}"]);
        console.log("✓ Abonnement /MNQ{=1m} enregistré");

        endpoint.connect((state) => {
            if (state === "CONNECTED") {
                console.log("\n✅ Connecté à dxFeed —", HOST);
                console.log("En attente de barres M1...\n");
            } else {
                process.stdout.write(`\r  État: ${state}   `);
            }
        });
        console.log("✓ Connexion dxFeed en cours →", HOST);

        sub.addEventListener((events) => {
            for (const event of events) {
                try {
                    const close = Number(event.close);
                    if (!close || close <= 0) continue;

                    const bar = {
                        time:   new Date(Number(event.time)).toISOString(),
                        open:   Number(event.open)  || close,
                        high:   Number(event.high)  || close,
                        low:    Number(event.low)   || close,
                        close:  close,
                        volume: Number(event.volume) || 0,
                    };

                    barBuffer.push(bar);
                    if (barBuffer.length > 600) barBuffer.shift();

                    fs.writeFileSync(OUTPUT_FILE, JSON.stringify({
                        updated:  new Date().toISOString(),
                        last_bar: bar,
                        bars:     barBuffer.slice(-120),
                    }, null, 2));

                    process.stdout.write(
                        `\r  [${bar.time.slice(11,16)} UTC] ${bar.close.toFixed(2)}  bars=${barBuffer.length}   `
                    );
                } catch (_) {}
            }
        });

    } catch (e) {
        console.error("\n❌ Erreur:", e.message);
        console.error("   HOST actuel:", HOST);
        console.error("   Essayer: set DXFEED_HOST=demo.dxfeed.com:7300 && node dxfeed_bridge.js");
        process.exit(1);
    }
}

// Keep-alive
setInterval(() => {}, 60000);

main();
