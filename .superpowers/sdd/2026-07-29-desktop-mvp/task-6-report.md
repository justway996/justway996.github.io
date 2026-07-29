# Task 6 report: secure Electron bridge

## Delivered

- Added a main-process IPC bridge with exactly seven `toolbox:*` handlers: scan, search, list workflows, import package, export workflow, preview plan, and apply plan.
- Added a sandboxed preload that exposes only the typed `window.toolbox` API through `contextBridge`; it does not expose Node, filesystem, child-process, raw IPC, or arbitrary path methods.
- Kept all dialog-selected paths in the main process. Workflow imports require an absolute `.workflow.zip` selection; exports and repair/update sources are selected with Electron dialogs.
- Plan previews are stored in the main process and applied by opaque plan ID, so the renderer cannot submit a forged plan or choose a managed root.
- Wired scan/search to the scanner and recommendations, package actions to workflow packaging, and previews/applies to the reversible maintenance planner.
- Updated the main TypeScript build to emit the preload beside the main bundle and configured BrowserWindow to load it with `contextIsolation: true` and `nodeIntegration: false`.

## TDD evidence

1. Added `tests/main/ipc.test.ts` before `src/main/ipc.ts` existed.
2. Ran the focused test and observed the expected red failure: `Cannot find module '../../src/main/ipc'`.
3. Implemented the narrow handler registry and then observed the focused test pass.

## Verification

- `pnpm vitest run tests/main/ipc.test.ts`: passed (1 test).
- `pnpm test`: passed (7 files, 32 tests).
- `pnpm build`: passed.
- `git diff --check`: passed.
