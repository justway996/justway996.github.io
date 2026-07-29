import { app, BrowserWindow, dialog, ipcMain } from 'electron';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { getScanPaths } from './app-paths.js';
import { registerToolboxHandlers } from './ipc.js';
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
      preload: join(currentDirectory, '../preload/index.js'),
    },
  });

  void window.loadURL(getRendererUrl(app.isPackaged, currentDirectory));
}

if (process.versions.electron) {
  app.whenReady().then(() => {
    registerToolboxHandlers({
      ipcMain,
      dialog,
      getAppDataPath: () => app.getPath('userData'),
      getScanPaths,
    });
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
