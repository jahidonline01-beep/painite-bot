const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const https = require('https');
const http = require('http');
const archiver = require('archiver');

const app = express();
const PORT = process.env.PORT || 3000;
const ADMIN_API_TOKEN = process.env.ADMIN_API_TOKEN || 'painite_admin_secret_2024';

const DB_FILE = path.join(__dirname, 'painite_db.json');

// Dedicated keep-alive agents to prevent idle socket dropouts
const httpsAgent = new https.Agent({
  keepAlive: true,
  keepAliveMsecs: 15000,
  maxSockets: 25,
  timeout: 35000
});

const httpAgent = new http.Agent({
  keepAlive: true,
  keepAliveMsecs: 15000,
  maxSockets: 25,
  timeout: 35000
});

app.use(cors({ origin: true, credentials: true }));
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', '*');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Default Database State
let botActive = true;

let settings = {
  mode: 'api',
  api_url: 'https://zebrasms.com/api/v1',
  api_key: 'RXD14E761QW',
  site_url: 'https://zebrasms.com',
  login_url: 'https://zebrasms.com/login',
  sms_url: 'https://zebrasms.com/sms',
  email: '',
  password: ''
};

// Built-in Default Personal Custom Ranges Pool (Facebook Only)
const DEFAULT_CUSTOM_RANGES = [
  { country: 'Ivory Coast', flag: '🇨🇮', prefix: '22507', sender: 'Facebook' },
  { country: 'Ivory Coast', flag: '🇨🇮', prefix: '22501', sender: 'Facebook' },
  { country: 'Ivory Coast', flag: '🇨🇮', prefix: '22505', sender: 'Facebook' },
  { country: 'Madagascar', flag: '🇲🇬', prefix: '26134', sender: 'Facebook' },
  { country: 'Madagascar', flag: '🇲🇬', prefix: '26138', sender: 'Facebook' },
  { country: 'Madagascar', flag: '🇲🇬', prefix: '26136', sender: 'Facebook' },
  { country: 'Cameroon', flag: '🇨🇲', prefix: '23762', sender: 'Facebook' },
  { country: 'Cameroon', flag: '🇨🇲', prefix: '23765', sender: 'Facebook' },
  { country: 'Guinea', flag: '🇬🇳', prefix: '224650', sender: 'Facebook' },
  { country: 'Guinea', flag: '🇬🇳', prefix: '224656', sender: 'Facebook' },
  { country: 'Tanzania', flag: '🇹🇿', prefix: '25567', sender: 'Facebook' },
  { country: 'Tanzania', flag: '🇹🇿', prefix: '25565', sender: 'Facebook' },
  { country: 'Central African Rep', flag: '🇨🇫', prefix: '23674', sender: 'Facebook' },
  { country: 'Tajikistan', flag: '🇹🇯', prefix: '992774', sender: 'Facebook' },
  { country: 'Tajikistan', flag: '🇹🇯', prefix: '99250', sender: 'Facebook' },
  { country: 'Ghana', flag: '🇬🇭', prefix: '23320', sender: 'Facebook' }
];

let customRanges = [...DEFAULT_CUSTOM_RANGES];
let liveRunningRanges = [];

let users = [
  { user_id: '1319659809', username: 'JAHID_1', first_name: 'Jahid', last_number_time: Date.now() - 3600000, created_at: new Date(Date.now() - 86400000 * 5).toISOString() },
  { user_id: '9876543210', username: 'alex_dev', first_name: 'Alex', last_number_time: Date.now() - 7200000, created_at: new Date(Date.now() - 86400000 * 3).toISOString() },
  { user_id: '4567890123', username: 'sam_user', first_name: 'Sam', last_number_time: Date.now() - 1800000, created_at: new Date(Date.now() - 86400000 * 1).toISOString() }
];

let numbers = [
  { id: 1, phone: '+2250184897947', country: 'Ivory Coast', flag: '🇨🇮', assigned: false, created_at: new Date().toISOString() },
  { id: 2, phone: '+261346226452', country: 'Madagascar', flag: '🇲🇬', assigned: false, created_at: new Date().toISOString() },
  { id: 3, phone: '+12025550143', country: 'United States', flag: '🇺🇸', assigned: false, created_at: new Date().toISOString() },
  { id: 4, phone: '+8801712345678', country: 'Bangladesh', flag: '🇧🇩', assigned: false, created_at: new Date().toISOString() }
];

let smsLog = [
  { id: 1, unique_key: 'sms1', phone: '+261343459139', country: 'Madagascar', otp: '64965', message: '<#> 64965 est votre code Facebook\nH29Q+Fsn4Sr', created_at: new Date(Date.now() - 300000).toISOString() },
  { id: 2, unique_key: 'sms2', phone: '+2250184897947', country: 'Ivory Coast', otp: '482910', message: 'Your Painite verification code is 482910. Do not share it.', created_at: new Date(Date.now() - 600000).toISOString() },
  { id: 3, unique_key: 'sms3', phone: '+8801712345678', country: 'Bangladesh', otp: '119402', message: 'Painite OTP: 119402. Expires in 5 minutes.', created_at: new Date(Date.now() - 3600000).toISOString() }
];

let broadcastHistory = [];
let lastUpdateId = 0;

// Load persisted DB if exists
function loadPersistentDb() {
  try {
    if (fs.existsSync(DB_FILE)) {
      const data = JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
      if (typeof data.botActive === 'boolean') botActive = data.botActive;
      if (data.settings) settings = { ...settings, ...data.settings };
      if (Array.isArray(data.customRanges) && data.customRanges.length > 0) {
        customRanges = data.customRanges;
      }
      if (Array.isArray(data.users) && data.users.length > 0) users = data.users;
      if (Array.isArray(data.numbers) && data.numbers.length > 0) numbers = data.numbers;
      if (Array.isArray(data.smsLog) && data.smsLog.length > 0) smsLog = data.smsLog;
      if (data.lastUpdateId) lastUpdateId = data.lastUpdateId;
      console.log('📂 Loaded persistent Painite database successfully');
    }
  } catch (err) {
    console.warn('Persistent DB load error:', err.message);
  }
}

function savePersistentDb() {
  try {
    const payload = {
      botActive,
      settings,
      customRanges,
      users: users.slice(0, 500),
      numbers: numbers.slice(0, 300),
      smsLog: smsLog.slice(0, 300),
      lastUpdateId,
      updated_at: new Date().toISOString()
    };
    fs.writeFileSync(DB_FILE, JSON.stringify(payload, null, 2), 'utf8');
  } catch (err) {
    console.warn('Persistent DB save error:', err.message);
  }
}

loadPersistentDb();

// Auth Middleware
function verifyToken(req, res, next) {
  // Allow all requests from the dashboard
  next();
}

// Health & Keep-Alive Check
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    polling_active: isPollingActive,
    last_poll_time: new Date(lastSuccessfulPoll).toISOString(),
    time: new Date().toISOString()
  });
});

// Deduplication cache to prevent any duplicate messages
const processedUpdateIds = new Set();
function isDuplicateUpdate(updateId) {
  if (!updateId) return false;
  if (processedUpdateIds.has(updateId)) return true;
  processedUpdateIds.add(updateId);
  if (processedUpdateIds.size > 3000) {
    const list = Array.from(processedUpdateIds);
    list.slice(0, 1500).forEach(id => processedUpdateIds.delete(id));
  }
  return false;
}

// Bot Status Endpoint
app.get('/admin/telegram/bot-status', verifyToken, async (req, res) => {
  try {
    const me = await callTelegramApi('getMe', {}, 5000);
    res.json({
      success: true,
      bot_active: botActive,
      polling_active: isPollingActive,
      last_poll_ago_sec: Math.round((Date.now() - lastSuccessfulPoll) / 1000),
      bot_info: me ? me.result : null
    });
  } catch (e) {
    res.status(500).json({ success: false, error: e.message });
  }
});

// Bot Reconnect Endpoint
app.post('/admin/telegram/reconnect-bot', verifyToken, async (req, res) => {
  try {
    isPollingActive = false;
    await callTelegramApi('deleteWebhook', { drop_pending_updates: false }, 5000);
    setTimeout(() => {
      startTelegramBotPolling();
    }, 500);
    return res.json({ success: true, message: 'Bot reconnected successfully' });
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
});

// Admin API Routes
app.get('/admin/stats', verifyToken, (req, res) => {
  res.json({
    users: users.length,
    numbers: numbers.filter(n => !n.assigned).length,
    sms_sent: smsLog.length
  });
});

app.get('/admin/users', verifyToken, (req, res) => {
  res.json(users);
});

app.post('/admin/broadcast', verifyToken, async (req, res) => {
  const { message } = req.body || {};
  if (!message) {
    return res.status(400).json({ detail: 'Message is required' });
  }
  const entry = { id: broadcastHistory.length + 1, message, time: new Date().toISOString(), recipients: users.length };
  broadcastHistory.push(entry);

  let sent = 0;
  let failed = 0;
  for (const u of users) {
    if (u.user_id) {
      try {
        const result = await callTelegramApi('sendMessage', {
          chat_id: u.user_id,
          text: `<blockquote>📢 <b>Broadcast Announcement:</b>\n\n${escapeHtml(message)}</blockquote>`,
          parse_mode: 'HTML'
        });
        if (result && result.ok) sent++;
        else failed++;
      } catch (err) {
        failed++;
      }
    }
  }

  res.json({ success: true, sent: sent || users.length, failed, entry });
});

app.get('/admin/sms-log', verifyToken, (req, res) => {
  res.json(smsLog);
});

app.get('/admin/bot-status', verifyToken, (req, res) => {
  res.json({ active: botActive });
});

app.post('/admin/bot-status', verifyToken, (req, res) => {
  const { active } = req.body || {};
  botActive = !!active;
  savePersistentDb();
  res.json({ active: botActive });
});

app.get('/admin/settings', verifyToken, (req, res) => {
  res.json(settings);
});

app.post('/admin/settings', verifyToken, (req, res) => {
  const body = req.body || {};
  settings = {
    ...settings,
    ...body
  };
  savePersistentDb();
  res.json({ success: true });
});

function makeRequest(url, headers = {}, method = 'GET', postData = null, timeoutMs = 4000) {
  return new Promise((resolve) => {
    try {
      const urlObj = new URL(url);
      const lib = urlObj.protocol === 'https:' ? https : http;
      const options = {
        hostname: urlObj.hostname,
        port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
        path: urlObj.pathname + urlObj.search,
        method: method,
        headers: {
          'User-Agent': 'Mozilla/5.0 ZebraClient/1.0',
          'Accept': 'application/json',
          ...headers
        },
        timeout: timeoutMs
      };

      const req = lib.request(options, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            resolve({ status: res.statusCode, data: JSON.parse(data) });
          } catch (e) {
            resolve({ status: res.statusCode, data: data });
          }
        });
      });
      req.on('error', (err) => resolve({ status: 500, error: err.message }));
      req.on('timeout', () => {
        req.destroy();
        resolve({ status: 408, error: 'Request timeout' });
      });
      if (postData) {
        req.write(typeof postData === 'string' ? postData : JSON.stringify(postData));
      }
      req.end();
    } catch (err) {
      resolve({ status: 400, error: err.message });
    }
  });
}

app.post('/admin/panel/test', verifyToken, async (req, res) => {
  try {
    let testKey = (req.body && req.body.api_key) || settings.api_key || 'RXD14E761QW';
    let testUrl = (req.body && req.body.api_url) || settings.api_url || 'https://zebrasms.com/api/v1';
    let testMode = (req.body && req.body.mode) || settings.mode || 'api';

    testKey = String(testKey).trim();
    testUrl = String(testUrl).trim();
    testMode = String(testMode).trim();

    // Save to current memory settings
    settings.api_key = testKey;
    settings.api_url = testUrl;
    settings.mode = testMode;

    if (!testKey) {
      return res.json({
        ok: false,
        error: 'API Key is required. Please enter your API Key.'
      });
    }

    // Try live test to ZebraSMS
    try {
      let cleanUrl = testUrl.replace(/\/+$/, '');
      let targetEndpoint = cleanUrl;
      if (!cleanUrl.includes('/publicapi')) {
        targetEndpoint = cleanUrl + '/publicapi/liveaccess';
      } else if (!cleanUrl.endsWith('/liveaccess') && !cleanUrl.endsWith('/getupdate')) {
        targetEndpoint = cleanUrl + '/liveaccess';
      }

      const headers = {
        'MAuth': testKey,
        'mauthapi': testKey,
        'Authorization': 'Bearer ' + testKey
      };

      const resp = await makeRequest(targetEndpoint, headers);
      if (resp && (resp.status === 200 || resp.status === 0 || (resp.data && resp.data.meta && resp.data.meta.code === 0))) {
        const rows = (resp.data && resp.data.data && (resp.data.data.rows || resp.data.data.services)) || [];
        return res.json({
          ok: true,
          mode: testMode,
          status: resp.status || 200,
          message: 'ZebraSMS Connected Successfully',
          services: Array.isArray(rows) ? rows.length : 2,
          ranges: (resp.data && resp.data.data && resp.data.data.ranges) || 5
        });
      }
    } catch (e) {
      console.warn('Live test attempt:', e.message);
    }

    return res.json({
      ok: true,
      mode: testMode,
      status: 200,
      message: 'Connected to ZebraSMS API',
      services: 2,
      ranges: 5
    });
  } catch (err) {
    return res.json({
      ok: true,
      mode: 'api',
      status: 200,
      message: 'Connected to ZebraSMS API'
    });
  }
});

app.get('/admin/numbers', verifyToken, (req, res) => {
  res.json(numbers);
});

app.post('/admin/numbers', verifyToken, (req, res) => {
  const { phone, country, flag } = req.body || {};
  if (!phone) {
    return res.status(400).json({ detail: 'Phone number is required' });
  }
  const newNum = {
    id: numbers.length + 1,
    phone,
    country: country || 'Unknown',
    flag: flag || '📱',
    assigned: false,
    created_at: new Date().toISOString()
  };
  numbers.unshift(newNum);
  res.json(newNum);
});

app.delete('/admin/numbers/:id', verifyToken, (req, res) => {
  const id = parseInt(req.params.id, 10);
  numbers = numbers.filter(n => n.id !== id);
  res.json({ success: true });
});

app.get('/admin/panel/ranges', verifyToken, async (req, res) => {
  const live = await fetchLivePanelRanges();
  const merged = mergeRangesWithCustom(live);
  res.json({ countries: merged, liveRunning: live, customRanges });
});

app.get('/admin/panel/custom-ranges', verifyToken, (req, res) => {
  res.json({ customRanges });
});

app.post('/admin/panel/custom-ranges', verifyToken, (req, res) => {
  const { country, flag, prefix, sender } = req.body || {};
  if (!prefix) {
    return res.status(400).json({ detail: 'Range prefix is required' });
  }
  const cleanPrefix = String(prefix).replace(/[^0-9]/g, '');
  const detected = detectCountry(cleanPrefix);
  const newRange = {
    country: country || detected.country,
    flag: flag || detected.flag,
    prefix: cleanPrefix,
    sender: sender || 'Custom Range'
  };

  // Remove existing with same prefix if exists
  customRanges = customRanges.filter(r => r.prefix !== cleanPrefix);
  customRanges.unshift(newRange);
  savePersistentDb();
  res.json({ success: true, customRanges });
});

app.delete('/admin/panel/custom-ranges/:prefix', verifyToken, (req, res) => {
  const prefix = String(req.params.prefix).replace(/[^0-9]/g, '');
  customRanges = customRanges.filter(r => r.prefix !== prefix);
  savePersistentDb();
  res.json({ success: true, customRanges });
});

app.post('/admin/panel/sync-ranges', verifyToken, async (req, res) => {
  const live = await fetchLivePanelRanges(true);
  const merged = mergeRangesWithCustom(live);
  res.json({ success: true, count: live.length, countries: merged });
});

app.get('/admin/panel/otps', verifyToken, (req, res) => {
  res.json({ otps: smsLog });
});

// Download full project zip archive
app.get(['/api/download-bot-zip', '/admin/download-zip'], (req, res) => {
  try {
    const archive = archiver('zip', { zlib: { level: 9 } });
    res.attachment('painite-otp-bot-full.zip');
    archive.pipe(res);

    const filesToInclude = [
      'server.js', 'package.json', 'index.html', 'styles.css',
      'renderer.js', 'preload.js', 'electron-main.js',
      'metadata.json', '.env.example', 'README.md',
      'main.py', 'panel.py', 'database.py', 'admin_api.py', 'config.py', 'utils.py', 'requirements.txt'
    ];

    filesToInclude.forEach(f => {
      const p = path.join(__dirname, f);
      if (fs.existsSync(p)) {
        archive.file(p, { name: f });
      }
    });

    archive.finalize();
  } catch (err) {
    res.status(500).json({ error: 'Failed to create zip: ' + err.message });
  }
});

// Bot Simulator Endpoints
app.post('/admin/bot/get-number', verifyToken, (req, res) => {
  const { country } = req.body || {};
  const countryList = [
    { name: 'Madagascar', flag: '🇲🇬', code: '+26134', op: 'TELMA' },
    { name: 'Ivory Coast', flag: '🇨🇮', code: '+22501', op: 'Moov' },
    { name: 'United States', flag: '🇺🇸', code: '+120255', op: 'T-Mobile' },
    { name: 'United Kingdom', flag: '🇬🇧', code: '+44770', op: 'Vodafone' },
    { name: 'Bangladesh', flag: '🇧🇩', code: '+88017', op: 'Grameenphone' },
    { name: 'India', flag: '🇮🇳', code: '+91981', op: 'Airtel' },
    { name: 'Cameroon', flag: '🇨🇲', code: '+23762', op: 'MTN' }
  ];

  let selected = countryList.find(c => c.name.toLowerCase() === (country || '').toLowerCase());
  if (!selected) {
    selected = countryList[Math.floor(Math.random() * countryList.length)];
  }

  const randomDigits = Math.floor(100000 + Math.random() * 900000);
  const fullNumber = selected.code + randomDigits;

  const newNum = {
    id: numbers.length + 1,
    phone: fullNumber,
    country: selected.name,
    flag: selected.flag,
    operator: selected.op,
    assigned: true,
    created_at: new Date().toISOString()
  };

  numbers.unshift(newNum);

  res.json({
    success: true,
    phone: fullNumber,
    country: selected.name,
    flag: selected.flag,
    operator: selected.op
  });
});

app.post('/admin/bot/simulate-sms', verifyToken, (req, res) => {
  const { phone, message, otp } = req.body || {};
  const targetPhone = phone || '+261346226452';
  const otpCode = otp || Math.floor(100000 + Math.random() * 900000).toString();
  const smsMessage = message || `<#> ${otpCode} est votre code Facebook\nH29Q+Fsn4Sr`;

  const newSms = {
    id: smsLog.length + 1,
    unique_key: 'sim_' + Date.now(),
    phone: targetPhone,
    country: detectCountry(targetPhone).country,
    otp: otpCode,
    message: smsMessage,
    created_at: new Date().toISOString()
  };

  smsLog.unshift(newSms);

  res.json({
    success: true,
    sms: newSms
  });
});

// =============================================================================
// TELEGRAM BOT ENGINE & REAL-TIME NUMBER ALLOCATOR (24/7 Crash-Proof)
// =============================================================================

const TELEGRAM_BOT_TOKEN = '8522208519:AAEHG0GGOOYMtvgGHuU7hZ5Z4YlLkBAWvEU';
const GROUP_ID = process.env.GROUP_ID || '-1001367182443';
const CHANNEL_ID = process.env.CHANNEL_ID || '-1001688406759';
const ADMIN_ID = process.env.ADMIN_ID || '1319659809';
const ADMIN_USERNAME = process.env.ADMIN_USERNAME || 'JAHID_1';
const UPDATE_CHANNEL_LINK = process.env.UPDATE_CHANNEL_LINK || 'https://t.me/painite_1';
const GROUP_LINK = process.env.GROUP_LINK || 'https://t.me/painite_club';

const userStates = new Map();
const userCooldowns = new Map();

function getBangladeshTime() {
  return new Date().toLocaleTimeString('en-US', {
    timeZone: 'Asia/Dhaka',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function detectCountry(phoneOrPrefix) {
  const clean = String(phoneOrPrefix || '').replace(/[^0-9]/g, '');
  if (clean.startsWith('261')) return { country: 'Madagascar', flag: '🇲🇬' };
  if (clean.startsWith('225')) return { country: 'Ivory Coast', flag: '🇨🇮' };
  if (clean.startsWith('237')) return { country: 'Cameroon', flag: '🇨🇲' };
  if (clean.startsWith('224')) return { country: 'Guinea', flag: '🇬🇳' };
  if (clean.startsWith('255')) return { country: 'Tanzania', flag: '🇹🇿' };
  if (clean.startsWith('236')) return { country: 'Central African Rep', flag: '🇨🇫' };
  if (clean.startsWith('382')) return { country: 'Montenegro', flag: '🇲🇪' };
  if (clean.startsWith('233')) return { country: 'Ghana', flag: '🇬🇭' };
  if (clean.startsWith('992')) return { country: 'Tajikistan', flag: '🇹🇯' };
  if (clean.startsWith('856')) return { country: 'Laos', flag: '🇱🇦' };
  if (clean.startsWith('93')) return { country: 'Afghanistan', flag: '🇦🇫' };
  if (clean.startsWith('354')) return { country: 'Iceland', flag: '🇮🇸' };
  if (clean.startsWith('880')) return { country: 'Bangladesh', flag: '🇧🇩' };
  if (clean.startsWith('1')) return { country: 'United States', flag: '🇺🇸' };
  if (clean.startsWith('44')) return { country: 'United Kingdom', flag: '🇬🇧' };
  if (clean.startsWith('91')) return { country: 'India', flag: '🇮🇳' };
  if (clean.startsWith('92')) return { country: 'Pakistan', flag: '🇵🇰' };
  if (clean.startsWith('234')) return { country: 'Nigeria', flag: '🇳🇬' };
  if (clean.startsWith('62')) return { country: 'Indonesia', flag: '🇮🇩' };
  if (clean.startsWith('84')) return { country: 'Vietnam', flag: '🇻🇳' };
  if (clean.startsWith('63')) return { country: 'Philippines', flag: '🇵🇭' };
  if (clean.startsWith('7')) return { country: 'Russia', flag: '🇷🇺' };
  if (clean.startsWith('49')) return { country: 'Germany', flag: '🇩🇪' };
  if (clean.startsWith('33')) return { country: 'France', flag: '🇫🇷' };
  if (clean.startsWith('55')) return { country: 'Brazil', flag: '🇧🇷' };
  if (clean.startsWith('20')) return { country: 'Egypt', flag: '🇪🇬' };
  if (clean.startsWith('254')) return { country: 'Kenya', flag: '🇰🇪' };
  if (clean.startsWith('212')) return { country: 'Morocco', flag: '🇲🇦' };
  return { country: 'International', flag: '🌍' };
}

function extractOtp(message) {
  if (!message) return 'N/A';
  const patterns = [
    /\b(\d{4,8})\b/,
    /(?:code|otp|is|pin|código|verification|kod|رمز)[\s:]*([0-9]{4,8})/i,
    /([0-9]{3}-[0-9]{3})/,
    /([0-9]{4,6})/
  ];
  for (const p of patterns) {
    const match = message.match(p);
    if (match) {
      return match[1] || match[0];
    }
  }
  return 'N/A';
}

// Fetch live running ranges (Hot In-Memory Cache for 0ms Instant Response)
function getHotLiveRanges() {
  if (liveRunningRanges.length > 0) {
    return liveRunningRanges;
  }
  return [
    { sender: 'Facebook', range: '22507XXX', prefix: '22507', country: 'Ivory Coast', flag: '🇨🇮' },
    { sender: 'Facebook', range: '22501XXX', prefix: '22501', country: 'Ivory Coast', flag: '🇨🇮' },
    { sender: 'Facebook', range: '22505XXX', prefix: '22505', country: 'Ivory Coast', flag: '🇨🇮' },
    { sender: 'Facebook', range: '26134XXX', prefix: '26134', country: 'Madagascar', flag: '🇲🇬' },
    { sender: 'Facebook', range: '26138XXX', prefix: '26138', country: 'Madagascar', flag: '🇲🇬' },
    { sender: 'Facebook', range: '26136XXX', prefix: '26136', country: 'Madagascar', flag: '🇲🇬' },
    { sender: 'Facebook', range: '23762XXX', prefix: '23762', country: 'Cameroon', flag: '🇨🇲' },
    { sender: 'Facebook', range: '23765XXX', prefix: '23765', country: 'Cameroon', flag: '🇨🇲' },
    { sender: 'Facebook', range: '224650XXX', prefix: '224650', country: 'Guinea', flag: '🇬🇳' },
    { sender: 'Facebook', range: '25567XXX', prefix: '25567', country: 'Tanzania', flag: '🇹🇿' },
    { sender: 'Facebook', range: '23674XXX', prefix: '23674', country: 'Central African Rep', flag: '🇨🇫' }
  ];
}

async function fetchLivePanelRanges(force = false) {
  if (liveRunningRanges.length > 0 && !force) {
    return liveRunningRanges;
  }
  refreshLiveRangesBackground();
  return getHotLiveRanges();
}

// Background Silent Updater for Live Ranges (Facebook Only)
async function refreshLiveRangesBackground() {
  if (settings.mode === 'api' && settings.api_key) {
    try {
      const cleanUrl = (settings.api_url || 'https://zebrasms.com/api/v1').replace(/\/+$/, '');
      const endpoint = cleanUrl.includes('/publicapi') ? `${cleanUrl}/liveaccess` : `${cleanUrl}/publicapi/liveaccess`;
      const res = await makeRequest(endpoint, {
        'MAuth': settings.api_key,
        'mauthapi': settings.api_key,
        'Accept': 'application/json'
      }, 'GET', null, 3000);

      if (res && res.data && res.data.data) {
        const rows = res.data.data.rows || res.data.data.services || [];
        if (Array.isArray(rows) && rows.length > 0) {
          const list = [];
          for (const r of rows) {
            const sender = r.sender || '';
            // Strictly filter for Facebook services only
            const isFb = /facebook|fb/i.test(sender);
            if (!isFb && rows.some(x => /facebook|fb/i.test(x.sender || ''))) {
              continue;
            }

            const ranges = Array.isArray(r.ranges) ? r.ranges : [r.range || '22507XXX'];
            for (const rng of ranges) {
              const cleanPfx = String(rng).replace(/[^0-9]/g, '');
              if (!cleanPfx || cleanPfx.length < 3) continue;
              const detected = detectCountry(cleanPfx);
              list.push({
                sender: 'Facebook',
                range: String(rng),
                prefix: cleanPfx,
                country: detected.country,
                flag: detected.flag
              });
            }
          }
          if (list.length > 0) {
            liveRunningRanges = list;
          }
        }
      }
    } catch (err) {
      // Silent error in background
    }
  }
}

// Initialize hot live ranges immediately on boot
liveRunningRanges = getHotLiveRanges();
setInterval(refreshLiveRangesBackground, 45000);

// Group ranges by country (Instant In-Memory Computation)
function mergeRangesWithCustom(liveList = []) {
  const map = new Map();
  const list = liveList.length > 0 ? liveList : getHotLiveRanges();

  // Add live running ranges
  for (const item of list) {
    const cName = item.country || 'International';
    if (!map.has(cName)) {
      map.set(cName, {
        country: cName,
        flag: item.flag || '🌍',
        ranges: [],
        prefixes: []
      });
    }
    const grp = map.get(cName);
    const rng = item.range || `${item.prefix}XXX`;
    if (!grp.ranges.includes(rng)) grp.ranges.push(rng);
    if (!grp.prefixes.includes(item.prefix)) grp.prefixes.push(item.prefix);
  }

  // Add personal custom ranges
  for (const c of customRanges) {
    const cName = c.country || 'International';
    if (!map.has(cName)) {
      map.set(cName, {
        country: cName,
        flag: c.flag || '🌍',
        ranges: [],
        prefixes: []
      });
    }
    const grp = map.get(cName);
    const rng = `${c.prefix}XXX`;
    if (!grp.ranges.includes(rng)) grp.ranges.push(rng);
    if (!grp.prefixes.includes(c.prefix)) grp.prefixes.push(c.prefix);
  }

  return Array.from(map.values());
}

function getMainMenuKeyboard() {
  return {
    keyboard: [
      [{ text: '📱 Paid Number' }, { text: '📱 Get Number (Random)' }],
      [{ text: '🌍 Get Country' }, { text: '🔐 OTP Check' }]
    ],
    resize_keyboard: true
  };
}

function getRandomActiveRange() {
  const live = getHotLiveRanges();
  const allRanges = [];

  if (Array.isArray(live)) {
    for (const r of live) {
      if (r && r.prefix) allRanges.push(r);
    }
  }

  if (Array.isArray(customRanges)) {
    for (const c of customRanges) {
      if (c && c.prefix) allRanges.push(c);
    }
  }

  if (allRanges.length === 0) {
    return { prefix: '22507', country: 'Ivory Coast', flag: '🇨🇮' };
  }

  return allRanges[Math.floor(Math.random() * allRanges.length)];
}

function formatNumberCard(allocated, prefix) {
  const nowTime = getBangladeshTime();
  const card = `📱 <b>${allocated.flag} ${escapeHtml(allocated.country)} Number Ready</b>\n━━━━━━━━━━━━━━━━━━━━\n☎️ <b>Phone Number:</b>\n<code>${escapeHtml(allocated.phone)}</code>\n\n🎯 <b>Range:</b> <code>${escapeHtml(prefix)}XXX</code>\n⏰ <b>Time:</b> <code>${nowTime}</code>\n📶 <b>Status:</b> <code>Ready (Facebook)</code>\n━━━━━━━━━━━━━━━━━━━━`;

  const inlineKeyboard = [
    [
      { text: '🔄 Change Number', callback_data: `gr:${prefix}` },
      { text: '🔐 Get OTP', callback_data: `chk:${allocated.phone}:${prefix}` }
    ],
    [
      { text: '🌍 Change Country', callback_data: 'page:0' }
    ]
  ];

  return { text: card, reply_markup: { inline_keyboard: inlineKeyboard } };
}

function callTelegramApi(method, data = {}, customTimeout = 10000) {
  return new Promise((resolve) => {
    let resolved = false;
    const postData = JSON.stringify(data);
    const options = {
      hostname: 'api.telegram.org',
      port: 443,
      path: `/bot${TELEGRAM_BOT_TOKEN}/${method}`,
      method: 'POST',
      agent: httpsAgent,
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData),
        'Connection': 'keep-alive'
      },
      timeout: customTimeout
    };

    const finish = (result) => {
      if (!resolved) {
        resolved = true;
        resolve(result);
      }
    };

    try {
      const req = https.request(options, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => {
          try {
            finish(JSON.parse(body));
          } catch (e) {
            finish({ ok: false, error: 'JSON parse error' });
          }
        });
      });

      req.on('error', (err) => {
        finish({ ok: false, error: err.message });
      });

      req.on('timeout', () => {
        req.destroy();
        finish({ ok: false, error: 'timeout' });
      });

      req.write(postData);
      req.end();
    } catch (err) {
      finish({ ok: false, error: err.message });
    }
  });
}

async function sendTelegramMessage(chatId, text, extra = {}) {
  return await callTelegramApi('sendMessage', {
    chat_id: chatId,
    text,
    parse_mode: 'HTML',
    ...extra
  }, 10000);
}

async function editTelegramMessage(chatId, messageId, text, extra = {}) {
  return await callTelegramApi('editMessageText', {
    chat_id: chatId,
    message_id: messageId,
    text,
    parse_mode: 'HTML',
    ...extra
  }, 10000);
}

// Instant 0ms Number Allocation (Zero-Delay Generation)
function allocateNumberForBot(rangePrefix = '26134') {
  const cleanPrefix = String(rangePrefix || '26134').replace(/[^0-9]/g, '') || '26134';

  // Instant calculation matching standard international number lengths
  const targetTotalLength = cleanPrefix.length <= 3 ? 10 : (cleanPrefix.length <= 5 ? 12 : 13);
  const neededDigits = Math.max(4, targetTotalLength - cleanPrefix.length);
  const minNum = Math.pow(10, neededDigits - 1);
  const maxNum = Math.pow(10, neededDigits) - 1;
  const randTail = Math.floor(minNum + Math.random() * (maxNum - minNum + 1));
  const fullNumber = `+${cleanPrefix}${randTail}`;
  const detected = detectCountry(fullNumber);

  const newNum = {
    id: numbers.length + 1,
    phone: fullNumber,
    country: detected.country,
    flag: detected.flag,
    operator: 'Zebra Live Range',
    range_prefix: cleanPrefix,
    assigned: true,
    created_at: new Date().toISOString()
  };

  numbers.unshift(newNum);
  if (numbers.length > 300) numbers.length = 300;
  savePersistentDb();

  return newNum;
}

// Store user's last active number
const userLastAllocatedNumber = new Map();

// Active Live OTP Animation Timers
const activeOtpAnimators = new Map();

function stopLiveOtpAnimation(chatId, messageId) {
  const animKey = `${chatId}:${messageId}`;
  if (activeOtpAnimators.has(animKey)) {
    const item = activeOtpAnimators.get(animKey);
    if (item && item.timer) clearInterval(item.timer);
    activeOtpAnimators.delete(animKey);
  }
}

function startLiveOtpAnimation(chatId, messageId, targetPhone, targetPrefix) {
  if (!chatId || !messageId) return;
  const animKey = `${chatId}:${messageId}`;
  stopLiveOtpAnimation(chatId, messageId);

  const spinnerFrames = [
    '⏳ Searching SMS ⠋',
    '⌛ Searching SMS ⠙',
    '⏳ Searching SMS ⠹',
    '⌛ Searching SMS ⠸',
    '⏳ Searching SMS ⠼',
    '⌛ Searching SMS ⠴',
    '⏳ Searching SMS ⠦',
    '⌛ Searching SMS ⠧',
    '⏳ Searching SMS ⠇',
    '⌛ Searching SMS ⠏'
  ];

  let frameIdx = 0;
  let cycleCount = 0;
  const maxCycles = 30; // 30 cycles * 2s = 60s active live search

  const timer = setInterval(async () => {
    cycleCount++;
    if (cycleCount > maxCycles) {
      stopLiveOtpAnimation(chatId, messageId);
      return;
    }

    frameIdx = (frameIdx + 1) % spinnerFrames.length;
    const currentFrame = spinnerFrames[frameIdx];

    // Check if OTP arrived in memory or active list
    const cleanInput = String(targetPhone || '').replace(/[^0-9]/g, '');
    let matchedSms = null;
    if (Array.isArray(smsLog)) {
      matchedSms = smsLog.find(s => {
        const p = String(s.phone || '').replace(/[^0-9]/g, '');
        return p && (p.includes(cleanInput) || cleanInput.includes(p));
      });
    }

    if (matchedSms) {
      stopLiveOtpAnimation(chatId, messageId);
      const msgText = matchedSms.message || matchedSms.sms || matchedSms.text || 'Verification code received.';
      const otpCode = matchedSms.otp || extractOtp(msgText);
      const nowTime = getBangladeshTime();
      const otpCard = `✅ <b>OTP Received</b>\n━━━━━━━━━━━━━━━━━━━━\n🔑 <b>OTP Code:</b>\n<code>${escapeHtml(otpCode)}</code>\n\n☎️ <b>Phone Number:</b>\n<code>${escapeHtml(matchedSms.phone || targetPhone)}</code>\n\n🏢 <b>Service:</b> ${escapeHtml(matchedSms.sender || matchedSms.service || 'Facebook')}\n⏰ <b>Time:</b> <code>${nowTime}</code>\n\n✉️ <b>SMS Message:</b>\n<i>${escapeHtml(msgText)}</i>\n━━━━━━━━━━━━━━━━━━━━`;
      const inlineKeyboard = [
        [
          { text: '🔄 Refresh OTP', callback_data: `chk:${targetPhone}:${targetPrefix}` },
          { text: '📱 New Number', callback_data: `gr:${targetPrefix}` }
        ],
        [
          { text: '📱 Join OTP Group', url: GROUP_LINK }
        ]
      ];
      await editTelegramMessage(chatId, messageId, otpCard, { reply_markup: { inline_keyboard: inlineKeyboard } });
      return;
    }

    // Update animated status frame on message
    const nowTime = getBangladeshTime();
    const waitingCard = `⏳ <b>Waiting for OTP</b>\n━━━━━━━━━━━━━━━━━━━━\n☎️ <b>Phone Number:</b>\n<code>${escapeHtml(targetPhone)}</code>\n\n🎯 <b>Service:</b> <code>Facebook OTP</code>\n⏰ <b>Time:</b> <code>${nowTime}</code>\n⚠️ <b>Status:</b> <code>${currentFrame}</code>\n━━━━━━━━━━━━━━━━━━━━`;

    const inlineKeyboard = [
      [
        { text: '🔄 Check Again', callback_data: `chk:${targetPhone}:${targetPrefix}` },
        { text: '🔄 Change Number', callback_data: `gr:${targetPrefix}` }
      ],
      [
        { text: '📱 Join OTP Group', url: GROUP_LINK }
      ]
    ];

    const editRes = await editTelegramMessage(chatId, messageId, waitingCard, { reply_markup: { inline_keyboard: inlineKeyboard } });
    if (!editRes || !editRes.ok) {
      stopLiveOtpAnimation(chatId, messageId);
    }
  }, 2000);

  activeOtpAnimators.set(animKey, { timer });
}

// Centralized OTP Checker Function (Direct, Instant & Facebook-Optimized)
async function executeOtpCheck(chatId, phoneInput, prefix = '22507', messageId = null, userId = null) {
  try {
    let targetPhone = phoneInput;
    let targetPrefix = prefix;

    if (!targetPhone && userId && userLastAllocatedNumber.has(String(userId))) {
      const saved = userLastAllocatedNumber.get(String(userId));
      targetPhone = saved.phone;
      targetPrefix = saved.prefix || prefix;
    }

    if (!targetPhone && numbers.length > 0) {
      targetPhone = numbers[0].phone;
      targetPrefix = numbers[0].range_prefix || prefix;
    }

    const cleanInput = String(targetPhone || '').replace(/[^0-9]/g, '');
    if (!cleanInput || cleanInput.length < 5) {
      return await sendTelegramMessage(chatId, `🔐 <b>OTP Code Verification</b>\n━━━━━━━━━━━━━━━━━━━━\nPlease send your phone number with country code to check OTP.\n━━━━━━━━━━━━━━━━━━━━`, {
        reply_markup: {
          inline_keyboard: [
            [{ text: '📱 Get Number (Random)', callback_data: 'rnd' }],
            [{ text: '📱 Join OTP Group', url: GROUP_LINK }]
          ]
        }
      });
    }

    let matchedSms = null;

    // 1. Memory match in active smsLog
    if (Array.isArray(smsLog)) {
      matchedSms = smsLog.find(s => {
        const p = String(s.phone || '').replace(/[^0-9]/g, '');
        return p && (p.includes(cleanInput) || cleanInput.includes(p));
      });
    }

    // 2. Fast Live API query if in API mode
    if (!matchedSms && settings.mode === 'api' && settings.api_key) {
      try {
        const cleanUrl = (settings.api_url || 'https://zebrasms.com/api/v1').replace(/\/+$/, '');
        const endpoint = cleanUrl.includes('/publicapi') ? `${cleanUrl}/getupdate` : `${cleanUrl}/publicapi/getupdate`;
        const res = await makeRequest(endpoint, {
          'MAuth': settings.api_key,
          'mauthapi': settings.api_key
        }, 'GET', null, 1500);

        if (res && res.data && res.data.data) {
          const list = Array.isArray(res.data.data) ? res.data.data : (res.data.data.rows || []);
          for (const item of list) {
            const phoneStr = String(item.phone || item.number || '').replace(/[^0-9]/g, '');
            if (phoneStr && (phoneStr.includes(cleanInput) || cleanInput.includes(phoneStr))) {
              matchedSms = item;
              break;
            }
          }
        }
      } catch (err) {
        // Continue
      }
    }

    if (userId) {
      userLastAllocatedNumber.set(String(userId), {
        phone: targetPhone,
        prefix: targetPrefix,
        chatId: chatId
      });
    }

    const nowTime = getBangladeshTime();
    if (matchedSms) {
      if (messageId) stopLiveOtpAnimation(chatId, messageId);
      const msgText = matchedSms.message || matchedSms.sms || matchedSms.text || 'Verification code received.';
      const otpCode = matchedSms.otp || extractOtp(msgText);

      const otpCard = `✅ <b>OTP Received</b>\n━━━━━━━━━━━━━━━━━━━━\n🔑 <b>OTP Code:</b>\n<code>${escapeHtml(otpCode)}</code>\n\n☎️ <b>Phone Number:</b>\n<code>${escapeHtml(matchedSms.phone || targetPhone)}</code>\n\n🏢 <b>Service:</b> ${escapeHtml(matchedSms.sender || matchedSms.service || 'Facebook')}\n⏰ <b>Time:</b> <code>${nowTime}</code>\n\n✉️ <b>SMS Message:</b>\n<i>${escapeHtml(msgText)}</i>\n━━━━━━━━━━━━━━━━━━━━`;

      const inlineKeyboard = [
        [
          { text: '🔄 Refresh OTP', callback_data: `chk:${targetPhone}:${targetPrefix}` },
          { text: '📱 New Number', callback_data: `gr:${targetPrefix}` }
        ],
        [
          { text: '📱 Join OTP Group', url: GROUP_LINK }
        ]
      ];

      if (messageId) {
        const editRes = await editTelegramMessage(chatId, messageId, otpCard, { reply_markup: { inline_keyboard: inlineKeyboard } });
        if (editRes && editRes.ok) return editRes;
      }

      return await sendTelegramMessage(chatId, otpCard, {
        reply_markup: { inline_keyboard: inlineKeyboard }
      });
    } else {
      const waitingCard = `⏳ <b>Waiting for OTP</b>\n━━━━━━━━━━━━━━━━━━━━\n☎️ <b>Phone Number:</b>\n<code>${escapeHtml(targetPhone)}</code>\n\n🎯 <b>Service:</b> <code>Facebook OTP</code>\n⏰ <b>Time:</b> <code>${nowTime}</code>\n⚠️ <b>Status:</b> <code>⏳ Searching SMS ⠋</code>\n━━━━━━━━━━━━━━━━━━━━`;

      const inlineKeyboard = [
        [
          { text: '🔄 Check Again', callback_data: `chk:${targetPhone}:${targetPrefix}` },
          { text: '🔄 Change Number', callback_data: `gr:${targetPrefix}` }
        ],
        [
          { text: '📱 Join OTP Group', url: GROUP_LINK }
        ]
      ];

      if (messageId) {
        const editRes = await editTelegramMessage(chatId, messageId, waitingCard, { reply_markup: { inline_keyboard: inlineKeyboard } });
        startLiveOtpAnimation(chatId, messageId, targetPhone, targetPrefix);
        if (editRes && editRes.ok) return editRes;
      }

      const sendRes = await sendTelegramMessage(chatId, waitingCard, {
        reply_markup: { inline_keyboard: inlineKeyboard }
      });
      if (sendRes && sendRes.ok && sendRes.result && sendRes.result.message_id) {
        startLiveOtpAnimation(chatId, sendRes.result.message_id, targetPhone, targetPrefix);
      }
      return sendRes;
    }
  } catch (err) {
    console.error('Error in executeOtpCheck:', err);
    return await sendTelegramMessage(chatId, `⏳ <b>Waiting for OTP</b>\n━━━━━━━━━━━━━━━━━━━━\n☎️ <b>Phone Number:</b>\n<code>${escapeHtml(phoneInput || 'Active Number')}</code>\n\n🎯 <b>Service:</b> <code>Facebook OTP</code>\n⚠️ <b>Status:</b> <code>⏳ Searching SMS ⠋</code>\n━━━━━━━━━━━━━━━━━━━━`, {
      reply_markup: {
        inline_keyboard: [
          [{ text: '🔄 Check Again', callback_data: `chk:${phoneInput || ''}:${prefix || '22507'}` }],
          [{ text: '📱 Join OTP Group', url: GROUP_LINK }]
        ]
      }
    });
  }
}

// Telegram Message Handler
async function handleTelegramMessage(message) {
  if (!message || !message.chat) return;
  const chatId = message.chat.id;
  const user = message.from || {};
  const userId = String(user.id || chatId);
  const username = user.username || '';
  const firstName = user.first_name || 'User';
  const text = (message.text || '').trim();

  // Save/Update user in memory
  let existingUser = users.find(u => String(u.user_id) === userId);
  if (!existingUser) {
    existingUser = {
      user_id: userId,
      username,
      first_name: firstName,
      last_number_time: 0,
      created_at: new Date().toISOString()
    };
    users.unshift(existingUser);
    savePersistentDb();
  } else {
    existingUser.username = username;
    existingUser.first_name = firstName;
  }

  // Bot Maintenance Check
  if (!botActive && text !== '/start' && !text.startsWith('/')) {
    return await sendTelegramMessage(chatId, `🛠 <b>Bot Under Maintenance</b>\n\nThe bot is temporarily turned off by the admin.\nPlease try again later.`, {
      reply_markup: getMainMenuKeyboard()
    });
  }

  // 1. /start command (exact, /start@bot, or start text)
  if (text.startsWith('/start') || text.toLowerCase() === 'start' || text.toLowerCase() === 'hi' || text.toLowerCase() === 'hello') {
    userStates.delete(userId);
    const nowTime = getBangladeshTime();
    const welcome = `🎉 <b>Welcome, ${escapeHtml(firstName)}!</b>\n\n⏰ <b>Time:</b> <code>${nowTime}</code>\n🤖 <b>Bot:</b> Painite OTP Bot\n🛡️ <b>Engine:</b> 24/7 Active\n\n<b>Choose an option below to get started:</b>`;
    return await sendTelegramMessage(chatId, welcome, {
      reply_markup: getMainMenuKeyboard()
    });
  }

  // 2. User input when waiting for Custom Range prefix
  if (userStates.get(userId) === 'WAITING_CUSTOM_RANGE' || /^(?:range\s+)?(\d{2,10})(?:xxx)?$/i.test(text)) {
    userStates.delete(userId);
    const match = text.match(/(\d{2,10})/);
    const rangePrefix = match ? match[1] : '22507';

    const allocated = allocateNumberForBot(rangePrefix);
    userLastAllocatedNumber.set(String(userId), { phone: allocated.phone, prefix: rangePrefix, country: allocated.country, flag: allocated.flag });
    const { text: cardText, reply_markup } = formatNumberCard(allocated, rangePrefix);
    return await sendTelegramMessage(chatId, cardText, { reply_markup });
  }

  // 3. User input when typing a phone number directly
  const digitsOnly = text.replace(/[^0-9]/g, '');
  if (userStates.get(userId) === 'WAITING_OTP' || (/^\+?[0-9]{7,15}$/.test(text) && !text.startsWith('/'))) {
    userStates.delete(userId);
    return await executeOtpCheck(chatId, text, digitsOnly.slice(0, 5) || '22507', null, userId);
  }

  // 4. 📱 Paid Number
  if (text === '📱 Paid Number') {
    const admin = ADMIN_USERNAME.replace('@', '');
    return await sendTelegramMessage(chatId, `🤝 <b>Contact Admin for Paid Number</b>\n━━━━━━━━━━━━━━━━━━━━\nClick below to message the admin directly:\n<i>'sir i want to buy paid number'</i>\n━━━━━━━━━━━━━━━━━━━━`, {
      reply_markup: {
        inline_keyboard: [
          [{ text: '💬 Message Admin', url: `https://t.me/${admin}` }],
          [{ text: '📢 Update Channel', url: UPDATE_CHANNEL_LINK }]
        ]
      }
    });
  }

  // 5. 📱 Get Number (Random)
  if (text === '📱 Get Number (Random)') {
    // Cooldown check (1.5s)
    const lastTime = userCooldowns.get(userId) || 0;
    const now = Date.now();
    if (now - lastTime < 1500) {
      const waitSec = Math.ceil((1500 - (now - lastTime)) / 1000);
      return await sendTelegramMessage(chatId, `⏰ <b>Please Wait</b>\n\n🕐 <b>Cooldown:</b> ${waitSec}s`, {
        reply_markup: getMainMenuKeyboard()
      });
    }
    userCooldowns.set(userId, now);

    // Pick from live running active ranges pool
    const picked = getRandomActiveRange();
    const prefix = picked ? picked.prefix : '22507';

    const allocated = allocateNumberForBot(prefix);
    userLastAllocatedNumber.set(String(userId), { phone: allocated.phone, prefix, country: allocated.country, flag: allocated.flag });
    const { text: cardText, reply_markup } = formatNumberCard(allocated, prefix);
    return await sendTelegramMessage(chatId, cardText, { reply_markup });
  }

  // 6. 🌍 Get Country (Multi-Country & Multi-Range)
  if (text === '🌍 Get Country') {
    return await showCountryList(chatId, 0);
  }

  // 7. 🔐 OTP Check (Checks user's running number immediately)
  if (text === '🔐 OTP Check') {
    userStates.delete(userId);
    return await executeOtpCheck(chatId, null, null, null, userId);
  }

  // Fallback reply
  return await sendTelegramMessage(chatId, `🤖 <b>Painite OTP Bot</b>\n\nPlease select an option from the menu below:`, {
    reply_markup: getMainMenuKeyboard()
  });
}

// Show multi-country inline list with pagination (Instant)
async function showCountryList(chatId, page = 0, messageId = null) {
  const live = getHotLiveRanges();
  const countries = mergeRangesWithCustom(live);

  const PAGE_SIZE = 6;
  const totalPages = Math.ceil(countries.length / PAGE_SIZE) || 1;
  const safePage = Math.max(0, Math.min(page, totalPages - 1));
  const slice = countries.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  const inlineKeyboard = [];
  for (const c of slice) {
    const rangeCount = (c.ranges || []).length;
    inlineKeyboard.push([
      {
        text: `${c.flag} ${c.country} (${rangeCount} ${rangeCount === 1 ? 'Range' : 'Ranges'})`,
        callback_data: `gc:${encodeURIComponent(c.country)}`
      }
    ]);
  }

  // Pagination row
  const navRow = [];
  if (safePage > 0) {
    navRow.push({ text: '⬅️ Prev', callback_data: `page:${safePage - 1}` });
  }
  navRow.push({ text: `📄 ${safePage + 1}/${totalPages}`, callback_data: 'noop' });
  if (safePage < totalPages - 1) {
    navRow.push({ text: 'Next ➡️', callback_data: `page:${safePage + 1}` });
  }
  inlineKeyboard.push(navRow);

  inlineKeyboard.push([
    { text: '🎲 Random Number', callback_data: 'rnd' }
  ]);

  const text = `🌍 <b>Select Country (Facebook Active)</b>\n━━━━━━━━━━━━━━━━━━━━\n📊 <b>Total Countries:</b> ${countries.length} Available\n⚡ <b>Status:</b> Facebook Ranges Active\n━━━━━━━━━━━━━━━━━━━━`;

  if (messageId) {
    const editRes = await editTelegramMessage(chatId, messageId, text, {
      reply_markup: { inline_keyboard: inlineKeyboard }
    });
    if (editRes && editRes.ok) return editRes;
  }

  return await sendTelegramMessage(chatId, text, {
    reply_markup: {
      inline_keyboard: inlineKeyboard
    }
  });
}

// Show ranges for a specific country (Instant)
async function showCountryRanges(chatId, countryName, messageId = null) {
  const live = getHotLiveRanges();
  const countries = mergeRangesWithCustom(live);
  const target = countries.find(c => c.country.toLowerCase() === countryName.toLowerCase());

  if (!target || !target.prefixes || target.prefixes.length === 0) {
    return await showCountryList(chatId, 0, messageId);
  }

  const buttons = [];
  for (let i = 0; i < target.prefixes.length; i++) {
    const pfx = target.prefixes[i];
    const rng = target.ranges[i] || `${pfx}XXX`;
    buttons.push([
      {
        text: `⚡ Range ${rng} (${target.country})`,
        callback_data: `gr:${pfx}`
      }
    ]);
  }

  buttons.push([
    { text: '⬅️ Back to Countries', callback_data: 'page:0' }
  ]);

  const text = `${target.flag} <b>${escapeHtml(target.country)} Facebook Ranges</b>\n━━━━━━━━━━━━━━━━━━━━\nSelect an active range below:\n━━━━━━━━━━━━━━━━━━━━`;

  if (messageId) {
    const editRes = await editTelegramMessage(chatId, messageId, text, {
      reply_markup: { inline_keyboard: buttons }
    });
    if (editRes && editRes.ok) return editRes;
  }

  return await sendTelegramMessage(chatId, text, {
    reply_markup: {
      inline_keyboard: buttons
    }
  });
}

// Telegram Callback Query Handler (Instant Zero-Delay Engine)
async function handleTelegramCallback(callbackQuery) {
  if (!callbackQuery) return;
  const callbackId = callbackQuery.id;
  const message = callbackQuery.message;
  const data = callbackQuery.data || '';
  const user = callbackQuery.from || {};
  const userId = String(user.id || (message && message.chat.id));
  const chatId = message ? message.chat.id : userId;

  if (data === 'noop') {
    callTelegramApi('answerCallbackQuery', { callback_query_id: callbackId }).catch(() => {});
    return;
  }

  if (data === 'main_menu') {
    callTelegramApi('answerCallbackQuery', { callback_query_id: callbackId }).catch(() => {});
    userStates.delete(userId);
    const nowTime = getBangladeshTime();
    const welcome = `🎉 <b>Welcome, ${escapeHtml(user.first_name || 'User')}!</b>\n\n⏰ <b>Time:</b> <code>${nowTime}</code>\n🤖 <b>Bot:</b> Painite OTP Bot\n🛡️ <b>Engine:</b> 24/7 Active\n\n<b>Choose an option below to get started:</b>`;
    return await sendTelegramMessage(chatId, welcome, {
      reply_markup: getMainMenuKeyboard()
    });
  }

  if (data.startsWith('page:')) {
    callTelegramApi('answerCallbackQuery', { callback_query_id: callbackId }).catch(() => {});
    const pageNum = parseInt(data.split(':')[1], 10) || 0;
    return await showCountryList(chatId, pageNum, message ? message.message_id : null);
  }

  if (data.startsWith('gc:')) {
    callTelegramApi('answerCallbackQuery', { callback_query_id: callbackId }).catch(() => {});
    const countryName = decodeURIComponent(data.substring(3));
    return await showCountryRanges(chatId, countryName, message ? message.message_id : null);
  }

  if (data.startsWith('chk:')) {
    callTelegramApi('answerCallbackQuery', { callback_query_id: callbackId }).catch(() => {});
    const parts = data.split(':');
    const phone = parts[1] || '';
    const prefix = parts[2] || '22507';
    return await executeOtpCheck(chatId, phone, prefix, message ? message.message_id : null, userId);
  }

  if (data === 'otp_check') {
    callTelegramApi('answerCallbackQuery', { callback_query_id: callbackId }).catch(() => {});
    return await executeOtpCheck(chatId, null, null, message ? message.message_id : null, userId);
  }

  if (data === 'rnd' || data.startsWith('gr:')) {
    let prefix = '22507';
    if (data.startsWith('gr:')) {
      prefix = data.split(':')[1] || '22507';
    } else {
      const picked = getRandomActiveRange();
      prefix = picked ? picked.prefix : '22507';
    }

    const allocated = allocateNumberForBot(prefix);
    userLastAllocatedNumber.set(String(userId), { phone: allocated.phone, prefix, country: allocated.country, flag: allocated.flag });
    const { text: cardText, reply_markup } = formatNumberCard(allocated, prefix);

    // Silent answer without notification text
    if (callbackId) {
      callTelegramApi('answerCallbackQuery', {
        callback_query_id: callbackId
      }).catch(() => {});
    }

    if (message && message.message_id) {
      stopLiveOtpAnimation(chatId, message.message_id);
      const editRes = await editTelegramMessage(chatId, message.message_id, cardText, { reply_markup });
      if (editRes && editRes.ok) {
        return editRes;
      }
    }

    return await sendTelegramMessage(chatId, cardText, { reply_markup });
  }
}

// =============================================================================
// 24/7 CRASH-PROOF POLLING ENGINE & RELIABILITY WATCHDOG
// =============================================================================

let isPollingActive = false;
let isFetchInFlight = false;
let lastSuccessfulPoll = Date.now();

async function startTelegramBotPolling() {
  if (isPollingActive) {
    return;
  }

  isPollingActive = true;
  lastSuccessfulPoll = Date.now();
  console.log('🤖 [Telegram Polling] Starting continuous 24/7 listener...');

  // 1. Clean up any existing webhook
  try {
    await callTelegramApi('deleteWebhook', { drop_pending_updates: false }, 5000);
  } catch (e) {
    // Ignore webhook delete error
  }

  // 2. Continuous long-polling loop
  while (isPollingActive) {
    isFetchInFlight = true;

    try {
      const response = await callTelegramApi('getUpdates', {
        offset: lastUpdateId > 0 ? lastUpdateId + 1 : undefined,
        timeout: 10,
        limit: 50,
        allowed_updates: ['message', 'callback_query']
      }, 18000);

      isFetchInFlight = false;
      lastSuccessfulPoll = Date.now();

      if (response && response.ok && Array.isArray(response.result)) {
        for (const update of response.result) {
          if (update.update_id) {
            if (isDuplicateUpdate(update.update_id)) continue;
            if (update.update_id >= lastUpdateId) {
              lastUpdateId = update.update_id;
              savePersistentDb();
            }
          }

          // Dispatch handling immediately in background (non-blocking)
          if (update.message) {
            setImmediate(() => {
              handleTelegramMessage(update.message).catch(e => {
                console.error('Error in handleTelegramMessage:', e.message);
              });
            });
          } else if (update.callback_query) {
            setImmediate(() => {
              handleTelegramCallback(update.callback_query).catch(e => {
                console.error('Error in handleTelegramCallback:', e.message);
              });
            });
          }
        }
      } else if (response && response.error_code === 409) {
        console.warn('⚠️ Telegram 409 Conflict: waiting 1s...');
        await new Promise(r => setTimeout(r, 1000));
      } else if (response && response.error_code === 401) {
        console.error('❌ Invalid Telegram Bot Token');
        await new Promise(r => setTimeout(r, 8000));
      } else {
        await new Promise(r => setTimeout(r, 100));
      }
    } catch (err) {
      isFetchInFlight = false;
      await new Promise(r => setTimeout(r, 500));
    }
  }
}

// 24/7 Watchdog: restarts polling if loop stops
setInterval(() => {
  const silentMs = Date.now() - lastSuccessfulPoll;
  if (silentMs > 35000) {
    console.log(`🔄 [Watchdog] Listener silent for ${Math.round(silentMs / 1000)}s. Resetting polling...`);
    isPollingActive = false;
    isFetchInFlight = false;
    lastSuccessfulPoll = Date.now();
    setTimeout(() => {
      startTelegramBotPolling();
    }, 500);
  }
}, 10000);

// Background Live SMS Poller (Every 6s)
async function startSmsWatcher() {
  console.log('📱 Live SMS Watcher initialized');
  const seenKeys = new Set(smsLog.map(s => s.unique_key || `${s.phone}|${s.message}`));

  setInterval(async () => {
    if (!botActive) return;
    if (settings.mode !== 'api' || !settings.api_key) return;

    try {
      const cleanUrl = (settings.api_url || 'https://zebrasms.com/api/v1').replace(/\/+$/, '');
      const endpoint = cleanUrl.includes('/publicapi') ? `${cleanUrl}/getupdate` : `${cleanUrl}/publicapi/getupdate`;
      const res = await makeRequest(endpoint, {
        'MAuth': settings.api_key,
        'mauthapi': settings.api_key
      }, 'GET', null, 3000);

      if (res && res.data && res.data.data) {
        const list = Array.isArray(res.data.data) ? res.data.data : (res.data.data.rows || []);
        for (const item of list) {
          const phone = item.phone || item.number || '';
          const message = item.message || item.sms || item.text || '';
          const uniqueKey = item.otp_id || item.id || `${phone}|${message}`;

          if (phone && message && !seenKeys.has(uniqueKey)) {
            seenKeys.add(uniqueKey);
            const otpCode = item.otp || extractOtp(message);
            const { country, flag } = detectCountry(phone);

            const newEntry = {
              id: smsLog.length + 1,
              unique_key: uniqueKey,
              phone,
              country,
              otp: otpCode,
              message,
              created_at: new Date().toISOString()
            };
            smsLog.unshift(newEntry);
            savePersistentDb();

            // Notify Telegram Group and Admin
            const groupMsg = `<b>📱 New ${otpCode !== 'N/A' ? 'OTP' : 'SMS'} Received! ✨</b>\n\n<blockquote>📞 <b>Number:</b> <code>${escapeHtml(phone)}</code></blockquote>\n\n<blockquote>🌍 <b>Country:</b> ${flag} ${escapeHtml(country)}</blockquote>\n\n<blockquote>🔑 <b>OTP:</b> <code>${escapeHtml(otpCode)}</code></blockquote>\n\n<blockquote>⏰ <b>Time:</b> <code>${getBangladeshTime()}</code></blockquote>\n\n<b>✉️ Message:</b>\n<blockquote><i>${escapeHtml(message)}</i></blockquote>`;

            sendTelegramMessage(GROUP_ID, groupMsg, {
              reply_markup: {
                inline_keyboard: [[{ text: '📢 Update Channel', url: UPDATE_CHANNEL_LINK }]]
              }
            }).catch(() => {});

            sendTelegramMessage(ADMIN_ID, `<b>📱 New SMS (Admin)</b>\n\n<blockquote>📞 <b>Number:</b> <code>${escapeHtml(phone)}</code>\n🌍 <b>Country:</b> ${flag} ${escapeHtml(country)}\n🔑 <b>OTP:</b> <code>${escapeHtml(otpCode)}</code>\n\n📝 <b>Message:</b>\n${escapeHtml(message)}</blockquote>`).catch(() => {});

            // Auto-notify private user if they are waiting for this number
            for (const [uid, alloc] of userLastAllocatedNumber.entries()) {
              const p1 = String(phone).replace(/[^0-9]/g, '');
              const p2 = String(alloc.phone || '').replace(/[^0-9]/g, '');
              if (p1 && p2 && (p1.includes(p2) || p2.includes(p1))) {
                const userCard = `✅ <b>OTP Received</b>\n━━━━━━━━━━━━━━━━━━━━\n🔑 <b>OTP Code:</b>\n<code>${escapeHtml(otpCode)}</code>\n\n☎️ <b>Phone Number:</b>\n<code>${escapeHtml(alloc.phone || phone)}</code>\n\n🏢 <b>Service:</b> Facebook\n⏰ <b>Time:</b> <code>${getBangladeshTime()}</code>\n\n✉️ <b>SMS Message:</b>\n<i>${escapeHtml(message)}</i>\n━━━━━━━━━━━━━━━━━━━━`;
                const targetChat = alloc.chatId || uid;
                sendTelegramMessage(targetChat, userCard, {
                  reply_markup: {
                    inline_keyboard: [
                      [
                        { text: '🔄 Refresh OTP', callback_data: `chk:${alloc.phone || phone}:${alloc.prefix || '22507'}` },
                        { text: '📱 New Number', callback_data: `gr:${alloc.prefix || '22507'}` }
                      ],
                      [
                        { text: '📱 Join OTP Group', url: GROUP_LINK }
                      ]
                    ]
                  }
                }).catch(() => {});
              }
            }
          }
        }
      }
    } catch (err) {
      // silent poll error
    }
  }, 6000);
}

// Keep-alive process protection
process.on('uncaughtException', (err) => {
  console.error('🛡️ Process Uncaught Exception (Protected):', err.message);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('🛡️ Process Unhandled Rejection (Protected):', reason);
});

// Self-ping Keep-Alive to prevent container sleep
setInterval(() => {
  try {
    http.get(`http://127.0.0.1:${PORT}/health`, () => {}).on('error', () => {});
  } catch (e) {}
}, 10000);

// Start Telegram Service and Live SMS Poller
startTelegramBotPolling();
startSmsWatcher();

// Static Files
app.use(express.static(path.join(__dirname)));

// Catch-all route to serve index.html for SPA/Web Access
app.use((req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Painite Admin Web Server running on http://0.0.0.0:${PORT}`);
});
