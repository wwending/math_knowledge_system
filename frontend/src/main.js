import { createApp } from 'vue'
import axios from 'axios'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import App from './App.vue'
import { API_BASE_URL } from './config/api'
import { clearAuthSession, getAccessToken } from './utils/auth'
import router from './router'

axios.defaults.baseURL = API_BASE_URL

axios.interceptors.request.use(config => {
  const token = getAccessToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}, error => {
  return Promise.reject(error)
})

axios.interceptors.response.use(response => {
  return response
}, error => {
  const shouldHandleUnauthorized = (
    error.response &&
    error.response.status === 401 &&
    !error.config?.skipAuthRedirect
  )

  if (shouldHandleUnauthorized) {
    clearAuthSession()
    const detail = error.response?.data?.detail
    ElMessage.error(detail || '登录状态已失效，请重新登录')
    if (router.currentRoute.value.path !== '/login') {
      router.replace('/login')
    }
  }
  return Promise.reject(error)
})

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus)
app.use(router)
app.mount('#app')
