import { createRouter, createWebHistory } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import { API_V1_BASE_URL } from '../config/api'
import { clearAuthSession, hasAccessToken } from '../utils/auth'

const routes = [
  { path: '/login', component: Login },
  {
    path: '/',
    component: Dashboard,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const validateStoredSession = async ({ showMessage = false } = {}) => {
  if (!hasAccessToken()) {
    return false
  }

  try {
    await axios.get(`${API_V1_BASE_URL}/auth/me`, { skipAuthRedirect: true })
    return true
  } catch (error) {
    if (showMessage) {
      const detail = error.response?.data?.detail
      ElMessage.error(detail || '登录状态已失效，请重新登录')
    }
    clearAuthSession()
    return false
  }
}

router.beforeEach(async (to, from, next) => {
  if (to.meta.requiresAuth && !hasAccessToken()) {
    ElMessage.warning('请先登录')
    next('/login')
    return
  }

  const isAuthenticated = await validateStoredSession({
    showMessage: to.meta.requiresAuth && hasAccessToken()
  })

  if (to.path === '/login' && isAuthenticated) {
    next('/')
    return
  }

  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/login')
    return
  }

  next()
})

export default router
