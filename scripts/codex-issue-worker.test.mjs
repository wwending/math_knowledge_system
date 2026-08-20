import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const launcher = join(scriptDir, "codex-issue-worker.ps1");

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
$outputIndex = [Array]::IndexOf($Rest, '-o')
if ($outputIndex -ge 0) { Set-Content -LiteralPath $Rest[$outputIndex + 1] -Value 'fake worker complete' -Encoding utf8NoBOM }
exit ([int]($env:FAKE_CODEX_EXIT ?? '0'))
`,
  );
  return { root, control, worktreeRoot, resultRoot, baseSha, fakeCodex };
}

function invokeLauncher(fixture, {
  issue = 101,
  branch = `chore/issue-${issue}-worker-test`,
  worktree = join(fixture.worktreeRoot, `issue-${issue}-worker-test`),
  baseRef = fixture.baseSha,
  dryRun = false,
  allowDirty = false,
  exitCode = 0,
} = {}) {
  const capture = join(fixture.root, `capture-${issue}-${Date.now()}.json`);
  const args = [
    "-NoProfile", "-File", launcher,
    "-IssueNumber", String(issue),
    "-Branch", branch,
    "-WorktreePath", worktree,
    "-BaseRef", baseRef,
    "-ExpectedRepository", "example/test",
    "-ControlPath", fixture.control,
    "-Prompt", "Perform the bounded fixture task.",
    "-CodexCommand", fixture.fakeCodex,
    "-ResultRoot", fixture.resultRoot,
  ];
  if (allowDirty) args.push("-AllowDirtyIssueWorktree");
  if (dryRun) args.push("-DryRun");
  const result = spawnSync("pwsh", args, {
    encoding: "utf8",
    env: { ...process.env, FAKE_CODEX_CAPTURE: capture, FAKE_CODEX_EXIT: String(exitCode) },
  });
  let json;
  try {
    json = JSON.parse(result.stdout.trim());
  } catch {
    throw new Error(`Launcher did not return JSON. stdout=${result.stdout} stderr=${result.stderr}`);
  }
  return { result, json, capture, worktree, branch };
}

test("dry-run resolves a new Issue without creating a branch, worktree, or Worker", () => {
  const fixture = createFixture();
  const beforeStatus = git(fixture.control, "status", "--porcelain=v1", "--branch");
  const invocation = invokeLauncher(fixture, { dryRun: true });
  assert.equal(invocation.result.status, 0);
  assert.equal(invocation.json.status, "DRY_RUN_OK");
  assert.equal(invocation.json.decision, "CREATE_BRANCH_AND_WORKTREE");
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
  assert.equal(git(invocation.worktree, "branch", "--show-current"), invocation.branch);
  const capture = JSON.parse(readFileSync(invocation.capture, "utf8"));
  assert.equal(resolve(capture.cwd).toLowerCase(), resolve(invocation.worktree).toLowerCase());
  const cdIndex = capture.args.indexOf("-C");
  assert.ok(cdIndex >= 0);
  assert.equal(resolve(capture.args[cdIndex + 1]).toLowerCase(), resolve(invocation.worktree).toLowerCase());
  assert.ok(capture.prompt.includes(`Issue: #101`));
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
  ]) {
    assert.doesNotMatch(invokedCommands, forbidden);
  }
});
