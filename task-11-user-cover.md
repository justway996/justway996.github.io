# Task 11 Report — Approved User Cover

## Outcome

Replaced the generated homepage artwork with the approved user-supplied cover while keeping the five existing destinations and child pages unchanged.

- Copied the approved source image to the versioned renderer asset `src/renderer/assets/approved-homepage-cover.png`.
- Rendered the complete 16:9 composition with `object-fit: contain`, so the artwork is not cropped.
- Masked only the left black narrative region and rebuilt its copy as three native editable text fields.
- Seeded profession-neutral defaults:
  - `我的工作成长之旅`
  - `A PROFESSIONAL'S GROWTH JOURNEY`
  - `持续探索，持续成长，找到属于自己的工作路径。`
- Kept exactly five keyboard-accessible buttons, aligned over the five photographed book pages: 总览、发现、工作流、我的工具、维护中心.
- Preserved the existing 820 ms route handoff and reduced-motion immediate navigation.
- Added the approved phased book sequence: hover/focus outline and lift, held emphasis, selected-page pull forward, click lock, fast blurred page stack, slowed spread, cover fade, then the existing child-page emergence and stabilization.
- Did not modify any child-page component or child-page styling.

## TDD evidence

The new renderer regressions were written before the production change.

RED:

```text
Test Files  1 failed (1)
Tests       3 failed | 5 skipped (8)

Unable to find an accessible element with the role "img"
and name "个人工具箱首页封面"

Unable to find an accessible element with the role "textbox"
and name "中文标题"

Expected data-hovered-page="workflows"
Received null
```

GREEN:

```text
Test Files  1 passed (1)
Tests       3 passed | 5 skipped (8)
```

The regressions verify:

- the approved cover asset is rendered;
- the portal still contains exactly five buttons with the expected ordered accessible names;
- editing the Chinese title, English subtitle, and supporting copy updates the rendered fields;
- hovering a book page applies the selected state;
- clicking enters the turning phase before the target child page appears.

## Verification

Full test suite:

```text
Test Files  8 passed (8)
Tests       40 passed (40)
```

Production build:

```text
TypeScript main build: passed
TypeScript renderer check: passed
Vite production build: passed
approved-homepage-cover-CR4NGSv0.png emitted
```

`git diff --check` completed without whitespace errors.
