# Task 12 Report — Book Storyboard Interaction

## Outcome

Refined only the approved homepage cover interaction. Child-page components and their visual styling remain unchanged.

- Hover and keyboard focus now pull the matching photographed white page forward and enlarge it.
- The hover treatment uses the page surface plus dark depth shadows; it has no white border, outline box, or white glow.
- Click now exposes the explicit storyboard phases within the existing 820 ms handoff:
  - `selected` at 0 ms
  - `flip-fast` at 140 ms
  - `flip-slow` at 380 ms
  - `child-emerge` at 640 ms
  - settled target child page at 820 ms
- Every flip sheet contains the selected child page's real eyebrow, headline, and supporting copy rather than a blank placeholder.
- The selected page begins with a slower pull-forward, accelerates through the multi-page flip, and decelerates as the spread expands before the child panel emerges.
- The existing reduced-motion path still skips the storyboard and opens the selected child page immediately.

## TDD evidence

The renderer regressions were written before production changes.

RED:

```text
Test Files  1 failed (1)
Tests       2 failed | 7 passed (9)

Expected the element to have class:
  portal-door--pull-forward

Unable to find an accessible element with the role "region"
and name "工作流页面预览"
```

GREEN:

```text
Test Files  1 passed (1)
Tests       9 passed (9)
```

The regressions verify:

- hover enters the pull-forward state;
- the hover contract is depth-only and the approved-cover CSS has a transparent border with dark, not white, shadows;
- click visits `selected`, `flip-fast`, `flip-slow`, and `child-emerge` in order before the target route settles;
- target-specific child-page content is present during both flip phases.

## Verification

Full test suite:

```text
Test Files  8 passed (8)
Tests       41 passed (41)
```

Production build:

```text
TypeScript main build: passed
TypeScript renderer check: passed
Vite production build: passed
approved-homepage-cover-CR4NGSv0.png emitted
```

`git diff --check` completed without whitespace errors.
