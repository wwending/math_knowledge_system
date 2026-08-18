import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const MAX_REFERENCES = 20;
const CLOSING_REFERENCE = /\b(?:close(?:s|d)?|fix(?:es|ed)?|resolve(?:s|d)?)\s*:?\s*#([1-9]\d*)\b/gi;

function stripNonProseMarkdown(body) {
  return body
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/(^|\n)[ \t]*(?:```|~~~)[^\n]*\n[\s\S]*?(?:\n[ \t]*(?:```|~~~)(?=\n|$)|$)/g, " ")
    .replace(/`[^`\n]*`/g, " ");
}

export function extractClosingIssueNumbers(body) {
  const matches = stripNonProseMarkdown(typeof body === "string" ? body : "").matchAll(CLOSING_REFERENCE);
  return [...new Set(Array.from(matches, (match) => Number(match[1])))];
}

export async function validateTraceability({ body, prCreatedAt, getIssue }) {
  const issueNumbers = extractClosingIssueNumbers(body);
  if (issueNumbers.length === 0) {
    return ['PR must link an existing GitHub Issue using "Closes #<issue-number>".'];
  }
  if (issueNumbers.length > MAX_REFERENCES) {
    return [`PR contains too many closing Issue references (maximum ${MAX_REFERENCES}).`];
  }

  const prCreated = Date.parse(prCreatedAt);
  if (!Number.isFinite(prCreated)) {
    return ["Pull Request creation time is missing or invalid."];
  }

  const errors = [];
  let hasPredatingIssue = false;

  for (const issueNumber of issueNumbers) {
    const response = await getIssue(issueNumber);
    if (response.status === 404) {
      errors.push(`Linked target #${issueNumber} does not exist in this repository.`);
      continue;
    }
    if (response.status !== 200) {
      errors.push(`Unable to verify linked target #${issueNumber} (GitHub API status ${response.status}).`);
      continue;
    }
    if (response.data?.pull_request) {
      errors.push(`Linked target #${issueNumber} is a Pull Request, not an Issue.`);
      continue;
    }

    const issueCreated = Date.parse(response.data?.created_at);
    if (!Number.isFinite(issueCreated)) {
      errors.push(`Linked Issue #${issueNumber} has an invalid creation time.`);
      continue;
    }
    if (issueCreated < prCreated) {
      hasPredatingIssue = true;
    }
  }

  if (!hasPredatingIssue && errors.length === 0) {
    errors.push("Linked Issue must exist before the Pull Request is created.");
  }

  return errors;
}

async function main() {
  const eventPath = process.env.GITHUB_EVENT_PATH;
  const repository = process.env.GITHUB_REPOSITORY;
  const token = process.env.GITHUB_TOKEN;
  if (!eventPath || !repository || !token) {
    throw new Error("GITHUB_EVENT_PATH, GITHUB_REPOSITORY, and GITHUB_TOKEN are required.");
  }
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) {
    throw new Error("GITHUB_REPOSITORY is invalid.");
  }

  const event = JSON.parse(await readFile(eventPath, "utf8"));
  if (!event.pull_request) {
    throw new Error("The workflow event does not contain a Pull Request.");
  }

  const errors = await validateTraceability({
    body: event.pull_request.body,
    prCreatedAt: event.pull_request.created_at,
    getIssue: async (issueNumber) => {
      const response = await fetch(`https://api.github.com/repos/${repository}/issues/${issueNumber}`, {
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${token}`,
          "X-GitHub-Api-Version": "2022-11-28",
        },
      });
      const data = response.status === 404 ? null : await response.json();
      return { status: response.status, data };
    },
  });

  if (errors.length > 0) {
    for (const error of errors) {
      console.error(`::error::${error}`);
    }
    process.exitCode = 1;
    return;
  }

  console.log("PR traceability check passed.");
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(`::error::${error.message}`);
    process.exitCode = 1;
  });
}
