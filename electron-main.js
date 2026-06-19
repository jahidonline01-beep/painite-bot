const { app, BrowserWindow, Menu, MenuItem } = require('electron');
const path = require('path');

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
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  Menu.setApplicationMenu(null);
  attachContextMenu(win);
  win.loadFile('index.html');
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
