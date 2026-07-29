import { app, BrowserWindow } from 'electron';
import { fileURLToPath } from 'node:url';
import { getRendererUrl } from './renderer-url.js';

const currentDirectory = fileURLToPath(new URL('.', import.meta.url));

function createWindow(): void {
  const window = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 960,
    minHeight: 640,
    title: 'Codex Skill Toolbox',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  void window.loadURL(getRendererUrl(app.isPackaged, currentDirectory));
}

if (process.versions.electron) {
  app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
      }
    });
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      app.quit();
    }
  });
}
