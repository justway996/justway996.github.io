import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import JSZip from 'jszip';
import { afterEach, describe, expect, it } from 'vitest';
import type { WorkflowDefinition } from '../../src/shared/models';
import { exportWorkflow, importWorkflow, validatePackage } from '../../src/main/workflow-package';

const temporaryDirectories: string[] = [];

const workflow: WorkflowDefinition = {
  id: 'client-proposal',
  name: 'Client proposal',
  category: 'presentation',
  description: 'Create a client proposal deck.',
  steps: [{ id: 'outline', title: 'Create outline', toolId: 'pptx-from-layouts' }],
  dependencies: [{ skillId: 'pptx-from-layouts', version: '1.2.3' }],
};

async function createTemporaryDirectory(): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), 'codex-workflow-package-'));
  temporaryDirectories.push(directory);
  return directory;
}

async function writePackageArchive(directory: string, configure: (zip: JSZip) => void): Promise<string> {
  const archivePath = join(directory, 'workflow.workflow.zip');
  const zip = new JSZip();
  zip.file('workflow.json', JSON.stringify(workflow));
  zip.file('lock.json', JSON.stringify({ dependencies: workflow.dependencies }));
  configure(zip);
  await writeFile(archivePath, await zip.generateAsync({ type: 'nodebuffer' }));
  return archivePath;
}

afterEach(async () => {
  await Promise.all(temporaryDirectories.splice(0).map((directory) => rm(directory, { force: true, recursive: true })));
});

describe('workflow packages', () => {
  it('round-trips a workflow with a locked dependency', async () => {
    const exportDirectory = await createTemporaryDirectory();
    const appDataDirectory = await createTemporaryDirectory();

    const archive = await exportWorkflow(workflow, exportDirectory);
    const imported = await importWorkflow(archive, appDataDirectory);

    expect(imported.workflow.dependencies).toEqual([{ skillId: 'pptx-from-layouts', version: '1.2.3' }]);
    expect(imported.lock.dependencies).toEqual([{ skillId: 'pptx-from-layouts', version: '1.2.3' }]);
  });

  it('rejects archives containing a token-like field', async () => {
    const archiveDirectory = await createTemporaryDirectory();
    const secretArchive = await writePackageArchive(archiveDirectory, (zip) => {
      zip.file('workflow.json', JSON.stringify({ ...workflow, token: 'do-not-export' }));
    });

    await expect(validatePackage(secretArchive)).rejects.toThrow('敏感凭据');
  });

  it('rejects secret markers in allowlisted text files', async () => {
    const archiveDirectory = await createTemporaryDirectory();
    const archive = await writePackageArchive(archiveDirectory, (zip) => {
      zip.file('tools/SKILL.md', 'name: demo\napiKey: do-not-export\n');
    });

    await expect(validatePackage(archive)).rejects.toThrow('敏感凭据');
  });

  it('rejects .env files in allowlisted directories', async () => {
    const archiveDirectory = await createTemporaryDirectory();
    const archive = await writePackageArchive(archiveDirectory, (zip) => {
      zip.file('assets/.env', 'TOKEN=do-not-export');
    });

    await expect(validatePackage(archive)).rejects.toThrow('敏感凭据');
  });

  it.each([
    ['non-allowlisted files', 'private.txt'],
    ['traversal paths', 'tools/../private.txt'],
  ])('rejects %s', async (_description, entryName) => {
    const archiveDirectory = await createTemporaryDirectory();
    const archive = await writePackageArchive(archiveDirectory, (zip) => {
      zip.file(entryName, 'safe text');
    });

    await expect(validatePackage(archive)).rejects.toThrow('Package contains an unsupported file.');
  });
});
