import { homedir } from 'node:os';
import { join } from 'node:path';

export type ScanPaths = {
  globalRoot: string;
  workspaceRoot?: string;
  managedRoot?: string;
};

export type AppPathOptions = {
  homeDirectory?: string;
  workspaceRoot?: string;
  managedRoot?: string;
};

export function getScanPaths(options: AppPathOptions = {}): ScanPaths {
  const homeDirectory = options.homeDirectory ?? homedir();

  return {
    globalRoot: homeDirectory,
    workspaceRoot: options.workspaceRoot,
    managedRoot: options.managedRoot ?? join(homeDirectory, '.codex-skill-toolbox', 'managed-skills'),
  };
}
