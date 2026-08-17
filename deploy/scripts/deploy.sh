#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/deploy/.env}"
COMPOSE_FILE="${REPO_ROOT}/compose.prod.yml"

source "${SCRIPT_DIR}/image-digests.sh"

cd "${REPO_ROOT}"

if [[ "$(git rev-parse --is-inside-work-tree 2>/dev/null)" != "true" ]]; then
    echo "Refusing to deploy outside a Git worktree." >&2
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Refusing to deploy from a dirty Git worktree." >&2
    exit 1
fi

GIT_SHA="$(git rev-parse HEAD)"
export GIT_SHA

BACKEND_REPOSITORY="ghcr.io/wwending/math-knowledge-backend"
WEB_REPOSITORY="ghcr.io/wwending/math-knowledge-web"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Missing deployment environment file: ${ENV_FILE}" >&2
    echo "Copy deploy/.env.production.example to deploy/.env and fill in its values." >&2
    exit 1
fi

read_env_value() {
    local key="$1"
    awk -F= -v key="${key}" '$1 == key { sub(/^[^=]*=/, ""); value=$0 } END { print value }' "${ENV_FILE}"
}

verify_image_revision() {
    local image="$1"
    local expected_revision="$2"
    local actual_revision

    if ! actual_revision="$(docker image inspect \
        --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
        "${image}")"; then
        echo "Failed to inspect image revision: ${image}" >&2
        return 1
    fi

    if [[ "${actual_revision}" != "${expected_revision}" ]]; then
        echo "Image revision mismatch for ${image}: expected ${expected_revision}, got ${actual_revision}" >&2
        return 1
    fi

    printf '%s\n' "${actual_revision}"
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

require_release_image_digests
BACKEND_IMAGE="${BACKEND_REPOSITORY}@${BACKEND_IMAGE_DIGEST}"
WEB_IMAGE="${WEB_REPOSITORY}@${WEB_IMAGE_DIGEST}"

install -d -m 0775 -o 10001 -g 10001 \
    "${DATA_ROOT}" \
    "${DATA_ROOT}/static" \
    "${DATA_ROOT}/static/uploads" \
    "${DATA_ROOT}/pdf_temp"
install -d -m 0775 "${BACKUP_ROOT}"

if ! docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" pull backend web; then
    echo "Failed to pull release images. GHCR authentication may be required." >&2
    exit 1
fi

BACKEND_REVISION="$(verify_image_revision "${BACKEND_IMAGE}" "${GIT_SHA}")"
WEB_REVISION="$(verify_image_revision "${WEB_IMAGE}" "${GIT_SHA}")"
BACKEND_REPO_DIGEST="$(verify_image_repo_digest "${BACKEND_IMAGE}" "${BACKEND_REPOSITORY}" "${BACKEND_IMAGE_DIGEST}")"
WEB_REPO_DIGEST="$(verify_image_repo_digest "${WEB_IMAGE}" "${WEB_REPOSITORY}" "${WEB_IMAGE_DIGEST}")"

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
echo "Deployed commit: ${GIT_SHA}"
echo "Backend image: ${BACKEND_IMAGE}"
echo "Backend revision: ${BACKEND_REVISION}"
echo "Backend digest: ${BACKEND_REPO_DIGEST}"
echo "Web image: ${WEB_IMAGE}"
echo "Web revision: ${WEB_REVISION}"
echo "Web digest: ${WEB_REPO_DIGEST}"
