import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { applyPlan, planDelete, planRepair, planUpdate, restorePlan } from '../../src/main/change-planner';

const temporaryDirectories: string[] = [];

async function createTemporaryDirectory(): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), 'codex-change-planner-'));
  temporaryDirectories.push(directory);
  return directory;
}

afterEach(async () => {
  await Promise.all(temporaryDirectories.splice(0).map((directory) => rm(directory, { force: true, recursive: true })));
});

describe('reversible maintenance plans', () => {
  it('creates a repair preview without writing files', async () => {
    const root = await createTemporaryDirectory();
    const source = join(root, 'source-skill');
    const managedRoot = join(root, 'managed');
    await mkdir(source);
    await writeFile(join(source, 'SKILL.md'), '---\nname: source\n---\n', 'utf8');

    const plan = await planRepair({ sourcePath: source, managedRoot });

    expect(plan.operations).toHaveLength(1);
    await expect(mkdir(managedRoot)).resolves.toBeUndefined();
  });

  it('requires confirmation before applying a delete plan', async () => {
    const root = await createTemporaryDirectory();
    const managedRoot = join(root, 'managed');
    await mkdir(join(managedRoot, 'obsolete'), { recursive: true });
    await writeFile(join(managedRoot, 'obsolete', 'SKILL.md'), 'old', 'utf8');

    const plan = await planDelete({ managedRoot, paths: ['obsolete'] });

    await expect(applyPlan(plan, false)).rejects.toThrow('闇€瑕佺‘璁');
  });

  it('deletes only the exact managed files named in its preview and restores them from its manifest', async () => {
    const root = await createTemporaryDirectory();
    const managedRoot = join(root, 'managed');
    const unmanagedPath = join(root, 'unmanaged.txt');
    await mkdir(join(managedRoot, 'obsolete'), { recursive: true });
    await writeFile(join(managedRoot, 'obsolete', 'SKILL.md'), 'old', 'utf8');
    await writeFile(unmanagedPath, 'keep', 'utf8');

    const plan = await planDelete({ managedRoot, paths: ['obsolete'] });

    expect(plan.operations).toEqual([{ kind: 'delete', path: join('obsolete', 'SKILL.md') }]);
    expect(plan.impact).not.toBe('');
    expect(plan.risk).not.toBe('');
    expect(plan.backup.manifestPath).toContain('.change-planner-backups');
    await applyPlan(plan, true);
    await expect(readFile(join(managedRoot, 'obsolete', 'SKILL.md'), 'utf8')).rejects.toThrow();
    await expect(readFile(unmanagedPath, 'utf8')).resolves.toBe('keep');

    await restorePlan(plan);
    await expect(readFile(join(managedRoot, 'obsolete', 'SKILL.md'), 'utf8')).resolves.toBe('old');
  });

  it('creates an isolated managed repair copy only after confirmation and can remove it on restore', async () => {
    const root = await createTemporaryDirectory();
    const source = join(root, 'source-skill');
    const managedRoot = join(root, 'managed');
    await mkdir(source);
    await writeFile(join(source, 'SKILL.md'), 'new', 'utf8');

    const plan = await planRepair({ sourcePath: source, managedRoot });
    await applyPlan(plan, true);

    await expect(readFile(join(managedRoot, 'source-skill', 'SKILL.md'), 'utf8')).resolves.toBe('new');
    await restorePlan(plan);
    await expect(readFile(join(managedRoot, 'source-skill', 'SKILL.md'), 'utf8')).rejects.toThrow();
  });

  it('marks only trusted compatible permission-preserving patch updates as auto-apply eligible', async () => {
    const root = await createTemporaryDirectory();
    const managedRoot = join(root, 'managed');
    const patchPath = join(root, 'patch.md');
    await mkdir(managedRoot);
    await writeFile(join(managedRoot, 'SKILL.md'), 'old', 'utf8');
    await writeFile(patchPath, 'new', 'utf8');

    const unsafe = await planUpdate({ managedRoot, patchPath, targetPath: 'SKILL.md', trusted: false, compatible: true, permissionsUnchanged: true });
    const safe = await planUpdate({ managedRoot, patchPath, targetPath: 'SKILL.md', trusted: true, compatible: true, permissionsUnchanged: true });

    expect(unsafe.autoApplyEligible).toBe(false);
    await expect(applyPlan(unsafe, true)).rejects.toThrow('not trusted');
    expect(safe.autoApplyEligible).toBe(true);
    await applyPlan(safe, true);
    await expect(readFile(join(managedRoot, 'SKILL.md'), 'utf8')).resolves.toBe('new');
  });
});
