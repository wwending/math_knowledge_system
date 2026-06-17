# AGENTS.md

## Role

You are the code executor for this project, not the architect.

The human user is the project owner. ChatGPT web is used as the project mentor and architecture reviewer.

## Project Snapshot

This is a high-school math OCR + LLM knowledge-tagging and question-bank system.

- Backend: FastAPI (Python)
- Frontend: Vue 3 + Vite
- Database: SQLite (development primary)
- Backend layers: `api` / `models` / `schemas` / `services` / `db` / `core`
- Frontend source: `frontend/src` (views, components, router, config, utils, assets)

## Current Architecture Context

**Read this before making any code change.**

- `/api/v1/recognize` is the current stable main pipeline. The frontend `Dashboard.vue` depends on it.
- Draft pipeline (`POST /api/v1/drafts`, etc.) is a backend-side capability only. It is NOT the frontend main pipeline.
- Do NOT rewrite, replace, or delete `/api/v1/recognize` unless the task explicitly says so.
- Do NOT switch `Dashboard.vue` to the draft pipeline unless the task explicitly says so.
- Do NOT promote draft to "main pipeline" in documentation or code comments.

## Test Convention

**Backend changes** — run from `backend/` directory:

```
python -m compileall app
python -m unittest discover tests
```

**Frontend changes** — run from `frontend/` directory:

```
npm run build
```

**Documentation-only changes** — no code tests needed, but the Completion Report must state "文档修改，未运行代码测试".

If `tests/` directory or specific test files do not exist on the current branch, report that in the Completion Report. Do not fabricate test results.

## Hard Rules

- Do not make unrelated changes.
- Do not refactor unless explicitly requested.
- Do not modify frontend files unless the task explicitly says so.
- Do not change database models unless the task explicitly allows it.
- Keep each task small.
- Add or update tests for backend behavior changes.

### Explicitly Do Not (without explicit task instruction)

- Do not delete `/api/v1/recognize`.
- Do not make Draft pipeline the frontend main pipeline.
- Do not add async queue / Celery / Redis or other heavy architecture.
- Do not add batch PDF processing.
- Do not do large-scale directory restructuring.
- Do not modify `Dashboard.vue` or the frontend main page unless the task explicitly says so.
- Do not introduce new heavy dependencies unless the task explicitly says so and you explain why.
- Do not copy the full contents of `docs/STATUS.md` or `docs/DECISIONS.md` into `AGENTS.md`. Reference them instead.

## Directory Overview

- `backend/app/api` — API routes and endpoint definitions
- `backend/app/models` — database models (SQLAlchemy)
- `backend/app/schemas` — Pydantic request/response schemas
- `backend/app/services` — OCR, LLM, and business logic services
- `backend/app/db` — database connection and Base
- `backend/app/core` — config, security, constants, events
- `backend/app/scripts` — admin initialization and utility scripts
- `backend/app/static` — static files served by backend
- `backend/tests` — backend test suite
- `frontend/src` — Vue frontend source (views, components, router, config, utils)
- `docs` — STATUS, DECISIONS, WORKLOG, KNOWN_ISSUES and other project documentation
- `scripts` — project-level utility scripts
- `test_data` — test data files
- `test_system` — system-level test fixtures

## Before Starting a Task

**Step 1 — Read these files before every task:**

- `AGENTS.md` (this file)
- `docs/STATUS.md` — current stage status and verification results
- `docs/DECISIONS.md` — why things are decided this way
- `docs/WORKLOG.md` — timeline of rounds and what was done
- `docs/KNOWN_ISSUES.md` — current unresolved boundaries and risks

**Step 2 — Summarize in 5 lines, then wait for user confirmation before editing code:**

1. 当前项目阶段
2. 已完成内容
3. 本项目硬性禁止事项
4. 当前已知风险
5. 你本轮执行任务前需要我提供什么

## Documentation Update Policy

After every non-trivial task, especially implementation, fix, refactor, test, or documentation work, check whether project docs need updating. Do not update every doc every time — only when relevant.

| Doc | When to update |
| --- | --- |
| `docs/WORKLOG.md` | After any non-trivial task (not pure Q&A). Append a round record. |
| `docs/STATUS.md` | Only when stage status, verification results, API status, or main pipeline state changes. |
| `docs/DECISIONS.md` | Only when a new architecture, API, data model, or process decision is made. |
| `docs/KNOWN_ISSUES.md` | Only when a new bug, risk, tech debt, unresolved issue, or workaround is discovered. |
| `README.md` | Only when install, startup, usage, project intro, or external-facing description changes. |
| `AGENTS.md` | Only when agent working rules, test conventions, red lines, or project snapshot changes. |

Rules:

- For non-trivial tasks, `docs/WORKLOG.md` should usually be updated. If it is not updated, explain why in the Completion Report.
- Do not write filler to "look like" docs were updated.
- Do not duplicate the same content across multiple docs.
- If only docs were changed, no code tests are needed — but the Completion Report must state this.

## Completion Report Format

After every task, report in this format:

- **Summary** — one sentence: what was done and why.
- **Modified Files** — list each file and a one-line description of what changed.
- **Tests Run** — which commands were run and their results.
- **Tests Not Run and Why** — if any test scope was skipped, state why.
- **Behavior Changes** — what a user or downstream system would notice differently.
- **Compatibility Notes** — any risk of breaking existing flows, migrations, or API contracts.
- **Docs Updated** — list documentation files updated and why; for non-trivial tasks, usually include `docs/WORKLOG.md`.
- **Docs Not Updated and Why** — explain why other project memory files were not changed.
- **Next Suggested Step** — what to do next (optional, one line).

## Code Comment Rules

When modifying or adding code, add concise comments only in key places.

Do comment:
- Complex business logic or non-obvious control flow.
- State transitions, status guards, and important error branches.
- Data model fields whose meaning is not obvious.
- API contracts, fallback logic, compatibility logic, and side effects.
- Any workaround, temporary solution, or behavior that may surprise future maintainers.

Do not comment:
- Obvious syntax or simple assignments.
- Every line of code.
- What the code already clearly says.

Comment style:
- Prefer short English comments in production code.
- Comments should explain "why" or "what invariant is protected", not merely repeat "what this line does".
- If the logic is hard to explain in one short comment, consider refactoring the code first.



## Python Environment Rules

This project must use the backend local virtual environment.

Before running any backend Python command, first enter:

```powershell
cd D:\math_knowledge_system\backend
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

After activation, verify the Python executable:

```powershell
python -c "import sys; print(sys.executable); print(sys.prefix)"
python -m pip -V
```

The expected Python executable is:

```text
D:\math_knowledge_system\backend\venv\Scripts\python.exe
```

Do not use:

```text
F:\conda\python.exe
```

Do not install project dependencies into the global Conda environment.

All package operations must use:

```powershell
python -m pip ...
```

not plain `pip`.

If `python` does not point to the backend venv, stop immediately and report the environment mismatch instead of modifying code, installing packages, or running tests.
