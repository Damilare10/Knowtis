const express = require('express');
const bodyParser = require('body-parser');
const axios = require('axios');
const pino = require('pino');
const QRCode = require('qrcode');
const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const app = express();
app.use(bodyParser.json());

const PORT = process.env.PORT || 3001;
const FASTAPI_WEBHOOK_URL = process.env.FASTAPI_WEBHOOK_URL || 'http://localhost:8000/api/v1/whatsapp/webhook';
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || '';
const CONNECTOR_API_SECRET = process.env.CONNECTOR_API_SECRET || WEBHOOK_SECRET;


let sock = null;
let connectionState = 'DISCONNECTED';
let latestQr = null;
let latestQrDataUrl = null;
let botJid = null;

const isLoopback = (req) => {
  const ip = req.ip || req.connection?.remoteAddress || '';
  return ip === '127.0.0.1' || ip === '::1' || ip === '::ffff:127.0.0.1';
};

const requireConnectorAuth = (req, res, next) => {
  if (!CONNECTOR_API_SECRET) {
    return res.status(503).json({ detail: 'Connector API auth is not configured.' });
  }

  // Allow the local browser to open the status/QR page without a secret so
  // users can simply click http://localhost:3001/status during local dev.
  // Read-only status; mutating endpoints (/join, /groups) still require auth.
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
    // FastAPI backend may not be running yet — that's ok
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

const runWhatsApp = async () => {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  
  sock = makeWASocket({
    auth: state,
    logger: pino({ level: 'warn' }),
    browser: ['Knowtis Bot', 'Chrome', '1.0.0']
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;
    
    // Debug: log full error details
    if (lastDisconnect?.error) {
      const err = lastDisconnect.error;
      console.error('CLOSE ERROR — message:', err.message);
      console.error('CLOSE ERROR — stack:', err.stack?.split('\n').slice(0, 3).join('\n'));
      console.error('CLOSE ERROR — statusCode:', err.output?.statusCode);
      if (err.data) console.error('CLOSE ERROR — data:', JSON.stringify(err.data));
    }
    
    if (qr) {
      latestQr = qr;
      connectionState = 'DISCONNECTED';
      console.log('QR code received (length: ' + qr.length + ' chars)');
      // Generate a data URL so the status page can display it as an image
      QRCode.toDataURL(qr, { width: 400, margin: 2 }, (err, url) => {
        if (err) {
          console.error('Failed to generate QR image:', err);
          latestQrDataUrl = null;
        } else {
          latestQrDataUrl = url;
          console.log('QR image generated — open http://localhost:' + PORT + '/status to scan');
        }
      });
    }

    if (connection === 'connecting') {
      connectionState = 'CONNECTING';
      console.log('Connecting to WhatsApp...');
    }

    if (connection === 'open') {
      connectionState = 'CONNECTED';
      latestQr = null;
      latestQrDataUrl = null;
      botJid = sock.user.id.split(':')[0] + '@s.whatsapp.net';
      console.log(`WhatsApp connection is OPEN. Bot JID: ${botJid}`);
      await sendWebhook('connection_status', { status: 'CONNECTED' });
    }

    if (connection === 'close') {
      connectionState = 'DISCONNECTED';
      botJid = null;
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`WhatsApp connection CLOSED (code=${statusCode}). Reconnecting? ${shouldReconnect}`);
      await sendWebhook('connection_status', { status: 'DISCONNECTED' });
      
      if (shouldReconnect) {
        // Add a small delay before reconnecting to avoid tight loop
        await new Promise(resolve => setTimeout(resolve, 3000));
        runWhatsApp();
      }
    }
  });

  // Listen for incoming messages
  sock.ev.on('messages.upsert', async (m) => {
    if (m.type !== 'notify') return;

    for (const msg of m.messages) {
      // Ignore outgoing messages or messages from system/bot itself
      if (msg.key.fromMe) continue;

      const remoteJid = msg.key.remoteJid;
      if (!remoteJid || !remoteJid.endsWith('@g.us')) continue; // Group messages only

      // Extract message text
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

      console.log(`Message received in group [${remoteJid}] from [${senderName}]: ${text.slice(0, 50)}...`);

      // Forward to FastAPI webhook
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

  // Listen for participant changes (bot removed detection)
  sock.ev.on('group-participants.update', async (update) => {
    const { id: groupJid, participants, action } = update;
    if (action === 'remove' && botJid && participants.includes(botJid)) {
      console.log(`Bot removed from group: ${groupJid}`);
      await sendWebhook('bot_removed', { group_jid: groupJid });
    }
  });
};

// Start Express endpoints
app.get('/status', requireConnectorAuth, (req, res) => {
  const accept = req.headers.accept || '';

  if (accept.includes('text/html') || accept.includes('*/*')) {
    const statusColor = connectionState === 'CONNECTED' ? '#22c55e' : connectionState === 'CONNECTING' ? '#f59e0b' : '#ef4444';
    const qrSection = latestQrDataUrl ? `
      <div class="qr-section">
        <h2>📱 Scan this QR code with WhatsApp</h2>
        <p class="hint">Open WhatsApp → Linked Devices → Link a Device</p>
        <img src="${latestQrDataUrl}" alt="QR Code" class="qr-img" />
        <p class="expiry">This QR code refreshes when a new one is generated</p>
      </div>
    ` : connectionState === 'DISCONNECTED' ? `
      <div class="qr-section">
        <h2>⏳ Waiting for QR Code...</h2>
        <p class="hint">The server is connecting to WhatsApp. A QR code will appear here shortly.</p>
        <div class="spinner"></div>
      </div>
    ` : '';

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
    .qr-img {
      background: white; padding: 16px; border-radius: 12px;
      max-width: 100%; width: 300px; display: block; margin: 0 auto;
    }
    .expiry { font-size: 0.75rem; color: #64748b; margin-top: 12px; }
    .spinner {
      width: 48px; height: 48px; border: 4px solid #334155;
      border-top-color: #3b82f6; border-radius: 50%;
      animation: spin 0.8s linear infinite; margin: 20px auto;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
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
      qrDataUrl: latestQrDataUrl,
      botJid: botJid
    });
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

  // Parse invite code from link
  let inviteCode = invite_link.trim().split('/').pop();

  try {
    console.log(`Attempting to join group with code: ${inviteCode}`);
    const groupJid = await sock.groupAcceptInvite(inviteCode);
    console.log(`Joined group successfully: ${groupJid}`);

    // Wait a brief moment and fetch group metadata
    await new Promise(resolve => setTimeout(resolve, 2000));
    const metadata = await sock.groupMetadata(groupJid);

    // Call webhook to instantly notify FastAPI of success
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

// Run WhatsApp client
runWhatsApp();

// Start HTTP server
app.listen(PORT, () => {
  console.log(`WhatsApp Connector listening on port ${PORT}`);
});
