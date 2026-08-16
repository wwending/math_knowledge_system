#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
config="${repo_root}/deploy/nginx/default.conf"

grep -Eq '^[[:space:]]*location \^~ /static/[[:space:]]*\{' "${config}"

static_block="$(awk '
    /^[[:space:]]*location \^~ \/static\/[[:space:]]*\{/ { in_static = 1 }
    in_static { print }
    in_static && /^[[:space:]]*\}[[:space:]]*$/ { exit }
' "${config}")"
grep -Eq '^[[:space:]]*proxy_pass http://math_backend;[[:space:]]*$' <<<"${static_block}"

! grep -Eq '^[[:space:]]*location /static/[[:space:]]*\{' "${config}"
grep -Fq 'location ~* \.mjs$ {' "${config}"
grep -Eq '^[[:space:]]*application/javascript mjs;[[:space:]]*$' "${config}"
grep -Fq 'location ~* \.(?:css|js|map|png|jpg|jpeg|gif|svg|ico|webp|woff|woff2|ttf)$ {' "${config}"
