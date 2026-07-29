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
    const secretArchive = join(archiveDirectory, 'secret.workflow.zip');
    const zip = new JSZip();
    zip.file('workflow.json', JSON.stringify({ ...workflow, token: 'do-not-export' }));
    zip.file('lock.json', JSON.stringify({ dependencies: workflow.dependencies }));
    await writeFile(secretArchive, await zip.generateAsync({ type: 'nodebuffer' }));

    await expect(validatePackage(secretArchive)).rejects.toThrow('鏁忔劅鍑嵁');
  });
});
