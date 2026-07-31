# Maintenance action center design

## Goal

Turn the Maintenance Center summary cards into safe, useful actions for a nontechnical user. The first release covers tool availability, duplicate/conflicting skills, and recovery points.

## Scope

- Each health card opens its corresponding inline detail panel in the Maintenance Center.
- The available-tools panel lists enabled skills and links to My Tools.
- The conflicts panel shows only detected duplicate skill IDs, their sources and paths, and the recommended retained copy.
- A user can create a repair plan from a conflict panel, review it in the existing plan dialog, and must explicitly confirm before any change is applied.
- The recovery panel lists known backup manifests and lets the user view their affected paths. Restore itself is not included in this first release.

## Interaction design

1. The user selects one of the three summary cards.
2. The selected card receives an active state and an inline panel appears below the card row.
3. The panel explains the status in plain language and offers only relevant next steps.
4. For a conflict, `Generate repair plan` opens the existing confirmation dialog. The dialog lists the exact operations, locations, impact, risk, and backup before exposing `Confirm`.
5. On confirmation, the existing plan application mechanism runs and reports success or failure through the current notice/error channel.

## Safe defaults

- Scanning remains read-only.
- No conflict is changed automatically.
- When multiple copies share an ID, the recommendation retains the highest-precedence record and identifies every affected path.
- The recovery area is informational in this release; no rollback action is available until a restorable plan is designed and verified.

## Data and component changes

- `MaintenancePage` derives duplicate groups from its `SkillRecord[]` input.
- It owns the selected health-card state and renders a small detail panel for `tools`, `conflicts`, or `restore`.
- Existing `onScan`, `onPreviewRepair`, and `onNotice` callbacks remain the boundaries to the Electron/IPC layer.
- `App` continues to create and apply a plan through the existing dialog; it receives an explicit maintenance recommendation from the page when a conflict plan is requested.

## Empty states

- No conflicts: show `No duplicate skills were found; no action is required.`
- No enabled skills: link to scan or My Tools rather than showing an empty action list.
- No recovery manifests: explain that a recovery point is created before a confirmed managed change.

## Verification

- Unit/rendering tests prove all three cards open the matching panel.
- Tests prove a duplicate group exposes `Generate repair plan` and invokes the supplied callback only after the user clicks it.
- Tests prove no-conflict and no-recovery empty states are understandable.
- Run the full Vitest suite, TypeScript checks, and production Vite build.

## Out of scope

- Online workflow discovery and real marketplace installation.
- Skill tags and custom labels.
- Task planning, voice input, or automatic scheduling.
- Automatic conflict repair or automatic deletion.
