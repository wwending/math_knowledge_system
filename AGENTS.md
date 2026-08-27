# AGENTS.md

## Purpose

This file is the repository-level operating contract for coding agents working on `math_knowledge_system`.
Keep this file concise. Current project facts live in `docs/`.

Project-specific machine/checkout rules belong in a repository-root `AGENTS.override.md`, which is intentionally ignored by Git. Do not require `math_knowledge_system`-specific rules in the user's global Codex home.

## Authority and instruction order

- The human user is the project owner and final decision maker.
- Follow direct user instructions for the current task unless they conflict with safety or an explicit repository invariant.
- Do not treat historical notes as current truth when they conflict with newer `docs/STATUS.md` or newer decisions.
- Do not duplicate large amounts of project history into this file.

## Project map

- `backend/` — FastAPI, SQLAlchemy, Alembic, OCR/LLM services, tests.
- `frontend/` — Vue 3 + Vite + Element Plus frontend and frontend contract/security tests.
- `deploy/` + `compose.prod.yml` — production-like single-server deployment assets.
- `docs/` — project state, decisions, work history, known issues, API and release/smoke documentation.
- `.github/workflows/` — CI and dependency-review gates.

## Sources of truth

Before a non-trivial task:

1. Read `docs/STATUS.md` for the current state and release checkpoint.
2. Read `docs/KNOWN_ISSUES.md` for active risks relevant to the task.
3. Read only the other documents relevant to the task:
   - development / Git / PR / Staging / Demo workflow -> `docs/ENGINEERING_WORKFLOW.md`
   - architecture / API / data-model / process change -> `docs/DECISIONS.md`
   - deployment / migration / backup / rollback -> `deploy/README.md` and relevant deployment docs/scripts
   - public API behavior -> `docs/API.md`
   - troubleshooting / observability / evidence locations -> `docs/TROUBLESHOOTING.md`
   - release or real-service verification -> `docs/MVP_RELEASE_CHECKLIST.md` and smoke docs
   - dependency/security work -> `SECURITY.md`
   - historical investigation only -> search `docs/WORKLOG.md`; do not read the whole file by default
4. Inspect the actual code and tests before making claims about current behavior.

If documentation and code disagree, report the drift and use the task scope to decide whether the code, docs, or both should change. Do not silently rewrite history.

## Domain terminology

- **原始页图**：用户上传的完整页面图片。
- **题目区域图**：从原始页图裁出的、包含一道完整题目的区域。
- **题目配图**：题目区域中的图形、表格或几何图片。
- **图形检测框**：在源图上定位题目配图的 bbox。
- **裁剪坐标**：相对于源图的归一化或像素坐标，用于裁出区域。
- **图文排版坐标**：题目画布中配图相对于文字的布局位置和尺寸。
- 编辑图形检测框不等于编辑题内图文排版；两者属于不同语义和功能边界。

## Product invariants

Unless the user explicitly asks to change them:

- The primary product flow is the Draft-confirmation flow documented in current `docs/STATUS.md`.
- OCR/LLM output must not silently become authoritative question-bank data without the existing user-confirmation boundary.
- LLM cleanup must preserve mathematical meaning; do not add missing conditions, solve the problem, replace variables/point names, or "repair" uncertain OCR by guessing a common problem pattern.
- User ownership/data isolation checks are security boundaries, not convenience checks.
- Paper/question snapshots must preserve historical output semantics when later source questions change.
- Do not introduce Redis, Celery, Kubernetes, PostgreSQL, or other heavy infrastructure merely for architectural neatness. Add infrastructure only when a concrete requirement justifies it.

## Task modes

### Analysis / review / audit

When the user asks to inspect, review, explain, audit, compare, or plan:

- Work read-only by default.
- Read-only work may use the permanent local Control Checkout because it does not change repository, index, or working-tree state.
- Do not edit files, commit, push, create PRs, deploy, migrate, or change machine configuration unless explicitly requested.

### Implementation / fix / refactor

When the user explicitly asks to implement, fix, modify, or refactor:

- You may edit files in scope, add/update tests, run safe local checks, commit to a task branch, push that branch, and create/update a Draft PR.
- Do not stop merely to ask for routine confirmation if the requested implementation is clear.
- Keep the patch narrowly scoped. Do not opportunistically rewrite unrelated code.

## Changes that require explicit authorization

Unless already explicitly requested by the user, stop and ask before:

- adding a new production dependency or external runtime service;
- changing database models or creating a new Alembic migration;
- making a breaking public API/schema change;
- changing authentication, authorization, registration policy, secret handling, or user-isolation semantics;
- deleting persistent/user data or resetting a database;
- modifying firewall, SSH, systemd, Docker daemon, host networking, or OS packages;
- reading or printing secret values;
- merging a PR, tagging/releasing, or deploying to the Demo/production-like server.

If the user explicitly requested one of these actions, do not ask a second time solely because it appears in this list; still perform preflight checks and report risks.

## Git and PR workflow

- Normal feature, fix, refactor, test, docs, chore, security, and deploy work is Issue-first. Before implementation, confirm that a real GitHub Issue already exists as the task's traceability root; use an Issue supplied by the user, and do not invent a meaningless Issue merely to satisfy the workflow.
- If no Issue exists, do not enter the normal branch/PR publication flow. The Issue should describe the requirement, defect, or task before implementation begins.
- The permanent local Control Checkout is management/reference-only. Do not implement normal writable Issue work there.
- Every writable Issue uses one Issue-numbered task branch, one linked dedicated worktree, and one Codex. Do not run concurrent repository or file writers in the same worktree.
- A writable Task Worker must start as a new Codex process rooted in its dedicated worktree. Changing an existing Control Codex's shell directory does not transfer workspace or sandbox ownership.
- The local launcher may provision and start that Worker, but it must reject overlapping linked-worktree paths and couple the exclusive per-worktree lease to the complete Worker process-tree lifetime. A surviving Worker tree must never coexist with available ownership. Orchestration is not permission to bypass isolation.
- Before writable work, confirm the Issue, designated branch and dedicated path, actual repository root, checked-out branch, intended base/HEAD, worktree inventory, clean working state, absence of unrelated changes, and expected directory ownership. Confirm there is no evidence that another Agent or external process is writing the same worktree.
- If the branch or worktree mapping is wrong, ownership is unexpected, unknown files or unrelated changes appear, another Agent is active there, or repository state changes externally, stop repository writes and report the evidence.
- Do not repair unknown or foreign work with `git reset --hard`, destructive `git clean`, `git stash`, checkout/switch over it, overwrite, force push, or worktree deletion. Preserve it until its owner decides what to do.
- Never develop directly on `main`.
- Every git command must explicitly target its repository or worktree with `git -C <path>`; never rely on the current shell working directory. Shell CWD can be silently reset, left stale by removed directories, or parked in the wrong checkout, so a correct command run from the wrong directory writes to the wrong repository. Real incident: 2026-08-23, a commit intended for an issue worktree landed on local `main` because CWD had been silently reset. Examples: `git -C D:\math_knowledge_system-worktrees\issue-123-slug status`, `git -C D:\math_knowledge_system pull --ff-only origin main`.
- Start implementation from a clean worktree and an up-to-date base when practical.
- Normal task branches must contain the Issue number, for example `feat/issue-123-description`, `fix/issue-123-description`, `chore/issue-123-description`, `docs/issue-123-description`, or `deploy/issue-123-description`. Do not rename historical branches solely to apply this rule retroactively.
- Do not use `git push --force`, `git reset --hard`, destructive `git clean`, or rewrite shared history unless the user explicitly asks and the consequences are understood.
- Do not amend or squash existing shared commits without explicit instruction.
- Prefer logical commits with meaningful messages.
- Commit messages must not include AI assistant attribution trailers such as `Co-Authored-By: Claude`. Committer/author metadata stays as the real account; traceability lives in the Issue -> Branch -> Commit -> PR chain, not in commit trailers.
- After implementation, push only the task branch and create/update a Draft PR unless the user asks for a different workflow.
- Every normal PR must link at least one existing Issue in this repository with a non-closing reference: `Refs #123` by default; a plain `#123` mention is also accepted. Closing keywords (`Closes`, `Fixes`, `Resolves` before an Issue number) are forbidden in PR titles and bodies and rejected by the `PR traceability` check, because merging must never auto-close an Issue.
- Every `#<number>` in a PR title or body (code spans/fences are ignored) is resolved through the GitHub API by the `PR traceability` check and must be an existing Issue created before the PR; a number that resolves to another Pull Request fails the check (`Linked target #N is a Pull Request, not an Issue.`). Real recurring incident: 2026-08-25, a PR body cited a previously merged PR's number and broke the gate. Issues and Pull Requests share one number sequence, so `#N` alone does not reveal which object it resolves to; verify every number resolves to an Issue before writing it into a PR title or body. Squash-merge commit titles end with `(#<pr-number>)`: that trailing number is the PR, not the Issue, and citing it in another PR's description breaks the gate. To refer to prior work, cite its Issue number, never its PR number.
- Before creating a Draft PR, confirm that the Issue exists, its number is correct, the PR body contains the `Refs #<issue>` link, every `#<number>` in the title/body points to an Issue rather than another PR, and the PR scope matches the Issue scope.
- Do not mark a PR ready, approve it, enable auto-merge, or merge it unless explicitly requested.
- Merging a PR does not close its Issue. After merge, the implementing agent posts one implementation-report comment on the Issue (what changed, root cause for fixes, tests run/not run, concrete acceptance steps with pass criteria) as defined in `docs/ENGINEERING_WORKFLOW.md`. Only the user's acceptance closes an Issue: manual close with a short evidence comment; batch acceptance across Issues is normal. Acceptance failures go back as Issue comments and the Issue stays open or is reopened.
- PR descriptions must state: scope, architecture/behavior changes, tests run, tests not run, deployment/migration impact, and known risks.
- Keep checkout-specific Codex instructions in root `AGENTS.override.md`; do not commit that file or move these project-specific rules into global `~/.codex` configuration.

## Test contract

Run the smallest relevant checks during iteration, then the appropriate final checks for touched areas.

### Backend changes (`backend/`)

From `backend/` using the project Python environment:

```text
python -m compileall app
python -m pytest -q
```

Add focused pytest coverage for behavior changes. Automatic tests must not require real Baidu OCR or real LLM credentials/network calls.

### Frontend changes (`frontend/`)

Normally run:

```text
npm run test:stage3-contract
npm run build
```

For dependency/lockfile/install-chain changes also run a clean install with the repository's safe install policy and the security install-script check documented by CI/`SECURITY.md`.

### Deployment changes

- Validate shell/Compose/build behavior in CI and/or the Staging Docker host.
- Windows local development is not expected to prove Docker runtime behavior.
- A mocked unit test is not a substitute for an explicitly required real-service smoke test.

### Documentation-only changes

- Do not run expensive unrelated test suites merely to satisfy a ritual.
- Run targeted validation if the documentation contains executable commands/contracts that were changed.
- State clearly what was and was not run.

Never fabricate test results. Distinguish `passed`, `failed`, `not run`, and `not available in this environment`.

## External-service tests

- Real Baidu OCR, LLM, email, or other paid/remote API calls require a task that explicitly includes real integration/smoke testing.
- Never print credentials or raw secrets.
- Prefer test fixtures/mocks for automatic CI.

## Documentation policy

Documentation is a system of record, not a mandatory copy target for every patch.

- `docs/STATUS.md` — current state only. Update when the current stage, supported flow, verification state, or release checkpoint changes. Do not append every minor task forever.
- `docs/DECISIONS.md` — durable architecture/API/data/process decisions and their rationale/boundaries. Do not log ordinary bug fixes here.
- `docs/KNOWN_ISSUES.md` — active unresolved bugs, risks, tech debt, and temporary workarounds. Remove or archive items once resolved instead of keeping them as active issues.
- `docs/WORKLOG.md` — chronological engineering history. Append a concise entry for meaningful engineering work when useful; avoid duplicating full PR descriptions or test logs.
- `README.md` — user/developer-facing project introduction, setup, startup, and usage only.
- `SECURITY.md` — durable security/dependency handling policy.

For every non-trivial task, decide which docs actually changed semantically. If none need updating, say why in the completion report. Do not write filler.

## Code quality rules

- Prefer existing abstractions and patterns over parallel implementations.
- Preserve API and persistence compatibility unless the task explicitly changes the contract.
- Avoid large refactors mixed into feature/fix PRs.
- Comments should explain invariants, security boundaries, compatibility decisions, non-obvious control flow, or temporary workarounds—not restate syntax.
- Validate untrusted input at boundaries and keep resource use bounded for parsing/rendering paths.

## Code review rules

Prioritize findings that can cause:

1. authorization/data-isolation failures;
2. data corruption or irreversible migration/rollback problems;
3. secret exposure, injection, SSRF/XSS, unsafe rendering, or unbounded resource consumption;
4. broken OCR/LLM fidelity or silent question-content mutation;
5. API/DB compatibility regressions;
6. deployment/runtime failures not covered by the claimed validation;
7. missing regression tests for meaningful behavior changes.

Do not spend review bandwidth on style nits already enforced by tools unless they hide a correctness problem.

## Completion report

End implementation tasks with:

- **Summary** — what changed and why.
- **Modified Files** — concise list.
- **Tests Run** — exact commands and results.
- **Tests Not Run** — and why.
- **Behavior / Compatibility** — user-visible or contract changes.
- **Migration / Deployment Impact** — `none` if none.
- **Docs Updated** — and why; or why none were needed.
- **Known Risks / Follow-up** — only real remaining items.
- **Git / PR State** — branch, commit(s), push/PR status when applicable.
- **Issue State** — left open pending user acceptance (default), or closed with evidence when acceptance already happened.
