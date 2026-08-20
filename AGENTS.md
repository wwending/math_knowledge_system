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
   - release or real-service verification -> `docs/MVP_RELEASE_CHECKLIST.md` and smoke docs
   - dependency/security work -> `SECURITY.md`
   - historical investigation only -> search `docs/WORKLOG.md`; do not read the whole file by default
4. Inspect the actual code and tests before making claims about current behavior.

If documentation and code disagree, report the drift and use the task scope to decide whether the code, docs, or both should change. Do not silently rewrite history.

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
- Start implementation from a clean worktree and an up-to-date base when practical.
- Normal task branches must contain the Issue number, for example `feat/issue-123-description`, `fix/issue-123-description`, `chore/issue-123-description`, `docs/issue-123-description`, or `deploy/issue-123-description`. Do not rename historical branches solely to apply this rule retroactively.
- Do not use `git push --force`, `git reset --hard`, destructive `git clean`, or rewrite shared history unless the user explicitly asks and the consequences are understood.
- Do not amend or squash existing shared commits without explicit instruction.
- Prefer logical commits with meaningful messages.
- After implementation, push only the task branch and create/update a Draft PR unless the user asks for a different workflow.
- Every normal PR must link at least one existing Issue in this repository with a GitHub closing keyword. Use `Closes #123` by default; `Fixes #123` and `Resolves #123` are also accepted. `Addresses #123` alone does not satisfy this rule because it does not express automatic closure after merge.
- Before creating a Draft PR, confirm that the Issue exists, its number is correct, the PR body contains the closing relationship, and the PR scope matches the Issue scope.
- Do not mark a PR ready, approve it, enable auto-merge, or merge it unless explicitly requested.
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
