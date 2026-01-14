import { createRouter, createWebHistory } from 'vue-router'
// 注意路径：如果 Login.vue 在 views 文件夹下，就要写 ../views/Login.vue
import Login from '../views/Login.vue' 
import Dashboard from '../views/Dashboard.vue'



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

// 全局前置守卫：检查是否有 token
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  
  // ????????? -> ???
  if (to.path === '/login' && token) {
    next('/')
    return
  }

  // ??????????????? token -> ?????
  if (to.meta.requiresAuth && !token) {
    next('/login')
    return
  }

  next()
})

export default router
