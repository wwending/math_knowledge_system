# Security Policy

## npm supply-chain controls

Frontend dependencies must be installed with lifecycle scripts disabled:

```bash
npm ci --ignore-scripts
```

This rule applies to local verification, CI, and production image builds. Do not replace it with an unrestricted `npm ci`, `npm install`, or global script enablement.

After installation, list packages that declare install lifecycle scripts without executing them:

```bash
cd frontend
npm run security:list-install-scripts
```

Any dependency that genuinely requires `preinstall`, `install`, or `postinstall` must be handled as a narrowly scoped exception. Before allowing a package's script, review the locked package version and script contents, document why it is needed, approve the exact package, and rerun the frontend contract tests and production build. Never use a blanket exception for all dependencies.

## Dependency and workflow review

- Commit `package-lock.json` changes together with the corresponding `package.json` change.
- Pull requests are checked by GitHub Dependency Review for newly introduced dependency risk.
- Third-party GitHub Actions must use a verified full 40-character commit SHA with a version comment.
- Checkout steps must set `persist-credentials: false` unless a separately reviewed job explicitly requires repository writes.
- Do not commit `.env`, `.npmrc`, registry tokens, GitHub tokens, or other credentials.
- Do not use `npm audit fix --force` as a substitute for reviewing compatibility and exploitability.

## Reporting a vulnerability

Report suspected vulnerabilities privately to the repository owner. Do not include credentials, production data, or complete third-party responses in an issue or log.
