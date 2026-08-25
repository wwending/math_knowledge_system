#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
restore_script="${repo_root}/deploy/scripts/restore.sh"
digest_helper="${repo_root}/deploy/scripts/image-digests.sh"
backend_digest="sha256:$(printf '1%.0s' {1..64})"
web_digest="sha256:$(printf '2%.0s' {1..64})"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Static contract: lifecycle ordering and safety invariants.
# ---------------------------------------------------------------------------
line_number() {
    local line
    line="$(grep -nF "$1" "${restore_script}" | tail -n 1 | cut -d: -f1)"
    [[ -n "${line}" ]] || fail "missing restore contract marker: $1"
    printf '%s\n' "${line}"
}

digests_line="$(line_number 'require_release_image_digests')"
checksum_line="$(line_number 'sha256sum -c SHA256SUMS')"
stop_line="$(line_number 'compose stop')"
quarantine_line="$(line_number 'mv "${existing_path}" "${quarantine_dir}/$(basename "${existing_path}")"')"
copy_db_line="$(line_number 'cp "${BACKUP_SOURCE_DIR}/math_knowledge.db" "${DATA_ROOT}/math_knowledge.db"')"
extract_uploads_line="$(line_number 'tar -xzf "${BACKUP_SOURCE_DIR}/uploads.tar.gz" -C "${DATA_ROOT}"')"
ownership_line="$(line_number 'chown -R 10001:10001')"
quick_check_line="$(line_number 'PRAGMA quick_check')"
migration_line="$(line_number 'alembic upgrade head')"
revision_line="$(line_number 'alembic current')"
up_line="$(line_number 'compose up -d')"

(( checksum_line > digests_line )) || fail "checksum verification must run after the digest gate"
(( stop_line > checksum_line )) || fail "stack must be stopped only after checksums pass"
(( quarantine_line > stop_line )) || fail "current data must be quarantined after stopping the stack"
(( copy_db_line > quarantine_line )) || fail "database restore must happen after quarantining current data"
(( extract_uploads_line > quarantine_line )) || fail "uploads restore must happen after quarantining current data"
(( ownership_line > copy_db_line )) || fail "ownership fix must follow the database restore"
(( quick_check_line > ownership_line )) || fail "quick_check must run on the restored, owned files"
(( migration_line > quick_check_line )) || fail "migration must run after quick_check passes"
(( revision_line > migration_line )) || fail "migration revision evidence must be printed after upgrade"
(( up_line > migration_line )) || fail "stack start must follow migration"

grep -Fq 'BACKUP_ROOT}/pre-restore-' "${restore_script}" \
    || fail "rollback point must be a quarantine directory under BACKUP_ROOT"
if grep -Eq '(^|[;&|[:space:]])rm([[:space:]]|$)' "${restore_script}"; then
    fail "restore.sh must never invoke rm; quarantine instead of delete"
fi
if grep -Fq 'load_or_resolve_release_image_digests' "${restore_script}"; then
    fail "restore.sh must require explicit trusted digests, not resolve them from containers"
fi

# ---------------------------------------------------------------------------
# Behavioral test sandbox.
# ---------------------------------------------------------------------------
sandbox="$(mktemp -d)"
trap 'rm -rf "${sandbox}"' EXIT

data_root="${sandbox}/data"
backup_root="${sandbox}/backups"
env_file="${sandbox}/env"
http_port="18443"

mkdir -p "${data_root}/uploads" "${backup_root}"
cat > "${env_file}" <<EOF
HTTP_PORT=${http_port}
EOF

make_backup_dir() {
    local backup_dir="$1"
    mkdir -p "${backup_dir}"
    printf 'NEW-DATABASE' > "${backup_dir}/math_knowledge.db"
    mkdir -p "${sandbox}/payload/uploads"
    printf 'restored-upload' > "${sandbox}/payload/uploads/restored.txt"
    tar -C "${sandbox}/payload" -czf "${backup_dir}/uploads.tar.gz" uploads
    rm -rf "${sandbox}/payload"
    printf '4805a2947b5f15623c68f071e514f0a76a7ba015' > "${backup_dir}/deploy_commit.txt"
    (cd "${backup_dir}" && sha256sum ./* > SHA256SUMS)
}

seed_live_data() {
    printf 'OLD-DATABASE' > "${data_root}/math_knowledge.db"
    printf 'old-upload' > "${data_root}/uploads/stale.txt"
}

# Mocked externals: record compose subcommands; never touch the real stack.
run_restore_with_mocks() {
    local backup_dir="$1"
    (
        set -Eeuo pipefail
        export BACKEND_IMAGE_DIGEST="${backend_digest}"
        export WEB_IMAGE_DIGEST="${web_digest}"
        export DATA_ROOT="${data_root}"
        export BACKUP_ROOT="${backup_root}"
        export ENV_FILE="${env_file}"
        unset HTTP_PORT

        compose_log="${sandbox}/compose.log"
        : > "${compose_log}"
        docker() {
            if [[ "${1:-}" == "compose" ]]; then
                echo "$*" >> "${compose_log}"
                return 0
            fi
            echo "unexpected docker invocation: $*" >&2
            return 1
        }
        curl() { return 0; }
        chown() { return 0; }

        source "${restore_script}" "${backup_dir}"
    )
}

# Happy path: restore over existing live data.
seed_live_data
make_backup_dir "${backup_root}/20260825T120000Z"
run_restore_with_mocks "${backup_root}/20260825T120000Z" \
    || fail "happy-path restore exited non-zero"

[[ "$(cat "${data_root}/math_knowledge.db")" == "NEW-DATABASE" ]] \
    || fail "restored database content mismatch"
[[ "$(cat "${data_root}/uploads/restored.txt")" == "restored-upload" ]] \
    || fail "restored uploads payload mismatch"
[[ ! -e "${data_root}/uploads/stale.txt" ]] \
    || fail "stale upload survived restore; uploads must be rebuilt from the backup"

quarantined_dirs=("${backup_root}"/pre-restore-*)
[[ -f "${quarantined_dirs[0]}/math_knowledge.db" ]] \
    || fail "pre-restore database was not quarantined"
[[ "$(cat "${quarantined_dirs[0]}/math_knowledge.db")" == "OLD-DATABASE" ]] \
    || fail "quarantined database content mismatch"
[[ -d "${quarantined_dirs[0]}/uploads" ]] \
    || fail "pre-restore uploads were not quarantined"

# Compose lifecycle order inside the mock log: stop -> run(s) -> up -d.
stop_log_line="$(grep -nE ' stop$' "${sandbox}/compose.log" | head -n 1 | cut -d: -f1)"
first_run_log_line="$(grep -nE ' run ' "${sandbox}/compose.log" | head -n 1 | cut -d: -f1)"
up_log_line="$(grep -nE ' up -d$' "${sandbox}/compose.log" | head -n 1 | cut -d: -f1)"
[[ -n "${stop_log_line}" ]] || fail "expected a compose stop invocation"
[[ -n "${first_run_log_line}" ]] || fail "expected compose run invocations"
[[ -n "${up_log_line}" ]] || fail "expected a compose up -d invocation"
(( stop_log_line < first_run_log_line )) || fail "stack must be stopped before any compose run"
(( first_run_log_line < up_log_line )) || fail "compose run steps must precede stack start"
run_calls="$(grep -cE ' run ' "${sandbox}/compose.log")"
[[ "${run_calls}" -ge 3 ]] || fail "expected quick_check + two alembic run invocations, got ${run_calls}"

# Fail-closed: checksum mismatch leaves the live system untouched.
seed_live_data
make_backup_dir "${backup_root}/20260825T130000Z"
printf 'tampered' > "${backup_root}/20260825T130000Z/math_knowledge.db"
if run_restore_with_mocks "${backup_root}/20260825T130000Z" 2>/dev/null; then
    fail "restore unexpectedly accepted a tampered backup"
fi
[[ "$(cat "${data_root}/math_knowledge.db")" == "OLD-DATABASE" ]] \
    || fail "failed checksum verification must not touch the live database"
# Only the happy-path quarantine directory may exist.
[[ "$(find "${backup_root}" -maxdepth 1 -name 'pre-restore-*' | wc -l)" -eq 1 ]] \
    || fail "failed restore must not create a quarantine directory"

# Fail-closed: missing digest environment.
if (
    set -Eeuo pipefail
    export DATA_ROOT="${data_root}"
    export BACKUP_ROOT="${backup_root}"
    export ENV_FILE="${env_file}"
    unset BACKEND_IMAGE_DIGEST WEB_IMAGE_DIGEST
    source "${restore_script}" "${backup_root}/20260825T130000Z"
) 2>/dev/null; then
    fail "restore unexpectedly accepted missing backend digest"
fi

# Fail-closed: incomplete backup directory.
mkdir -p "${backup_root}/incomplete"
if run_restore_with_mocks "${backup_root}/incomplete" 2>/dev/null; then
    fail "restore unexpectedly accepted an incomplete backup directory"
fi

# Fail-closed: nonexistent backup directory.
if run_restore_with_mocks "${backup_root}/does-not-exist" 2>/dev/null; then
    fail "restore unexpectedly accepted a nonexistent backup directory"
fi

# Digest validator itself stays shared with deploy/backup (already exercised by
# test_ghcr_pull_deployment.sh); here we only pin that restore sources it.
# shellcheck source=../scripts/image-digests.sh
source "${digest_helper}"
validate_image_digest TEST_DIGEST "${backend_digest}"

echo "test_restore_script: PASS"
