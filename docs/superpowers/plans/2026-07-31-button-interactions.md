# Button Interactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every visible toolbox action button navigate, invoke its existing safe action, or present an explicit response.

**Architecture:** Keep page state in `App.tsx`, which already owns page navigation, notices, search state, and the safe repair dialog. Pass small callbacks into page components; do not introduce routing or global state.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library.

## Global Constraints

- No new dependencies or external services.
- Existing scan, import, export, and repair confirmation flows remain the only local mutation paths.
- Visual-only workflow filters remain unchanged until their filter semantics are specified.

---

### Task 1: Add interaction callbacks and tests

**Files:**
- Modify: `src/renderer/App.tsx`
- Modify: `src/renderer/pages/DashboardPage.tsx`
- Modify: `src/renderer/pages/WorkflowsPage.tsx`
- Modify: `src/renderer/pages/MaintenancePage.tsx`
- Test: `tests/renderer/App.test.tsx`

**Interfaces:**
- Produces `onNavigate(page: PageId): void`, `onNotice(message: string): void`, and `onRepair(recommendation: WorkflowRecommendation): Promise<void>` callbacks for page actions.
- Consumes existing `PageId`, `WorkflowRecommendation`, and safe repair-plan dialog state from `App.tsx`.

- [ ] **Step 1: Write failing renderer tests**

```tsx
it('navigates from the dashboard actions to tools and workflows', async () => {
  render(<App api={api} />);
  await enterPortalPage('总览');
  await user.click(screen.getByRole('button', { name: /查看全部工具/ }));
  expect(screen.getByRole('heading', { name: '我的工具' })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused test**

Run: `node node_modules/vitest/vitest.mjs run tests/renderer/App.test.tsx`

Expected: FAIL because the dashboard action has no click handler.

- [ ] **Step 3: Add minimal callback wiring**

```tsx
const showNotice = useCallback((message: string) => setNotice(message), []);
<DashboardPage onNavigate={navigate} onNotice={showNotice} ... />
<WorkflowsPage onNotice={showNotice} ... />
<MaintenancePage onRepair={previewRepair} ... />
```

Bind dashboard actions to `onNavigate('tools')` and `onNavigate('workflows')`; bind workflow opening and tool management to `onNotice`; bind maintenance recommendation actions to the existing `onRepair` flow.

- [ ] **Step 4: Run the focused test again**

Run: `node node_modules/vitest/vitest.mjs run tests/renderer/App.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/renderer/App.tsx src/renderer/pages/DashboardPage.tsx src/renderer/pages/WorkflowsPage.tsx src/renderer/pages/MaintenancePage.tsx tests/renderer/App.test.tsx
git commit -m "feat: wire toolbox action buttons"
```

### Task 2: Make search completion explicit

**Files:**
- Modify: `src/renderer/App.tsx`
- Modify: `src/renderer/styles.css`
- Test: `tests/renderer/App.test.tsx`

**Interfaces:**
- Consumes `search(query: string): Promise<void>` in `App.tsx`.
- Produces an existing `toast` notice and a stable `id="recommendations"` results section.

- [ ] **Step 1: Write failing renderer test**

```tsx
it('announces that a matching workflow was found after searching', async () => {
  render(<App api={api} />);
  await enterPortalPage('总览');
  await user.type(screen.getByRole('searchbox'), '做ppt');
  await user.click(screen.getByRole('button', { name: /查找方案/ }));
  expect(await screen.findByRole('status')).toHaveTextContent('已为你找到');
});
```

- [ ] **Step 2: Run the focused test**

Run: `node node_modules/vitest/vitest.mjs run tests/renderer/App.test.tsx`

Expected: FAIL because a successful search does not show a confirmation notice.

- [ ] **Step 3: Add search feedback**

```tsx
if (results.length > 0) {
  setNotice(`已为你找到 ${results.length} 个可运行方案`);
}
```

Give the recommendation section `id="recommendations"` and call `document.getElementById('recommendations')?.scrollIntoView({ behavior: 'smooth', block: 'start' })` after successful results are rendered.

- [ ] **Step 4: Run the focused test again**

Run: `node node_modules/vitest/vitest.mjs run tests/renderer/App.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/renderer/App.tsx src/renderer/styles.css tests/renderer/App.test.tsx
git commit -m "feat: confirm search results"
```

### Task 3: Verify desktop delivery

**Files:**
- Modify: none
- Verify: `tests/renderer/App.test.tsx`, `tests/main/preload-runtime.test.ts`, `release/`

- [ ] **Step 1: Run all tests**

Run: `node node_modules/vitest/vitest.mjs run`

Expected: all tests pass.

- [ ] **Step 2: Build the application**

Run: `node node_modules/typescript/bin/tsc -p tsconfig.main.json && node node_modules/typescript/bin/tsc --noEmit && node node_modules/vite/bin/vite.js build`

Expected: exit code 0.

- [ ] **Step 3: Create and inspect the Windows installer**

Run: `node node_modules/electron-builder/cli.js --win nsis --x64`

Expected: `release/Codex Skill Toolbox-<version>-Setup.exe` exists and includes `dist/preload/index.cjs` and relative renderer assets.
