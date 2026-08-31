import { reactive } from 'vue'
import axios from 'axios'

import { API_V1_BASE_URL } from '../config/api.js'

const ACCESS_TOKEN_STORAGE_KEY = 'auth.access_token'
const DEFAULT_AUTH_CAPABILITIES = Object.freeze({
  public_signup_enabled: false,
  password_recovery_mode: 'admin_contact',
  sms_code_login_enabled: false,
  sms_password_recovery_enabled: false
})

export const AUTH_CAPABILITY_STATUS = Object.freeze({
  IDLE: 'idle',
  LOADING: 'loading',
  READY: 'ready',
  ERROR: 'error'
})

export const PASSWORD_CHANGE_REQUIRED_DETAIL = 'Password change is required before accessing this resource'
export const DISABLED_USER_DETAIL = 'User account is disabled'
export const PUBLIC_SIGNUP_DISABLED_DETAIL = 'Public signup is disabled in this environment'

const normalizeAuthCapabilities = (capabilities) => {
  const passwordRecoveryMode = capabilities?.password_recovery_mode

  return {
    public_signup_enabled: Boolean(capabilities?.public_signup_enabled),
    password_recovery_mode:
      typeof passwordRecoveryMode === 'string' && passwordRecoveryMode.trim()
        ? passwordRecoveryMode.trim()
        : DEFAULT_AUTH_CAPABILITIES.password_recovery_mode,
    sms_code_login_enabled: Boolean(capabilities?.sms_code_login_enabled),
    sms_password_recovery_enabled: Boolean(capabilities?.sms_password_recovery_enabled)
  }
}

const readStoredAccessToken = () => {
  try {
    return sessionStorage.getItem(ACCESS_TOKEN_STORAGE_KEY) || ''
  } catch (error) {
    console.warn('Failed to read access token from sessionStorage.', error)
    return ''
  }
}

const persistAccessToken = (token) => {
  try {
    if (token) {
      sessionStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token)
      return
    }
    sessionStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
  } catch (error) {
    console.warn('Failed to persist access token in sessionStorage.', error)
  }
}

const authState = reactive({
  accessToken: readStoredAccessToken(),
  currentUser: null,
  capabilities: normalizeAuthCapabilities(null),
  capabilitiesStatus: AUTH_CAPABILITY_STATUS.IDLE,
  capabilitiesError: null,
  capabilitiesPromise: null,
  refreshPromise: null,
  mePromise: null
})

const applyAuthPayload = (payload) => {
  const accessToken = payload?.access_token || ''
  if (!accessToken) {
    throw new Error('Missing access token')
  }
  setAccessToken(accessToken)
  setCurrentUser(payload?.user || null)
  return payload
}

export { authState }

export const getAccessToken = () => authState.accessToken || ''

export const hasAccessToken = () => Boolean(getAccessToken())

export const getCurrentUser = () => authState.currentUser

export const setCurrentUser = (user) => {
  authState.currentUser = user || null
}

export const setAccessToken = (token) => {
  authState.accessToken = token || ''
  persistAccessToken(authState.accessToken)
}

export const clearAuthSession = () => {
  setAccessToken('')
  setCurrentUser(null)
}

const clearAuthSessionIfUnchanged = (expectedAccessToken = '') => {
  if ((authState.accessToken || '') === (expectedAccessToken || '')) {
    clearAuthSession()
  }
}

export const needsPasswordChange = (user = authState.currentUser) => {
  return false
}

export const isAdminRole = (role) => ['admin', 'super_admin'].includes(role)

export const isAdminUser = (user = authState.currentUser) => isAdminRole(user?.role)
export const isSuperAdminUser = (user = authState.currentUser) => user?.role === 'super_admin'

export const getAuthCapabilities = () => normalizeAuthCapabilities(authState.capabilities)

export const getPublicSignupCapabilityState = () => {
  const capabilities = getAuthCapabilities()
  const status = authState.capabilitiesStatus || AUTH_CAPABILITY_STATUS.IDLE
  const failed = status === AUTH_CAPABILITY_STATUS.ERROR
  const loading = status === AUTH_CAPABILITY_STATUS.IDLE || status === AUTH_CAPABILITY_STATUS.LOADING

  return {
    status,
    loading,
    ready: status === AUTH_CAPABILITY_STATUS.READY || failed,
    failed,
    enabled: status === AUTH_CAPABILITY_STATUS.READY && Boolean(capabilities.public_signup_enabled),
    capabilities
  }
}

export const isPublicSignupEnabled = (publicSignupCapability = getPublicSignupCapabilityState()) => {
  if (typeof publicSignupCapability?.enabled === 'boolean') {
    return publicSignupCapability.enabled
  }
  return Boolean(normalizeAuthCapabilities(publicSignupCapability).public_signup_enabled)
}

export const fetchAuthCapabilities = async ({ force = false } = {}) => {
  if (authState.capabilitiesStatus === AUTH_CAPABILITY_STATUS.READY && !force) {
    return getAuthCapabilities()
  }

  if (authState.capabilitiesPromise && !force) {
    return authState.capabilitiesPromise
  }

  authState.capabilitiesStatus = AUTH_CAPABILITY_STATUS.LOADING
  authState.capabilitiesError = null
  authState.capabilitiesPromise = axios
    .get(`${API_V1_BASE_URL}/auth/capabilities`, {
      skipAuthRedirect: true,
      skipRefreshRetry: true
    })
    .then((response) => {
      authState.capabilities = normalizeAuthCapabilities(response.data)
      authState.capabilitiesStatus = AUTH_CAPABILITY_STATUS.READY
      return authState.capabilities
    })
    .catch((error) => {
      authState.capabilities = normalizeAuthCapabilities(null)
      authState.capabilitiesStatus = AUTH_CAPABILITY_STATUS.ERROR
      authState.capabilitiesError = error
      throw error
    })
    .finally(() => {
      authState.capabilitiesPromise = null
    })

  return authState.capabilitiesPromise
}

export const resolvePublicSignupCapability = async ({ force = false } = {}) => {
  try {
    await fetchAuthCapabilities({ force })
  } catch (error) {
    // Capability fetch failures stay observable through authState.capabilitiesStatus,
    // while the UI consumes the same helper in a safe closed state.
  }

  return getPublicSignupCapabilityState()
}

export const login = async ({ username, password }) => {
  const response = await axios.post(
    `${API_V1_BASE_URL}/auth/login`,
    { username, password },
    {
      skipAuthRedirect: true,
      skipRefreshRetry: true
    }
  )
  return applyAuthPayload(response.data)
}

export const register = async ({ username, displayName, password }) => {
  const response = await axios.post(
    `${API_V1_BASE_URL}/auth/register`,
    {
      username,
      display_name: displayName,
      password
    },
    {
      skipAuthRedirect: true,
      skipRefreshRetry: true
    }
  )
  return response.data
}

export const fetchCurrentUser = async () => {
  if (authState.mePromise) {
    return authState.mePromise
  }

  authState.mePromise = axios
    .get(`${API_V1_BASE_URL}/auth/me`, {
      skipAuthRedirect: true,
      skipRefreshRetry: true
    })
    .then((response) => {
      setCurrentUser(response.data || null)
      return authState.currentUser
    })
    .finally(() => {
      authState.mePromise = null
    })

  return authState.mePromise
}

export const refreshSession = async () => {
  if (authState.refreshPromise) {
    return authState.refreshPromise
  }

  const accessTokenBeforeRefresh = getAccessToken()
  authState.refreshPromise = axios
    .post(
      `${API_V1_BASE_URL}/auth/refresh`,
      {},
      {
        skipAuthRedirect: true,
        skipRefreshRetry: true
      }
    )
    .then((response) => applyAuthPayload(response.data))
    .catch((error) => {
      clearAuthSessionIfUnchanged(accessTokenBeforeRefresh)
      throw error
    })
    .finally(() => {
      authState.refreshPromise = null
    })

  return authState.refreshPromise
}

export const ensureAuthenticated = async () => {
  if (hasAccessToken()) {
    try {
      await fetchCurrentUser()
      return true
    } catch (error) {
      const status = error.response?.status
      const detail = error.response?.data?.detail
      if (status === 403 && detail === DISABLED_USER_DETAIL) {
        clearAuthSession()
        return false
      }
      if (status !== 401) {
        clearAuthSession()
        return false
      }
    }
  }

  const accessTokenBeforeRefresh = getAccessToken()
  try {
    await refreshSession()
    return true
  } catch (error) {
    clearAuthSessionIfUnchanged(accessTokenBeforeRefresh)
    return false
  }
}

export const logout = async () => {
  try {
    await axios.post(
      `${API_V1_BASE_URL}/auth/logout`,
      {},
      {
        skipAuthRedirect: true,
        skipRefreshRetry: true
      }
    )
  } finally {
    clearAuthSession()
  }
}

export const changePassword = async ({ currentPassword, newPassword }) => {
  const response = await axios.post(
    `${API_V1_BASE_URL}/auth/change-password`,
    {
      current_password: currentPassword,
      new_password: newPassword
    },
    {
      skipAuthRedirect: true,
      skipRefreshRetry: true
    }
  )
  return applyAuthPayload(response.data)
}
