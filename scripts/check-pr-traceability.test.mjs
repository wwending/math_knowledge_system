import assert from "node:assert/strict";
import test from "node:test";

import { extractClosingIssueNumbers, extractIssueNumbers, validateTraceability } from "./check-pr-traceability.mjs";

const PR_CREATED_AT = "2026-08-18T15:00:00Z";
const BEFORE_PR = "2026-08-18T14:00:00Z";
const AFTER_PR = "2026-08-18T16:00:00Z";

function issueResponse(createdAt = BEFORE_PR) {
  return { status: 200, data: { created_at: createdAt } };
}

test("extracts issue references from a Refs link and ignores template comments", () => {
  const body = "<!-- Refs #999 placeholder -->\n## Linked Issue\nRefs #32";
  assert.deepEqual(extractIssueNumbers(body), [32]);
  assert.deepEqual(extractClosingIssueNumbers(body), []);
});

test("extracts closing keywords for rejection", () => {
  assert.deepEqual(extractClosingIssueNumbers("Refs #31\nCloses #32"), [32]);
  assert.deepEqual(extractClosingIssueNumbers("fixes: #33 and Resolves #34"), [33, 34]);
});

test("fails when the body contains no Issue reference", async () => {
  const errors = await validateTraceability({
    title: "feat: something",
    body: "No linked issue here.",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => issueResponse(),
  });
  assert.deepEqual(errors, ['PR must link an existing GitHub Issue using "Refs #<issue-number>".']);
});

test("fails when a closing keyword appears in the body even though an Issue is referenced", async () => {
  const errors = await validateTraceability({
    title: "fix: something",
    body: "Closes #32",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => issueResponse(),
  });
  assert.match(errors[0], /^Closing keywords/);
  assert.equal(errors.length, 1);
});

test("fails when a closing keyword appears in the title even when the body links properly", async () => {
  const errors = await validateTraceability({
    title: "Fixes #32",
    body: "Refs #32",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => issueResponse(),
  });
  assert.match(errors[0], /^Closing keywords/);
});

test("does not reject closing-keyword text inside HTML template comments", async () => {
  const errors = await validateTraceability({
    title: "docs: something",
    body: "<!-- Do NOT use Closes/Fixes/Resolves #N -->\n## Linked Issue\nRefs #32",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => issueResponse(),
  });
  assert.deepEqual(errors, []);
});

test("accepts a bare #N mention as the linked Issue", async () => {
  const errors = await validateTraceability({
    title: "chore: something",
    body: "Linked Issue: #32",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => issueResponse(),
  });
  assert.deepEqual(errors, []);
});

test("fails when the referenced target does not exist", async () => {
  const errors = await validateTraceability({
    title: "",
    body: "Refs #404",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => ({ status: 404, data: null }),
  });
  assert.deepEqual(errors, ["Linked target #404 does not exist in this repository."]);
});

test("fails when the referenced target is a Pull Request", async () => {
  const errors = await validateTraceability({
    title: "",
    body: "Refs #33",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => ({ status: 200, data: { created_at: BEFORE_PR, pull_request: {} } }),
  });
  assert.deepEqual(errors, ["Linked target #33 is a Pull Request, not an Issue."]);
});

test("fails when the linked Issue was created after the Pull Request", async () => {
  const errors = await validateTraceability({
    title: "",
    body: "Refs #32",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => issueResponse(AFTER_PR),
  });
  assert.deepEqual(errors, ["Linked Issue must exist before the Pull Request is created."]);
});

test("passes when a valid linked Issue predates the Pull Request", async () => {
  const errors = await validateTraceability({
    title: "feat: observability",
    body: "## Linked Issue\nRefs #32",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => issueResponse(),
  });
  assert.deepEqual(errors, []);
});
