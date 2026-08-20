# Engineering Workflow

## Environment roles

### Windows workstation

Primary local host environment. Writable development happens only in dedicated Task Worktrees.

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

## Local checkout roles

### Control Checkout

`D:\math_knowledge_system` is the permanent local Control Checkout. It is management/reference-only: use it to inspect repository state, list or create linked worktrees, fetch deliberate updates, and perform read-only analysis/review/audit. Normal writable Issue implementation must never happen there.

### Task Worktree

Every writable feature, fix, refactor, test, docs, chore, security, or deploy Issue uses exactly one Issue-numbered task branch, one linked dedicated worktree, and one Codex. The Windows path convention is:

```text
D:\math_knowledge_system-worktrees\issue-<number>-<description>
```

The task prompt should identify the Issue, branch, dedicated path, and intended base. Only that task's Codex may write repository files or Git state in the Task Worktree; concurrent repository/file writers must not share it. Read-only analysis, review, and audit remain allowed in the Control Checkout and do not require a Task Worktree.

Linked worktrees isolate each checkout's `HEAD`, index, and working files. They are not a VM, container, permission, or process security boundary: linked worktrees still share repository objects, refs, remotes, and most repository configuration. Avoid unnecessary remote, shared-ref, repository-configuration, global-configuration, or shared-history mutations, and never use them to work around an ownership or workspace mismatch.

### Control launcher and Worker startup

`scripts/codex-issue-worker.ps1` is the thin local handoff layer between the Control Codex and a writable Worker Codex. It accepts explicit Issue, branch, dedicated worktree, base, repository identity, and task-prompt inputs; validates the Control Checkout and linked-worktree inventory; resolves the base to an exact commit; safely creates or reuses the expected branch/worktree; and starts a new Worker process whose process cwd and Codex workspace are both the dedicated Task Worktree.

The launcher does not implement the Issue, maintain a service or task queue, merge, deploy, or clean up worktrees. Its scope is `provision -> isolate -> launch -> observe`. A shell `cd` performed by the existing Control Codex is not a substitute for the new `codex exec -C <dedicated-worktree>` process because it does not reinitialize the original process's workspace and sandbox ownership.

Use `-DryRun` first. Dry-run resolves only locally available refs and reports `DRY_RUN_OK` or `BLOCKED`; it does not fetch, create a branch/worktree, launch Codex, commit, or publish. Example:

```powershell
pwsh -NoProfile -File .\scripts\codex-issue-worker.ps1 `
  -IssueNumber 41 `
  -Branch hotfix/issue-41-example `
  -WorktreePath D:\math_knowledge_system-worktrees\issue-41-example `
  -BaseRef origin/main `
  -ExpectedRepository wwending/math_knowledge_system `
  -ControlPath D:\math_knowledge_system `
  -PromptFile D:\tasks\issue-41.txt `
  -DryRun
```

After reviewing that report, omit `-DryRun` to provision and start the Worker. For an `origin/<branch>` base, the write-mode run performs a narrow `git fetch --no-tags origin <branch>` and refuses to continue if the ref changed after preflight; rerun to deliberately accept and record the new SHA. An exact release/deployed commit may be supplied directly as `-BaseRef`. The Control Checkout's current branch, index, dirty files, and working files are never used as the task base and are not switched, stashed, reset, cleaned, or overwritten.

Create-or-reuse is fail closed:

- absent branch and path: create both from the resolved base SHA;
- existing expected branch and exact clean linked worktree: reuse;
- existing unattached expected branch and absent exact path: attach that branch at the exact path;
- branch attached elsewhere, path linked to another branch, or an existing non-worktree path: `BLOCKED`;
- dirty expected worktree: `BLOCKED` unless the caller explicitly supplies `-AllowDirtyIssueWorktree` after recognizing every change as belonging to that Issue; the launcher never cleans, resets, or stashes it.

The Worker prompt is sent over stdin rather than exposed in the command line. It includes the Issue number, branch, exact worktree path, resolved base SHA, recognized working state, ownership boundaries, and a pointer to the repository instructions. Runtime files (`events.jsonl`, stderr, and the final Worker message) are stored under the OS temporary directory by default; `-ResultRoot` is rejected if it points inside the Control Checkout or Task Worktree. Stable terminal statuses include `DRY_RUN_OK`, `PROVISIONED`, `WORKER_STARTED`, `WORKER_SUCCEEDED`, `WORKER_FAILED`, and `BLOCKED`.

The implementation was designed against locally installed `codex-cli 0.148.0` and rechecks the required `exec` capabilities at every run: `-C/--cd`, `--sandbox`, `--approve-for-me`, `--add-dir`, `--json`, and `--output-last-message`. The launch shape is:

```text
codex exec -C <dedicated-worktree> --sandbox workspace-write --approve-for-me --add-dir <git-common-dir> --json -o <temporary-result-file> -
```

The additional writable directory is limited to the repository's shared Git common-dir because linked-worktree commits update shared Git metadata. This does not remove the shared-state risk or authorize unrelated ref/config/history changes. Do not replace this with `danger-full-access` or a bypass mode, and do not modify global Codex security settings. Authentication, PAT, MFA, private keys, and denied approval boundaries remain manual/trusted boundaries.

The current local Codex approval and network setup supports Model A: the Control launcher may require an automatically reviewed host approval to inspect/provision the external sibling worktree, and a Worker may request the same narrow boundary for `git fetch`/`git push`; keyring-backed `gh` operations run outside the sandbox as required by `AGENTS.md`. A restricted offline sandbox identity can otherwise trigger Windows Git dubious-ownership checks, which must remain a `BLOCKED` result rather than being bypassed with a global `safe.directory` change. The Worker, not the launcher, performs any task-authorized commit, push, and Draft PR create/update. If approval, network, or authentication is unavailable, the Worker reports the boundary and stops; the launcher does not weaken security or write through the Control Checkout to compensate.

## Normal change flow

```text
GitHub Issue [required]
  -> issue-numbered local task branch
  -> dedicated linked Task Worktree
  -> one Codex assigned to that worktree
  -> local focused tests
  -> commit
  -> push branch
  -> Draft PR linked with `Closes #<issue>`
  -> PR traceability gate
  -> GitHub Actions
  -> Staging exact-SHA validation [when runtime/integration dependent]
  -> review + fixes
  -> merge main
  -> linked Issue closes
  -> Demo exact-SHA deployment [when intentionally releasing to Demo]
  -> safe Task Worktree retirement
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

Ordinary work normally creates its issue-numbered branch and Task Worktree from the current `origin/main`. A production/Demo hotfix may deliberately start from either `origin/main` or the exact deployed/release SHA; record that selected base rather than assuming the newest branch tip is the correct operational base.

## Writable-task preflight and fail-safe stop

Before any repository write, confirm all of the following:

- the real GitHub Issue exists and matches the requested scope;
- the designated Issue-numbered branch and dedicated Task Worktree path are known;
- the actual repository root is exactly that dedicated path and the expected branch is checked out there;
- `HEAD`/base is the intended commit, or a legitimate upstream change is understood before continuing;
- `git worktree list` maps the branch to that worktree and other worktrees will be preserved;
- the worktree is clean, or every existing change and untracked file is known to belong to this Issue;
- filesystem ownership is expected and there is no evidence of another Agent, external writer, or concurrent repository/file mutation in this worktree.

If a branch/worktree mapping is wrong, ownership is unexpected, unknown or unrelated files appear, another Agent is using the worktree, or state changes externally during the task, stop repository writes and report the evidence. Do not try to recover by resetting, destructively cleaning, stashing unknown work, checking out or switching over foreign work, overwriting files, force-pushing, or deleting/recreating a worktree. Resume only after the workspace owner resolves the conflict or explicitly identifies the state as safe.

Recheck the root, branch, `HEAD`, status, and intended diff before staging, committing, and pushing. Stage only files belonging to the Issue and push only its task branch.

## Worktree lifecycle and urgent work

The normal lifecycle is:

```text
Issue created
  -> deliberately select base
  -> create Issue-numbered branch and linked Task Worktree
  -> assign one Codex
  -> implement and run focused checks
  -> commit, push, and open Draft PR with `Closes #<issue>`
  -> CI / required Staging / review / merge or intentional abandonment
  -> inspect unique work and remote divergence
  -> retire only the known-safe Task Worktree
```

Before removal, verify that the exact Task Worktree has no unique uncommitted or untracked work, its branch has no unpushed commits, and the task is truly complete or intentionally abandoned. Remove and prune only explicitly identified, inspected worktrees; never auto-delete an unknown or occupied worktree. Branch deletion is a separate deliberate action and must not discard unique work.

Urgency does not justify interrupting another Issue's checkout. For example, Issue #40 remains on its branch in worktree #40. The Control launcher gives urgent Issue #41 its own Issue-numbered branch and worktree #41 from a deliberately selected `origin/main` or exact deployed/release SHA, then starts a separate Worker rooted there. Never switch, reset, clean, or stash #40 to make room for #41.

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
Do not introduce dynamic override generation or synchronization: keep the tracked project-wide contract stable and use a simple ignored override only for facts specific to one checkout.

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
