import { copyFile, lstat, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, join, relative, resolve } from 'node:path';

type OperationKind = 'copy' | 'delete' | 'update';

export type MaintenanceOperation = {
  kind: OperationKind;
  path: string;
  sourcePath?: string;
};

export type BackupManifest = {
  manifestPath: string;
  entries: Array<{ path: string; backupPath?: string }>;
};

export type MaintenancePlan = {
  id: string;
  managedRoot: string;
  operations: MaintenanceOperation[];
  impact: string;
  risk: string;
  backup: BackupManifest;
  autoApplyEligible: boolean;
};

export type RepairOptions = { sourcePath: string; managedRoot: string; targetPath?: string };
export type DeleteOptions = { managedRoot: string; paths: string[] };
export type UpdateOptions = {
  managedRoot: string;
  patchPath: string;
  targetPath: string;
  trusted: boolean;
  compatible: boolean;
  permissionsUnchanged: boolean;
};

type StoredManifest = BackupManifest & { operations: MaintenanceOperation[] };

export async function planRepair(options: RepairOptions): Promise<MaintenancePlan> {
  const targetPath = options.targetPath ?? basename(resolve(options.sourcePath));
  const sourceFiles = await filesIn(options.sourcePath);
  const target = withinManagedRoot(options.managedRoot, targetPath);
  const operations = sourceFiles.map((sourcePath) => ({
    kind: 'copy' as const,
    path: relative(resolve(options.managedRoot), join(target, relative(resolve(options.sourcePath), sourcePath))),
    sourcePath,
  }));

  return createPlan(options.managedRoot, operations, 'Repair preview: create an isolated managed copy.', 'Copies only after confirmation; existing managed files are backed up.');
}

export async function planDelete(options: DeleteOptions): Promise<MaintenancePlan> {
  const operations: MaintenanceOperation[] = [];
  for (const path of options.paths) {
    const target = withinManagedRoot(options.managedRoot, path);
    for (const file of await filesIn(target)) {
      operations.push({ kind: 'delete', path: relative(resolve(options.managedRoot), file) });
    }
  }

  return createPlan(options.managedRoot, operations, 'Delete preview: remove the listed managed files.', 'Deletes only listed managed files after confirmation; every removed file is backed up.');
}

export async function planUpdate(options: UpdateOptions): Promise<MaintenancePlan> {
  const target = withinManagedRoot(options.managedRoot, options.targetPath);
  await lstat(options.patchPath);
  const eligible = options.trusted && options.compatible && options.permissionsUnchanged;
  const operation: MaintenanceOperation = {
    kind: 'update',
    path: relative(resolve(options.managedRoot), target),
    sourcePath: options.patchPath,
  };
  const plan = await createPlan(options.managedRoot, [operation], 'Update preview: replace one managed file with a supplied patch.', 'Updates require confirmation and preserve a backup of the managed file.');
  return { ...plan, autoApplyEligible: eligible };
}

export async function applyPlan(plan: MaintenancePlan, confirmed: boolean): Promise<void> {
  if (!confirmed) throw new Error('闇€瑕佺‘璁');
  if (plan.operations.some((operation) => operation.kind === 'update') && !plan.autoApplyEligible) {
    throw new Error('Update is not trusted, compatible, and permission-preserving.');
  }

  const manifest: StoredManifest = { ...plan.backup, entries: [], operations: plan.operations };
  await mkdir(resolve(plan.managedRoot), { recursive: true });
  await mkdir(resolve(plan.managedRoot, '.change-planner-backups', plan.id), { recursive: true });

  for (const [index, operation] of plan.operations.entries()) {
    const target = withinManagedRoot(plan.managedRoot, operation.path);
    const backupPath = join(resolve(plan.managedRoot, '.change-planner-backups', plan.id), `${index}.backup`);
    const exists = await pathExists(target);
    if (exists) {
      await mkdir(join(backupPath, '..'), { recursive: true });
      await copyFile(target, backupPath);
    }
    manifest.entries.push({ path: operation.path, ...(exists ? { backupPath } : {}) });

    if (operation.kind === 'delete') {
      if (exists) await rm(target);
    } else {
      if (!operation.sourcePath) throw new Error('Copy operation is missing a source path.');
      await mkdir(join(target, '..'), { recursive: true });
      await copyFile(operation.sourcePath, target);
    }
  }

  await writeFile(plan.backup.manifestPath, JSON.stringify(manifest, null, 2), 'utf8');
}

export async function restorePlan(plan: MaintenancePlan): Promise<void> {
  const manifest = JSON.parse(await readFile(plan.backup.manifestPath, 'utf8')) as StoredManifest;
  for (const entry of manifest.entries) {
    const target = withinManagedRoot(plan.managedRoot, entry.path);
    if (entry.backupPath) {
      await mkdir(join(target, '..'), { recursive: true });
      await copyFile(entry.backupPath, target);
    } else {
      await rm(target, { force: true });
    }
  }
}

async function createPlan(managedRoot: string, operations: MaintenanceOperation[], impact: string, risk: string): Promise<MaintenancePlan> {
  const id = `plan-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const root = resolve(managedRoot);
  const backup: BackupManifest = {
    manifestPath: join(root, '.change-planner-backups', id, 'manifest.json'),
    entries: operations.map((operation) => ({ path: operation.path })),
  };
  return { id, managedRoot: root, operations, impact, risk, backup, autoApplyEligible: false };
}

async function filesIn(path: string): Promise<string[]> {
  const entry = await lstat(path);
  if (entry.isFile()) return [resolve(path)];
  if (!entry.isDirectory()) throw new Error('Only regular files and directories can be planned.');

  const files: string[] = [];
  for (const child of await readdir(path, { withFileTypes: true })) {
    const childPath = join(path, child.name);
    if (child.isDirectory()) files.push(...await filesIn(childPath));
    else if (child.isFile()) files.push(resolve(childPath));
    else throw new Error('Links and special files cannot be planned.');
  }
  return files;
}

function withinManagedRoot(managedRoot: string, path: string): string {
  const root = resolve(managedRoot);
  const target = resolve(root, path);
  if (target === root || relative(root, target).startsWith('..')) throw new Error('Path must stay inside the supplied managed root.');
  return target;
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await lstat(path);
    return true;
  } catch {
    return false;
  }
}
