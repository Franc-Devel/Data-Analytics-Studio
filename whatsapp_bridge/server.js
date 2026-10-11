const path = require('path');
const fs = require('fs');

// Cargar variables de entorno desde .env raíz si existe
const dotenv = require('dotenv');
const rootEnvPath = path.join(__dirname, '..', '.env');
if (fs.existsSync(rootEnvPath)) {
  dotenv.config({ path: rootEnvPath });
} else {
  dotenv.config();
}

let makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion, Browsers;

async function loadBaileys() {
  if (!makeWASocket) {
    const baileys = await import('@whiskeysockets/baileys');
    makeWASocket = baileys.default || baileys.makeWASocket;
    useMultiFileAuthState = baileys.useMultiFileAuthState;
    DisconnectReason = baileys.DisconnectReason;
    fetchLatestBaileysVersion = baileys.fetchLatestBaileysVersion;
    Browsers = baileys.Browsers;
  }
}
const express = require('express');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const pino = require('pino');
const QRCode = require('qrcode');

const crypto = require('crypto');
const app = express();

// Seguridad de cabeceras HTTP
app.use(helmet());

// Límite estricto de tamaño de payload JSON
app.use(express.json({ limit: '100kb' }));

// Limitadores de tasa de peticiones (Rate Limiting)
const generalLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minuto
  max: 120, // 120 peticiones por minuto
  standardHeaders: true,
  legacyHeaders: false,
  message: { ok: false, error: 'Demasiadas solicitudes. Intente nuevamente en un minuto.' },
});

const sensitiveActionLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minuto
  max: 15, // 15 intentos por minuto
  standardHeaders: true,
  legacyHeaders: false,
  message: { ok: false, error: 'Límite de solicitudes críticas excedido.' },
});

app.use(generalLimiter);

// Middleware de Autenticación por Token de Servicio (Bearer / X-API-Key) con Comparación en Tiempo Constante
const BRIDGE_TOKEN = process.env.WHATSAPP_BRIDGE_TOKEN || '';
const IS_PROD = process.env.APP_ENV === 'production' || process.env.APP_ENV === 'prod' || process.env.NODE_ENV === 'production';

if (IS_PROD && !BRIDGE_TOKEN) {
  console.error('⛔ FATAL: WHATSAPP_BRIDGE_TOKEN es estrictamente obligatorio en producción. Abortando inicio.');
  process.exit(1);
}

function safeCompareTokens(provided, actual) {
  if (typeof provided !== 'string' || typeof actual !== 'string') return false;
  if (!provided || !actual) return false;
  const bufA = Buffer.from(provided);
  const bufB = Buffer.from(actual);
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

function authMiddleware(req, res, next) {
  if (!BRIDGE_TOKEN) {
    if (IS_PROD) {
      return res.status(500).json({
        ok: false,
        error: 'Configuración insegura: WHATSAPP_BRIDGE_TOKEN obligatorio en producción.',
      });
    }
    return next();
  }

  const authHeader = req.headers['authorization'] || '';
  const token = authHeader.startsWith('Bearer ')
    ? authHeader.slice(7).trim()
    : (req.headers['x-api-key'] || '');

  if (!token || !safeCompareTokens(token, BRIDGE_TOKEN)) {
    return res.status(401).json({
      ok: false,
      error: 'Acceso no autorizado: Token de servicio de WhatsApp Bridge inválido o ausente.',
    });
  }
  next();
}

app.use(authMiddleware);


const PORT = 3001;
const AUTH_FOLDER = path.join(__dirname, 'auth_info_baileys');
const INBOX_FILE = path.join(__dirname, '..', 'whatsapp_inbox', 'live_incoming_messages.json');


let sock = null;
let latestQrBase64 = null;
let latestQrRaw = null;
let qrGeneratedAt = null;
let connectionStatus = 'DESCONECTADO';
let connectedPhone = null;
let latestPairingCode = null;
let receivedMessages = [];

// Asegurar carpeta whatsapp_inbox
const inboxDir = path.dirname(INBOX_FILE);
if (!fs.existsSync(inboxDir)) {
  fs.mkdirSync(inboxDir, { recursive: true });
}

async function startWhatsAppBridge() {
  try {
    await loadBaileys();
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
      version,
      logger: pino({ level: 'silent' }),
      printQRInTerminal: false,
      auth: state,
      browser: Browsers.ubuntu('Chrome'),
      generateHighQualityLinkPreview: false,
      syncFullHistory: true,
      shouldSyncHistoryMessage: () => true,
      shouldIgnoreJid: (jid) => jid?.endsWith('@g.us') || jid?.includes('status'),
      markOnlineOnConnect: true,
      fireInitQueries: true,
      enableRecentMessageCache: true,
      connectTimeoutMs: 60000,
      keepAliveIntervalMs: 25000,
    });

    sock.ev.on('creds.update', saveCreds);

    const CONTACTS_CACHE_FILE = path.join(inboxDir, 'contacts_cache.json');
    let contactsMap = {};
    let lidToPhoneMap = {};

    // Cargar caché previa de contactos y LIDs
    if (fs.existsSync(CONTACTS_CACHE_FILE)) {
      try {
        const cached = JSON.parse(fs.readFileSync(CONTACTS_CACHE_FILE, 'utf-8'));
        contactsMap = cached.contactsMap || {};
        lidToPhoneMap = cached.lidToPhoneMap || {};
      } catch (e) {}
    }

    function saveContactsCache() {
      try {
        fs.writeFileSync(
          CONTACTS_CACHE_FILE,
          JSON.stringify({ contactsMap, lidToPhoneMap }, null, 2),
          'utf-8'
        );
      } catch (e) {}
    }

    function updateContactMappings(contactList) {
      if (!contactList || !Array.isArray(contactList)) return;
      let changed = false;
      for (const c of contactList) {
        if (!c) continue;
        const name = c.name || c.notify || c.verifiedName || '';
        if (c.id) {
          if (name && !contactsMap[c.id]) {
            contactsMap[c.id] = name;
            changed = true;
          }
          if (c.id.includes('@s.whatsapp.net')) {
            const rawPhone = c.id.replace('@s.whatsapp.net', '');
            if (c.lid && !lidToPhoneMap[c.lid]) {
              lidToPhoneMap[c.lid] = rawPhone;
              lidToPhoneMap[c.lid.replace('@lid', '')] = rawPhone;
              changed = true;
            }
            if (c.phoneNumber) {
              const cleanP = c.phoneNumber.replace(/\D/g, '');
              lidToPhoneMap[c.id] = cleanP;
              changed = true;
            }
          }
        }
        if (c.lid && name && !contactsMap[c.lid]) {
          contactsMap[c.lid] = name;
          contactsMap[c.lid.replace('@lid', '')] = name;
          changed = true;
        }
      }
      if (changed) saveContactsCache();
    }

    function extractMessageText(msg) {
      if (!msg) return '';
      let mObj = msg.message || msg;
      // Desenpaquetar mensajes anidados (efímeros / temporales, viewOnce, multimedia)
      while (
        mObj?.ephemeralMessage?.message ||
        mObj?.viewOnceMessage?.message ||
        mObj?.viewOnceMessageV2?.message ||
        mObj?.documentWithCaptionMessage?.message
      ) {
        mObj =
          mObj.ephemeralMessage?.message ||
          mObj.viewOnceMessage?.message ||
          mObj.viewOnceMessageV2?.message ||
          mObj.documentWithCaptionMessage?.message;
      }

      if (!mObj) return '';

      return (
        mObj.conversation ||
        mObj.extendedTextMessage?.text ||
        mObj.imageMessage?.caption ||
        mObj.videoMessage?.caption ||
        mObj.documentMessage?.caption ||
        mObj.templateButtonReplyMessage?.selectedDisplayText ||
        mObj.buttonsResponseMessage?.selectedDisplayText ||
        mObj.buttonsResponseMessage?.selectedButtonId ||
        mObj.listResponseMessage?.title ||
        mObj.interactiveResponseMessage?.body?.text ||
        (mObj.locationMessage ? `[Ubicación: ${mObj.locationMessage.name || mObj.locationMessage.address || 'GPS'}]` : '') ||
        (mObj.contactMessage ? `[Contacto compartido: ${mObj.contactMessage.displayName || 'Contacto'}]` : '') ||
        (mObj.audioMessage ? '[Nota de voz / Audio]' : '') ||
        (mObj.imageMessage ? '[Imagen]' : '') ||
        (mObj.documentMessage ? `[Documento: ${mObj.documentMessage.fileName || 'Archivo'}]` : '') ||
        ''
      );
    }

    function hashString(str) {
      let hash = 0;
      for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) - hash) + str.charCodeAt(i);
        hash |= 0;
      }
      return Math.abs(hash).toString(16);
    }

    function processAndSaveMessage(rawMsg, fallbackJid = '') {
      if (!rawMsg) return null;
      const msg = rawMsg.msg || rawMsg;
      if (!msg) return null;

      const isFromMe = Boolean(msg.key?.fromMe || rawMsg.key?.fromMe);
      const remoteJid = msg.key?.remoteJid || rawMsg.key?.remoteJid || fallbackJid || '';
      if (!remoteJid || remoteJid.endsWith('@g.us') || remoteJid.includes('status')) return null;

      let rawId = remoteJid.replace('@s.whatsapp.net', '').replace('@lid', '').replace(/:\d+/, '');
      let phone = lidToPhoneMap[remoteJid] || lidToPhoneMap[rawId] || (msg.key?.participant ? msg.key.participant.replace('@s.whatsapp.net', '') : rawId);

      let contactName = contactsMap[remoteJid] || contactsMap[rawId] || msg.pushName || rawMsg.pushName || '';
      if (!contactName && !isFromMe) {
        contactName = 'Cliente WhatsApp';
      }

      const text = extractMessageText(msg);
      if (!text) return null;

      const rawTs = msg.messageTimestamp || rawMsg.messageTimestamp;
      let timestamp = new Date().toISOString();
      if (rawTs) {
        const numTs = typeof rawTs === 'object' && rawTs.low !== undefined ? rawTs.low : Number(rawTs);
        if (numTs > 0) {
          timestamp = new Date(numTs * 1000).toISOString();
        }
      }

      const msgId = msg.key?.id || rawMsg.key?.id || `hist_${hashString(remoteJid + text + timestamp)}`;

      return {
        id: msgId,
        phone: phone,
        name: contactName || (isFromMe ? 'Contacto WhatsApp' : 'Cliente WhatsApp'),
        text: text,
        timestamp: timestamp,
        is_from_me: isFromMe,
        remote_jid: remoteJid,
      };
    }

    function saveBatchMessages(leadMsgs) {
      if (!leadMsgs || leadMsgs.length === 0) return;
      try {
        let existing = [];
        if (fs.existsSync(INBOX_FILE)) {
          const raw = fs.readFileSync(INBOX_FILE, 'utf-8');
          existing = JSON.parse(raw);
          if (!Array.isArray(existing)) existing = [];
        }
        const existingIds = new Set(existing.map((m) => m.id));
        let added = 0;
        for (const lm of leadMsgs) {
          if (!existingIds.has(lm.id)) {
            existing.push(lm);
            existingIds.add(lm.id);
            receivedMessages.push(lm);
            added++;
          }
        }
        if (added > 0) {
          fs.writeFileSync(INBOX_FILE, JSON.stringify(existing, null, 2), 'utf-8');
          console.log(`💾 [WhatsApp Bridge] Guardados ${added} mensajes nuevos/históricos en el CRM.`);
        }
      } catch (err) {
        console.error('Error guardando mensajes por lote:', err);
      }
    }

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        latestQrRaw = qr;
        qrGeneratedAt = Date.now();
        connectionStatus = 'ESPERANDO_QR';
        try {
          latestQrBase64 = await QRCode.toDataURL(qr, { margin: 2, scale: 8 });
        } catch (err) {
          console.error('Error generando QR DataURL:', err);
        }
        console.log('📲 [WhatsApp Bridge] Nuevo código QR oficial generado.');
      }

      if (connection === 'open') {
        connectionStatus = 'CONECTADO';
        latestQrBase64 = null;
        latestQrRaw = null;
        latestPairingCode = null;
        connectedPhone = sock.user ? sock.user.id.split(':')[0] : 'Conectado';
        console.log(`🟢 [WhatsApp Bridge] ¡Conectado exitosamente con +${connectedPhone}!`);
      }

      if (connection === 'close') {
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        const isLoggedOut = statusCode === DisconnectReason.loggedOut;
        const mustRelink = isLoggedOut || statusCode === 401 || statusCode === 403;
        connectionStatus = 'DESCONECTADO';
        connectedPhone = null;
        console.log(`🔴 [WhatsApp Bridge] Conexión cerrada (código ${statusCode || 'desconocido'}).`);
        
        if (mustRelink) {
          console.log(`⚠️ [WhatsApp Bridge] Sesión vencida o cerrada (código ${statusCode}). Limpiando credenciales para emitir nuevo QR...`);
          if (fs.existsSync(AUTH_FOLDER)) {
            try {
              fs.rmSync(AUTH_FOLDER, { recursive: true, force: true });
            } catch (e) {}
          }
          setTimeout(startWhatsAppBridge, 1000);
        } else {
          // 428/440 commonly represent a transient/precondition or another
          // active connection. Preserve the linked-device keys and reconnect.
          console.log('🔄 [WhatsApp Bridge] Reconectando en 3 segundos...');
          setTimeout(startWhatsAppBridge, 3000);
        }
      }
    });

    sock.ev.on('contacts.set', ({ contacts }) => {
      updateContactMappings(contacts);
      console.log(`📇 [WhatsApp Bridge] ${Object.keys(contactsMap).length} contactos sincronizados.`);
    });

    sock.ev.on('contacts.upsert', (contacts) => {
      updateContactMappings(contacts);
    });

    sock.ev.on('contacts.update', (updates) => {
      updateContactMappings(updates);
    });

    // Capturar historial completo de conversaciones
    sock.ev.on('messaging-history.set', ({ chats, contacts, messages, isLatest, syncType, progress }) => {
      console.log(`📜 [WhatsApp Bridge] Sincronización de Historial: ${chats?.length || 0} chats, ${messages?.length || 0} mensajes directos (syncType: ${syncType || 'N/A'}, progreso: ${progress || 100}%).`);
      if (contacts) updateContactMappings(contacts);
      const processed = [];
      if (messages && messages.length > 0) {
        for (const m of messages) {
          const pm = processAndSaveMessage(m);
          if (pm) processed.push(pm);
        }
      }
      if (chats && chats.length > 0) {
        for (const chat of chats) {
          const chatJid = chat.id || '';
          if (chat.name && chatJid) contactsMap[chatJid] = chat.name;
          if (chat.messages && Array.isArray(chat.messages)) {
            for (const item of chat.messages) {
              const pm = processAndSaveMessage(item, chatJid);
              if (pm) processed.push(pm);
            }
          }
        }
      }
      saveBatchMessages(processed);
    });

    sock.ev.on('messages.set', ({ messages }) => {
      console.log(`📥 [WhatsApp Bridge] messages.set recibido: ${messages?.length || 0} mensajes.`);
      if (!messages) return;
      const processed = [];
      for (const m of messages) {
        const pm = processAndSaveMessage(m);
        if (pm) processed.push(pm);
      }
      saveBatchMessages(processed);
    });

    sock.ev.on('chats.set', ({ chats }) => {
      console.log(`💬 [WhatsApp Bridge] ${chats?.length || 0} chats sincronizados desde el teléfono.`);
      if (!chats) return;
      const leadMsgs = [];
      for (const chat of chats) {
        const chatJid = chat.id || '';
        if (chat.name && chatJid) contactsMap[chatJid] = chat.name;
        if (chat.messages && Array.isArray(chat.messages)) {
          for (const item of chat.messages) {
            const pm = processAndSaveMessage(item, chatJid);
            if (pm) leadMsgs.push(pm);
          }
        }
      }
      saveBatchMessages(leadMsgs);
    });

    sock.ev.on('chats.upsert', (chats) => {
      if (!chats) return;
      const leadMsgs = [];
      for (const chat of chats) {
        const chatJid = chat.id || '';
        if (chat.name && chatJid) contactsMap[chatJid] = chat.name;
        if (chat.messages && Array.isArray(chat.messages)) {
          for (const item of chat.messages) {
            const pm = processAndSaveMessage(item, chatJid);
            if (pm) leadMsgs.push(pm);
          }
        }
      }
      saveBatchMessages(leadMsgs);
    });

    sock.ev.on('chats.update', (updates) => {
      if (!updates) return;
      for (const u of updates) {
        if (u.id && u.name) {
          contactsMap[u.id] = u.name;
        }
      }
    });

    sock.ev.on('messages.upsert', async ({ messages }) => {
      if (!messages || messages.length === 0) return;
      const processed = [];
      for (const msg of messages) {
        const pm = processAndSaveMessage(msg);
        if (pm) {
          processed.push(pm);
          const dir = pm.is_from_me ? '📤 ENVIADO' : '📥 RECIBIDO';
          console.log(`${dir} [WhatsApp Bridge] ${pm.name} (${pm.phone}): "${pm.text.substring(0, 60)}"`);
        }
      }
      saveBatchMessages(processed);
    });
  } catch (err) {
    console.error('Error en startWhatsAppBridge:', err);
    setTimeout(startWhatsAppBridge, 5000);
  }
}

// Iniciar WhatsApp Socket si se ejecuta directamente
if (require.main === module) {
  startWhatsAppBridge();
}

// Rutas API HTTP
app.get('/status', (req, res) => {
  const qrAgeMs = qrGeneratedAt ? Date.now() - qrGeneratedAt : 999999;
  const isQrFresh = qrAgeMs < 28000; // Códigos QR de WhatsApp expiran en ~30s

  let savedTotal = 0;
  if (fs.existsSync(INBOX_FILE)) {
    try {
      const d = JSON.parse(fs.readFileSync(INBOX_FILE, 'utf-8'));
      savedTotal = Array.isArray(d) ? d.length : 0;
    } catch (e) {}
  }

  res.json({
    connected: connectionStatus === 'CONECTADO',
    status: connectionStatus,
    phone: connectedPhone ? `${connectedPhone.slice(0, 4)}****${connectedPhone.slice(-3)}` : null,
    has_qr: !!latestQrBase64 && isQrFresh,
    qr_age_seconds: Math.floor(qrAgeMs / 1000),
    total_saved_messages: savedTotal,
  });
});

app.get('/history-summary', (req, res) => {
  let messages = [];
  if (fs.existsSync(INBOX_FILE)) {
    try {
      messages = JSON.parse(fs.readFileSync(INBOX_FILE, 'utf-8'));
      if (!Array.isArray(messages)) messages = [];
    } catch (e) {}
  }

  const phoneSet = new Set();
  let outgoing = 0;
  let incoming = 0;
  for (const m of messages) {
    if (m.phone) phoneSet.add(m.phone);
    if (m.is_from_me) outgoing++;
    else incoming++;
  }

  res.json({
    total_messages: messages.length,
    unique_contacts: phoneSet.size,
    outgoing_messages: outgoing,
    incoming_messages: incoming,
  });
});

app.get('/qr.png', async (req, res) => {
  if (!latestQrRaw) {
    return res.status(404).send('No QR code available');
  }
  try {
    const pngBuffer = await QRCode.toBuffer(latestQrRaw, { type: 'png', margin: 2, scale: 8 });
    res.setHeader('Content-Type', 'image/png');
    res.send(pngBuffer);
  } catch (err) {
    res.status(500).send('Error generando PNG');
  }
});

app.post('/send-message', sensitiveActionLimiter, async (req, res) => {
  try {
    const { phone, message, media_url, quoted_id } = req.body || {};
    if (!phone || !message) {
      return res.status(400).json({ ok: false, error: 'Parámetros requeridos: phone, message' });
    }

    if (!sock || connectionStatus !== 'CONECTADO') {
      return res.status(503).json({
        ok: false,
        error: 'WhatsApp Bridge desconectado. Vincule su sesión antes de enviar mensajes.',
      });
    }

    const cleanDigits = String(phone).replace(/\D/g, '');
    if (cleanDigits.length < 8 || cleanDigits.length > 18) {
      return res.status(400).json({ ok: false, error: 'Número de teléfono inválido.' });
    }

    const jid = `${cleanDigits}@s.whatsapp.net`;
    const messagePayload = { text: String(message).trim() };

    const sendResult = await sock.sendMessage(jid, messagePayload);
    const messageId = sendResult?.key?.id || `msg_${Date.now()}`;

    console.log(`📤 [WhatsApp Bridge] Mensaje enviado a +${cleanDigits.slice(0, 4)}**** (ID: ${messageId})`);
    return res.json({
      ok: true,
      message_id: messageId,
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    console.error('Error enviando mensaje WhatsApp:', err);
    return res.status(500).json({
      ok: false,
      error: `Falla enviando mensaje: ${err.message || 'Error desconocido'}`,
    });
  }
});

app.post('/request-pairing-code', sensitiveActionLimiter, async (req, res) => {
  try {
    const rawPhone = req.body.phone || '';
    const cleanDigits = rawPhone.replace(/\D/g, '');
    if (!cleanDigits || cleanDigits.length < 8 || cleanDigits.length > 18) {
      return res.status(400).json({ ok: false, error: 'Número de teléfono inválido (ej: 5493512383481)' });
    }
    if (!sock) {
      return res.status(500).json({ ok: false, error: 'Socket de WhatsApp no inicializado' });
    }
    const code = await sock.requestPairingCode(cleanDigits);
    latestPairingCode = code;
    console.log(`🔑 [WhatsApp Bridge] Pairing Code generado para +${cleanDigits.slice(0, 4)}****`);
    res.json({ ok: true, pairing_code: code });
  } catch (err) {
    console.error('Error al generar Pairing Code:', err);
    res.status(500).json({ ok: false, error: 'Error interno generando código de vinculación' });
  }
});

app.post('/reset-session', sensitiveActionLimiter, async (req, res) => {
  try {
    connectionStatus = 'DESCONECTADO';
    connectedPhone = null;
    latestQrBase64 = null;
    latestQrRaw = null;
    latestPairingCode = null;

    if (sock) {
      try {
        sock.ev.removeAllListeners();
        sock.end(new Error('Reset Session'));
      } catch (e) {}
      sock = null;
    }

    if (fs.existsSync(AUTH_FOLDER)) {
      try {
        fs.rmSync(AUTH_FOLDER, { recursive: true, force: true });
      } catch (e) {
        console.error('Error borrando AUTH_FOLDER:', e);
      }
    }

    console.log('🔄 [WhatsApp Bridge] Sesión restablecida limpiamente. Generando nuevo QR...');
    setTimeout(startWhatsAppBridge, 500);
    res.json({ ok: true, message: 'Sesión reiniciada limpiamente. Generando nuevo código QR...' });
  } catch (err) {
    res.status(500).json({ ok: false, error: 'Error interno al restablecer la sesión' });
  }
});

app.get('/messages', (req, res) => {
  res.json(receivedMessages);
});

if (require.main === module) {
  app.listen(PORT, '127.0.0.1', () => {
    console.log(`🚀 [WhatsApp Bridge] Servidor escuchando en http://127.0.0.1:${PORT}`);
  });
}

module.exports = { app, authMiddleware, safeCompareTokens };

