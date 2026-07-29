# Task 10 Report — Home Portal

## Outcome

Added a dedicated full-viewport homepage that is visually and structurally separate from the five functional business pages.

- Five tall native-button chapter leaves map to 总览、发现、工作流、我的工具、维护中心.
- The homepage uses an original black-stage book journey: white paper leaves progressively increase in height and width while unfolding toward a final open page.
- Each chapter carries its own CSS-only geometric traveler pose, creating a human progression across the journey. All five figures are `aria-hidden` and pointer-transparent.
- The final open leaf uses a restrained aqua edge and figure highlight; the other pages stay monochrome.
- Clicking a door holds the homepage in a selected page-turn state for 820 ms, then opens the corresponding existing page.
- The turn uses perspective, an edge transform origin, front/back faces, a shadow sweep, and slow-fast-slow `cubic-bezier(0.16, 0.72, 0.16, 1)` keyframes.
- `prefers-reduced-motion: reduce` skips the staged turn and navigates immediately.
- Existing internal pages retain their sidebar, topbar, and functional business UI; the portal composition appears only on the homepage.
- The renderer document declares `lang="zh-CN"` and `translate="no"` so browser translation cannot rewrite accessible portal labels and invalidate a pending click target.
- No external image, copied source asset, or new dependency was added.

## TDD evidence

### Cycle 1 — Portal controls and navigation

Test:

`keeps five Chinese portal controls stable and opens 工作流 exactly`

RED:

```text
Test Files  1 failed (1)
Tests       1 failed | 4 skipped (5)

Unable to find an accessible element with the role "navigation"
and name "工具箱入口"
```

GREEN:

```text
Test Files  1 passed (1)
Tests       1 passed | 4 skipped (5)
```

The test scopes to the portal navigation, asserts exactly five controls and their ordered accessible names, then verifies 工作流 opens the real existing 工作流 page.

### Cycle 2 — Book page-turn state

Test:

`turns the selected portal door like a page before opening its target`

RED:

```text
Test Files  1 failed (1)
Tests       1 failed | 5 skipped (6)

Expected main to have class "home-portal--turning"
Received "app-main"
```

GREEN:

```text
Test Files  1 passed (1)
Tests       1 passed | 5 skipped (6)
```

The test proves the clicked 工作流 door receives `portal-door--turning`, the homepage remains visible before 820 ms, and the target page appears only after the turn duration.

### Cycle 3 — Reduced motion

Test:

`opens the selected portal target immediately when reduced motion is preferred`

RED:

```text
Test Files  1 failed (1)
Tests       1 failed | 6 skipped (7)

Unable to find the 工作流 page heading because the portal remained
in "home-portal--turning"
```

GREEN:

```text
Test Files  1 passed (1)
Tests       1 passed | 6 skipped (7)
```

The test provides a real `matchMedia` contract with reduced motion enabled and verifies immediate navigation without the portal transition state.

### Cycle 4 — Stable language metadata and exact 工作流 mapping

The Cycle 1 regression was extended to parse the real renderer document before exercising the application.

RED:

```text
Expected document language: "zh-CN"
Received: "en"

Expected translate metadata: "no"
Received: null
```

GREEN:

```text
Test Files  1 passed (1)
Tests       1 passed | 6 skipped (7)
```

Root-cause tracing showed the application mapping was already direct and correct: chapter 03 uses `id: "workflows"`, `navigate` stores that same `PageId`, and `App` renders `WorkflowsPage`. The real Chrome page instead mutated 工作流 to 工作流程 between observations because the Chinese application declared an English document and allowed translation. Correct document metadata prevents that semantic-target race, while the regression also proves the exact 工作流 heading appears and the 发现 heading does not.

## Implementation notes

- `HomePortal.tsx` owns only portal markup, the five destination definitions, and the per-chapter decorative traveler geometry.
- `App.tsx` keeps the homepage/selected-target transition state and preserves the existing internal-page navigation path.
- `index.html` supplies stable Chinese language and translation metadata.
- `styles.css` supplies the paper leaves, progressive perspective/depth, five figure poses, hover/focus transitions, and page-turn keyframes.
- Existing renderer tests now enter 总览 through the portal before exercising unchanged dashboard business behavior.

## Browser preview evidence

The correct worktree server was checked in a real Chrome session:

- 5 portal buttons and 5 decorative traveler figures
- 0 legacy central figure overlays
- exact stable labels: 总览、发现、工作流、我的工具、维护中心
- progressively unfolding leaf geometry with a larger final open page
- after clicking 工作流, the 300 ms state remained `portal-door--workflows`; after 900 ms the heading and active navigation were both 工作流

## Verification

Renderer tests:

```text
Test Files  1 passed (1)
Tests       7 passed (7)
```

Full test suite:

```text
Test Files  8 passed (8)
Tests       39 passed (39)
```

Production build:

```text
TypeScript main build: passed
TypeScript renderer check: passed
Vite production build: passed
```

`git diff --check` completed without whitespace errors.
