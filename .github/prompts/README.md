# Taghag Prompt Library

This directory stores reusable agent prompts for Taghag.

Filename template:
- `taghag-<order>-<scope>.prompt.md`

Naming rules:
- Start with `taghag-`.
- Use a two-digit ordering slot such as `00`, `01`, `02`.
- Use a short kebab-case scope name.
- End with `.prompt.md`.

Examples:
- `taghag-00-master-implementation-plan.prompt.md`
- `taghag-03-import-cli.prompt.md`
- `taghag-09-verification-checklist.prompt.md`

Current prompt set:
- `taghag-00-master-implementation-plan.prompt.md`
- `taghag-01-repo-layout.prompt.md`
- `taghag-02-first-migration.prompt.md`
- `taghag-03-import-cli.prompt.md`
- `taghag-04-postman-evidence.prompt.md`
- `taghag-05-web-types-and-client.prompt.md`
- `taghag-06-react-vite-ui-shell.prompt.md`
- `taghag-07-tests.prompt.md`
- `taghag-08-clean-room-audit.prompt.md`
- `taghag-09-verification-checklist.prompt.md`
- `taghag-10-definition-of-done.prompt.md`

When adding a new prompt, follow the same filename template so the order and intent stay obvious in both GitHub and local agent sessions.
