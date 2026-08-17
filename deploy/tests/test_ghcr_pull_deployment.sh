#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="${repo_root}/compose.prod.yml"
deploy_script="${repo_root}/deploy/scripts/deploy.sh"
backup_script="${repo_root}/deploy/scripts/backup.sh"
digest_helper="${repo_root}/deploy/scripts/image-digests.sh"
env_file="${repo_root}/deploy/.env"
backend_digest="sha256:$(printf '1%.0s' {1..64})"
web_digest="sha256:$(printf '2%.0s' {1..64})"

compose_json="$(
    BACKEND_IMAGE_DIGEST="${backend_digest}" \
    WEB_IMAGE_DIGEST="${web_digest}" \
    docker compose --env-file "${env_file}" -f "${compose_file}" config --format json
)"

printf '%s' "${compose_json}" | python3 -c '
import json
import sys

config = json.load(sys.stdin)
expected = {
    "backend": f"ghcr.io/wwending/math-knowledge-backend@{sys.argv[1]}",
    "web": f"ghcr.io/wwending/math-knowledge-web@{sys.argv[2]}",
}
for service_name, image in expected.items():
    service = config["services"][service_name]
    assert service["image"] == image, (service_name, service.get("image"))
    assert "build" not in service, service_name
' "${backend_digest}" "${web_digest}"

missing_digest_output="$(mktemp)"
trap 'rm -f "${missing_digest_output}"' EXIT

if env -u BACKEND_IMAGE_DIGEST \
    WEB_IMAGE_DIGEST="${web_digest}" \
    docker compose --env-file "${env_file}" -f "${compose_file}" config \
    >"${missing_digest_output}" 2>&1; then
    echo "Compose unexpectedly accepted a missing BACKEND_IMAGE_DIGEST." >&2
    exit 1
fi
grep -Fq 'BACKEND_IMAGE_DIGEST must be set' "${missing_digest_output}"

if env -u WEB_IMAGE_DIGEST \
    BACKEND_IMAGE_DIGEST="${backend_digest}" \
    docker compose --env-file "${env_file}" -f "${compose_file}" config \
    >"${missing_digest_output}" 2>&1; then
    echo "Compose unexpectedly accepted a missing WEB_IMAGE_DIGEST." >&2
    exit 1
fi
grep -Fq 'WEB_IMAGE_DIGEST must be set' "${missing_digest_output}"

# Exercise the strict validator sourced by deploy.sh and backup.sh.
# shellcheck source=../scripts/image-digests.sh
source "${digest_helper}"
validate_image_digest TEST_DIGEST "${backend_digest}"
invalid_digests=(
    ''
    'sha256:ABCDEF'
    'sha512:0123456789abcdef'
    '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
    'ghcr.io/example/image@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'
    'sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcde '
    'latest'
    'sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcde$'
)
for invalid_digest in "${invalid_digests[@]}"; do
    if validate_image_digest TEST_DIGEST "${invalid_digest}" 2>/dev/null; then
        echo "Digest validator unexpectedly accepted: ${invalid_digest}" >&2
        exit 1
    fi
done

if (
    unset BACKEND_IMAGE_DIGEST
    WEB_IMAGE_DIGEST="${web_digest}"
    require_release_image_digests
) 2>/dev/null; then
    echo "Deployment digest gate unexpectedly accepted a missing backend digest." >&2
    exit 1
fi
if (
    BACKEND_IMAGE_DIGEST="${backend_digest}"
    unset WEB_IMAGE_DIGEST
    require_release_image_digests
) 2>/dev/null; then
    echo "Deployment digest gate unexpectedly accepted a missing web digest." >&2
    exit 1
fi

test_repository='ghcr.io/wwending/math-knowledge-backend'
test_image="${test_repository}@${backend_digest}"
mock_repo_digests="${test_repository}@sha256:$(printf '3%.0s' {1..64})
${test_repository}@${backend_digest}"
docker() {
    printf '%s\n' "${mock_repo_digests}"
}
[[ "$(verify_image_repo_digest "${test_image}" "${test_repository}" "${backend_digest}")" == "${test_image}" ]]
mock_repo_digests="${test_repository}@sha256:$(printf '3%.0s' {1..64})"
if verify_image_repo_digest "${test_image}" "${test_repository}" "${backend_digest}" 2>/dev/null; then
    echo "RepoDigest gate unexpectedly accepted a different digest from the same repository." >&2
    exit 1
fi
unset -f docker

mock_container_image="${test_image}"
docker() {
    if [[ "$1" == 'ps' ]]; then
        printf '%s\n' 'backend-container-id'
    elif [[ "$1" == 'inspect' ]]; then
        printf '%s\n' "${mock_container_image}"
    else
        return 1
    fi
}
[[ "$(resolve_running_image_digest backend "${test_repository}")" == "${backend_digest}" ]]
mock_container_image="${test_repository}:0123456789abcdef0123456789abcdef01234567"
if resolve_running_image_digest backend "${test_repository}" 2>/dev/null; then
    echo "Standalone backup resolution unexpectedly accepted a tag reference." >&2
    exit 1
fi
unset -f docker

! grep -Eq 'docker compose .* build' "${deploy_script}"
! grep -Fq '${IMAGE_TAG}' "${compose_file}" "${deploy_script}" "${backup_script}"
grep -Fq 'load_or_resolve_release_image_digests' "${backup_script}"

line_number() {
    local pattern="$1"
    local line
    line="$(grep -nF "${pattern}" "${deploy_script}" | tail -n 1 | cut -d: -f1)"
    [[ -n "${line}" ]] || {
        echo "Missing deploy contract marker: ${pattern}" >&2
        return 1
    }
    printf '%s\n' "${line}"
}

digest_validation_line="$(line_number 'require_release_image_digests')"
directory_line="$(line_number 'install -d -m 0775 -o 10001')"
pull_line="$(line_number 'pull backend web')"
backend_revision_line="$(line_number 'BACKEND_REVISION="$(verify_image_revision')"
web_revision_line="$(line_number 'WEB_REVISION="$(verify_image_revision')"
backend_digest_line="$(line_number 'BACKEND_REPO_DIGEST="$(verify_image_repo_digest')"
web_digest_line="$(line_number 'WEB_REPO_DIGEST="$(verify_image_repo_digest')"
backup_line="$(line_number '"${SCRIPT_DIR}/backup.sh"')"
migration_line="$(line_number 'run --rm backend alembic upgrade head')"

(( digest_validation_line < directory_line ))
(( directory_line < pull_line ))
for verified_line in \
    "${backend_revision_line}" "${web_revision_line}" \
    "${backend_digest_line}" "${web_digest_line}"; do
    (( pull_line < verified_line ))
    (( verified_line < backup_line ))
    (( verified_line < migration_line ))
done
(( backup_line < migration_line ))

grep -Fq 'BACKEND_IMAGE="${BACKEND_REPOSITORY}@${BACKEND_IMAGE_DIGEST}"' "${deploy_script}"
grep -Fq 'WEB_IMAGE="${WEB_REPOSITORY}@${WEB_IMAGE_DIGEST}"' "${deploy_script}"
grep -Fq 'expected_repo_digest="${expected_repository}@${expected_digest}"' "${digest_helper}"
