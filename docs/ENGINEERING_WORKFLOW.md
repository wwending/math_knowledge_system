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

Integration environment.

Responsibilities:

- test an exact PR/head commit under Linux + Docker;
- real Compose/network/volume/Nginx/Gotenberg validation;
- requested real Baidu OCR + LLM smoke tests;
- migration and backup rehearsal;
- deployment script validation.

### Demo Debian server

Production-like demonstration environment.

Responsibilities:

- run only reviewed/validated commits;
- practice backup, migration, exact-SHA deployment, health checks, smoke tests, and rollback discipline.

## Normal change flow

```text
Issue / task
  -> local task branch
  -> local focused tests
  -> push branch
  -> Draft PR
  -> GitHub Actions
  -> Staging deploy exact PR HEAD SHA
  -> real integration/smoke evidence
  -> review + fixes
  -> merge main
  -> resolve merged main SHA
  -> Demo backup/preflight
  -> Demo deploy exact SHA
  -> Demo health + minimal smoke
```

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

Every Staging and Demo report should record the exact commit SHA tested/deployed.
Branch names such as `main` or `feat/foo` are moving references and are not sufficient deployment evidence.

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

### Layer 3 — Staging

Real runtime gate:

- container startup/health;
- networking/volumes/permissions;
- Nginx routing;
- Gotenberg/PDF when relevant;
- Alembic migration when relevant;
- real Baidu OCR/LLM smoke when explicitly required.

### Layer 4 — Demo

Minimal post-deploy verification proving the intended artifact/SHA is actually healthy in the production-like environment.

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
- environment-specific unverified items are either tested in Staging or explicitly documented;
- migration/deployment impact is stated;
- active known risks are recorded in the correct place;
- PR is reviewable and reversible at a reasonable cost.
