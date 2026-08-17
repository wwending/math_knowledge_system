#!/usr/bin/env bash

validate_image_digest() {
    local variable_name="$1"
    local digest="$2"

    if [[ -z "${digest}" ]]; then
        echo "${variable_name} must be set to sha256 followed by 64 lowercase hexadecimal characters." >&2
        return 1
    fi
    if [[ ! "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
        echo "${variable_name} is invalid; expected sha256 followed by 64 lowercase hexadecimal characters." >&2
        return 1
    fi
}

require_release_image_digests() {
    validate_image_digest BACKEND_IMAGE_DIGEST "${BACKEND_IMAGE_DIGEST:-}" || return 1
    validate_image_digest WEB_IMAGE_DIGEST "${WEB_IMAGE_DIGEST:-}" || return 1
    export BACKEND_IMAGE_DIGEST WEB_IMAGE_DIGEST
}

verify_image_repo_digest() {
    local image="$1"
    local expected_repository="$2"
    local expected_digest="$3"
    local expected_repo_digest="${expected_repository}@${expected_digest}"
    local repo_digest

    while IFS= read -r repo_digest; do
        if [[ "${repo_digest}" == "${expected_repo_digest}" ]]; then
            printf '%s\n' "${repo_digest}"
            return 0
        fi
    done < <(docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "${image}")

    echo "Exact RepoDigest ${expected_repo_digest} was not found on ${image}." >&2
    return 1
}

resolve_running_image_digest() {
    local service="$1"
    local expected_repository="$2"
    local container_output
    local container_ids=()
    local configured_image
    local digest

    if ! container_output="$(docker ps \
        --filter 'label=com.docker.compose.project=math-knowledge' \
        --filter "label=com.docker.compose.service=${service}" \
        --format '{{.ID}}')"; then
        echo "Failed to find the running ${service} container." >&2
        return 1
    fi
    mapfile -t container_ids <<<"${container_output}"
    if [[ -z "${container_output}" || "${#container_ids[@]}" -ne 1 ]]; then
        echo "Expected exactly one running ${service} container; provide release digests explicitly." >&2
        return 1
    fi

    if ! configured_image="$(docker inspect --format '{{.Config.Image}}' "${container_ids[0]}")"; then
        echo "Failed to inspect the running ${service} container image; provide release digests explicitly." >&2
        return 1
    fi
    if [[ "${configured_image}" != "${expected_repository}@"* ]]; then
        echo "Running ${service} image is not pinned to ${expected_repository}; provide release digests explicitly." >&2
        return 1
    fi

    digest="${configured_image#"${expected_repository}@"}"
    validate_image_digest "running ${service} image digest" "${digest}" || return 1
    printf '%s\n' "${digest}"
}

load_or_resolve_release_image_digests() {
    if [[ -n "${BACKEND_IMAGE_DIGEST:-}" ]]; then
        validate_image_digest BACKEND_IMAGE_DIGEST "${BACKEND_IMAGE_DIGEST}" || return 1
    else
        BACKEND_IMAGE_DIGEST="$(resolve_running_image_digest backend "${BACKEND_REPOSITORY}")" || return 1
    fi

    if [[ -n "${WEB_IMAGE_DIGEST:-}" ]]; then
        validate_image_digest WEB_IMAGE_DIGEST "${WEB_IMAGE_DIGEST}" || return 1
    else
        WEB_IMAGE_DIGEST="$(resolve_running_image_digest web "${WEB_REPOSITORY}")" || return 1
    fi

    export BACKEND_IMAGE_DIGEST WEB_IMAGE_DIGEST
}
