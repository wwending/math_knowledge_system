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
GitHub Issue [required]
  -> issue-numbered local task branch
  -> local focused tests
  -> push branch
  -> Draft PR linked with `Closes #<issue>`
  -> PR traceability gate
  -> GitHub Actions
  -> Staging exact-SHA validation [when runtime/integration dependent]
  -> review + fixes
  -> merge main
  -> linked Issue closes
  -> Demo exact-SHA deployment [when intentionally releasing to Demo]
```

Documentation-only, governance-only, or other non-runtime changes normally do not require Staging or Demo deployment unless they change executable deployment commands, runtime contracts, infrastructure behavior, or release evidence.

## Issue-first / Traceability

Normal feature, fix, refactor, test, docs, chore, security, and deploy work starts from a real GitHub Issue. The Issue is the traceability root and records the why: the requirement, defect, or task. It must exist before implementation enters the normal branch and PR publication flow.

The development records have distinct roles:

- Issue: why the change is needed and what outcome is required;
- branch: the isolated implementation workspace, with the Issue number in its name;
- commit: the concrete change history;
- PR: the review, validation, and merge unit, linked with a closing keyword.

Together they form `Issue -> Branch -> Commit -> PR -> Merge`, with each layer traceable to the same Issue. Every normal PR must include a same-repository closing relationship such as `Closes #123` (preferred), `Fixes #123`, or `Resolves #123`. A plain mention such as `Addresses #123` is not sufficient. The automated `PR traceability` check verifies that the referenced target exists, is an Issue rather than a PR, and that at least one valid linked Issue predates the PR.

This policy applies prospectively after the governance change is merged. Historical branches and merged PRs are not renamed or rewritten.

## Branch naming

Use one intent per branch:

- `feat/issue-123-description`
- `fix/issue-123-description`
- `refactor/issue-123-description`
- `test/issue-123-description`
- `docs/issue-123-description`
- `chore/issue-123-description`
- `security/issue-123-description`
- `deploy/issue-123-description`

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

After a change is merged to `main`, the trusted release image workflow builds the backend and web images once and pushes them to GitHub Container Registry with the full Git commit SHA tag:

- `ghcr.io/wwending/math-knowledge-backend:<full-sha>`
- `ghcr.io/wwending/math-knowledge-web:<full-sha>`

The SHA tag remains the source-oriented discovery and traceability handle. The workflow also records each pushed immutable digest and preserves the same SHA in the OCI revision metadata. Production-like deployment requires the backend and web digests from the successful main publisher, pulls exact `repository@sha256:...` references, verifies both OCI revisions equal the checkout SHA, and verifies each local RepoDigest exactly matches the supplied digest before backup or migration. The server does not resolve a deployment digest from a mutable tag, rebuild application images, or fall back to a local build if pull fails.

Artifact promotion is therefore `main -> build once -> SHA-tagged GHCR release artifact + recorded digest -> Staging/Demo deploy by digest`. A checkout can be deployed only after its `main` publish workflow succeeds and the trusted backend/web digests are supplied explicitly. GHCR authentication remains an administrator preflight responsibility. This first-party digest contract does not claim that the third-party Gotenberg image is digest-pinned.

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
- a linked same-repository Issue exists and predates the PR;
- the PR body contains a valid closing relationship, normally `Closes #<issue-number>`;
- the automated `PR traceability` check passes;
- regression tests exist for meaningful behavior changes;
- relevant local checks pass;
- required CI passes;
- environment-specific unverified items are either tested in Staging when required or explicitly documented;
- migration/deployment impact is stated;
- active known risks are recorded in the correct place;
- PR is reviewable and reversible at a reasonable cost.
