const { app, BrowserWindow, Menu, MenuItem } = require('electron');
const path = require('path');
const http = require('http');

const LOCAL_PORT = process.env.PORT || 3889;

// Start embedded local backend server for offline and standalone execution
function initLocalServer() {
  try {
    process.env.PORT = String(LOCAL_PORT);
    require('./server.js');
    console.log(`[Painite Electron] Embedded server initialized on port ${LOCAL_PORT}`);
  } catch (err) {
    console.warn('[Painite Electron] Local server init notice:', err.message);
  }
}

function attachContextMenu(win) {
  win.webContents.on('context-menu', (event, params) => {
    const menu = new Menu();
    if (params.isEditable) {
      menu.append(new MenuItem({ role: 'cut', enabled: params.editFlags.canCut }));
      menu.append(new MenuItem({ role: 'copy', enabled: params.editFlags.canCopy }));
      menu.append(new MenuItem({ role: 'paste', enabled: params.editFlags.canPaste }));
      menu.append(new MenuItem({ type: 'separator' }));
      menu.append(new MenuItem({ role: 'selectAll' }));
      menu.popup();
    } else if (params.selectionText) {
      menu.append(new MenuItem({ role: 'copy' }));
      menu.popup();
    }
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 360,
    minHeight: 480,
    resizable: true,
    maximizable: true,
    minimizable: true,
    fullscreenable: true,
    backgroundColor: '#0a0a0f',
    title: 'Painite Admin',
    icon: path.join(__dirname, 'icon.png'),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: false,
      nodeIntegration: true,
      webSecurity: false,
      allowRunningInsecureContent: true
    }
  });

  Menu.setApplicationMenu(null);
  attachContextMenu(win);

  // Allow F5 and Ctrl+R to reload the window
  win.webContents.on('before-input-event', (event, input) => {
    if ((input.control || input.meta) && input.key.toLowerCase() === 'r') {
      win.reload();
      event.preventDefault();
    }
    if (input.key === 'F5') {
      win.reload();
      event.preventDefault();
    }
    if (input.key === 'F12' || ((input.control || input.meta) && input.shift && input.key.toLowerCase() === 'i')) {
      win.webContents.toggleDevTools();
      event.preventDefault();
    }
  });

  // Try loading local server URL first, fallback to index.html
  const localUrl = `http://127.0.0.1:${LOCAL_PORT}`;
  
  function checkAndLoad() {
    const req = http.get(localUrl + '/health', (res) => {
      if (res.statusCode === 200) {
        win.loadURL(localUrl);
      } else {
        win.loadFile('index.html');
      }
    });
    req.on('error', () => {
      win.loadFile('index.html');
    });
    req.setTimeout(1200, () => {
      req.destroy();
      win.loadFile('index.html');
    });
  }

  // Brief delay to allow express to bind port
  setTimeout(checkAndLoad, 300);
}

app.whenReady().then(() => {
  initLocalServer();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

