import { createApp } from 'vue'
import axios from 'axios'
import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import { API_BASE_URL } from './config/api'
import router from './router'
import {
  clearAuthSession,
  DISABLED_USER_DETAIL,
  getAccessToken,
  PASSWORD_CHANGE_REQUIRED_DETAIL,
  refreshSession
} from './utils/auth'

const REFRESH_EXCLUDED_PATHS = [
  '/auth/login',
  '/auth/register',
  '/auth/refresh',
  '/auth/logout',
  '/auth/capabilities'
]

const shouldSkipRefreshRetry = (url = '') => {
  return REFRESH_EXCLUDED_PATHS.some((path) => String(url).includes(path))
}

const clearAuthSessionIfUnchanged = (expectedAccessToken = '') => {
  if ((getAccessToken() || '') === (expectedAccessToken || '')) {
    clearAuthSession()
  }
}

axios.defaults.baseURL = API_BASE_URL
axios.defaults.withCredentials = true

axios.interceptors.request.use(
  (config) => {
    const token = getAccessToken()
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    const originalRequest = error.config || {}

    const canRetryWithRefresh =
      status === 401 &&
      !originalRequest.skipRefreshRetry &&
      !originalRequest._retryAfterRefresh &&
      !shouldSkipRefreshRetry(originalRequest.url)

    if (canRetryWithRefresh) {
      originalRequest._retryAfterRefresh = true
      const accessTokenBeforeRefresh = getAccessToken()
      try {
        await refreshSession()
        originalRequest.headers = originalRequest.headers || {}
        const nextToken = getAccessToken()
        if (nextToken) {
          originalRequest.headers.Authorization = `Bearer ${nextToken}`
        }
        return axios(originalRequest)
      } catch (refreshError) {
        clearAuthSessionIfUnchanged(accessTokenBeforeRefresh)
      }
    }

    if (status === 403 && detail === PASSWORD_CHANGE_REQUIRED_DETAIL && !originalRequest.skipAuthRedirect) {
      ElMessage.warning('当前账号需要先修改密码后再继续使用。')
      if (router.currentRoute.value.path !== '/change-password') {
        router.replace('/change-password')
      }
      return Promise.reject(error)
    }

    if (status === 403 && detail === DISABLED_USER_DETAIL && !originalRequest.skipAuthRedirect) {
      clearAuthSession()
      ElMessage.error('当前账号已被管理员禁用，请联系管理员。')
      if (router.currentRoute.value.path !== '/login') {
        router.replace('/login')
      }
      return Promise.reject(error)
    }

    if (status === 401 && !originalRequest.skipAuthRedirect) {
      clearAuthSession()
      ElMessage.error(detail || '登录状态已失效，请重新登录。')
      if (router.currentRoute.value.path !== '/login') {
        router.replace('/login')
      }
    }

    return Promise.reject(error)
  }
)

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus)
app.use(router)
app.mount('#app')
