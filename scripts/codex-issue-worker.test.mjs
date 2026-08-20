import assert from "node:assert/strict";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const launcher = join(scriptDir, "codex-issue-worker.ps1");
let invocationCounter = 0;

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: "utf8", ...options });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed (${result.status}): ${result.stderr || result.stdout}`);
  }
  return result.stdout.trim();
}

function git(repo, ...args) {
  return run("git", ["-C", repo, ...args]);
}

function createFixture() {
  const root = mkdtempSync(join(tmpdir(), "codex-worker-test-"));
  const control = join(root, "control");
  const worktreeRoot = join(root, "worktrees");
  const resultRoot = join(root, "results");
  mkdirSync(control);
  mkdirSync(worktreeRoot);
  git(control, "init", "-b", "main");
  git(control, "config", "user.name", "Test User");
  git(control, "config", "user.email", "test@example.invalid");
  git(control, "remote", "add", "origin", "https://example.invalid/example/test.git");
  writeFileSync(join(control, "README.md"), "fixture\n");
  git(control, "add", "README.md");
  git(control, "commit", "-m", "fixture");
  const baseSha = git(control, "rev-parse", "HEAD");
  const fakeCodex = join(root, "fake-codex.ps1");
  writeFileSync(
    fakeCodex,
    String.raw`$Rest = $args
if ($Rest -contains '--version') { Write-Output 'codex-cli test-0.0.0'; exit 0 }
if ($Rest -contains '--help') { Write-Output '--cd --sandbox --approve-for-me --add-dir --json --output-last-message'; exit 0 }
$stdinText = [Console]::In.ReadToEnd()
$capture = $env:FAKE_CODEX_CAPTURE
[ordered]@{ cwd = (Get-Location).Path; args = $Rest; prompt = $stdinText } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $capture -Encoding utf8NoBOM
$sleepMs = [int]($env:FAKE_CODEX_SLEEP_MS ?? '0')
if ($sleepMs -gt 0) { Start-Sleep -Milliseconds $sleepMs }
$outputIndex = [Array]::IndexOf($Rest, '-o')
if ($outputIndex -ge 0) { Set-Content -LiteralPath $Rest[$outputIndex + 1] -Value 'fake worker complete' -Encoding utf8NoBOM }
exit ([int]($env:FAKE_CODEX_EXIT ?? '0'))
`,
  );
  return { root, control, worktreeRoot, resultRoot, baseSha, fakeCodex };
}

function buildLauncherInvocation(fixture, {
  issue = 101,
  branch = `chore/issue-${issue}-worker-test`,
  worktree = join(fixture.worktreeRoot, `issue-${issue}-worker-test`),
  baseRef = fixture.baseSha,
  dryRun = false,
  allowDirty = false,
  exitCode = 0,
  sleepMs = 0,
  resultRoot = fixture.resultRoot,
  omitControl = false,
} = {}) {
  const capture = join(fixture.root, `capture-${issue}-${Date.now()}-${++invocationCounter}.json`);
  const args = [
    "-NoProfile", "-File", launcher,
    "-IssueNumber", String(issue),
    "-Branch", branch,
    "-WorktreePath", worktree,
    "-BaseRef", baseRef,
    "-ExpectedRepository", "example/test",
    "-Prompt", "Perform the bounded fixture task.",
    "-CodexCommand", fixture.fakeCodex,
    "-ResultRoot", resultRoot,
  ];
  if (!omitControl) args.push("-ControlPath", fixture.control);
  if (allowDirty) args.push("-AllowDirtyIssueWorktree");
  if (dryRun) args.push("-DryRun");
  const env = {
    ...process.env,
    FAKE_CODEX_CAPTURE: capture,
    FAKE_CODEX_EXIT: String(exitCode),
    FAKE_CODEX_SLEEP_MS: String(sleepMs),
  };
  return { args, env, capture, worktree, branch };
}

function invokeLauncher(fixture, options = {}) {
  const invocation = buildLauncherInvocation(fixture, options);
  const result = spawnSync("pwsh", invocation.args, {
    encoding: "utf8",
    env: invocation.env,
  });
  let json;
  try {
    json = JSON.parse(result.stdout.trim());
  } catch {
    throw new Error(`Launcher did not return JSON. stdout=${result.stdout} stderr=${result.stderr}`);
  }
  return { ...invocation, result, json };
}

function startLauncher(fixture, options = {}) {
  const invocation = buildLauncherInvocation(fixture, options);
  const child = spawn("pwsh", invocation.args, { encoding: "utf8", env: invocation.env });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (chunk) => { stdout += chunk; });
  child.stderr.on("data", (chunk) => { stderr += chunk; });
  const completed = new Promise((resolvePromise, rejectPromise) => {
    child.on("error", rejectPromise);
    child.on("close", (status) => {
      try {
        resolvePromise({
          ...invocation,
          result: { status, stdout, stderr },
          json: JSON.parse(stdout.trim()),
        });
      } catch (error) {
        rejectPromise(new Error(`Async launcher did not return JSON. stdout=${stdout} stderr=${stderr}`, { cause: error }));
      }
    });
  });
  return { ...invocation, child, completed };
}

async function waitForFile(path, timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (existsSync(path)) return;
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 25));
  }
  throw new Error(`Timed out waiting for ${path}`);
}

test("dry-run resolves a new Issue without creating a branch, worktree, or Worker", () => {
  const fixture = createFixture();
  const beforeStatus = git(fixture.control, "status", "--porcelain=v1", "--branch");
  const invocation = invokeLauncher(fixture, { dryRun: true });
  assert.equal(invocation.result.status, 0);
  assert.equal(invocation.json.status, "DRY_RUN_OK");
  assert.equal(invocation.json.decision, "CREATE_BRANCH_AND_WORKTREE");
  assert.equal(invocation.json.branchHeadSha, null);
  assert.equal(invocation.json.intendedInitialHeadSha, fixture.baseSha);
  const missingBranch = spawnSync("git", ["-C", fixture.control, "show-ref", "--verify", "--quiet", `refs/heads/${invocation.branch}`]);
  assert.equal(missingBranch.status, 1);
  assert.equal(git(fixture.control, "status", "--porcelain=v1", "--branch"), beforeStatus);
  assert.equal(readFileSync(invocation.capture, { encoding: "utf8", flag: "a+" }), "");
});

test("provisions a new branch/worktree and passes the real cwd plus -C to the Worker", () => {
  const fixture = createFixture();
  const controlBranch = git(fixture.control, "branch", "--show-current");
  const controlStatus = git(fixture.control, "status", "--porcelain=v1");
  const invocation = invokeLauncher(fixture);
  assert.equal(invocation.result.status, 0);
  assert.equal(invocation.json.status, "WORKER_SUCCEEDED");
  assert.equal(invocation.json.decision, "CREATE_BRANCH_AND_WORKTREE");
  assert.equal(invocation.json.resolvedBaseSha, fixture.baseSha);
  assert.equal(invocation.json.branchHeadSha, fixture.baseSha);
  assert.equal(git(invocation.worktree, "branch", "--show-current"), invocation.branch);
  const capture = JSON.parse(readFileSync(invocation.capture, "utf8"));
  assert.equal(resolve(capture.cwd).toLowerCase(), resolve(invocation.worktree).toLowerCase());
  const cdIndex = capture.args.indexOf("-C");
  assert.ok(cdIndex >= 0);
  assert.equal(resolve(capture.args[cdIndex + 1]).toLowerCase(), resolve(invocation.worktree).toLowerCase());
  const addDirIndexes = capture.args.flatMap((value, index) => value === "--add-dir" ? [index] : []);
  assert.equal(addDirIndexes.length, 1);
  const commonGitDir = resolve(fixture.control, git(fixture.control, "rev-parse", "--git-common-dir"));
  assert.equal(resolve(capture.args[addDirIndexes[0] + 1]).toLowerCase(), commonGitDir.toLowerCase());
  assert.notEqual(resolve(capture.args[addDirIndexes[0] + 1]).toLowerCase(), resolve(fixture.control).toLowerCase());
  assert.doesNotMatch(capture.args.join(" "), /danger-full-access|dangerously-bypass|yolo/i);
  assert.ok(capture.prompt.includes(`Issue: #101`));
  assert.ok(capture.prompt.includes(`Branch HEAD SHA: ${fixture.baseSha}`));
  assert.equal(git(fixture.control, "branch", "--show-current"), controlBranch);
  assert.equal(git(fixture.control, "status", "--porcelain=v1"), controlStatus);
});

test("reuses an existing correctly mapped clean worktree", () => {
  const fixture = createFixture();
  const first = invokeLauncher(fixture);
  assert.equal(first.result.status, 0);
  const second = invokeLauncher(fixture);
  assert.equal(second.result.status, 0);
  assert.equal(second.json.decision, "REUSE");
  assert.equal(second.json.status, "WORKER_SUCCEEDED");
  assert.equal(second.json.branchHeadSha, fixture.baseSha);
  assert.equal(second.json.resolvedBaseSha, fixture.baseSha);
});

test("blocks when the expected branch is mapped to another worktree", () => {
  const fixture = createFixture();
  const branch = "chore/issue-102-wrong-map";
  const other = join(fixture.worktreeRoot, "issue-102-other");
  git(fixture.control, "worktree", "add", "-b", branch, other, fixture.baseSha);
  const invocation = invokeLauncher(fixture, {
    issue: 102,
    branch,
    worktree: join(fixture.worktreeRoot, "issue-102-expected"),
  });
  assert.equal(invocation.result.status, 2);
  assert.equal(invocation.json.status, "BLOCKED");
  assert.match(invocation.json.blocker, /already attached to another worktree/);
});

test("blocks a dirty target without cleaning, resetting, or stashing it", () => {
  const fixture = createFixture();
  const first = invokeLauncher(fixture, { issue: 103 });
  assert.equal(first.result.status, 0);
  const marker = join(first.worktree, "unknown.txt");
  writeFileSync(marker, "preserve me\n");
  const second = invokeLauncher(fixture, { issue: 103 });
  assert.equal(second.result.status, 2);
  assert.equal(second.json.status, "BLOCKED");
  assert.match(second.json.blocker, /dirty/);
  assert.equal(readFileSync(marker, "utf8"), "preserve me\n");
  assert.match(git(first.worktree, "status", "--porcelain=v1"), /unknown\.txt/);
});

test("blocks an invalid or unresolvable base", () => {
  const fixture = createFixture();
  const invocation = invokeLauncher(fixture, { issue: 104, baseRef: "refs/heads/does-not-exist" });
  assert.equal(invocation.result.status, 2);
  assert.equal(invocation.json.status, "BLOCKED");
  assert.match(invocation.json.blocker, /cannot be resolved/);
});

test("blocks and preserves an existing path that is not a linked worktree", () => {
  const fixture = createFixture();
  const target = join(fixture.worktreeRoot, "issue-106-unknown-path");
  mkdirSync(target);
  const marker = join(target, "foreign.txt");
  writeFileSync(marker, "foreign state\n");
  const invocation = invokeLauncher(fixture, { issue: 106, worktree: target });
  assert.equal(invocation.result.status, 2);
  assert.equal(invocation.json.status, "BLOCKED");
  assert.match(invocation.json.blocker, /not the expected linked worktree/);
  assert.equal(readFileSync(marker, "utf8"), "foreign state\n");
});

test("reuses a dirty Issue worktree only with explicit recognition", () => {
  const fixture = createFixture();
  const first = invokeLauncher(fixture, { issue: 107 });
  assert.equal(first.result.status, 0);
  const marker = join(first.worktree, "known-issue-work.txt");
  writeFileSync(marker, "known Issue state\n");
  const second = invokeLauncher(fixture, { issue: 107, allowDirty: true });
  assert.equal(second.result.status, 0);
  assert.equal(second.json.status, "WORKER_SUCCEEDED");
  assert.equal(second.json.workingState, "DIRTY_ACCEPTED");
  assert.equal(readFileSync(marker, "utf8"), "known Issue state\n");
});

test("propagates a non-zero Worker exit as WORKER_FAILED", () => {
  const fixture = createFixture();
  const invocation = invokeLauncher(fixture, { issue: 105, exitCode: 7 });
  assert.equal(invocation.result.status, 7);
  assert.equal(invocation.json.status, "WORKER_FAILED");
  assert.equal(invocation.json.workerExitCode, 7);
});

test("blocks a concurrent Worker on the same worktree and releases the lease after exit", async () => {
  const fixture = createFixture();
  const first = startLauncher(fixture, { issue: 108, sleepMs: 4000 });
  await waitForFile(first.capture);

  const concurrent = invokeLauncher(fixture, { issue: 108 });
  assert.equal(concurrent.result.status, 2);
  assert.equal(concurrent.json.status, "BLOCKED");
  assert.match(concurrent.json.blocker, /lease is already held/);

  const completedFirst = await first.completed;
  assert.equal(completedFirst.result.status, 0);
  assert.equal(completedFirst.json.status, "WORKER_SUCCEEDED");
  assert.deepEqual(completedFirst.json.statuses, ["PROVISIONED", "WORKER_STARTED", "WORKER_SUCCEEDED"]);

  const afterRelease = invokeLauncher(fixture, { issue: 108 });
  assert.equal(afterRelease.result.status, 0);
  assert.equal(afterRelease.json.status, "WORKER_SUCCEEDED");
  assert.equal(afterRelease.json.decision, "REUSE");
  assert.equal(afterRelease.json.workerLeaseKey, completedFirst.json.workerLeaseKey);
});

test("allows Workers for different sibling worktrees to run independently", async () => {
  const fixture = createFixture();
  const first = startLauncher(fixture, { issue: 109, sleepMs: 4000 });
  await waitForFile(first.capture);

  const sibling = invokeLauncher(fixture, { issue: 110 });
  assert.equal(sibling.result.status, 0);
  assert.equal(sibling.json.status, "WORKER_SUCCEEDED");
  assert.notEqual(sibling.json.workerLeaseKey, (await first.completed).json.workerLeaseKey);
});

test("blocks a target nested in another linked worktree and preserves the foreign worktree", () => {
  const fixture = createFixture();
  const foreign = join(fixture.worktreeRoot, "issue-111-feature");
  git(fixture.control, "worktree", "add", "-b", "chore/issue-111-feature", foreign, fixture.baseSha);
  const marker = join(foreign, "foreign-state.txt");
  writeFileSync(marker, "foreign bytes\n");
  const beforeStatus = git(foreign, "status", "--porcelain=v1", "--untracked-files=all");
  const nested = join(foreign, "scratch", "issue-112-hotfix");

  const blocked = invokeLauncher(fixture, {
    issue: 112,
    worktree: nested,
    branch: "hotfix/issue-112-hotfix",
  });
  assert.equal(blocked.result.status, 2);
  assert.equal(blocked.json.status, "BLOCKED");
  assert.match(blocked.json.blocker, /overlaps another linked worktree/);
  assert.equal(readFileSync(marker, "utf8"), "foreign bytes\n");
  assert.equal(git(foreign, "status", "--porcelain=v1", "--untracked-files=all"), beforeStatus);

  const sibling = invokeLauncher(fixture, { issue: 113 });
  assert.equal(sibling.result.status, 0);
  assert.equal(sibling.json.status, "WORKER_SUCCEEDED");
});

test("blocks ResultRoot inside another linked worktree without writing there", () => {
  const fixture = createFixture();
  const foreign = join(fixture.worktreeRoot, "issue-114-feature");
  git(fixture.control, "worktree", "add", "-b", "chore/issue-114-feature", foreign, fixture.baseSha);
  const foreignResultRoot = join(foreign, "worker-results");

  const blocked = invokeLauncher(fixture, {
    issue: 115,
    resultRoot: foreignResultRoot,
  });
  assert.equal(blocked.result.status, 2);
  assert.equal(blocked.json.status, "BLOCKED");
  assert.match(blocked.json.blocker, /ResultRoot overlaps a linked repository worktree/);
  assert.equal(existsSync(foreignResultRoot), false);
  assert.equal(git(foreign, "status", "--porcelain=v1"), "");
});

test("requires the primary Control Checkout and rejects a linked Task Worktree as control", () => {
  const fixture = createFixture();
  const taskControl = join(fixture.worktreeRoot, "issue-116-task-control");
  git(fixture.control, "worktree", "add", "-b", "chore/issue-116-task-control", taskControl, fixture.baseSha);

  const omitted = buildLauncherInvocation(fixture, { issue: 117, omitControl: true });
  const omittedResult = spawnSync("pwsh", omitted.args, {
    cwd: taskControl,
    encoding: "utf8",
    env: omitted.env,
  });
  assert.notEqual(omittedResult.status, 0);
  assert.match(`${omittedResult.stdout}\n${omittedResult.stderr}`, /ControlPath/);
  assert.equal(spawnSync("git", ["-C", fixture.control, "show-ref", "--verify", "--quiet", "refs/heads/chore/issue-117-worker-test"]).status, 1);

  const incorrect = invokeLauncher(
    { ...fixture, control: taskControl },
    { issue: 118, worktree: join(fixture.worktreeRoot, "issue-118-worker-test") },
  );
  assert.equal(incorrect.result.status, 2);
  assert.equal(incorrect.json.status, "BLOCKED");
  assert.match(incorrect.json.blocker, /primary permanent Control Checkout/);
});

test("attaches an existing branch without moving its HEAD and reports base separately", () => {
  const fixture = createFixture();
  const issue = 119;
  const branch = "chore/issue-119-existing-head";
  const tree = git(fixture.control, "rev-parse", `${fixture.baseSha}^{tree}`);
  const existingHead = git(fixture.control, "commit-tree", tree, "-p", fixture.baseSha, "-m", "existing branch commit");
  git(fixture.control, "update-ref", `refs/heads/${branch}`, existingHead);

  const invocation = invokeLauncher(fixture, { issue, branch });
  assert.equal(invocation.result.status, 0);
  assert.equal(invocation.json.decision, "ATTACH_EXISTING_BRANCH");
  assert.equal(invocation.json.requestedBaseRef, fixture.baseSha);
  assert.equal(invocation.json.resolvedBaseSha, fixture.baseSha);
  assert.equal(invocation.json.branchHeadSha, existingHead);
  assert.notEqual(invocation.json.branchHeadSha, invocation.json.resolvedBaseSha);
  assert.equal(git(invocation.worktree, "rev-parse", "HEAD"), existingHead);
  const capture = JSON.parse(readFileSync(invocation.capture, "utf8"));
  assert.ok(capture.prompt.includes(`Resolved base SHA: ${fixture.baseSha}`));
  assert.ok(capture.prompt.includes(`Branch HEAD SHA: ${existingHead}`));
});

test("source contains no forbidden destructive Git recovery commands", () => {
  const source = readFileSync(launcher, "utf8");
  const gitInvocationLines = source.split(/\r?\n/).filter((line) => line.includes("Invoke-Git") && line.includes("-Arguments"));
  const invokedCommands = gitInvocationLines.join("\n");
  for (const forbidden of [
    /"reset"[^\r\n]*"--hard"/i,
    /"clean"[^\r\n]*"-[^"\r\n]*f/i,
    /"stash"/i,
    /"push"[^\r\n]*"--force"/i,
    /"worktree"[^\r\n]*"remove"/i,
    /"branch"[^\r\n]*"-[dD]"/i,
    /"rebase"/i,
  ]) {
    assert.doesNotMatch(invokedCommands, forbidden);
  }
});
