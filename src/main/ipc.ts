import { isAbsolute } from 'node:path';
import type { ScanPaths } from './app-paths.js';
import { applyPlan, planDelete, planRepair, planUpdate, type MaintenancePlan } from './change-planner.js';
import { recommendWorkflows } from './recommendations.js';
import { scanSkills } from './skill-scanner.js';
import { exportWorkflow, importWorkflow } from './workflow-package.js';
import { catalog } from '../shared/catalog.js';
import type { PlanPreviewRequest } from '../shared/models.js';

type OpenDialogResult = { canceled: boolean; filePaths: string[] };

export type ToolboxIpcDependencies = {
  ipcMain: { handle(channel: string, listener: (...args: unknown[]) => unknown): void };
  dialog: { showOpenDialog(options: Record<string, unknown>): Promise<OpenDialogResult> };
  getAppDataPath(): string;
  getScanPaths(): ScanPaths;
};

export function registerToolboxHandlers(dependencies: ToolboxIpcDependencies): void {
  const plans = new Map<string, MaintenancePlan>();
  const { ipcMain: handlers } = dependencies;

  handlers.handle('toolbox:scan', async () => scanSkills(dependencies.getScanPaths()));
  handlers.handle('toolbox:search', async (_event, query: unknown) => {
    const skills = await scanSkills(dependencies.getScanPaths());
    return recommendWorkflows(typeof query === 'string' ? query : '', catalog, skills);
  });
  handlers.handle('toolbox:list-workflows', () => catalog);
  handlers.handle('toolbox:import-package', async () => {
    const selection = await dependencies.dialog.showOpenDialog({
      title: 'Import workflow package',
      properties: ['openFile'],
      filters: [{ name: 'Workflow packages', extensions: ['workflow.zip', 'zip'] }],
    });
    const packagePath = selection.filePaths[0];
    if (selection.canceled || !packagePath) return undefined;
    if (!isWorkflowPackagePath(packagePath)) throw new Error('Select a .workflow.zip package.');
    return importWorkflow(packagePath, dependencies.getAppDataPath());
  });
  handlers.handle('toolbox:export-workflow', async (_event, workflowId: unknown) => {
    const workflow = catalog.find((item) => item.id === workflowId);
    if (!workflow) throw new Error('Unknown workflow.');
    const selection = await dependencies.dialog.showOpenDialog({
      title: 'Choose workflow export folder',
      properties: ['openDirectory', 'createDirectory'],
    });
    const exportDirectory = selection.filePaths[0];
    if (selection.canceled || !exportDirectory) return undefined;
    if (!isAbsolute(exportDirectory)) throw new Error('Export directory must be absolute.');
    return exportWorkflow(workflow, exportDirectory);
  });
  handlers.handle('toolbox:preview-plan', async (_event, request: unknown) => {
    const plan = await createPlan(request, dependencies);
    if (plan) plans.set(plan.id, plan);
    return plan;
  });
  handlers.handle('toolbox:apply-plan', async (_event, planId: unknown, confirmed: unknown) => {
    if (typeof planId !== 'string') throw new Error('Unknown change plan.');
    const plan = plans.get(planId);
    if (!plan) throw new Error('Unknown change plan.');
    await applyPlan(plan, confirmed === true);
    plans.delete(planId);
  });
}

async function createPlan(request: unknown, dependencies: ToolboxIpcDependencies): Promise<MaintenancePlan | undefined> {
  if (!isPlanPreviewRequest(request)) throw new Error('Invalid change-plan request.');
  const managedRoot = dependencies.getScanPaths().managedRoot;
  if (!managedRoot) throw new Error('Managed storage is unavailable.');

  if (request.kind === 'delete') return planDelete({ managedRoot, paths: request.paths });
  if (request.kind === 'repair') {
    const selection = await dependencies.dialog.showOpenDialog({ title: 'Choose skill folder to repair', properties: ['openDirectory'] });
    const sourcePath = selection.filePaths[0];
    if (selection.canceled || !sourcePath) return undefined;
    if (!isAbsolute(sourcePath)) throw new Error('Selected skill folder must be absolute.');
    return planRepair({ managedRoot, sourcePath });
  }

  const selection = await dependencies.dialog.showOpenDialog({ title: 'Choose update patch', properties: ['openFile'] });
  const patchPath = selection.filePaths[0];
  if (selection.canceled || !patchPath) return undefined;
  if (!isAbsolute(patchPath)) throw new Error('Selected update patch must be absolute.');
  return planUpdate({ managedRoot, patchPath, ...request });
}

function isWorkflowPackagePath(path: string): boolean {
  return isAbsolute(path) && path.toLowerCase().endsWith('.workflow.zip');
}

function isPlanPreviewRequest(value: unknown): value is PlanPreviewRequest {
  if (value === null || typeof value !== 'object' || !('kind' in value)) return false;
  const request = value as Record<string, unknown>;
  if (request.kind === 'repair') return true;
  if (request.kind === 'delete') return Array.isArray(request.paths) && request.paths.every((path) => typeof path === 'string');
  return request.kind === 'update'
    && typeof request.targetPath === 'string'
    && typeof request.trusted === 'boolean'
    && typeof request.compatible === 'boolean'
    && typeof request.permissionsUnchanged === 'boolean';
}
