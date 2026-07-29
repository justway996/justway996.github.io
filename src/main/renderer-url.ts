import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

export function getRendererUrl(
  isPackaged: boolean,
  currentDirectory: string,
  devServerUrl = process.env.VITE_DEV_SERVER_URL,
): string {
  if (!isPackaged) {
    return devServerUrl ?? 'http://127.0.0.1:5173';
  }

  return pathToFileURL(join(currentDirectory, '../renderer/index.html')).toString();
}
