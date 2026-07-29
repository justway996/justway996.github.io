import { describe, expect, it } from 'vitest';
import { registerToolboxHandlers } from '../../src/main/ipc';

describe('secure toolbox IPC bridge', () => {
  it('registers only the fixed toolbox channels and never a shell channel', () => {
    const channels: string[] = [];

    registerToolboxHandlers({
      ipcMain: { handle: (channel) => { channels.push(channel); } },
      dialog: {
        showOpenDialog: async () => ({ canceled: true, filePaths: [] }),
      },
      getAppDataPath: () => 'C:\\app-data',
      getScanPaths: () => ({ globalRoot: 'C:\\home' }),
    });

    expect(channels).toEqual([
      'toolbox:scan',
      'toolbox:search',
      'toolbox:list-workflows',
      'toolbox:import-package',
      'toolbox:export-workflow',
      'toolbox:preview-plan',
      'toolbox:apply-plan',
    ]);
    expect(channels).toContain('toolbox:scan');
    expect(channels).toContain('toolbox:search');
    expect(channels).toContain('toolbox:preview-plan');
    expect(channels).not.toContain('shell:exec');
  });
});
