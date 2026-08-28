# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues in `wwending/math_knowledge_system`. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body-file <file>`.
- **Read an issue**: `gh issue view <number> --comments`, including its labels.
- **List issues**: use `gh issue list` with appropriate `--label`, `--state`, and JSON filters.
- **Comment on an issue**: `gh issue comment <number> --body-file <file>`.
- **Apply or remove labels**: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- **Close an issue**: only after the project owner's acceptance, following the closure contract in `AGENTS.md` and `docs/ENGINEERING_WORKFLOW.md`.

Infer the repo from `git remote -v`; `gh` does this automatically when run inside the clone.

## Pull requests as a triage surface

**PRs as a request surface: no.**

Pull requests are not included in the triage queue. Normal implementation work remains Issue-first. PRs reference existing issues with `Refs #<issue>` and must not use auto-closing keywords.

GitHub shares one number space across issues and pull requests. Verify a bare `#42` before treating it as an issue.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: an issue labelled `wayfinder:map`, holding Notes, Decisions-so-far, and Fog.
- **Child ticket**: link it to the map as a GitHub sub-issue. If sub-issues are unavailable, use a task list in the map and add `Part of #<map>` to the child.
- **Ticket labels**: `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`.
- **Blocking**: prefer GitHub's native issue dependencies. If unavailable, add `Blocked by: #<n>` at the top of the child.
- **Frontier query**: select the first open, unblocked, unassigned child in map order.
- **Claim**: `gh issue edit <number> --add-assignee @me`.
- **Resolve**: post the result to the issue. Closing still follows this repository's owner-acceptance contract.
