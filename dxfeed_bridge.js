/**
 * dxFeed Bridge — DxLink WebSocket → MNQ M1 candles → C:\tmp\mnq_live.json
 * Protocole DxLink (4PropTrader production)
 * Usage: node dxfeed_bridge.js
 */

const WebSocket = require("ws");
const fs        = require("fs");
const https     = require("https");
const path      = require("path");

// Charge .env manuellement (pas besoin de dotenv)
function loadEnv() {
    const envPath = path.join(__dirname, ".env");
    if (!fs.existsSync(envPath)) { console.log("  .env introuvable à:", envPath); return; }
    fs.readFileSync(envPath, "utf8").split(/\r?\n/).forEach(line => {
        const [k, ...v] = line.split("=");
        if (k && v.length) process.env[k.trim()] = v.join("=").trim();
    });
}
loadEnv();

const HOST = "wss://get-prod-dxlink-rt.dxfeed.com/realtime";

// ── Utilitaires HTTP ──────────────────────────────────────────────────────────
function generateUUID() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0;
        return (c === "x" ? r : (r & 0x3 | 0x8)).toString(16);
    });
}

function httpsRequest(method, url, body, extraHeaders = {}) {
    return new Promise((resolve, reject) => {
        const u = new URL(url);
        const bodyBuf = body ? Buffer.from(body, "utf8") : null;
        const opts = {
            hostname: u.hostname,
            path: u.pathname + u.search,
            method,
            rejectUnauthorized: false,
            headers: {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                ...(bodyBuf ? { "Content-Length": bodyBuf.length } : {}),
                ...extraHeaders,
            },
        };
        const req = https.request(opts, res => {
            const setCookie = res.headers["set-cookie"] || [];
            if ([301, 302, 303].includes(res.statusCode) && res.headers.location) {
                const next = res.headers.location.startsWith("http")
                    ? res.headers.location
                    : new URL(res.headers.location, url).href;
                res.resume();
                return resolve(httpsRequest("GET", next, null, extraHeaders)
                    .then(r => ({ ...r, cookies: [...setCookie, ...(r.cookies || [])] })));
            }
            let data = "";
            res.on("data", c => data += c);
            res.on("end", () => resolve({ status: res.statusCode, body: data.trim(), cookies: setCookie }));
        }).on("error", reject);
        if (bodyBuf) req.write(bodyBuf);
        req.end();
    });
}

// ── 1. Token via Volumetric Trading API (4PropTrader — MÉTHODE PRINCIPALE) ───
// Comment obtenir le VOLUMETRIC_JTOKEN :
//   → Ouvre https://4proptrader.com/iframes/volumetric-app/301700
//   → Copie le paramètre jtoken= depuis l'URL de la page qui s'ouvre
//   → Colle dans .env : VOLUMETRIC_JTOKEN=eyJhbGci...
//   Le jtoken est valide 24h. À renouveler chaque jour de trading.
async function getTokenFromVolumetric() {
    const jtoken  = process.env.VOLUMETRIC_JTOKEN   || "";
    const popupId = process.env.VOLUMETRIC_POPUP_ID || "";
    if (!jtoken) return null;

    // Vérifie expiration du jtoken
    try {
        const payload = JSON.parse(Buffer.from(jtoken.split(".")[1], "base64").toString());
        if (payload.exp && Date.now() / 1000 > payload.exp) {
            console.log("  ⚠️  VOLUMETRIC_JTOKEN expiré — ouvre 4PropTrader pour en obtenir un nouveau");
            return null;
        }
    } catch {}

    try {
        // Étape 1 : GET la page webapp avec jtoken → établit la session (cookie)
        const pageUrl = popupId
            ? `https://webapp.volumetricatrading.com/?popupId=${popupId}&theme=2&jtoken=${jtoken}`
            : `https://webapp.volumetricatrading.com/?jtoken=${jtoken}&theme=2`;
        const pageResp = await httpsRequest("GET", pageUrl, null, {
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "fr-FR,fr;q=0.9",
        });
        const cookies = (pageResp.cookies || []).map(c => c.split(";")[0]).join("; ");

        // Étape 2 : POST /api/connections/dxfeed/Auth avec le cookie de session
        const body = `connectionId=${generateUUID()}`;
        const authResp = await httpsRequest("POST",
            "https://webapp.volumetricatrading.com/api/connections/dxfeed/Auth",
            body,
            {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://webapp.volumetricatrading.com",
                "Referer": pageUrl,
                "X-Requested-With": "XMLHttpRequest",
                ...(cookies ? { "Cookie": cookies } : {}),
            }
        );

        if (authResp.status === 200) {
            const data = JSON.parse(authResp.body);
            if (data.success && data.data && data.data.dataToken) {
                console.log("  Token via Volumetric API ✓ (fourproptrader-nonpro)");
                return data.data.dataToken;
            }
            console.log("  Volumetric API réponse inattendue:", authResp.body.slice(0, 120));
        } else {
            console.log("  Volumetric API HTTP", authResp.status);
        }
    } catch (e) {
        console.log("  Volumetric API erreur:", e.message);
    }
    return null;
}

// ── 2. Lit token depuis logs ATAS (fallback si ATAS connecté au compte réel) ──
function getTokenFromAtasLog() {
    const { execSync } = require("child_process");
    const ps1 = __dirname + "\\get_dxfeed_token.ps1";
    try {
        const token = execSync(`powershell -NoProfile -ExecutionPolicy Bypass -File "${ps1}"`, { encoding: "utf8" }).trim();
        if (!token) return null;
        try {
            const decoded = Buffer.from(token.split(".")[0], "base64").toString("utf8");
            if (decoded.includes("atas-demo")) {
                console.log("  ⚠️  Token ATAS = compte DEMO → invalide. Ajoute VOLUMETRIC_JTOKEN dans .env");
                return null;
            }
        } catch {}
        console.log("  Token depuis ATAS log (compte live)");
        return token;
    } catch (e) { console.log("  PowerShell erreur:", e.message.slice(0, 80)); }
    return null;
}

// ── Obtient un token valide — priorité : Volumetric > ATAS ───────────────────
async function getToken() {
    const volToken = await getTokenFromVolumetric();
    if (volToken) return volToken;
    const atasToken = getTokenFromAtasLog();
    if (atasToken) return atasToken;
    return null;
}

// Lance la connexion une fois le token obtenu
getToken().then(token => {
    if (!token) {
        console.error("❌ Token introuvable.");
        console.error("   → Ajoute dans .env : VOLUMETRIC_JTOKEN=<jtoken depuis 4PropTrader>");
        console.error("   → Ouvre : https://4proptrader.com/iframes/volumetric-app/301700");
        console.error("   → Copie le paramètre jtoken= de l'URL de la page webapp");
        process.exit(1);
    }
    console.log("  Token:", token.slice(0, 30) + "...");
    startBridge(token);
}).catch(err => {
    console.error("❌ Erreur init:", err.message);
    process.exit(1);
});

// Tout le reste de la logique est dans startBridge(TOKEN)
function startBridge(initialToken) {
let TOKEN = initialToken;
// Test plusieurs symboles jusqu'à recevoir des ticks
const SYMBOLS_TO_TEST = ["/MNQM26:XCME", "/MNQM6:XCME", "/MNQM6", "#MNQM6", "MNQM6"];
let symbolIdx = 0;
let SYMBOL = SYMBOLS_TO_TEST[symbolIdx];
let tickTimeout;
const OUTPUT_FILE = "C:\\tmp\\mnq_live.json";

if (!fs.existsSync("C:\\tmp")) fs.mkdirSync("C:\\tmp", { recursive: true });

console.log("=".repeat(55));
console.log("  dxFeed Bridge — MNQ M1 (DxLink WebSocket)");
console.log("=".repeat(55));
console.log("Host   :", HOST);
console.log("Output :", OUTPUT_FILE);
console.log("");

// ── Candle builder ──────────────────────────────────────────
const barBuffer = [];
let currentBar  = null;

function floorMinute(ms) { return Math.floor(ms / 60000) * 60000; }

function writeFile(closedBar) {
    const liveBar = currentBar ? {
        time: new Date(currentBar.ts).toISOString(),
        open: currentBar.open, high: currentBar.high,
        low: currentBar.low,  close: currentBar.close,
        volume: currentBar.volume, live: true,
    } : null;
    try {
        fs.writeFileSync(OUTPUT_FILE, JSON.stringify({
            updated: new Date().toISOString(),
            last_bar: closedBar || liveBar,
            live_bar: liveBar,
            bars: barBuffer.slice(-120),
        }));
    } catch(e) { /* fichier momentanément verrouillé, on ignore */ }
}

function onTick(price, ts) {
    const barTs = floorMinute(ts);
    if (!currentBar || currentBar.ts !== barTs) {
        if (currentBar) {
            const bar = {
                time: new Date(currentBar.ts).toISOString(),
                open: currentBar.open, high: currentBar.high,
                low: currentBar.low,  close: currentBar.close,
                volume: currentBar.volume,
            };
            barBuffer.push(bar);
            if (barBuffer.length > 600) barBuffer.shift();
            process.stdout.write(
                `\r  [${bar.time.slice(11,16)} UTC] C=${bar.close.toFixed(2)}  bars=${barBuffer.length}   `
            );
            currentBar = { ts: barTs, open: price, high: price, low: price, close: price, volume: 1 };
            writeFile(bar);
        } else {
            currentBar = { ts: barTs, open: price, high: price, low: price, close: price, volume: 1 };
            writeFile(null);
        }
    } else {
        if (price > currentBar.high) currentBar.high = price;
        if (price < currentBar.low)  currentBar.low  = price;
        currentBar.close = price;
        currentBar.volume++;
        writeFile(null);
    }
}

// ── DxLink WebSocket ─────────────────────────────────────────
const CHANNEL = 1;
let ws;
let keepaliveTimer;
let reconnectTimer;
let connected = false;
let channelOpened = false;

function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(obj));
    }
}

function subscribe() {
    send({ type: "CHANNEL_REQUEST", channel: CHANNEL, service: "FEED", parameters: { contract: "AUTO" } });
}

function trySubscribe() {
    console.log(`✓ FEED_CONFIG → test symbole: ${SYMBOL}`);
    send({ type: "FEED_SUBSCRIPTION", channel: CHANNEL, add: [{ type: "Quote", symbol: SYMBOL }, { type: "Trade", symbol: SYMBOL }] });
    // Si pas de ticks dans 5s, essaie le symbole suivant
    tickTimeout = setTimeout(() => {
        symbolIdx++;
        if (symbolIdx >= SYMBOLS_TO_TEST.length) {
            console.log("❌ Aucun symbole ne retourne de données. Marché fermé ?");
            return;
        }
        SYMBOL = SYMBOLS_TO_TEST[symbolIdx];
        console.log(`  → Pas de ticks, essai: ${SYMBOL}`);
        send({ type: "FEED_SUBSCRIPTION", channel: CHANNEL, reset: true, add: [{ type: "Quote", symbol: SYMBOL }, { type: "Trade", symbol: SYMBOL }] });
        tickTimeout = setTimeout(arguments.callee, 5000);
    }, 5000);
}

const seenTypes = new Set();

function onMessage(raw) {
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }

    // Debug: affiche chaque type de message reçu (une fois)
    if (!seenTypes.has(msg.type)) {
        seenTypes.add(msg.type);
        console.log("  [MSG]", msg.type, JSON.stringify(msg).slice(0, 120));
    }

    switch (msg.type) {

        case "SETUP":
            send({ type: "SETUP", channel: 0, version: "1.0", keepaliveTimeout: 60, acceptKeepaliveTimeout: 60 });
            break;

        case "AUTH_STATE":
            if (msg.state === "UNAUTHORIZED") {
                if (!TOKEN) { console.error("❌ Token introuvable — ATAS doit être ouvert et connecté"); process.exit(1); }
                send({ type: "AUTH", channel: 0, token: TOKEN });
            } else if (msg.state === "AUTHORIZED" && !channelOpened) {
                channelOpened = true;
                console.log("✓ Authentifié → ouverture channel");
                subscribe();
            }
            break;

        case "CHANNEL_OPENED":
            if (msg.channel === CHANNEL) {
                console.log("✓ Channel Feed ouvert → envoi FEED_SETUP");
                send({
                    type: "FEED_SETUP", channel: CHANNEL,
                    acceptDataFormat: "COMPACT",
                    acceptEventFields: {
                        "Quote": ["bidPrice", "askPrice", "bidTime"],
                        "Trade": ["price", "size", "time"],
                    },
                });
            }
            break;

        case "FEED_CONFIG":
            if (seenTypes.has("FEED_CONFIG_DONE")) break;
            seenTypes.add("FEED_CONFIG_DONE"); // évite double subscribe
            trySubscribe();
            break;

        case "FEED_DATA": {
            // Format COMPACT: [evtType, [val0, val1, ...], [val0, val1, ...], ...]
            // Fields définis dans FEED_SETUP acceptEventFields (positionnels):
            //   Quote: [bidPrice, askPrice, bidTime]
            //   Trade: [price, size, time]
            const data = msg.data;
            if (!Array.isArray(data) || typeof data[0] !== "string") break;
            const evtType = data[0];
            for (let i = 1; i < data.length; i++) {
                const vals = data[i];
                if (!Array.isArray(vals)) continue;
                let price = 0, ts = Date.now();
                if (evtType === "Quote") {
                    const bid = Number(vals[0]), ask = Number(vals[1]);
                    if (bid > 0 && ask > 0) { price = (bid + ask) / 2; ts = vals[2] || ts; }
                } else if (evtType === "Trade") {
                    price = Number(vals[0]);
                    ts = vals[2] || ts;
                }
                if (price > 0) {
                    if (tickTimeout) { clearTimeout(tickTimeout); tickTimeout = null; console.log(`✓ Ticks reçus sur ${SYMBOL} (${evtType})`); }
                    onTick(price, typeof ts === "number" ? ts : Date.now());
                }
            }
            break;
        }

        case "KEEPALIVE":
            send({ type: "KEEPALIVE", channel: 0 });
            break;

        case "ERROR":
            console.error("\n❌ Erreur DxLink:", msg.error, msg.message || "");
            if (msg.error === "UNAUTHORIZED") {
                console.log("  → Token rejeté. Tentative de renouvellement...");
                clearInterval(keepaliveTimer);
                clearTimeout(tickTimeout);
                ws.terminate();
                getTokenFromAPI().then(freshToken => {
                    if (freshToken) {
                        console.log("  → Nouveau token REST ✓");
                        TOKEN = freshToken;
                    } else {
                        // REST API indispo → fallback logs ATAS
                        const atasToken = getTokenFromAtasLog();
                        if (atasToken && atasToken !== TOKEN) {
                            console.log("  → Nouveau token ATAS ✓");
                            TOKEN = atasToken;
                        } else {
                            console.log("  → Aucun nouveau token — ouvre ATAS pour renouveler");
                        }
                    }
                    reconnectTimer = setTimeout(() => { reconnectTimer = null; connect(); }, 10000);
                }).catch(() => {
                    const atasToken = getTokenFromAtasLog();
                    if (atasToken && atasToken !== TOKEN) { TOKEN = atasToken; }
                    reconnectTimer = setTimeout(() => { reconnectTimer = null; connect(); }, 10000);
                });
            }
            break;
    }
}

function connect() {
    console.log(`Connexion → ${HOST}`);
    ws = new WebSocket(HOST, { rejectUnauthorized: false });

    ws.on("open", () => {
        connected = true;
        process.stdout.write("  État: CONNECTED\n");
        // Le client envoie SETUP en premier dans DxLink
        send({ type: "SETUP", channel: 0, version: "1.0", keepaliveTimeout: 60, acceptKeepaliveTimeout: 60 });
        keepaliveTimer = setInterval(() => {
            send({ type: "KEEPALIVE", channel: 0 });
        }, 30000);
    });

    ws.on("message", (data) => onMessage(data.toString()));

    ws.on("close", (code, reason) => {
        connected = false;
        clearInterval(keepaliveTimer);
        channelOpened = false;
        if (reconnectTimer) return; // déjà planifié par ERROR handler
        console.log(`\n  Déconnecté (${code}). Renouvellement token + reconnexion dans 5s...`);
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            getTokenFromAPI().then(freshToken => {
                if (freshToken) { TOKEN = freshToken; console.log("  → Token REST renouvelé ✓"); }
                else {
                    const atasToken = getTokenFromAtasLog();
                    if (atasToken && atasToken !== TOKEN) { TOKEN = atasToken; console.log("  → Token ATAS renouvelé ✓"); }
                }
                connect();
            }).catch(() => {
                const atasToken = getTokenFromAtasLog();
                if (atasToken && atasToken !== TOKEN) { TOKEN = atasToken; }
                connect();
            });
        }, 5000);
    });

    ws.on("error", (err) => {
        console.error("\n❌ WS Erreur:", err.message);
    });
}

connect();
} // fin startBridge
