#!/usr/bin/env bash
set -euo pipefail

image="${1:?usage: test_nginx_mime.sh <web-image>}"
container="math-knowledge-nginx-mime-${RANDOM}-$$"

cleanup() {
    docker rm --force "${container}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run --rm --add-host backend:127.0.0.1 "${image}" nginx -t
docker run --detach --name "${container}" --add-host backend:127.0.0.1 "${image}" >/dev/null

for _ in $(seq 1 20); do
    if docker exec "${container}" wget -q -O /dev/null http://127.0.0.1/index.html; then
        break
    fi
    sleep 1
done
docker exec "${container}" wget -q -O /dev/null http://127.0.0.1/index.html

find_asset() {
    local pattern="$1"
    local asset
    asset="$(docker exec "${container}" find /usr/share/nginx/html/assets -maxdepth 1 -type f -name "${pattern}" -print | head -n 1)"
    if [[ -z "${asset}" ]]; then
        echo "No built asset matched ${pattern}" >&2
        return 1
    fi
    printf '/assets/%s\n' "$(basename "${asset}")"
}

assert_content_type() {
    local path="$1"
    local expected="$2"
    local headers
    headers="$(docker exec "${container}" wget -S -O /dev/null "http://127.0.0.1${path}" 2>&1)"
    if ! grep -Eiq "^[[:space:]]*Content-Type:[[:space:]]*${expected}([;[:space:]]|$)" <<<"${headers}"; then
        echo "Unexpected Content-Type for ${path}; expected ${expected}" >&2
        printf '%s\n' "${headers}" >&2
        return 1
    fi
    echo "PASS ${path} -> ${expected}"
}

assert_content_type "$(find_asset '*.mjs')" 'application/javascript'
assert_content_type "$(find_asset '*.js')" 'application/javascript'
assert_content_type "$(find_asset '*.css')" 'text/css'
assert_content_type "$(find_asset '*.woff2')" 'font/woff2'
assert_content_type '/index.html' 'text/html'
