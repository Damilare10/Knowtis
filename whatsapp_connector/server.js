const express = require('express');
const bodyParser = require('body-parser');
const axios = require('axios');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

// Minimal logger (replaces pino to save ~5MB)
const logger = {
  silent: { child: () => logger.silent },
  trace: () => {},
  debug: () => {},
  info: () => {},
  warn: () => {},
  error: () => {},
  fatal: () => {},
  child: () => logger.silent,
};

const app = express();
app.use(bodyParser.json());

const PORT = process.env.PORT || 3001;
const FASTAPI_WEBHOOK_URL = process.env.FASTAPI_WEBHOOK_URL || 'http://localhost:8000/api/v1/whatsapp/webhook';
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || '';
const CONNECTOR_API_SECRET = process.env.CONNECTOR_API_SECRET || WEBHOOK_SECRET;

let sock = null;
let connectionState = 'DISCONNECTED';
let latestQr = null;
let botJid = null;

const isLoopback = (req) => {
  const ip = req.ip || req.connection?.remoteAddress || '';
  return ip === '127.0.0.1' || ip === '::1' || ip === '::ffff:127.0.0.1';
};

const requireConnectorAuth = (req, res, next) => {
  if (!CONNECTOR_API_SECRET) {
    return res.status(503).json({ detail: 'Connector API auth is not configured.' });
  }

  if (req.path === '/status' && isLoopback(req)) {
    return next();
  }

  const provided = req.get('X-Connector-Secret') || (req.query && req.query.secret) || '';
  if (provided !== CONNECTOR_API_SECRET) {
    return res.status(401).json({ detail: 'Invalid connector secret.' });
  }

  next();
};

// Ensure auth directory exists
const AUTH_DIR = path.join(__dirname, 'auth_info_baileys');
if (!fs.existsSync(AUTH_DIR)) {
  fs.mkdirSync(AUTH_DIR);
}

const sendWebhook = async (event, data) => {
  try {
    console.log(`Sending webhook [${event}] to FastAPI...`);
    await axios.post(FASTAPI_WEBHOOK_URL, { event, data }, { 
      timeout: 10000,
      headers: { 'X-Webhook-Secret': WEBHOOK_SECRET }
    });
  } catch (err) {
    if (process.env.NODE_ENV !== 'production') {
      console.error(`Webhook [${event}] failed:`, err.message);
    }
  }
};

const extractContextInfo = (msg) => {
  if (!msg?.message) return null;

  if (msg.message.extendedTextMessage?.contextInfo) {
    return msg.message.extendedTextMessage.contextInfo;
  }
  if (msg.message.imageMessage?.contextInfo) {
    return msg.message.imageMessage.contextInfo;
  }
  if (msg.message.videoMessage?.contextInfo) {
    return msg.message.videoMessage.contextInfo;
  }
  return null;
};

// ─── WhatsApp Socket Creation ──────────────────────────────────────────────

const createSocket = () => {
  const { state, saveCreds } = useMultiFileAuthState(AUTH_DIR);
  
  sock = makeWASocket({
    auth: state,
    logger,
    browser: ['Knowtis Bot', 'Chrome', '1.0.0'],
    // Reduce connection timeout to speed up deploys
    connectTimeoutMs: 20000,
    defaultQueryTimeoutMs: 20000,
    // Limit pre-key count to save memory
    generateHighQualityKey: false,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;
    
    if (qr) {
      latestQr = qr;
      connectionState = 'AWAITING_SCAN';
      console.log('QR code received — visit /generate-qr to get the image');
    }

    if (connection === 'connecting') {
      connectionState = 'CONNECTING';
      console.log('Connecting to WhatsApp...');
    }

    if (connection === 'open') {
      connectionState = 'CONNECTED';
      latestQr = null;
      botJid = sock.user.id.split(':')[0] + '@s.whatsapp.net';
      console.log(`WhatsApp connection is OPEN. Bot JID: ${botJid}`);
      await sendWebhook('connection_status', { status: 'CONNECTED' });
    }

    if (connection === 'close') {
      connectionState = 'DISCONNECTED';
      botJid = null;
      latestQr = null;
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`WhatsApp connection CLOSED (code=${statusCode}). Reconnecting? ${shouldReconnect}`);
      await sendWebhook('connection_status', { status: 'DISCONNECTED' });
      
      if (shouldReconnect) {
        await new Promise(resolve => setTimeout(resolve, 3000));
        createSocket();
      }
    }
  });

  sock.ev.on('messages.upsert', async (m) => {
    if (m.type !== 'notify') return;

    for (const msg of m.messages) {
      if (msg.key.fromMe) continue;

      const remoteJid = msg.key.remoteJid;
      if (!remoteJid || !remoteJid.endsWith('@g.us')) continue;

      let text = '';
      if (msg.message) {
        if (msg.message.conversation) {
          text = msg.message.conversation;
        } else if (msg.message.extendedTextMessage) {
          text = msg.message.extendedTextMessage.text;
        } else if (msg.message.imageMessage && msg.message.imageMessage.caption) {
          text = msg.message.imageMessage.caption;
        }
      }

      if (!text) continue;

      const senderJid = msg.key.participant || remoteJid;
      const senderName = msg.pushName || 'WhatsApp User';
      const timestamp = msg.messageTimestamp;
      const contextInfo = extractContextInfo(msg);
      const mentionedJids = Array.isArray(contextInfo?.mentionedJid) ? contextInfo.mentionedJid : [];
      const mentionAll =
        Boolean(contextInfo?.groupMentions?.length) ||
        Boolean(contextInfo?.memberLabel) ||
        /@(all|everyone|here)\b/i.test(text);
      const isBotMentioned = Boolean(botJid && mentionedJids.includes(botJid));

      console.log(`Message in [${remoteJid}] from ${senderName}: ${text.slice(0, 50)}...`);

      await sendWebhook('message', {
        message_id: msg.key.id,
        sender_jid: senderJid,
        sender_name: senderName,
        message_text: text,
        group_jid: remoteJid,
        timestamp: timestamp,
        mentioned_jids: mentionedJids,
        is_bot_mentioned: isBotMentioned,
        mention_all: mentionAll,
      });
    }
  });

  sock.ev.on('group-participants.update', async (update) => {
    const { id: groupJid, participants, action } = update;
    if (action === 'remove' && botJid && participants.includes(botJid)) {
      console.log(`Bot removed from group: ${groupJid}`);
      await sendWebhook('bot_removed', { group_jid: groupJid });
    }
  });

  return sock;
};

// ─── Express Endpoints ─────────────────────────────────────────────────────

app.get('/status', requireConnectorAuth, (req, res) => {
  const accept = req.headers.accept || '';

  if (accept.includes('text/html') || accept.includes('*/*')) {
    const statusColor = connectionState === 'CONNECTED' ? '#22c55e' : connectionState === 'CONNECTING' ? '#f59e0b' : connectionState === 'AWAITING_SCAN' ? '#3b82f6' : '#ef4444';
    const qrSection = connectionState === 'AWAITING_SCAN' ? `
      <div class="qr-section">
        <h2>📱 QR Code Pending</h2>
        <p class="hint">Visit <code style="background:#334155;padding:2px 6px;border-radius:4px;">/generate-qr</code> to get the QR image when ready.</p>
      </div>
    ` : connectionState === 'CONNECTED' ? `
      <div class="qr-section">
        <h2>✅ Connected</h2>
        <p class="hint">Bot is running. You can safely disconnect when needed.</p>
      </div>
    ` : connectionState === 'CONNECTING' ? `
      <div class="qr-section">
        <h2>⏳ Connecting...</h2>
        <p class="hint">Establishing connection to WhatsApp.</p>
      </div>
    ` : `
      <div class="qr-section">
        <h2>❌ Disconnected</h2>
        <p class="hint">No active session. Visit <code style="background:#334155;padding:2px 6px;border-radius:4px;">/generate-qr</code> to start.</p>
      </div>
    `;

    res.send(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WhatsApp Connector — Status</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f172a; color: #e2e8f0; min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
    }
    .card {
      background: #1e293b; border-radius: 16px; padding: 40px;
      max-width: 560px; width: 90%; text-align: center;
      box-shadow: 0 25px 50px rgba(0,0,0,0.4);
    }
    h1 { font-size: 1.5rem; margin-bottom: 24px; color: #f8fafc; }
    .status-badge {
      display: inline-block; padding: 8px 20px; border-radius: 999px;
      font-weight: 600; font-size: 0.875rem;
      background: ${statusColor}22; color: ${statusColor};
      border: 1px solid ${statusColor}44; margin-bottom: 24px;
    }
    .qr-section { margin-top: 16px; }
    .qr-section h2 { font-size: 1.1rem; margin-bottom: 8px; color: #f1f5f9; }
    .hint { font-size: 0.85rem; color: #94a3b8; margin-bottom: 16px; }
    .expiry { font-size: 0.75rem; color: #64748b; margin-top: 12px; }
    .meta { margin-top: 24px; font-size: 0.8rem; color: #64748b; }
    .meta span { color: #94a3b8; }
    .refresh-btn {
      margin-top: 16px; padding: 8px 24px; border-radius: 8px;
      background: #334155; color: #e2e8f0; border: none;
      font-size: 0.85rem; cursor: pointer; transition: background 0.2s;
    }
    .refresh-btn:hover { background: #475569; }
  </style>
</head>
<body>
  <div class="card">
    <h1>📞 WhatsApp Connector</h1>
    <div class="status-badge">${connectionState}</div>
    ${qrSection}
    <div class="meta">
      Bot JID: <span>${botJid || '—'}</span><br>
      Server: <span>http://localhost:${PORT}</span>
    </div>
    <button class="refresh-btn" onclick="location.reload()">↻ Refresh</button>
  </div>
</body>
</html>`);
  } else {
    res.json({
      status: connectionState,
      qrCode: latestQr,
      botJid: botJid
    });
  }
});

app.post('/generate-qr', requireConnectorAuth, async (req, res) => {
  if (!sock) {
    return res.status(503).json({ detail: 'WhatsApp socket not initialized.' });
  }
  if (connectionState === 'CONNECTED') {
    return res.status(409).json({ detail: 'Already connected. Disconnect first if you need a new QR code.', status: connectionState });
  }

  try {
    // Trigger a reconnect which will push a new QR code
    console.log('Manually triggering QR code generation...');
    sock.end();
    await new Promise(r => setTimeout(r, 2000));
    createSocket();
    
    // Wait up to 30 seconds for the QR to arrive
    const startTime = Date.now();
    while (Date.now() - startTime < 30000) {
      if (latestQr) {
        return res.json({
          success: true,
          qrCode: latestQr,
          message: 'QR code received. Scan it with WhatsApp → Linked Devices → Link a Device.'
        });
      }
      await new Promise(r => setTimeout(r, 1000));
    }

    return res.status(504).json({ detail: 'Timed out waiting for QR code. Check logs.' });
  } catch (err) {
    console.error('QR generation failed:', err);
    return res.status(500).json({ detail: `QR generation failed: ${err.message}` });
  }
});

app.post('/disconnect', requireConnectorAuth, async (req, res) => {
  if (!sock) {
    return res.status(503).json({ detail: 'No active connection.' });
  }
  try {
    sock.end();
    connectionState = 'DISCONNECTED';
    latestQr = null;
    console.log('WhatsApp connection closed manually.');
    await sendWebhook('connection_status', { status: 'DISCONNECTED' });
    return res.json({ success: true, message: 'Disconnected.' });
  } catch (err) {
    console.error('Disconnect failed:', err);
    return res.status(500).json({ detail: `Disconnect failed: ${err.message}` });
  }
});

app.post('/reconnect', requireConnectorAuth, async (req, res) => {
  if (!sock) {
    return res.status(503).json({ detail: 'No active connection.' });
  }
  try {
    sock.end();
    await new Promise(r => setTimeout(r, 2000));
    createSocket();
    return res.json({ success: true, message: 'Reconnecting...' });
  } catch (err) {
    console.error('Reconnect failed:', err);
    return res.status(500).json({ detail: `Reconnect failed: ${err.message}` });
  }
});

app.post('/join', requireConnectorAuth, async (req, res) => {
  const { invite_link } = req.body;
  if (!invite_link) {
    return res.status(400).json({ detail: 'invite_link is required' });
  }

  if (connectionState !== 'CONNECTED') {
    return res.status(503).json({ detail: 'WhatsApp bot is not authenticated/connected.' });
  }

  let inviteCode = invite_link.trim().split('/').pop();

  try {
    console.log(`Attempting to join group with code: ${inviteCode}`);
    const groupJid = await sock.groupAcceptInvite(inviteCode);
    console.log(`Joined group successfully: ${groupJid}`);

    await new Promise(resolve => setTimeout(resolve, 2000));
    const metadata = await sock.groupMetadata(groupJid);

    await sendWebhook('group_joined', {
      invite_code: inviteCode,
      group_jid: groupJid,
      group_name: metadata.subject,
      group_description: metadata.desc || ''
    });

    res.json({
      success: true,
      group_jid: groupJid,
      group_name: metadata.subject,
      group_description: metadata.desc || ''
    });
  } catch (err) {
    console.error(`Error joining group [${inviteCode}]:`, err.message);
    res.status(500).json({ detail: `Failed to join group: ${err.message}` });
  }
});

app.get('/groups', requireConnectorAuth, async (req, res) => {
  if (connectionState !== 'CONNECTED') {
    return res.status(503).json({ detail: 'WhatsApp bot is not connected.' });
  }

  try {
    const list = await sock.groupFetchAllParticipating();
    const groups = Object.values(list).map(g => ({
      jid: g.id,
      name: g.subject,
      description: g.desc || ''
    }));
    res.json({ groups });
  } catch (err) {
    res.status(500).json({ detail: `Failed to fetch groups: ${err.message}` });
  }
});

// ─── Start HTTP Server Only (No Auto-Connect) ──────────────────────────────

app.listen(PORT, () => {
  console.log(`WhatsApp Connector listening on port ${PORT}`);
  console.log(`  GET  /status       — Check connection status`);
  console.log(`  POST /generate-qr  — Manually trigger QR code (when ready)`);
  console.log(`  POST /disconnect   — Disconnect the bot`);
  console.log(`  POST /reconnect    — Reconnect the bot`);
  console.log(`  POST /join         — Join a WhatsApp group`);
  console.log(`  GET  /groups       — List all joined groups`);
});
