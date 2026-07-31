# Button interactions

## Goal

Every visible action button in the toolbox either navigates to the relevant page, invokes its existing local action, or gives a clear in-app response.

## Scope

- After a search, move focus to the recommendation section and show a success notice.
- Dashboard actions navigate to My Tools or Workflows.
- Tool management and workflow opening show a concise in-app notice.
- Maintenance actions open the existing safe repair-plan dialog.
- Existing scan, import, export, and confirmation flows remain unchanged.

## Constraints

- No new dependencies or external services.
- No destructive action is performed without the existing confirmation dialog.
- Buttons that are purely visual filters are not added until filtering behavior is defined.

## Verification

- Renderer tests cover search feedback and dashboard navigation.
- The full test suite and packaged build must pass.
