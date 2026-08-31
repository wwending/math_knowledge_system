import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Dashboard from '../views/Dashboard.vue'
import QuestionEditor from '../views/QuestionEditor.vue'
import ChangePassword from '../views/ChangePassword.vue'
import {
  ensureAuthenticated,
  getCurrentUser,
  resolvePublicSignupCapability
} from '../utils/auth'

const PUBLIC_SIGNUP_DISABLED_MESSAGE = '当前环境未开放公开注册，请联系管理员创建账号。'
const PUBLIC_SIGNUP_CAPABILITY_UNAVAILABLE_MESSAGE = '暂时无法确认当前环境是否开放公开注册，前端会按关闭状态处理，请稍后重试。'

const routes = [
  {
    path: '/login',
    component: Login,
    meta: { guestOnly: true }
  },
  {
    path: '/register',
    component: Register,
    meta: { guestOnly: true }
  },
  {
    path: '/change-password',
    component: ChangePassword,
    meta: { requiresAuth: true }
  },
  {
    path: '/',
    component: Dashboard,
    meta: { requiresAuth: true }
  },
  {
    path: '/questions/:id/edit',
    name: 'question-editor',
    component: QuestionEditor,
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  if (to.meta.guestOnly) {
    const authenticated = await ensureAuthenticated()
    if (authenticated) {
      const currentUser = getCurrentUser()
      next('/')
      return
    }
  }

  if (to.path === '/register') {
    const publicSignupCapability = await resolvePublicSignupCapability({ force: true })
    if (!publicSignupCapability.enabled) {
      ElMessage[publicSignupCapability.failed ? 'error' : 'warning'](
        publicSignupCapability.failed
          ? PUBLIC_SIGNUP_CAPABILITY_UNAVAILABLE_MESSAGE
          : PUBLIC_SIGNUP_DISABLED_MESSAGE
      )
      next('/login')
      return
    }
  }

  if (to.meta.requiresAuth) {
    const authenticated = await ensureAuthenticated()
    if (!authenticated) {
      next('/login')
      return
    }
  }

  const currentUser = getCurrentUser()
  if (to.path === '/login' && currentUser) {
    next('/')
    return
  }

  next()
})

export default router
