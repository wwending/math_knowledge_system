const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'
const DEFAULT_API_V1_PREFIX = '/api/v1'
const DEFAULT_STATIC_URL_PREFIX = '/static'

const stripTrailingSlash = (value) => value.replace(/\/+$/, '')

const normalizePrefix = (value, fallback) => {
  const normalized = (value || fallback).trim()
  if (!normalized) {
    return fallback
  }
  if (normalized === '/') {
    return '/'
  }
  return normalized.startsWith('/') ? normalized.replace(/\/+$/, '') : `/${normalized.replace(/\/+$/, '')}`
}

export const API_BASE_URL = stripTrailingSlash(
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL
)

export const API_V1_PREFIX = normalizePrefix(
  import.meta.env.VITE_API_V1_PREFIX,
  DEFAULT_API_V1_PREFIX
)

export const STATIC_URL_PREFIX = normalizePrefix(
  import.meta.env.VITE_STATIC_URL_PREFIX,
  DEFAULT_STATIC_URL_PREFIX
)

export const API_V1_BASE_URL = `${API_BASE_URL}${API_V1_PREFIX}`

export const buildStaticUrl = (path) => {
  if (!path) {
    return ''
  }
  const normalizedPath = String(path).replace(/^\/+/, '')
  return `${API_BASE_URL}${STATIC_URL_PREFIX}/${normalizedPath}`
}

export const buildAssetUrl = (path) => {
  if (!path) {
    return ''
  }
  const normalizedPath = String(path).trim()
  if (!normalizedPath) {
    return ''
  }
  if (/^https?:\/\//i.test(normalizedPath)) {
    return normalizedPath
  }
  if (normalizedPath.startsWith('/')) {
    return `${API_BASE_URL}${normalizedPath}`
  }
  return `${API_BASE_URL}/${normalizedPath.replace(/^\/+/, '')}`
}

export const resolveQuestionImageUrl = (item) => {
  if (!item) {
    return ''
  }
  return buildAssetUrl(item.image_url || item.origin_image || '')
}

export const buildUploadUrl = buildAssetUrl
