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

## Python dependency locking

- `backend/requirements.txt` declares direct dependencies with minimum specifiers only; it is not an install source for production.
- `backend/requirements.lock` is the fully pinned universal resolution (every direct and transitive dependency, environment markers included, Python 3.11 floor). Docker image builds and CI backend jobs install from the lock so rebuilds of the same Git SHA produce one auditable dependency tree.
- Regenerate the lock after changing `requirements.txt`:

  ```bash
  cd backend
  uv pip compile --universal --python-version 3.11 requirements.txt -o requirements.lock
  ```

- Commit `requirements.txt` and `requirements.lock` changes together. CI runs `backend/dev_scripts/check_requirements_lock.py` as an offline drift gate: every direct dependency must have a satisfying exact pin in the lock.
- Refreshing the lock (new upstream versions) is a deliberate, separately reviewed change — never a side effect of an unrelated PR.

## Dependency and workflow review

- Commit `package-lock.json` changes together with the corresponding `package.json` change.
- Pull requests are checked by GitHub Dependency Review for newly introduced dependency risk.
- Third-party GitHub Actions must use a verified full 40-character commit SHA with a version comment.
- Checkout steps must set `persist-credentials: false` unless a separately reviewed job explicitly requires repository writes.
- Do not commit `.env`, `.npmrc`, registry tokens, GitHub tokens, or other credentials.
- Do not use `npm audit fix --force` as a substitute for reviewing compatibility and exploitability.

## Reporting a vulnerability

Report suspected vulnerabilities through GitHub's private vulnerability reporting on this repository: open the repository's **Security** tab and use **Report a vulnerability**. This is the only accepted reporting channel — do not describe vulnerabilities in public issues, discussions, or pull requests.

Include in the report:

- The affected Git SHA (and image digest, if the finding is deployment-related).
- The affected environment and the steps to reproduce.
- Your assessment of the impact, and any mitigation you have already applied.

Do not include credentials, production data, or complete third-party responses in an issue or log.

## Credential rotation baseline

- GHCR publish tokens are scoped to `write:packages` only and used solely by the image publishing workflow; Staging/demo hosts pull with `read:packages` tokens or unauthenticated public pulls where possible.
- Rotate GHCR tokens at least every 90 days, and immediately after any suspected exposure, publisher-machine change, or CI secret list change.
- SSH keys for server access are dedicated per operator and per machine, protected by passphrases; rotate them at least every 90 days, and immediately after any suspected exposure or operator departure.
- Remove stale entries from the server's `authorized_keys` and revoke revoked-operator tokens as part of each rotation pass.
- Any credential that may have appeared in logs, issues, screenshots, or backups is treated as exposed and rotated out of band — rotation is not deferred to the next cycle.
## 公开注册可信客户端 IP 边界

匿名注册限流只在 `SECURE_TRANSPORT_MODE=trusted_proxy_tls` 时读取 `X-Forwarded-For` 的入口客户端地址；该模式必须配合部署文档要求的可信 TLS 代理和防火墙入口限制。其他模式使用直连地址并忽略转发头，禁止把任意客户端可写的头作为限流身份。注册审计不得包含密码。
