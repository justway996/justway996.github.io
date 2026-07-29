import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { resolveEffectiveSkills, scanSkills } from '../../src/main/skill-scanner';

const tempDirectories: string[] = [];

async function createTempDirectory(): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), 'codex-skill-scanner-'));
  tempDirectories.push(directory);
  return directory;
}

async function writeSkill(root: string, relativePath: string, content: string): Promise<void> {
  const path = join(root, relativePath);
  await mkdir(join(path, '..'), { recursive: true });
  await writeFile(path, content, 'utf8');
}

afterEach(async () => {
  await Promise.all(tempDirectories.splice(0).map((directory) => rm(directory, { force: true, recursive: true })));
});

describe('local Codex skill scanner', () => {
  it('returns no records when configured roots do not exist', async () => {
    const tempDir = await createTempDirectory();

    await expect(scanSkills({
      globalRoot: join(tempDir, 'missing-global'),
      workspaceRoot: join(tempDir, 'missing-workspace'),
    })).resolves.toEqual([]);
  });

  it('reads skill metadata from a SKILL.md file', async () => {
    const tempDir = await createTempDirectory();
    await writeSkill(tempDir, '.codex/skills/ppt/SKILL.md', '---\nname: ppt\ndescription: Make slides\nversion: 1.2.0\n---\n');

    await expect(scanSkills({ globalRoot: tempDir })).resolves.toEqual([
      expect.objectContaining({
        id: 'ppt',
        name: 'ppt',
        description: 'Make slides',
        source: 'global',
        enabled: true,
        precedence: 1,
        version: '1.2.0',
      }),
    ]);
  });

  it('ignores SKILL.md files with malformed front matter', async () => {
    const tempDir = await createTempDirectory();
    await writeSkill(tempDir, '.codex/skills/broken/SKILL.md', 'name: broken\ndescription: No delimiters\n');

    await expect(scanSkills({ globalRoot: tempDir })).resolves.toEqual([]);
  });

  it('marks the higher-precedence workspace copy as effective', async () => {
    const tempDir = await createTempDirectory();
    await writeSkill(tempDir, '.codex/skills/ppt/SKILL.md', '---\nname: ppt\ndescription: Make slides\n---');
    await writeSkill(tempDir, 'workspace/.codex/skills/ppt/SKILL.md', '---\nname: ppt\ndescription: Local slides\n---');
    const records = await scanSkills({ globalRoot: tempDir, workspaceRoot: join(tempDir, 'workspace') });
    expect(resolveEffectiveSkills(records).find((item) => item.id === 'ppt')?.source).toBe('workspace');
  });
});
