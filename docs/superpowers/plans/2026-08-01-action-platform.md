# Codex Skill Toolbox Action Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace static figures and local demo recommendations with a safe, actionable Skill workspace: online discovery, reviewed installation, tags, planning, and maintenance actions.

**Architecture:** Keep operating-system access behind Electron IPC. Persist only user tags and plans under app data; scan Skills read-only. Normalize marketplace and GitHub metadata into one discovery record, but require an explicit, reviewed plan before every mutation.

**Tech Stack:** Electron, React, TypeScript, Vitest, Testing Library, Node built-ins, existing Codex CLI.

## Global Constraints

- Scanning is read-only; no install, update, deletion, repair, or execution happens without a displayed plan and explicit confirmation.
- Marketplace installation is limited to official or user-configured Codex marketplaces.
- A community GitHub repository must pass manifest, maintenance, and risk review before becoming installable.
- Typed planning always works; microphone permission is requested only after the user clicks voice input.
- Preserve the current book-cover motion and child-page visual system.

---

### Task 1: Persist the user workspace

**Files:**
- Modify: `src/shared/models.ts`, `src/main/ipc.ts`, `src/preload/index.cts`, `src/renderer/App.tsx`
- Create: `src/main/user-workspace.ts`
- Test: `tests/main/user-workspace.test.ts`

**Interfaces:**
- Produce `SkillTag`, `PlannedTask`, and `UserWorkspace`.
- Produce `loadWorkspace(appDataPath): Promise<UserWorkspace>` and `saveWorkspace(appDataPath, workspace): Promise<UserWorkspace>`.
- Extend `ToolboxApi` with `getWorkspace` and `saveWorkspace`.

- [ ] **Step 1: Write the failing persistence test**

```ts
it('round-trips tags and planned tasks', async () => {
  const input = { tags: [{ id: 'ppt', name: 'PPT', color: '#67ddd0', order: 0 }], skillTags: { 'pptx-from-layouts': ['ppt'] }, tasks: [{ id: 'today-1', title: '整理提案', bucket: 'today', priority: 'high', status: 'open' }] };
  await saveWorkspace(tempPath, input);
  expect(await loadWorkspace(tempPath)).toEqual(input);
});
```

- [ ] **Step 2: Run it and verify it fails**

Run: `node node_modules/vitest/vitest.mjs run tests/main/user-workspace.test.ts`

Expected: FAIL because the workspace module does not exist.

- [ ] **Step 3: Implement the minimum storage and IPC bridge**

Store validated JSON as `toolbox-workspace.json` under app data. Store tags and tasks only; never copy or change a Skill file. Expose the two methods through `contextBridge`.

- [ ] **Step 4: Verify and commit**

Run: `node node_modules/vitest/vitest.mjs run tests/main/user-workspace.test.ts`

Expected: PASS.

Run: `git add src/shared/models.ts src/main/user-workspace.ts src/main/ipc.ts src/preload/index.cts src/renderer/App.tsx tests/main/user-workspace.test.ts && git commit -m "feat: persist toolbox workspace data"`

### Task 2: Make Maintenance Center cards actionable

**Files:**
- Modify: `src/renderer/pages/MaintenancePage.tsx`, `src/renderer/App.tsx`, `src/renderer/styles.css`
- Test: `tests/renderer/App.test.tsx`

**Interfaces:**
- Produce `selectedMaintenancePanel: 'tools' | 'conflicts' | 'restore' | null`.
- Consume existing `onScan`, `onPreviewRepair`, `onNotice`, and add `onNavigate`.

- [ ] **Step 1: Write the failing interaction test**

```tsx
it('opens conflicts and only creates a plan after explicit action', async () => {
  render(<App api={apiWithDuplicateSkills} />);
  enterPortalPage('维护中心');
  await user.click(screen.getByRole('button', { name: /重复项目/ }));
  expect(screen.getByText(/推荐保留/)).toBeInTheDocument();
  expect(api.previewPlan).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: '生成修复计划' }));
  expect(api.previewPlan).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run it and verify it fails**

Run: `node node_modules/vitest/vitest.mjs run tests/renderer/App.test.tsx -t "opens conflicts"`

Expected: FAIL because the cards are display-only.

- [ ] **Step 3: Implement the three inline panels**

Make cards buttons. The tools panel lists enabled Skills and navigates to My Tools. The conflicts panel groups duplicate IDs, paths, and highest-precedence recommendation, and exposes `生成修复计划`. The recovery panel explains available manifests; mutations still use the existing plan dialog.

- [ ] **Step 4: Verify and commit**

Run: `node node_modules/vitest/vitest.mjs run tests/renderer/App.test.tsx -t "Maintenance|conflicts|recovery"`

Expected: PASS, including no-conflict and no-recovery states.

Run: `git add src/renderer/pages/MaintenancePage.tsx src/renderer/App.tsx src/renderer/styles.css tests/renderer/App.test.tsx && git commit -m "feat: make maintenance summaries actionable"`

### Task 3: Categorize local Skills with editable business tags

**Files:**
- Modify: `src/renderer/pages/MyToolsPage.tsx`, `src/renderer/App.tsx`, `src/renderer/styles.css`
- Test: `tests/renderer/App.test.tsx`

**Interfaces:**
- Consume `skills`, `workspace`, and `onSaveWorkspace(workspace)`.
- Produce tag filters and `skillTags[skill.id]` assignments.

- [ ] **Step 1: Write the failing tag test**

```tsx
it('filters a Skill by PPT and saves a custom tag', async () => {
  render(<App api={apiWithWorkspace} />);
  enterPortalPage('我的工具');
  await user.click(screen.getByRole('button', { name: 'PPT' }));
  expect(screen.getByRole('heading', { name: 'PPT 版式制作' })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: '新建标签' }));
  await user.type(screen.getByLabelText('标签名称'), '客户交付');
  await user.click(screen.getByRole('button', { name: '保存标签' }));
  expect(api.saveWorkspace).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run it and verify it fails**

Run: `node node_modules/vitest/vitest.mjs run tests/renderer/App.test.tsx -t "custom tag"`

Expected: FAIL because no tag manager exists.

- [ ] **Step 3: Implement tags**

Seed editable `PPT`, `设计`, `文档`, and `图像` tags. Add create, rename, color, sort, assign, unassign, and filter controls using stable tag IDs. Keep paths and technical details visible.

- [ ] **Step 4: Verify and commit**

Run: `node node_modules/vitest/vitest.mjs run tests/renderer/App.test.tsx -t "tag"`

Expected: PASS.

Run: `git add src/renderer/pages/MyToolsPage.tsx src/renderer/App.tsx src/renderer/styles.css tests/renderer/App.test.tsx && git commit -m "feat: organize skills with business tags"`

### Task 4: Add daily and weekly planning with voice fallback

**Files:**
- Create: `src/renderer/components/PlannerBoard.tsx`
- Modify: `src/renderer/pages/DashboardPage.tsx`, `src/renderer/App.tsx`, `src/renderer/styles.css`
- Test: `tests/renderer/PlannerBoard.test.tsx`

**Interfaces:**
- Produce `extractTasks(input, bucket): PlannedTask[]`.
- Consume `tasks` and `onSave(tasks)`.

- [ ] **Step 1: Write the failing planner test**

```tsx
it('turns a multi-line weekly note into editable task cards', async () => {
  render(<PlannerBoard tasks={[]} onSave={onSave} />);
  await user.type(screen.getByLabelText('本周计划输入'), '周一做PPT\n周三检查交付');
  await user.click(screen.getByRole('button', { name: '整理为计划' }));
  expect(screen.getByDisplayValue('周一做PPT')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run it and verify it fails**

Run: `node node_modules/vitest/vitest.mjs run tests/renderer/PlannerBoard.test.tsx`

Expected: FAIL because PlannerBoard does not exist.

- [ ] **Step 3: Implement planner and speech fallback**

Split non-empty lines and Chinese sentence boundaries into task cards. Suggest priority from `今天`, `紧急`, and `本周`, but allow edits to title, time, priority, and completion. Request `SpeechRecognition` only on `语音输入`; if denied or unavailable, show typed input guidance.

- [ ] **Step 4: Verify and commit**

Run: `node node_modules/vitest/vitest.mjs run tests/renderer/PlannerBoard.test.tsx`

Expected: PASS, including microphone-denied fallback.

Run: `git add src/renderer/components/PlannerBoard.tsx src/renderer/pages/DashboardPage.tsx src/renderer/App.tsx src/renderer/styles.css tests/renderer/PlannerBoard.test.tsx && git commit -m "feat: add editable daily and weekly planner"`

### Task 5: Discover, review, and install online Skills safely

**Files:**
- Create: `src/main/online-discovery.ts`, `src/main/community-review.ts`
- Modify: `src/main/ipc.ts`, `src/preload/index.cts`, `src/shared/models.ts`, `src/renderer/pages/DiscoverPage.tsx`, `src/renderer/components/WorkflowCard.tsx`, `src/renderer/App.tsx`
- Test: `tests/main/online-discovery.test.ts`, `tests/main/community-review.test.ts`, `tests/renderer/App.test.tsx`

**Interfaces:**
- Produce `discoverOnline(query, sources): Promise<OnlineRecommendation[]>` and `reviewCommunitySkill(candidate): CommunityReview`.
- Extend `ToolboxApi` with `discoverOnline(query)` and `previewInstall(recommendationId)`.

- [ ] **Step 1: Verify Codex CLI contracts and write failing fixture tests**

Inspect installed Codex with `plugin --help`, `plugin marketplace --help`, and `plugin list --json`; capture only command shapes and JSON fixtures. Do not install during discovery tests.

```ts
it('marks marketplace results installable only when the configured source supports installation', async () => {
  const results = await discoverOnline('PPT', fixtureSources);
  expect(results.find((item) => item.source.kind === 'marketplace')?.installEligible).toBe(true);
});
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `node node_modules/vitest/vitest.mjs run tests/main/online-discovery.test.ts tests/main/community-review.test.ts`

Expected: FAIL because discovery and review modules do not exist.

- [ ] **Step 3: Implement discovery and review**

Read configured marketplace listings first. Search GitHub only for repositories containing `SKILL.md`; rank matching metadata, stars, recent push date, and quality signals. Require readable manifest, recent maintenance, and no executable installation directive before a community result becomes reviewed; otherwise show a rejection reason.

- [ ] **Step 4: Implement plan-only installation**

Marketplace recommendations create a plan identifying the marketplace reference and CLI action. Reviewed community Skills create a plan to stage allowed Skill files into managed storage. Search never installs; only confirmation in the existing plan dialog can apply a change.

- [ ] **Step 5: Wire result cards, verify, and commit**

Show source, update date, score rationale, review state, dependencies, and eligibility. Use `查看安装计划` only when a real plan source exists.

Run: `node node_modules/vitest/vitest.mjs run tests/main/online-discovery.test.ts tests/main/community-review.test.ts tests/renderer/App.test.tsx`

Expected: PASS.

Run: `git add src/main/online-discovery.ts src/main/community-review.ts src/main/ipc.ts src/preload/index.cts src/shared/models.ts src/renderer/pages/DiscoverPage.tsx src/renderer/components/WorkflowCard.tsx src/renderer/App.tsx tests/main/online-discovery.test.ts tests/main/community-review.test.ts tests/renderer/App.test.tsx && git commit -m "feat: discover and review online skills"`

### Task 6: Verify the desktop package

**Files:**
- Modify: `package.json` only if the release version changes
- Verify: `tests/`, `dist/`, `release/`

- [ ] **Step 1: Run full verification**

Run: `node node_modules/vitest/vitest.mjs run && node node_modules/typescript/bin/tsc -p tsconfig.main.json && node node_modules/typescript/bin/tsc --noEmit && node node_modules/vite/bin/vite.js build`

Expected: all tests pass and builds exit 0.

- [ ] **Step 2: Build and smoke test installer**

Run: `node node_modules/electron-builder/cli.js --win nsis --x64`

Install in a separate smoke directory; verify maintenance cards react, tags survive restart, typed planning creates editable tasks, and online results distinguish unavailable from reviewed-installable.

- [ ] **Step 3: Commit release configuration only**

Run: `git add package.json electron-builder.yml scripts/ensure-packaging-config.mjs && git commit -m "chore: package actionable toolbox release"`
