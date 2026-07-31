# Codex Skill Toolbox action platform design

## Goal

Turn the existing visual toolbox into an actionable, nontechnical Codex Skill workspace. The release covers online discovery, safe installation, local-skill classification, task planning, and actionable maintenance.

## Scope

- The Maintenance Center cards open inline action panels for tools, conflicts, and recovery points.
- My Tools groups local skills by business tags such as PPT and design; users can create, rename, color, reorder, and assign custom tags.
- The Overview becomes a daily/weekly planning surface for typed tasks and browser voice input. It extracts a concise task list, proposes priorities and dates, and always allows manual edits.
- Discover searches configured Codex marketplaces and ranked community GitHub Skill repositories rather than only local demo data.
- A workflow installation can include the required skills and versions. Installation is always preceded by a plan and explicit confirmation.
- Imported workflow packages remain supported, including dependency checking and installation planning.

## Interaction design

### Online discovery and installation

1. The user describes an outcome, such as `make a customer proposal PPT`.
2. Discover returns matching workflows and skills from configured Codex marketplaces and GitHub community sources.
3. Each result states source, purpose, last update, popularity signals, required skills, permissions, compatibility, local readiness, and risk status.
4. Marketplace results may be installed after a plan preview.
5. Community GitHub results are first scanned into a review record. Only repositories that have a clear skill manifest, recent maintenance, no obvious high-risk install pattern, and a compatible dependency plan can offer installation.
6. The user reviews dependencies, affected local paths, conflicts, and backup behavior, then confirms. The application installs, rescans local skills, and records the outcome.

### My Tools and tags

1. Users switch between `All`, built-in business tags, and custom tags.
2. A tag editor creates and manages customer-defined categories without editing the underlying Skill files.
3. Each Skill can have multiple tags and appears in every matching category.
4. Skill rows keep source, technical details, and a management action; the category names stay business-oriented.

### Planning workspace

1. The user enters tasks in a Today or This Week input, or uses voice input after granting microphone permission.
2. The system turns free text into editable task cards with suggested category, priority, estimate, and time slot.
3. The user can edit text, time, and priority, mark work complete, or create custom milestones.
4. The planner may recommend a matching installed workflow, but never starts it automatically.

### Maintenance action center

1. The user selects one of the three summary cards.
2. The selected card receives an active state and an inline panel appears below the card row.
3. The panel explains the status in plain language and offers only relevant next steps.
4. For a conflict, `Generate repair plan` opens the existing confirmation dialog. The dialog lists the exact operations, locations, impact, risk, and backup before exposing `Confirm`.
5. On confirmation, the existing plan application mechanism runs and reports success or failure through the current notice/error channel.

## Safe defaults

- Scanning remains read-only.
- No conflict is changed automatically.
- When multiple copies share an ID, the recommendation retains the highest-precedence record and identifies every affected path.
- Marketplace installation is limited to official or user-configured Codex marketplaces.
- Community GitHub repositories can be recommended, but they must pass review before installation becomes available.
- No repository, Skill, workflow, update, deletion, or repair runs automatically.
- Every mutation exposes a plan, waits for confirmation, and creates a recovery point where managed files are changed.
- Voice transcription requires microphone permission and always has a typed-input fallback.

## Data and component changes

- A shared local capability store is the single source of truth for scanned skills, tags, source metadata, compatibility, and installed versions.
- `MaintenancePage` derives duplicate groups from `SkillRecord[]`, owns the selected health-card state, and renders panels for `tools`, `conflicts`, or `restore`.
- The Discover IPC service is separate from the local scanner: it gathers marketplace and GitHub metadata, normalizes it to a common recommendation shape, and never installs during search.
- The installation service converts one selected recommendation into the existing plan/confirmation workflow, then delegates to the appropriate Codex marketplace or managed-skill installer.
- The planner persists its user-owned tasks independently from skill metadata and sends only an optional workflow recommendation to Discover.
- Existing `onScan`, `onPreviewRepair`, `onNotice`, and plan-dialog behavior remain the UI safety boundary and are extended rather than bypassed.

## Empty states

- No conflicts: show `No duplicate skills were found; no action is required.`
- No enabled skills: link to scan or My Tools rather than showing an empty action list.
- No recovery manifests: explain that a recovery point is created before a confirmed managed change.
- No online result: explain which sources were searched and offer a broader query rather than presenting local demo results as online results.
- A community source that fails review remains visible with its failure reason and has no installation control.
- If microphone permission is denied, the planning input remains usable through text entry.

## Verification

- Unit/rendering tests prove all three maintenance cards open the matching panel.
- Tests prove a duplicate group exposes `Generate repair plan` and invokes the supplied callback only after the user clicks it.
- Tests prove business tags, custom tags, and multi-tag assignment filter local skills correctly.
- Tests prove task extraction always leaves the user with editable results and microphone denial falls back to typed input.
- Tests prove online recommendations are labeled with their source, community review state, and installation eligibility.
- Tests prove installation cannot execute until a reviewed plan is confirmed.
- Run the full Vitest suite, TypeScript checks, and production Vite build.

## Out of scope

- Autonomous installation, repair, deletion, or workflow execution.
- Searching arbitrary sites beyond configured marketplaces and GitHub repositories.
- Silent microphone access or background recording.
- Remote account synchronization, team collaboration, billing, or cloud backup.
