#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/deploy/.env}"
COMPOSE_FILE="${REPO_ROOT}/compose.prod.yml"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing deployment environment file: ${ENV_FILE}" >&2
    echo "Copy deploy/.env.production.example to deploy/.env and fill in its values." >&2
    exit 1
fi

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
SECRET_KEY_VALUE="$(read_env_value SECRET_KEY)"
CORS_ALLOW_ORIGINS_VALUE="$(read_env_value CORS_ALLOW_ORIGINS)"

if [[ -z "${SECRET_KEY_VALUE}" ]]; then
    echo "SECRET_KEY must be set in ${ENV_FILE}." >&2
    exit 1
fi

if [[ "${CORS_ALLOW_ORIGINS_VALUE}" == *SERVER_IP* || "${CORS_ALLOW_ORIGINS_VALUE}" == *PORT* ]]; then
    echo "Replace the CORS_ALLOW_ORIGINS placeholder in ${ENV_FILE}." >&2
    exit 1
fi

install -d -m 0775 -o 10001 -g 10001 \
    "${DATA_ROOT}" \
    "${DATA_ROOT}/static" \
    "${DATA_ROOT}/static/uploads" \
    "${DATA_ROOT}/pdf_temp"
install -d -m 0775 "${BACKUP_ROOT}"

cd "${REPO_ROOT}"
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" build

ENV_FILE="${ENV_FILE}" "${SCRIPT_DIR}/backup.sh"

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm backend alembic upgrade head
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d

health_url="http://127.0.0.1:${HTTP_PORT}/healthz"
for attempt in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 5 "${health_url}" >/dev/null; then
        echo "Health check passed: ${health_url}"
        break
    fi
    if [[ "${attempt}" -eq 30 ]]; then
        echo "Health check failed after ${attempt} attempts: ${health_url}" >&2
        docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
        exit 1
    fi
    sleep 2
done

curl --fail --silent --show-error "${health_url}"
echo
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
echo "Deployed commit: $(git rev-parse HEAD)"
