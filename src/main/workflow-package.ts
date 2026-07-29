import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { basename, join, relative, resolve } from 'node:path';
import JSZip from 'jszip';
import { z } from 'zod';
import type { WorkflowDefinition } from '../shared/models.js';

const sensitiveKeyPattern = /token|secret|apiKey|password/i;
const sensitiveTextPattern = /(?:^|[\s{,])(?:token|secret|api[_-]?key|password)\s*[:=]/im;
const sensitiveMessage = '敏感凭据';

const dependencySchema = z.object({
  skillId: z.string().min(1),
  version: z.string().min(1).optional(),
}).strict();

const workflowSchema = z.object({
  id: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/),
  name: z.string().min(1),
  category: z.string().min(1),
  description: z.string(),
  steps: z.array(z.object({
    id: z.string().min(1),
    title: z.string().min(1),
    toolId: z.string().min(1),
  }).strict()),
  dependencies: z.array(dependencySchema),
}).strict();

const lockSchema = z.object({
  dependencies: z.array(dependencySchema),
}).strict();

export type WorkflowLock = z.infer<typeof lockSchema>;

export type WorkflowPackage = {
  workflow: WorkflowDefinition;
  lock: WorkflowLock;
};

export async function saveWorkflow(workflow: WorkflowDefinition, appDataDirectory: string): Promise<string> {
  const validatedWorkflow = parseWorkflow(workflow);
  const workflowsDirectory = resolve(appDataDirectory, 'workflows');
  const workflowPath = inside(appDataDirectory, workflowsDirectory, `${validatedWorkflow.id}.json`);

  await mkdir(workflowsDirectory, { recursive: true });
  await writeFile(workflowPath, JSON.stringify(validatedWorkflow, null, 2), 'utf8');
  return workflowPath;
}

export async function exportWorkflow(workflow: WorkflowDefinition, exportDirectory: string): Promise<string> {
  const validatedWorkflow = parseWorkflow(workflow);
  const lock = createLock(validatedWorkflow);
  const archivePath = inside(exportDirectory, exportDirectory, `${validatedWorkflow.id}.workflow.zip`);
  const zip = new JSZip();

  zip.file('workflow.json', JSON.stringify(validatedWorkflow, null, 2));
  zip.file('lock.json', JSON.stringify(lock, null, 2));
  await mkdir(resolve(exportDirectory), { recursive: true });
  await writeFile(archivePath, await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }));
  return archivePath;
}

export async function importWorkflow(archivePath: string, appDataDirectory: string): Promise<WorkflowPackage> {
  const workflowPackage = await validatePackage(archivePath);
  const workflowPath = await saveWorkflow(workflowPackage.workflow, appDataDirectory);
  const lockPath = inside(appDataDirectory, resolve(appDataDirectory, 'workflows'), `${basename(workflowPath, '.json')}.lock.json`);

  await writeFile(lockPath, JSON.stringify(workflowPackage.lock, null, 2), 'utf8');
  return workflowPackage;
}

export async function validatePackage(archivePath: string): Promise<WorkflowPackage> {
  const zip = await JSZip.loadAsync(await readFile(archivePath));
  let workflowContent: unknown;
  let lockContent: unknown;

  for (const entry of Object.values(zip.files)) {
    if (entry.dir) continue;

    const name = entry.unsafeOriginalName ?? entry.name;
    validateEntryName(name);
    const text = decodeText(await entry.async('nodebuffer'));
    if (text !== undefined) rejectSensitiveText(text);

    if (name.endsWith('.json')) {
      const parsed = parseJson(text, name);
      rejectSensitiveData(parsed);

      if (name === 'workflow.json') workflowContent = parsed;
      if (name === 'lock.json') lockContent = parsed;
    }
  }

  if (workflowContent === undefined || lockContent === undefined) {
    throw new Error('Package must contain workflow.json and lock.json.');
  }

  const workflow = parseWorkflow(workflowContent);
  const lock = parseLock(lockContent);
  ensureLocksMatch(workflow, lock);
  return { workflow, lock };
}

function createLock(workflow: WorkflowDefinition): WorkflowLock {
  return { dependencies: workflow.dependencies.map((dependency) => ({ ...dependency })) };
}

function parseWorkflow(value: unknown): WorkflowDefinition {
  rejectSensitiveData(value);
  return workflowSchema.parse(value);
}

function parseLock(value: unknown): WorkflowLock {
  rejectSensitiveData(value);
  return lockSchema.parse(value);
}

function decodeText(value: Uint8Array): string | undefined {
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(value);
  } catch {
    return undefined;
  }
}

function parseJson(content: string | undefined, name: string): unknown {
  if (content === undefined) throw new Error(`Invalid JSON in ${name}.`);

  try {
    return JSON.parse(content);
  } catch {
    throw new Error(`Invalid JSON in ${name}.`);
  }
}

function rejectSensitiveData(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(rejectSensitiveData);
    return;
  }

  if (value !== null && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if (sensitiveKeyPattern.test(key)) throw new Error(sensitiveMessage);
      rejectSensitiveData(child);
    }
  }
}

function rejectSensitiveText(value: string): void {
  if (sensitiveTextPattern.test(value)) throw new Error(sensitiveMessage);
}

function validateEntryName(name: string): void {
  if (/(^|\/)\.env(?:\.|$)/i.test(name)) {
    throw new Error(sensitiveMessage);
  }

  const isAllowed = name === 'workflow.json'
    || name === 'lock.json'
    || name.startsWith('tools/')
    || name.startsWith('assets/');

  if (!isAllowed || name.includes('..') || name.startsWith('/') || name.includes('\\')) {
    throw new Error('Package contains an unsupported file.');
  }
}

function ensureLocksMatch(workflow: WorkflowDefinition, lock: WorkflowLock): void {
  const workflowLocks = JSON.stringify(createLock(workflow).dependencies);
  if (workflowLocks !== JSON.stringify(lock.dependencies)) {
    throw new Error('Locked dependencies do not match the workflow.');
  }
}

function inside(root: string, directory: string, filename: string): string {
  const rootPath = resolve(root);
  const target = resolve(directory, filename);
  if (relative(rootPath, target).startsWith('..')) throw new Error('Path must stay inside the supplied directory.');
  return target;
}
