import assert from "node:assert/strict";
import test from "node:test";

import { extractClosingIssueNumbers, validateTraceability } from "./check-pr-traceability.mjs";

const PR_CREATED_AT = "2026-08-18T15:00:00Z";
const BEFORE_PR = "2026-08-18T14:00:00Z";
const AFTER_PR = "2026-08-18T16:00:00Z";

function issueResponse(createdAt = BEFORE_PR) {
  return { status: 200, data: { created_at: createdAt } };
}

test("extracts valid Closes #32 and ignores template comments", () => {
  const body = "<!-- Closes #999 -->\n## Linked Issue\nCloses #32";
  assert.deepEqual(extractClosingIssueNumbers(body), [32]);
});

test("fails when the closing Issue reference is missing", async () => {
  const errors = await validateTraceability({
    body: "Addresses #32",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => issueResponse(),
  });
  assert.deepEqual(errors, ['PR must link an existing GitHub Issue using "Closes #<issue-number>".']);
});

test("fails when the referenced target does not exist", async () => {
  const errors = await validateTraceability({
    body: "Fixes #404",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => ({ status: 404, data: null }),
  });
  assert.deepEqual(errors, ["Linked target #404 does not exist in this repository."]);
});

test("fails when the referenced target is a Pull Request", async () => {
  const errors = await validateTraceability({
    body: "Resolves #33",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => ({ status: 200, data: { created_at: BEFORE_PR, pull_request: {} } }),
  });
  assert.deepEqual(errors, ["Linked target #33 is a Pull Request, not an Issue."]);
});

test("fails when the linked Issue was created after the Pull Request", async () => {
  const errors = await validateTraceability({
    body: "Closes #32",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => issueResponse(AFTER_PR),
  });
  assert.deepEqual(errors, ["Linked Issue must exist before the Pull Request is created."]);
});

test("passes when a valid linked Issue predates the Pull Request", async () => {
  const errors = await validateTraceability({
    body: "closes: #32",
    prCreatedAt: PR_CREATED_AT,
    getIssue: async () => issueResponse(),
  });
  assert.deepEqual(errors, []);
});
