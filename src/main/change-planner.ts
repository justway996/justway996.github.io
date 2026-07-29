import { copyFile, lstat, mkdir, readdir, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { basename, dirname, join, relative, resolve } from 'node:path';

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

type ManagedContext = { root: string; realRoot: string };

export async function planRepair(options: RepairOptions): Promise<MaintenancePlan> {
  const targetPath = options.targetPath ?? basename(resolve(options.sourcePath));
  const sourceFiles = await filesIn(options.sourcePath);
  const target = withinManagedRoot(options.managedRoot, targetPath);
  if (await pathExists(target)) throw new Error('Repair target already exists.');
  const operations = sourceFiles.map((sourcePath) => ({
    kind: 'copy' as const,
    path: relative(resolve(options.managedRoot), join(target, relative(resolve(options.sourcePath), sourcePath))),
    sourcePath,
  }));

  return createPlan(options.managedRoot, operations, 'Repair preview: create an isolated managed copy.', 'Copies only after confirmation; existing managed files are backed up.');
}

export async function planDelete(options: DeleteOptions): Promise<MaintenancePlan> {
  const operations: MaintenanceOperation[] = [];
  const plannedPaths = new Set<string>();
  for (const path of options.paths) {
    const target = withinManagedRoot(options.managedRoot, path);
    for (const file of await filesIn(target)) {
      const plannedPath = relative(resolve(options.managedRoot), file);
      if (!plannedPaths.has(plannedPath.toLowerCase())) {
        plannedPaths.add(plannedPath.toLowerCase());
        operations.push({ kind: 'delete', path: plannedPath });
      }
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

  const context = await managedContext(plan.managedRoot);
  const backupDirectory = await ensureManagedDirectory(context, join('.change-planner-backups', plan.id));
  const manifestPath = backupManifestPath(context, plan, backupDirectory);
  const manifest: StoredManifest = { ...plan.backup, manifestPath, entries: [], operations: plan.operations };
  await writeManifest(manifestPath, manifest);

  for (const [index, operation] of plan.operations.entries()) {
    const target = await safeManagedPath(context, operation.path);
    const backupPath = await safeManagedPath(context, join('.change-planner-backups', plan.id, `${index}.backup`));
    const exists = await pathExists(target);
    if (exists) {
      await ensureManagedDirectory(context, join('.change-planner-backups', plan.id));
      await copyFile(target, backupPath);
    }
    manifest.entries.push({ path: operation.path, ...(exists ? { backupPath } : {}) });
    await writeManifest(manifestPath, manifest);

    if (operation.kind === 'delete') {
      if (exists) await rm(target);
    } else {
      if (!operation.sourcePath) throw new Error('Copy operation is missing a source path.');
      await ensureManagedDirectory(context, relative(context.root, dirname(target)));
      await safeManagedPath(context, operation.path);
      await copyFile(operation.sourcePath, target);
    }
  }

  await writeManifest(manifestPath, manifest);
}

export async function restorePlan(plan: MaintenancePlan): Promise<void> {
  const context = await managedContext(plan.managedRoot);
  const backupDirectory = await ensureManagedDirectory(context, join('.change-planner-backups', plan.id));
  const manifestPath = backupManifestPath(context, plan, backupDirectory);
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8')) as StoredManifest;
  for (const entry of manifest.entries) {
    const target = await safeManagedPath(context, entry.path);
    if (entry.backupPath) {
      const backupPath = await safeManagedPath(context, relative(context.root, entry.backupPath));
      await ensureManagedDirectory(context, relative(context.root, dirname(target)));
      await safeManagedPath(context, entry.path);
      await copyFile(backupPath, target);
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

async function managedContext(managedRoot: string): Promise<ManagedContext> {
  const root = resolve(managedRoot);
  await assertNoReparsePoint(root);
  await mkdir(root, { recursive: true });
  await assertNoReparsePoint(root);
  const entry = await lstat(root);
  if (!entry.isDirectory() || entry.isSymbolicLink()) throw new Error('Managed root cannot be a reparse point.');
  return { root, realRoot: await realpath(root) };
}

async function safeManagedPath(context: ManagedContext, path: string): Promise<string> {
  const target = withinManagedRoot(context.root, path);
  await assertNoReparsePoint(target);
  const existing = await nearestExistingPath(target);
  const realExisting = await realpath(existing);
  if (realExisting !== context.realRoot && !realExisting.startsWith(`${context.realRoot}\\`) && !realExisting.startsWith(`${context.realRoot}/`)) {
    throw new Error('Managed path crosses a reparse point.');
  }
  return target;
}

async function ensureManagedDirectory(context: ManagedContext, path: string): Promise<string> {
  const directory = resolve(context.root, path);
  if (directory !== context.root && relative(context.root, directory).startsWith('..')) throw new Error('Path must stay inside the supplied managed root.');
  const segments = relative(context.root, directory).split(/[\\/]/).filter(Boolean);
  let current = context.root;
  for (const segment of segments) {
    current = join(current, segment);
    await assertNoReparsePoint(current);
    if (await pathExists(current)) {
      const entry = await lstat(current);
      if (!entry.isDirectory() || entry.isSymbolicLink()) throw new Error('Managed path crosses a reparse point.');
    } else {
      await mkdir(current);
    }
  }
  await safeManagedPath(context, relative(context.root, directory) || '.change-planner-root');
  return directory;
}

function backupManifestPath(context: ManagedContext, plan: MaintenancePlan, backupDirectory: string): string {
  const expected = join(backupDirectory, 'manifest.json');
  if (resolve(plan.backup.manifestPath) !== expected) throw new Error('Backup manifest path is invalid.');
  return expected;
}

async function writeManifest(path: string, manifest: StoredManifest): Promise<void> {
  await writeFile(path, JSON.stringify(manifest, null, 2), 'utf8');
}

async function assertNoReparsePoint(path: string): Promise<void> {
  let current = resolve(path);
  while (true) {
    try {
      const entry = await lstat(current);
      if (entry.isSymbolicLink()) throw new Error('Managed path crosses a reparse point.');
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    }
    const parent = dirname(current);
    if (parent === current) return;
    current = parent;
  }
}

async function nearestExistingPath(path: string): Promise<string> {
  let current = resolve(path);
  while (!(await pathExists(current))) {
    const parent = dirname(current);
    if (parent === current) throw new Error('Managed root does not exist.');
    current = parent;
  }
  return current;
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await lstat(path);
    return true;
  } catch {
    return false;
  }
}
