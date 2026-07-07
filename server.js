// Thin wrapper — starts the real server from the whatsapp_connector directory
// so the Procfile at repo root (web: node server.js) works.
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, 'whatsapp_connector', '.env') });
process.chdir(path.join(__dirname, 'whatsapp_connector'));
require('./whatsapp_connector/server');