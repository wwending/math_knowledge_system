#!/usr/bin/env bash
set -Eeuo pipefail

# Restore a full backup produced by backup.sh onto the persistent data root.
# Lifecycle: verify checksums -> stop stack -> quarantine current data ->
# restore DB/uploads -> fix ownership (10001) -> offline quick_check ->
# Alembic migration -> start stack -> health check.
#
# Safety contract: this script never deletes user data. Existing DB and
# uploads are moved into a quarantine directory under BACKUP_ROOT and stay
# there as the manual rollback point until an operator removes them.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/deploy/.env}"
COMPOSE_FILE="${REPO_ROOT}/compose.prod.yml"

source "${SCRIPT_DIR}/image-digests.sh"

if [[ "${#}" -ne 1 ]]; then
    echo "Usage: $0 <backup_dir>" >&2
    echo "  <backup_dir> is a timestamped directory written by deploy/scripts/backup.sh" >&2
    echo "Required environment: BACKEND_IMAGE_DIGEST, WEB_IMAGE_DIGEST (sha256:<64 hex>)." >&2
    exit 1
fi
BACKUP_SOURCE_DIR="${1}"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing deployment environment file: ${ENV_FILE}" >&2
    exit 1
fi

BACKEND_REPOSITORY="ghcr.io/wwending/math-knowledge-backend"
WEB_REPOSITORY="ghcr.io/wwending/math-knowledge-web"

# Restore must work on a degraded or stopped stack where running-container
# digest resolution is unavailable, so explicit trusted digests are mandatory.
require_release_image_digests

read_env_value() {
    local key="$1"
    awk -F= -v key="${key}" '$1 == key { sub(/^[^=]*=/, ""); value=$0 } END { print value }' "${ENV_FILE}"
}

DATA_ROOT="${DATA_ROOT:-$(read_env_value DATA_ROOT)}"
BACKUP_ROOT="${BACKUP_ROOT:-$(read_env_value BACKUP_ROOT)}"
HTTP_PORT="${HTTP_PORT:-$(read_env_value HTTP_PORT)}"
DATA_ROOT="${DATA_ROOT:-/srv/math-knowledge/data}"
BACKUP_ROOT="${BACKUP_ROOT:-/srv/math-knowledge/backups}"
HTTP_PORT="${HTTP_PORT:-8080}"

if [[ ! -d "${BACKUP_SOURCE_DIR}" ]]; then
    echo "Backup directory not found: ${BACKUP_SOURCE_DIR}" >&2
    exit 1
fi

for required_file in SHA256SUMS math_knowledge.db uploads.tar.gz deploy_commit.txt; do
    if [[ ! -f "${BACKUP_SOURCE_DIR}/${required_file}" ]]; then
        echo "Backup is incomplete: missing ${required_file} in ${BACKUP_SOURCE_DIR}." >&2
        exit 1
    fi
done

echo "Verifying backup checksums in ${BACKUP_SOURCE_DIR}..."
checksum_output="$(cd "${BACKUP_SOURCE_DIR}" && sha256sum -c SHA256SUMS)" || {
    printf '%s\n' "${checksum_output}" >&2
    echo "Checksum verification failed; refusing to touch the current system." >&2
    exit 1
}
printf '%s\n' "${checksum_output}"

compose() {
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

quarantine_dir="${BACKUP_ROOT}/pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"

on_error() {
    local exit_code="$?"
    echo "Restore FAILED (exit ${exit_code}). No data was deleted." >&2
    if [[ -d "${quarantine_dir}" ]]; then
        echo "Pre-restore data is quarantined at: ${quarantine_dir}" >&2
        echo "Manual rollback: stop the stack, move quarantined math_knowledge.db and uploads back under ${DATA_ROOT}, chown -R 10001:10001, then start the stack." >&2
    fi
    exit "${exit_code}"
}
trap on_error ERR

backup_commit="$(cat "${BACKUP_SOURCE_DIR}/deploy_commit.txt")"
echo "Restore plan:"
echo "  source backup : ${BACKUP_SOURCE_DIR} (deploy commit ${backup_commit})"
echo "  data root     : ${DATA_ROOT}"
echo "  backend image : ${BACKEND_REPOSITORY}@${BACKEND_IMAGE_DIGEST}"
echo "  web image     : ${WEB_REPOSITORY}@${WEB_IMAGE_DIGEST}"

echo "Stopping stack (dependency order: web -> backend -> gotenberg)..."
compose stop

mkdir -p "${quarantine_dir}"
chmod 0775 "${quarantine_dir}"
for existing_path in \
    "${DATA_ROOT}/math_knowledge.db" \
    "${DATA_ROOT}/math_knowledge.db-wal" \
    "${DATA_ROOT}/math_knowledge.db-shm" \
    "${DATA_ROOT}/uploads"; do
    if [[ -e "${existing_path}" ]]; then
        mv "${existing_path}" "${quarantine_dir}/$(basename "${existing_path}")"
        echo "Quarantined: ${existing_path}"
    fi
done

echo "Restoring database and uploads from ${BACKUP_SOURCE_DIR}..."
cp "${BACKUP_SOURCE_DIR}/math_knowledge.db" "${DATA_ROOT}/math_knowledge.db"
tar -xzf "${BACKUP_SOURCE_DIR}/uploads.tar.gz" -C "${DATA_ROOT}"

chown -R 10001:10001 "${DATA_ROOT}/math_knowledge.db" "${DATA_ROOT}/uploads"
chmod 0644 "${DATA_ROOT}/math_knowledge.db"

echo "Running SQLite quick_check on the restored database..."
compose run --rm --no-deps backend python -c '
import sqlite3
conn = sqlite3.connect("file:/data/math_knowledge.db?mode=ro", uri=True)
quick_check = conn.execute("PRAGMA quick_check").fetchall()
foreign_key_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
conn.close()
print("quick_check:", quick_check)
print("foreign_key_check violations:", foreign_key_violations)
assert quick_check == [("ok",)], quick_check
assert foreign_key_violations == [], foreign_key_violations
'

echo "Applying Alembic migrations to head..."
compose run --rm --no-deps backend alembic upgrade head
echo "Current migration revision:"
compose run --rm --no-deps backend alembic current

echo "Starting stack..."
compose up -d

health_url="http://127.0.0.1:${HTTP_PORT}/healthz"
for attempt in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 5 "${health_url}" >/dev/null; then
        echo "Health check passed: ${health_url}"
        break
    fi
    if [[ "${attempt}" -eq 30 ]]; then
        echo "Health check failed after ${attempt} attempts: ${health_url}" >&2
        compose ps
        exit 1
    fi
    sleep 2
done

trap - ERR

echo
echo "Restore complete."
echo "  restored from : ${BACKUP_SOURCE_DIR}"
echo "  deploy commit : ${backup_commit}"
echo "  backend image : ${BACKEND_REPOSITORY}@${BACKEND_IMAGE_DIGEST}"
echo "  web image     : ${WEB_REPOSITORY}@${WEB_IMAGE_DIGEST}"
echo "  rollback point: ${quarantine_dir}"
echo "Next: run the business smoke checklist (docs/MVP_RELEASE_CHECKLIST.md), keep ${quarantine_dir} until acceptance, then remove it manually."
