const TOKEN_STORAGE_KEY = 'token'

export const getAccessToken = () => {
  return localStorage.getItem(TOKEN_STORAGE_KEY) || ''
}

export const hasAccessToken = () => {
  return Boolean(getAccessToken())
}

export const setAccessToken = (token) => {
  if (!token) {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    return
  }
  localStorage.setItem(TOKEN_STORAGE_KEY, token)
}

export const clearAuthSession = () => {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
}
