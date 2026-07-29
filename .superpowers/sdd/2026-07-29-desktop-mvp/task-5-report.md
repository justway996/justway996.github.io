# Task 5 report: reversible maintenance plans

## Delivered

- Added `src/main/change-planner.ts` with preview-only repair, delete, and update plans.
- Plans expose exact operations, impact, risk, and an on-disk backup-manifest location.
- `applyPlan` requires explicit confirmation (`闇€瑕佺‘璁` when absent), confines all writes to the supplied managed root, and records pre-change managed files in its backup manifest.
- `restorePlan` reads that manifest to put deleted or replaced managed files back, or remove a newly created repair copy.
- Repair copies a source skill into an isolated directory under the managed root. Delete lists each exact managed file and never targets an unmanaged path. Update is eligible only when trusted, compatible, and permission-preserving; it still requires confirmation.

## TDD evidence

1. Added the first focused test before `change-planner.ts` existed.
2. Ran `pnpm vitest run tests/main/change-planner.test.ts` with the bundled Node runtime on `PATH`.
3. Observed the intended red failure: `Cannot find module '../../src/main/change-planner'`.
4. Added the minimal planner implementation and focused coverage for delete/restore, repair/restore, and update eligibility.

## Verification

- `pnpm vitest run tests/main/change-planner.test.ts`: 1 file, 5 tests passed.
- `pnpm tsc --noEmit`: passed.
- `git diff --check`: passed.
