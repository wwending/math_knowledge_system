# Engineering Workflow

## Environment roles

### Windows workstation

Primary coding environment.

Responsibilities:

- feature/fix development;
- local backend/frontend tests;
- Git branch/commit/push;
- Draft PR creation and iteration.

Non-responsibilities:

- authoritative Docker/Linux runtime validation;
- Demo deployment.

### Staging Debian server

Integration environment used when a change needs real Linux/Docker/runtime validation.

Responsibilities:

- test an exact PR/head commit under Linux + Docker;
- real Compose/network/volume/Nginx/Gotenberg validation when relevant;
- requested real Baidu OCR + LLM smoke tests;
- migration and backup rehearsal when relevant;
- deployment script validation.

### Demo Debian server

Production-like demonstration environment used only when intentionally deploying a reviewed release candidate or merged commit.

Responsibilities:

- run only reviewed/validated commits;
- practice backup, migration, exact-SHA deployment, health checks, smoke tests, and rollback discipline when a Demo deployment is actually requested.

## Normal change flow

```text
Issue / task
  -> local task branch
  -> local focused tests
  -> push branch
  -> Draft PR
  -> GitHub Actions
  -> Staging exact-SHA validation [when runtime/integration dependent]
  -> review + fixes
  -> merge main
  -> Demo exact-SHA deployment [when intentionally releasing to Demo]
```

Documentation-only, governance-only, or other non-runtime changes normally do not require Staging or Demo deployment unless they change executable deployment commands, runtime contracts, infrastructure behavior, or release evidence.

## Branch naming

Use one intent per branch:

- `feat/...`
- `fix/...`
- `refactor/...`
- `test/...`
- `docs/...`
- `chore/...`
- `security/...`
- `deploy/...`

## PR lifecycle

### Draft PR

Use while implementation or validation is incomplete.
The PR description must explicitly list unverified items, especially real Docker/external-service tests unavailable on Windows.

### Ready for review

Only after:

- implementation is complete for the stated scope;
- relevant local checks pass;
- GitHub Actions pass;
- required Staging integration evidence is available for runtime-dependent changes;
- known blockers are documented.

### Merge

Merge is a human-controlled release decision, not an automatic consequence of green tests.

## Exact-SHA principle

Every Staging test report and every Demo deployment report should record the exact commit SHA tested/deployed.
Branch names such as `main` or `feat/foo` are moving references and are not sufficient deployment evidence.

## GHCR release images

After a change is merged to `main`, the release image workflow builds the backend and web images once and pushes them to GitHub Container Registry with the full Git commit SHA as the immutable-style tag:

- `ghcr.io/wwending/math-knowledge-backend:<full-sha>`
- `ghcr.io/wwending/math-knowledge-web:<full-sha>`

The workflow records each pushed digest and preserves the same SHA in the OCI revision metadata. Production-like deployment selects those backend and web images by the checkout's full Git SHA, pulls them from GHCR, verifies their OCI revision before backup or migration, and records the pulled RepoDigests in the deployment report. The server does not rebuild application images and does not fall back to a local build if pull fails. In short: `main -> build once -> GHCR -> Staging/Demo pull`. A checkout can therefore be deployed only after its `main` publish workflow has succeeded; GHCR authentication, when required, remains an administrator preflight responsibility.

## Validation layers

### Layer 1 — local

Fast feedback:

- compile/syntax;
- backend pytest;
- frontend contract/security tests;
- frontend production build;
- diff inspection.

### Layer 2 — GitHub Actions

Independent clean-environment gate:

- backend tests;
- frontend install/contracts/build;
- dependency review;
- Compose/shell/image-build checks currently defined in workflows.

### Layer 3 — Staging (when required)

Use for changes whose correctness depends on real Linux/Docker/runtime behavior, including as relevant:

- container startup/health;
- networking/volumes/permissions;
- Nginx routing;
- Gotenberg/PDF;
- Alembic migration;
- backup/restore rehearsal;
- real Baidu OCR/LLM smoke when explicitly required.

Do not require Staging merely as a ritual for documentation-only or other changes with no runtime/integration dependency.

### Layer 4 — Demo (when intentionally deploying)

Minimal post-deploy verification proving the intended artifact/SHA is actually healthy in the production-like environment.

Do not deploy every merged PR to Demo automatically. Demo deployment is an explicit release/deployment action.

## Project-local Codex rules

Project-wide instructions live in the repository-tracked root `AGENTS.md`.
Checkout-specific instructions for Windows, Staging, or Demo belong in a root `AGENTS.override.md` inside that checkout and are intentionally ignored by Git.

Do not place `math_knowledge_system`-specific instructions into global `~/.codex/AGENTS.md` or `~/.codex/AGENTS.override.md` as part of this project workflow.

## Documentation ownership

- `STATUS.md`: compact current state, not a chronological diary.
- `DECISIONS.md`: durable decisions only.
- `KNOWN_ISSUES.md`: active unresolved issues only.
- `WORKLOG.md`: history; archive/split when it becomes unwieldy.
- PRs/commits: detailed change evidence; do not duplicate every detail into all docs.

## Definition of done for a normal PR

A normal PR is done when:

- scope is complete and unrelated changes are absent;
- regression tests exist for meaningful behavior changes;
- relevant local checks pass;
- required CI passes;
- environment-specific unverified items are either tested in Staging when required or explicitly documented;
- migration/deployment impact is stated;
- active known risks are recorded in the correct place;
- PR is reviewable and reversible at a reasonable cost.
