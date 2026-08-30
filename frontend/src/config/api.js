const DEFAULT_DEV_API_BASE_URL = 'http://127.0.0.1:8000'
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

const explicitApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()
const defaultApiBaseUrl = import.meta.env.PROD ? '' : DEFAULT_DEV_API_BASE_URL

export const API_BASE_URL = stripTrailingSlash(explicitApiBaseUrl || defaultApiBaseUrl)

export const API_V1_PREFIX = normalizePrefix(
  import.meta.env.VITE_API_V1_PREFIX,
  DEFAULT_API_V1_PREFIX
)

export const STATIC_URL_PREFIX = normalizePrefix(
  import.meta.env.VITE_STATIC_URL_PREFIX,
  DEFAULT_STATIC_URL_PREFIX
)

export const API_V1_BASE_URL = `${API_BASE_URL}${API_V1_PREFIX}`

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

// Authenticated image channel (#44): question images are served by
// GET /api/v1/questions/{id}/image and must be fetched with an Authorization
// header, then rendered via blob URLs.
export const buildQuestionImageUrl = (questionId) => `${API_V1_BASE_URL}/questions/${questionId}/image`
export const buildQuestionFigureImageUrl = (questionId, figureId) => `${API_V1_BASE_URL}/questions/${questionId}/figures/${figureId}`

// Authenticated image channel (#22): the draft reference image is served by
// GET /api/v1/drafts/{id}/image and must be fetched as an authenticated blob,
// then rendered via an object URL.
export const buildDraftImageUrl = (draftId) => `${API_V1_BASE_URL}/drafts/${draftId}/image`

// Authenticated image channel (#59): the figure frozen in a paper item is
// served by GET /api/v1/papers/{paperId}/items/{paperItemId}/image and must be
// fetched as an authenticated blob, then rendered via an object URL.
export const buildPaperItemImageUrl = (paperId, paperItemId) =>
  `${API_V1_BASE_URL}/papers/${paperId}/items/${paperItemId}/image`
