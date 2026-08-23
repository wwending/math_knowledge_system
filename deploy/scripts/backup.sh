#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/deploy/.env}"
COMPOSE_FILE="${REPO_ROOT}/compose.prod.yml"

source "${SCRIPT_DIR}/image-digests.sh"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing deployment environment file: ${ENV_FILE}" >&2
    exit 1
fi

BACKEND_REPOSITORY="ghcr.io/wwending/math-knowledge-backend"
WEB_REPOSITORY="ghcr.io/wwending/math-knowledge-web"
load_or_resolve_release_image_digests

read_env_value() {
    local key="$1"
    awk -F= -v key="${key}" '$1 == key { sub(/^[^=]*=/, ""); value=$0 } END { print value }' "${ENV_FILE}"
}

DATA_ROOT="${DATA_ROOT:-$(read_env_value DATA_ROOT)}"
BACKUP_ROOT="${BACKUP_ROOT:-$(read_env_value BACKUP_ROOT)}"
DATA_ROOT="${DATA_ROOT:-/srv/math-knowledge/data}"
BACKUP_ROOT="${BACKUP_ROOT:-/srv/math-knowledge/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${BACKUP_ROOT}/${timestamp}"
container_backup_dir="/backups/${timestamp}"

install -d -m 0775 -o 10001 -g 10001 "${backup_dir}"

if [[ -f "${DATA_ROOT}/math_knowledge.db" ]]; then
    cd "${REPO_ROOT}"
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm --no-deps \
        -e BACKUP_DB_PATH="${container_backup_dir}/math_knowledge.db" \
        backend python -c \
        'import os, sqlite3; source = sqlite3.connect("file:/data/math_knowledge.db?mode=ro", uri=True); target = sqlite3.connect(os.environ["BACKUP_DB_PATH"]); source.backup(target); target.close(); source.close()'
else
    echo "No existing SQLite database found; database backup skipped."
fi

if [[ -d "${DATA_ROOT}/uploads" ]]; then
    tar -C "${DATA_ROOT}" -czf "${backup_dir}/uploads.tar.gz" uploads
elif [[ -d "${DATA_ROOT}/static/uploads" ]]; then
    # Pre-#44 layout; kept so backups still work before deploy.sh migrates the files.
    tar -C "${DATA_ROOT}/static" -czf "${backup_dir}/uploads.tar.gz" uploads
fi

git -C "${REPO_ROOT}" rev-parse HEAD > "${backup_dir}/deploy_commit.txt"
awk -F= '
    /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
    /^[A-Za-z_][A-Za-z0-9_]*=/ { key=$1; sub(/^[[:space:]]+/, "", key); print key }
' "${ENV_FILE}" | sort -u > "${backup_dir}/environment_fields.txt"

(
    cd "${backup_dir}"
    sha256sum ./* > SHA256SUMS
)

echo "Backup written to ${backup_dir}"
