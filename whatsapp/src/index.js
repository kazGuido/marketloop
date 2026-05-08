import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState
} from "@whiskeysockets/baileys";
import express from "express";
import Pino from "pino";
import qrcode from "qrcode-terminal";

const PORT = Number(process.env.PORT || 3000);
const AUTH_DIR = process.env.BAILEYS_AUTH_DIR || "/data/auth";
const API_KEY = process.env.BAILEYS_API_KEY || "";

const logger = Pino({ level: process.env.LOG_LEVEL || "info" });
let sock = null;
let latestQr = null;
let connected = false;

async function startSocket() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();
  sock = makeWASocket({
    version,
    auth: state,
    logger: logger.child({ module: "baileys" }),
    browser: ["Harmonic Sentinel", "Chrome", "1.0.0"]
  });

  sock.ev.on("creds.update", saveCreds);
  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      latestQr = qr;
      logger.info("WhatsApp pairing QR generated");
      qrcode.generate(qr, { small: true });
    }
    if (connection === "open") {
      connected = true;
      latestQr = null;
      logger.info("WhatsApp bridge connected");
    }
    if (connection === "close") {
      connected = false;
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      logger.warn({ statusCode, shouldReconnect }, "WhatsApp bridge disconnected");
      if (shouldReconnect) {
        setTimeout(() => startSocket().catch((error) => logger.error({ error }, "Reconnect failed")), 3000);
      }
    }
  });
}

function requireApiKey(req, res, next) {
  if (!API_KEY) return next();
  if (req.header("x-api-key") !== API_KEY) {
    return res.status(401).json({ error: "unauthorized" });
  }
  return next();
}

function toJid(input) {
  if (!input || typeof input !== "string") {
    throw new Error("recipient is required");
  }
  if (input.includes("@")) return input;
  const digits = input.replace(/\D/g, "");
  if (!digits) throw new Error("recipient must contain digits or be a WhatsApp JID");
  return `${digits}@s.whatsapp.net`;
}

const app = express();
app.use(express.json({ limit: "256kb" }));

app.get("/health", (_req, res) => {
  res.json({ status: "ok", connected, hasQr: Boolean(latestQr) });
});

app.get("/status", requireApiKey, (_req, res) => {
  res.json({ connected, qr: latestQr });
});

app.post("/send", requireApiKey, async (req, res) => {
  try {
    if (!sock || !connected) {
      return res.status(503).json({ error: "whatsapp bridge is not connected", hasQr: Boolean(latestQr) });
    }
    const jid = toJid(req.body?.to);
    const text = String(req.body?.message || "");
    if (!text.trim()) {
      return res.status(400).json({ error: "message is required" });
    }
    const result = await sock.sendMessage(jid, { text });
    return res.json({ status: "sent", jid, id: result?.key?.id });
  } catch (error) {
    logger.error({ error }, "Failed to send WhatsApp message");
    return res.status(400).json({ error: error.message || "send failed" });
  }
});

app.listen(PORT, () => {
  logger.info({ port: PORT }, "WhatsApp bridge listening");
});

startSocket().catch((error) => {
  logger.error({ error }, "Failed to start WhatsApp bridge");
});
