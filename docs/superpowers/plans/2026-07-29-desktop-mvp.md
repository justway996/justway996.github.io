# Codex Skill Toolbox Desktop MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows desktop MVP that discovers local Codex skills, recommends conflict-safe task workflows, and manages reusable workflow packages for non-technical users.

**Architecture:** Electron provides the Windows desktop shell. A TypeScript main-process domain layer scans local Codex locations, persists Toolbox metadata, calculates recommendations and produces reversible change plans. A React renderer displays business-first views; it calls the domain layer only through a typed preload bridge and never reads arbitrary filesystem paths directly.

**Tech Stack:** Electron, React, TypeScript, Vite, Vitest, Testing Library, Zod, Electron Builder.

## Global Constraints

- Target Windows desktop computers; package with Electron Builder only after MVP tests pass.
- Treat Codex, Skills, plugins and MCPs as advanced concepts; default copy must use business tasks.
- Never silently install, enable, update, delete, execute commands, or access an external account.
- Scans are read-only; all filesystem mutations use a previewed, user-confirmed plan and a recoverable managed backup.
- Recommended workflows must use a locked dependency manifest and report `ready`, `needs_install`, `needs_permission`, `conflict`, or `unknown`.
- Exported workflow packages must exclude secrets, OAuth tokens and private files.
- UI style: deep teal, mist-white panels, thin light borders, large rounded corners, restrained soft shadows, clear feature categories.

---

## File Structure

```text
package.json                         scripts and Windows build configuration
vite.config.ts                       renderer build and test aliases
electron-builder.yml                 NSIS installer metadata
src/shared/models.ts                 all cross-process types and status unions
src/shared/catalog.ts                starter prop-designer tools and curated workflows
src/main/app-paths.ts                isolated application paths and Codex discovery candidates
src/main/skill-scanner.ts            read-only Skill/plugin discovery and precedence resolution
src/main/recommendations.ts          query-to-workflow ranking and conflict preflight
src/main/change-planner.ts           install/update/delete/repair plans and backup records
src/main/workflow-package.ts         save, import, export and package validation
src/main/ipc.ts                      typed Electron IPC handlers
src/main/index.ts                    Electron window and startup composition
src/preload/index.ts                 narrow window.toolbox API bridge
src/renderer/main.tsx                React mount point
src/renderer/App.tsx                 application navigation and data loading
src/renderer/styles.css              global technology-inspired visual system
src/renderer/components/*.tsx        focused cards, dialogs and status components
src/renderer/pages/*.tsx             Dashboard, Discover, Workflows, MyTools, Maintenance
tests/main/*.test.ts                 domain tests with temporary directory fixtures
tests/renderer/*.test.tsx            interaction and copy tests
```

## Task 1: Bootstrap the Electron application and shared model

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `vite.config.ts`
- Create: `src/shared/models.ts`
- Create: `src/renderer/main.tsx`
- Create: `src/renderer/index.html`
- Test: `tests/main/models.test.ts`

**Interfaces:**
- Produces `SkillRecord`, `WorkflowDefinition`, `WorkflowStatus`, `PreflightResult`, `ChangePlan` and `ToolboxApi` for all later tasks.

- [ ] **Step 1: Write the failing model test**

```ts
import { describe, expect, it } from 'vitest';
import { workflowStatuses } from '../../src/shared/models';

describe('workflow status contract', () => {
  it('contains all user-visible preflight states', () => {
    expect(workflowStatuses).toEqual([
      'ready', 'needs_install', 'needs_permission', 'conflict', 'unknown',
    ]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm vitest run tests/main/models.test.ts`

Expected: FAIL because `src/shared/models.ts` does not exist.

- [ ] **Step 3: Add the minimal shared contract and application scripts**

```ts
export const workflowStatuses = ['ready', 'needs_install', 'needs_permission', 'conflict', 'unknown'] as const;
export type WorkflowStatus = typeof workflowStatuses[number];

export type SkillRecord = {
  id: string; name: string; description: string; path: string;
  source: 'global' | 'workspace' | 'plugin' | 'managed'; enabled: boolean;
  precedence: number; version?: string;
};

export type WorkflowDefinition = {
  id: string; name: string; category: string; description: string;
  steps: Array<{ id: string; title: string; toolId: string }>;
  dependencies: Array<{ skillId: string; version?: string }>;
};
```

Configure `package.json` with `dev`, `test`, `build` and `dist` scripts, Electron/React/Vite/Vitest dependencies, and a strict TypeScript configuration.

- [ ] **Step 4: Run the unit test and type check**

Run: `pnpm vitest run tests/main/models.test.ts && pnpm tsc --noEmit`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add package.json tsconfig.json vite.config.ts src/shared tests/main/models.test.ts
git commit -m "feat: bootstrap desktop toolbox contracts"
```

## Task 2: Build the read-only local Codex scanner

**Files:**
- Create: `src/main/app-paths.ts`
- Create: `src/main/skill-scanner.ts`
- Test: `tests/main/skill-scanner.test.ts`

**Interfaces:**
- Consumes: `SkillRecord` from `src/shared/models.ts`.
- Produces: `scanSkills(paths: ScanPaths): Promise<SkillRecord[]>` and `resolveEffectiveSkills(records): SkillRecord[]`.

- [ ] **Step 1: Write failing scanner tests using a temporary Codex fixture**

```ts
it('marks the higher-precedence workspace copy as effective', async () => {
  await writeSkill(tempDir, '.codex/skills/ppt/SKILL.md', '---\nname: ppt\ndescription: Make slides\n---');
  await writeSkill(tempDir, 'workspace/.codex/skills/ppt/SKILL.md', '---\nname: ppt\ndescription: Local slides\n---');
  const records = await scanSkills({ globalRoot: tempDir, workspaceRoot: join(tempDir, 'workspace') });
  expect(resolveEffectiveSkills(records).find((item) => item.id === 'ppt')?.source).toBe('workspace');
});
```

- [ ] **Step 2: Run scanner tests to verify failure**

Run: `pnpm vitest run tests/main/skill-scanner.test.ts`

Expected: FAIL because `scanSkills` is not defined.

- [ ] **Step 3: Implement discovery without mutations**

`app-paths.ts` returns candidate global, workspace and managed roots without reading beyond configured locations. `skill-scanner.ts` recursively finds only `SKILL.md` files under those roots, parses the minimal YAML front matter, computes an ID from `name`, and assigns precedence `workspace > managed > plugin > global`. Missing locations return an empty list.

- [ ] **Step 4: Run tests**

Run: `pnpm vitest run tests/main/skill-scanner.test.ts`

Expected: PASS for empty roots, valid metadata, malformed metadata and precedence.

- [ ] **Step 5: Commit**

```bash
git add src/main/app-paths.ts src/main/skill-scanner.ts tests/main/skill-scanner.test.ts
git commit -m "feat: scan local Codex skills safely"
```

## Task 3: Seed the prop-designer catalog and task recommendation engine

**Files:**
- Create: `src/shared/catalog.ts`
- Create: `src/main/recommendations.ts`
- Test: `tests/main/recommendations.test.ts`

**Interfaces:**
- Consumes: `WorkflowDefinition`, `SkillRecord`.
- Produces: `recommendWorkflows(query: string, catalog: WorkflowDefinition[], skills: SkillRecord[]): Recommendation[]`.

- [ ] **Step 1: Write failing recommendation tests**

```ts
it('recommends the client proposal workflow for PPT searches', () => {
  const results = recommendWorkflows('我要做客户提案PPT', catalog, readySkills);
  expect(results[0]).toMatchObject({ workflowId: 'prop-client-proposal', status: 'ready' });
  expect(results).toHaveLength(1);
});

it('does not mark a shadowed dependency as ready', () => {
  const results = recommendWorkflows('做 PPT', catalog, shadowedPptSkills);
  expect(results[0]?.status).toBe('conflict');
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pnpm vitest run tests/main/recommendations.test.ts`

Expected: FAIL because the catalog and recommendation engine do not exist.

- [ ] **Step 3: Implement the catalog and deterministic ranking**

Create five prop-designer tools and the `prop-client-proposal` workflow. Rank Chinese and English query keywords by title, category, description and explicit aliases. Calculate status from effective installed Skills: missing dependency -> `needs_install`; disabled or permission-gated dependency -> `needs_permission`; duplicate/shadowed dependency -> `conflict`; unknown metadata -> `unknown`; otherwise `ready`. Return one recommended result and at most two alternatives, including human-readable reasons.

- [ ] **Step 4: Run recommendation tests**

Run: `pnpm vitest run tests/main/recommendations.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/shared/catalog.ts src/main/recommendations.ts tests/main/recommendations.test.ts
git commit -m "feat: recommend conflict-safe task workflows"
```

## Task 4: Persist workflows and validate import/export packages

**Files:**
- Create: `src/main/workflow-package.ts`
- Test: `tests/main/workflow-package.test.ts`

**Interfaces:**
- Produces `saveWorkflow`, `exportWorkflow`, `importWorkflow`, and `validatePackage`.
- Package contract: `workflow.json`, `lock.json`, optional `tools/`, optional `assets/`, never secrets.

- [ ] **Step 1: Write failing package tests**

```ts
it('round-trips a workflow with a locked dependency', async () => {
  const archive = await exportWorkflow(workflow, tempDir);
  const imported = await importWorkflow(archive, anotherTempDir);
  expect(imported.workflow.dependencies).toEqual(workflow.dependencies);
});

it('rejects archives containing a token-like field', async () => {
  await expect(validatePackage(secretArchive)).rejects.toThrow('敏感凭据');
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pnpm vitest run tests/main/workflow-package.test.ts`

Expected: FAIL because package functions do not exist.

- [ ] **Step 3: Implement schema validation and safe persistence**

Use Zod to validate `workflow.json` and `lock.json`. Save user-created workflows under the application data directory. Build ZIP archives from explicit allowlisted entries only, recursively reject keys matching `token`, `secret`, `apiKey`, `password` and `.env` files, and preserve locked dependency versions.

- [ ] **Step 4: Run package tests**

Run: `pnpm vitest run tests/main/workflow-package.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/main/workflow-package.ts tests/main/workflow-package.test.ts
git commit -m "feat: save and share locked workflow packages"
```

## Task 5: Create reversible conflict, deletion and update plans

**Files:**
- Create: `src/main/change-planner.ts`
- Test: `tests/main/change-planner.test.ts`

**Interfaces:**
- Produces `planRepair`, `planDelete`, `planUpdate`, `applyPlan`, and `restorePlan`.
- `applyPlan` accepts only a plan ID previously created by the planner and `confirmed: true`.

- [ ] **Step 1: Write failing plan tests**

```ts
it('creates a repair plan without changing files', async () => {
  const plan = await planRepair(conflictingWorkflow, fixtureState);
  expect(plan.operations).toContainEqual(expect.objectContaining({ kind: 'create-managed-copy' }));
  expect(await listFiles(managedRoot)).toEqual([]);
});

it('requires confirmation before applying a delete plan', async () => {
  const plan = await planDelete(managedSkill, fixtureState);
  await expect(applyPlan(plan, false)).rejects.toThrow('需要确认');
});
```

- [ ] **Step 2: Run plan tests to verify failure**

Run: `pnpm vitest run tests/main/change-planner.test.ts`

Expected: FAIL because planner functions do not exist.

- [ ] **Step 3: Implement constrained plan execution**

Plans contain operations, impacted workflows, risks and an automatically created backup directory. `planRepair` creates a managed isolated copy rather than replacing an unmanaged file. `planDelete` lists every exact managed path and marks unmanaged entries as manual-confirmation items. `planUpdate` only sets `autoApplicable: true` for trusted compatible patch updates with unchanged permissions. `applyPlan` writes only inside the application-managed root and saves a manifest required by `restorePlan`.

- [ ] **Step 4: Run plan tests**

Run: `pnpm vitest run tests/main/change-planner.test.ts`

Expected: PASS for repair preview, confirmation gate, restore and non-automatic major updates.

- [ ] **Step 5: Commit**

```bash
git add src/main/change-planner.ts tests/main/change-planner.test.ts
git commit -m "feat: add reversible maintenance plans"
```

## Task 6: Expose the domain layer through a narrow Electron bridge

**Files:**
- Create: `src/main/ipc.ts`
- Create: `src/main/index.ts`
- Create: `src/preload/index.ts`
- Modify: `src/shared/models.ts`
- Test: `tests/main/ipc.test.ts`

**Interfaces:**
- Produces `window.toolbox.scan()`, `search(query)`, `listWorkflows()`, `importPackage()`, `exportWorkflow(id)`, `previewPlan(action, id)`, and `applyPlan(planId)`.

- [ ] **Step 1: Write failing IPC registration test**

```ts
it('registers only allowlisted toolbox channels', () => {
  const channels = registerIpc(fakeIpc, fakeServices);
  expect(channels).toEqual(expect.arrayContaining(['toolbox:scan', 'toolbox:search', 'toolbox:preview-plan']));
  expect(channels).not.toContain('shell:exec');
});
```

- [ ] **Step 2: Run the test to verify failure**

Run: `pnpm vitest run tests/main/ipc.test.ts`

Expected: FAIL because `registerIpc` is not defined.

- [ ] **Step 3: Implement explicit IPC handlers**

Use `contextIsolation: true`, `nodeIntegration: false`, and a preload API with fixed method signatures. Do not expose `fs`, `child_process`, raw `ipcRenderer`, arbitrary paths or shell execution to the renderer. File selection goes through Electron dialogs and returns validated package paths only.

- [ ] **Step 4: Run IPC tests**

Run: `pnpm vitest run tests/main/ipc.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/main/ipc.ts src/main/index.ts src/preload/index.ts src/shared/models.ts tests/main/ipc.test.ts
git commit -m "feat: add secure desktop toolbox bridge"
```

## Task 7: Implement the business-first React interface and visual system

**Files:**
- Create: `src/renderer/App.tsx`
- Create: `src/renderer/styles.css`
- Create: `src/renderer/components/Sidebar.tsx`
- Create: `src/renderer/components/SearchPanel.tsx`
- Create: `src/renderer/components/WorkflowCard.tsx`
- Create: `src/renderer/components/StatusPill.tsx`
- Create: `src/renderer/components/PlanDialog.tsx`
- Create: `src/renderer/pages/DashboardPage.tsx`
- Create: `src/renderer/pages/DiscoverPage.tsx`
- Create: `src/renderer/pages/WorkflowsPage.tsx`
- Create: `src/renderer/pages/MyToolsPage.tsx`
- Create: `src/renderer/pages/MaintenancePage.tsx`
- Test: `tests/renderer/App.test.tsx`

**Interfaces:**
- Consumes `window.toolbox` and all shared status/data types.
- Produces a five-category navigation: 总览, 发现, 工作流, 我的工具, 维护中心.

- [ ] **Step 1: Write failing interface tests**

```tsx
it('shows a business recommendation instead of raw Skills for a PPT search', async () => {
  render(<App api={fakeReadyApi} />);
  await userEvent.type(screen.getByRole('searchbox'), '做 PPT');
  expect(await screen.findByText('客户提案 PPT')).toBeInTheDocument();
  expect(screen.queryByText('pptx-from-layouts')).not.toBeInTheDocument();
});

it('opens a confirmation dialog before applying a maintenance plan', async () => {
  render(<App api={fakeConflictApi} />);
  await userEvent.click(await screen.findByRole('button', { name: '修复此工具' }));
  expect(screen.getByText('将要变更的项目')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run renderer tests to verify failure**

Run: `pnpm vitest run tests/renderer/App.test.tsx`

Expected: FAIL because `App` and components do not exist.

- [ ] **Step 3: Build the five pages and visual system**

Use deep teal `#043F3A`, mist `#EAF4F1`, accent `#A5DCD2`, and ink `#12312D`. Apply 24–32px rounded cards, 1px translucent borders, offset soft shadows and compact utility controls. Keep raw Skill names behind a “查看技术详情” disclosure. Dashboard features the prop-designer toolbox; Discover contains task search plus curated recommendations; Workflows manages saved/imported/exported workflows; My Tools handles local/custom tools; Maintenance shows scan results, updates, conflicts and deletion plans.

- [ ] **Step 4: Run renderer tests and build**

Run: `pnpm vitest run tests/renderer/App.test.tsx && pnpm build`

Expected: PASS and a renderer bundle is produced.

- [ ] **Step 5: Commit**

```bash
git add src/renderer tests/renderer
git commit -m "feat: add polished toolbox interface"
```

## Task 8: Add curated workflow deployment and Windows installer verification

**Files:**
- Create: `src/shared/curated-workflows.ts`
- Create: `src/main/deployment.ts`
- Create: `electron-builder.yml`
- Modify: `package.json`
- Test: `tests/main/deployment.test.ts`

**Interfaces:**
- Produces `listCuratedWorkflows(query)`, `previewDeployment(id)`, and `deployCuratedWorkflow(id, confirmed)`.

- [ ] **Step 1: Write failing deployment tests**

```ts
it('does not mark a curated workflow ready until validation succeeds', async () => {
  const result = await deployCuratedWorkflow('ppt-client-proposal', true, failingValidator);
  expect(result.status).toBe('needs_install');
  expect(result.rolledBack).toBe(true);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pnpm vitest run tests/main/deployment.test.ts`

Expected: FAIL because deployment functions do not exist.

- [ ] **Step 3: Implement curated entries and deployment transaction**

Seed the catalog with a verified prop-client-proposal workflow and a PPT client-proposal workflow. Each includes publisher, version, compatibility date, dependency locks, risk labels and a validation prompt. Deployment composes a change plan, requires confirmation, applies managed changes, invokes the safe validator abstraction and restores the backup if validation fails. Package the app as an NSIS installer with an application icon and Windows metadata.

- [ ] **Step 4: Run the complete verification suite and package**

Run: `pnpm vitest run && pnpm tsc --noEmit && pnpm build && pnpm dist`

Expected: all tests PASS and `release/` contains the Windows installer.

- [ ] **Step 5: Commit**

```bash
git add src/shared/curated-workflows.ts src/main/deployment.ts electron-builder.yml package.json tests/main/deployment.test.ts
git commit -m "feat: deploy curated workflows and package Windows app"
```

## Plan Self-Review

- Spec coverage: tasks 2 and 6 cover local Codex discovery; task 3 covers task search, recommendation and conflict preflight; task 4 covers custom workflow persistence/sharing; task 5 covers repair, deletion, backups and updates; task 7 covers clear functional categories and the requested visual direction; task 8 covers curated workflows, local deployment and installer packaging.
- Placeholder scan: each task contains a test, command, implementation boundary and commit, with no unfinished implementation markers.
- Type consistency: `SkillRecord`, `WorkflowDefinition`, `WorkflowStatus`, `ChangePlan` and `ToolboxApi` are defined in Task 1 and are the contracts used by Tasks 2–8.
