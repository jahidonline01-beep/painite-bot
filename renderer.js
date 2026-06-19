let API = '';
let TOKEN = '';

const $ = (id) => document.getElementById(id);

function toast(msg, type = '') {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast show ' + type;
  setTimeout(() => { t.className = 'toast ' + type; }, 2600);
}

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'x-admin-token': TOKEN,
      ...(options.headers || {})
    }
  });
  if (res.status === 401) throw new Error('Unauthorized — wrong token');
  if (!res.ok) {
    const err = new Error('Request failed (' + res.status + ')');
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function fmtDate(v) {
  if (!v) return '—';
  try {
    const d = new Date(v);
    if (isNaN(d)) return String(v);
    return d.toLocaleString();
  } catch { return String(v); }
}

/* ---------- LOGIN ---------- */
$('login-btn').addEventListener('click', login);
$('admin-token').addEventListener('keydown', (e) => { if (e.key === 'Enter') login(); });

/* Show / hide password */
$('toggle-pw').addEventListener('click', () => {
  const inp = $('admin-token');
  const btn = $('toggle-pw');
  if (inp.type === 'password') {
    inp.type = 'text';
    btn.classList.add('active');
    btn.textContent = '🙈';
  } else {
    inp.type = 'password';
    btn.classList.remove('active');
    btn.textContent = '👁';
  }
});

async function login() {
  const url = $('api-url').value.trim().replace(/\/+$/, '');
  const token = $('admin-token').value.trim();
  const err = $('login-error');
  err.textContent = '';
  if (!url || !token) { err.textContent = 'Enter API URL and token'; return; }

  API = url;
  TOKEN = token;
  const btn = $('login-btn');
  btn.disabled = true; btn.textContent = 'Connecting...';
  try {
    await api('/admin/stats');
    localStorage.setItem('painite_api', API);
    localStorage.setItem('painite_token', TOKEN);
    $('login-screen').classList.add('hidden');
    $('app').classList.remove('hidden');
    loadAll();
  } catch (e) {
    err.textContent = e.message || 'Connection failed';
    API = ''; TOKEN = '';
  } finally {
    btn.disabled = false; btn.textContent = 'Connect';
  }
}

function logout() {
  localStorage.removeItem('painite_api');
  localStorage.removeItem('painite_token');
  API = ''; TOKEN = '';
  $('app').classList.add('hidden');
  $('login-screen').classList.remove('hidden');
}
$('logout-btn').addEventListener('click', logout);

/* ---------- NAVIGATION ---------- */
document.querySelectorAll('.nav-item').forEach((b) => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach((x) => x.classList.remove('active'));
    document.querySelectorAll('.page').forEach((x) => x.classList.remove('active'));
    b.classList.add('active');
    $('page-' + b.dataset.page).classList.add('active');
  });
});

/* ---------- LOADERS ---------- */
$('refresh-btn').addEventListener('click', () => { loadAll(); toast('Refreshed', 'success'); });

async function loadAll() {
  loadStats();
  loadNumbers();
  loadUsers();
  loadSmsLog();
  loadBotStatus();
  loadSettings();
}

/* ---------- BOT ON/OFF ---------- */
function renderBotState(active) {
  const t1 = $('bot-toggle'), t2 = $('bot-toggle-2');
  const s1 = $('bot-state'), s2 = $('bot-state-2');
  if (t1) t1.checked = active;
  if (t2) t2.checked = active;
  const label = active ? 'ON' : 'OFF';
  const cls = 'bot-state ' + (active ? 'on' : 'off');
  if (s1) { s1.textContent = label; s1.className = cls; }
  if (s2) { s2.textContent = label; s2.className = cls; }
}

async function loadBotStatus() {
  try {
    const r = await api('/admin/bot-status');
    renderBotState(!!r.active);
  } catch (e) { /* ignore */ }
}

async function setBotStatus(active) {
  try {
    await api('/admin/bot-status', { method: 'POST', body: JSON.stringify({ active }) });
    renderBotState(active);
    toast('Bot turned ' + (active ? 'ON' : 'OFF'), active ? 'success' : 'error');
  } catch (e) {
    toast(e.message, 'error');
    loadBotStatus();
  }
}

['bot-toggle', 'bot-toggle-2'].forEach((id) => {
  const el = $(id);
  if (el) el.addEventListener('change', (e) => setBotStatus(e.target.checked));
});

/* ---------- SETTINGS PASSWORD TOGGLES ---------- */
document.querySelectorAll('.pw-toggle[data-target]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const inp = $(btn.dataset.target);
    if (!inp) return;
    if (inp.type === 'password') { inp.type = 'text'; btn.textContent = '🙈'; }
    else { inp.type = 'password'; btn.textContent = '👁'; }
  });
});

/* ---------- SETTINGS / PANEL CONFIG ---------- */
function applyModeView(mode) {
  const isApi = mode === 'api';
  const gApi = $('group-api'), gScrape = $('group-scrape');
  if (gApi) gApi.style.display = isApi ? 'block' : 'none';
  if (gScrape) gScrape.style.display = isApi ? 'none' : 'block';
}

async function loadSettings() {
  try {
    const s = await api('/admin/settings');
    $('set-mode').value = s.mode || 'scrape';
    $('set-api-url').value = s.api_url || '';
    $('set-api-key').value = s.api_key || '';
    $('set-site-url').value = s.site_url || '';
    $('set-login-url').value = s.login_url || '';
    $('set-sms-url').value = s.sms_url || '';
    $('set-email').value = s.email || '';
    $('set-password').value = s.password || '';
    applyModeView($('set-mode').value);
  } catch (e) { /* ignore */ }
}

const modeSel = $('set-mode');
if (modeSel) modeSel.addEventListener('change', (e) => applyModeView(e.target.value));

const saveSettingsBtn = $('save-settings-btn');
if (saveSettingsBtn) saveSettingsBtn.addEventListener('click', async () => {
  const payload = {
    mode: $('set-mode').value,
    api_url: $('set-api-url').value.trim(),
    api_key: $('set-api-key').value.trim(),
    site_url: $('set-site-url').value.trim(),
    login_url: $('set-login-url').value.trim(),
    sms_url: $('set-sms-url').value.trim(),
    email: $('set-email').value.trim(),
    password: $('set-password').value
  };
  const btn = $('save-settings-btn');
  btn.disabled = true; btn.textContent = 'Saving...';
  try {
    await api('/admin/settings', { method: 'POST', body: JSON.stringify(payload) });
    $('settings-result').textContent = '✓ Settings saved';
    toast('Settings saved', 'success');
  } catch (e) {
    $('settings-result').textContent = '';
    toast(e.message, 'error');
  } finally {
    btn.disabled = false; btn.textContent = '💾 Save';
  }
});

const testPanelBtn = $('test-panel-btn');
if (testPanelBtn) testPanelBtn.addEventListener('click', async () => {
  const btn = $('test-panel-btn');
  btn.disabled = true; btn.textContent = 'Testing...';
  $('settings-result').textContent = '';
  try {
    const r = await api('/admin/panel/test', { method: 'POST' });
    if (r.ok) {
      $('settings-result').textContent = '✓ Connection OK' + (r.status ? ' (status ' + r.status + ')' : '');
      toast('Panel connection OK', 'success');
    } else {
      $('settings-result').textContent = '✗ Failed: ' + (r.error || ('status ' + (r.status || '?')));
      toast('Panel test failed', 'error');
    }
  } catch (e) {
    $('settings-result').textContent = '✗ ' + e.message;
    toast(e.message, 'error');
  } finally {
    btn.disabled = false; btn.textContent = '🔌 Test Connection';
  }
});

async function loadStats() {
  try {
    const s = await api('/admin/stats');
    $('stat-users').textContent = s.users ?? 0;
    $('stat-numbers').textContent = s.numbers ?? 0;
    $('stat-sms').textContent = s.sms_sent ?? 0;
  } catch (e) { toast(e.message, 'error'); }
}

async function loadNumbers() {
  try {
    const res = await api('/admin/panel/ranges');
    const list = (res && res.countries) || [];
    const body = $('numbers-body');
    body.innerHTML = '';
    $('numbers-empty').classList.toggle('hidden', list.length > 0);
    const statEl = $('stat-numbers');
    if (statEl) statEl.textContent = list.length;
    list.forEach((c) => {
      const tr = document.createElement('tr');
      const flag = c.flag || '🌍';
      const country = c.country || '—';
      const ranges = (c.ranges || []).join(', ');
      tr.innerHTML =
        '<td>' + flag + ' ' + escapeHtml(country) + '</td>' +
        '<td><span class="mono">' + escapeHtml(ranges) + '</span></td>' +
        '<td>' + ((c.ranges || []).length) + '</td>';
      body.appendChild(tr);
    });
  } catch (e) { toast(e.message, 'error'); }
}

async function loadUsers() {
  try {
    const list = await api('/admin/users');
    const body = $('users-body');
    body.innerHTML = '';
    $('users-empty').classList.toggle('hidden', list.length > 0);
    list.forEach((u) => {
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + escapeHtml(u.user_id) + '</td>' +
        '<td>' + (u.username ? '@' + escapeHtml(u.username) : '—') + '</td>' +
        '<td>' + escapeHtml(u.first_name || '—') + '</td>' +
        '<td>' + fmtDate(u.created_at) + '</td>';
      body.appendChild(tr);
    });
  } catch (e) { toast(e.message, 'error'); }
}

async function loadSmsLog() {
  try {
    const list = await api('/admin/sms-log');
    const body = $('smslog-body');
    body.innerHTML = '';
    $('smslog-empty').classList.toggle('hidden', list.length > 0);
    list.forEach((s) => {
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + escapeHtml(s.phone || '—') + '</td>' +
        '<td>' + escapeHtml(s.country || '—') + '</td>' +
        '<td><span class="otp-chip">' + escapeHtml(s.otp || '—') + '</span></td>' +
        '<td>' + escapeHtml((s.message || '').slice(0, 60)) + '</td>' +
        '<td>' + fmtDate(s.created_at) + '</td>';
      body.appendChild(tr);
    });

    // Dashboard recent
    const recent = $('dash-recent');
    recent.innerHTML = '';
    if (!list.length) { recent.innerHTML = '<div class="empty">No activity yet</div>'; }
    list.slice(0, 6).forEach((s) => {
      const row = document.createElement('div');
      row.className = 'mini-row';
      row.innerHTML =
        '<span>' + escapeHtml(s.phone || '—') + ' · ' + escapeHtml(s.country || '') + '</span>' +
        '<span class="otp-chip">' + escapeHtml(s.otp || '—') + '</span>';
      recent.appendChild(row);
    });
  } catch (e) { toast(e.message, 'error'); }
}

/* ---------- ACTIONS ---------- */
const rangesRefreshBtn = $('ranges-refresh');
if (rangesRefreshBtn) {
  rangesRefreshBtn.addEventListener('click', async () => {
    rangesRefreshBtn.disabled = true;
    const old = rangesRefreshBtn.textContent;
    rangesRefreshBtn.textContent = 'Loading...';
    try { await loadNumbers(); toast('Ranges refreshed', 'success'); }
    catch (e) { toast(e.message, 'error'); }
    finally { rangesRefreshBtn.disabled = false; rangesRefreshBtn.textContent = old; }
  });
}

$('broadcast-btn').addEventListener('click', async () => {
  const message = $('broadcast-msg').value.trim();
  if (!message) { toast('Type a message first', 'error'); return; }
  const btn = $('broadcast-btn');
  btn.disabled = true; btn.textContent = 'Sending...';
  try {
    const r = await api('/admin/broadcast', { method: 'POST', body: JSON.stringify({ message }) });
    const sent = r.sent ?? r.success ?? '?';
    $('broadcast-result').textContent = '✓ Sent to ' + sent + ' users';
    $('broadcast-msg').value = '';
    toast('Broadcast sent', 'success');
  } catch (e) {
    $('broadcast-result').textContent = '';
    toast(e.message, 'error');
  } finally {
    btn.disabled = false; btn.textContent = '📢 Send Broadcast';
  }
});

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/* ---------- AUTO LOGIN ---------- */
(function init() {
  const savedApi = localStorage.getItem('painite_api');
  const savedToken = localStorage.getItem('painite_token');
  if (savedApi && savedToken) {
    $('api-url').value = savedApi;
    $('admin-token').value = savedToken;
    API = savedApi; TOKEN = savedToken;
    api('/admin/stats').then(() => {
      $('login-screen').classList.add('hidden');
      $('app').classList.remove('hidden');
      loadAll();
    }).catch(() => { API = ''; TOKEN = ''; });
  }
})();
