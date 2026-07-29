import { readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import type { SkillRecord } from '../shared/models.js';
import type { ScanPaths } from './app-paths.js';

export type { ScanPaths } from './app-paths.js';

const sourcePrecedence = {
  global: 1,
  plugin: 2,
  managed: 3,
  workspace: 4,
} as const;

type SkillSource = SkillRecord['source'];

export async function scanSkills(paths: ScanPaths): Promise<SkillRecord[]> {
  const roots: Array<{ path?: string; source: SkillSource }> = [
    { path: join(paths.globalRoot, '.codex', 'skills'), source: 'global' },
    { path: join(paths.globalRoot, '.codex', 'plugins'), source: 'plugin' },
    { path: paths.managedRoot, source: 'managed' },
    { path: paths.workspaceRoot && join(paths.workspaceRoot, '.codex', 'skills'), source: 'workspace' },
  ];

  const records = await Promise.all(roots.map(async ({ path, source }) => {
    if (!path) return [];
    return scanRoot(path, source);
  }));

  return records.flat();
}

export function resolveEffectiveSkills(records: SkillRecord[]): SkillRecord[] {
  const effective = new Map<string, SkillRecord>();

  for (const record of records) {
    const current = effective.get(record.id);
    if (!current || record.precedence > current.precedence) {
      effective.set(record.id, record);
    }
  }

  return [...effective.values()];
}

async function scanRoot(root: string, source: SkillSource): Promise<SkillRecord[]> {
  const files = await findSkillFiles(root);
  const records = await Promise.all(files.map(async (path) => parseSkillFile(path, source)));
  return records.filter((record): record is SkillRecord => record !== null);
}

async function findSkillFiles(directory: string): Promise<string[]> {
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch {
    return [];
  }

  const nested = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory() && !entry.isSymbolicLink()) return findSkillFiles(path);
    return entry.isFile() && entry.name === 'SKILL.md' ? [path] : [];
  }));

  return nested.flat();
}

async function parseSkillFile(path: string, source: SkillSource): Promise<SkillRecord | null> {
  let content: string;
  try {
    content = await readFile(path, 'utf8');
  } catch {
    return null;
  }

  const metadata = parseFrontMatter(content);
  if (!metadata?.name || !metadata.description) return null;

  return {
    id: metadata.name.trim().toLowerCase().replace(/\s+/g, '-'),
    name: metadata.name,
    description: metadata.description,
    path,
    source,
    enabled: true,
    precedence: sourcePrecedence[source],
    ...(metadata.version ? { version: metadata.version } : {}),
  };
}

function parseFrontMatter(content: string): Record<string, string> | null {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  if (!match) return null;

  const metadata: Record<string, string> = {};
  for (const line of match[1].split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;

    const field = line.match(/^([A-Za-z][A-Za-z0-9_-]*):[ \t]+(.+)$/);
    if (!field) return null;

    const value = parseScalar(field[2]);
    if (value === null || metadata[field[1]]) return null;
    metadata[field[1]] = value;
  }

  return metadata;
}

function parseScalar(value: string): string | null {
  if (value.startsWith('"')) {
    try {
      const parsed: unknown = JSON.parse(value);
      return typeof parsed === 'string' ? parsed : null;
    } catch {
      return null;
    }
  }

  if (value.startsWith("'")) {
    if (!value.endsWith("'") || value.length < 2) return null;
    return value.slice(1, -1).replace(/''/g, "'");
  }

  return /^[^\[\]{}&,*!|>@`]+$/.test(value) ? value : null;
}
