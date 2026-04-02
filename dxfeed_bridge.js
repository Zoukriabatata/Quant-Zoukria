/**
 * dxFeed Bridge — DxLink WebSocket → MNQ M1 candles → C:\tmp\mnq_live.json
 * Protocole DxLink (4PropTrader production)
 * Usage: node dxfeed_bridge.js
 */

const WebSocket = require("ws");
const fs        = require("fs");

// Toujours URL propre — les credentials passent par AUTH, pas dans l'URL
const HOST = "wss://get-prod-dxlink-rt.dxfeed.com/realtime";

// Lit le token JWT via PowerShell (bypass lock Windows sur dxapi.log.0)
function getTokenFromAtasLog() {
    const { execSync } = require("child_process");
    const ps1 = __dirname + "\\get_dxfeed_token.ps1";
    try {
        const token = execSync(`powershell -NoProfile -ExecutionPolicy Bypass -File "${ps1}"`, { encoding: "utf8" }).trim();
        if (token) { console.log("  Token lu depuis dxapi.log.0"); return token; }
    } catch (e) { console.log("  PowerShell erreur:", e.message.slice(0, 80)); }
    return null;
}

const TOKEN = process.env.DXFEED_TOKEN || getTokenFromAtasLog();
console.log("  Token:", TOKEN ? TOKEN.slice(0, 30) + "..." : "INTROUVABLE");
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
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify({
        updated: new Date().toISOString(),
        last_bar: closedBar || liveBar,
        live_bar: liveBar,
        bars: barBuffer.slice(-120),
    }, null, 2));
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
        console.log(`\n  Déconnecté (${code}). Reconnexion dans 5s...`);
        reconnectTimer = setTimeout(connect, 5000);
    });

    ws.on("error", (err) => {
        console.error("\n❌ WS Erreur:", err.message);
    });
}

connect();
