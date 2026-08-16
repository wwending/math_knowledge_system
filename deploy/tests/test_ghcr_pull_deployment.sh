#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="${repo_root}/compose.prod.yml"
deploy_script="${repo_root}/deploy/scripts/deploy.sh"
env_file="${repo_root}/deploy/.env"
test_sha="0123456789abcdef0123456789abcdef01234567"

compose_json="$(IMAGE_TAG="${test_sha}" docker compose \
    --env-file "${env_file}" -f "${compose_file}" config --format json)"

printf '%s' "${compose_json}" | python3 -c '
import json
import sys

config = json.load(sys.stdin)
sha = sys.argv[1]
expected = {
    "backend": f"ghcr.io/wwending/math-knowledge-backend:{sha}",
    "web": f"ghcr.io/wwending/math-knowledge-web:{sha}",
}
for service_name, image in expected.items():
    service = config["services"][service_name]
    assert service["image"] == image, (service_name, service.get("image"))
    assert "build" not in service, service_name
' "${test_sha}"

missing_tag_output="$(mktemp)"
trap 'rm -f "${missing_tag_output}"' EXIT
if env -u IMAGE_TAG docker compose --env-file "${env_file}" \
    -f "${compose_file}" config >"${missing_tag_output}" 2>&1; then
    echo "Compose unexpectedly accepted a missing IMAGE_TAG." >&2
    exit 1
fi
grep -Fq 'IMAGE_TAG must be set' "${missing_tag_output}"

! grep -Eq 'docker compose .* build' "${deploy_script}"

line_number() {
    local pattern="$1"
    grep -nF "${pattern}" "${deploy_script}" | tail -n 1 | cut -d: -f1
}

pull_line="$(line_number 'pull backend web')"
backend_revision_line="$(line_number 'BACKEND_REVISION="$(verify_image_revision')"
web_revision_line="$(line_number 'WEB_REVISION="$(verify_image_revision')"
backend_digest_line="$(line_number 'BACKEND_DIGEST="$(get_image_repo_digest')"
web_digest_line="$(line_number 'WEB_DIGEST="$(get_image_repo_digest')"
backup_line="$(line_number '"${SCRIPT_DIR}/backup.sh"')"
migration_line="$(line_number 'run --rm backend alembic upgrade head')"

for verified_line in \
    "${backend_revision_line}" "${web_revision_line}" \
    "${backend_digest_line}" "${web_digest_line}"; do
    (( pull_line < verified_line ))
    (( verified_line < backup_line ))
done
(( backup_line < migration_line ))
