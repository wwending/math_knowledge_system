import { createRouter, createWebHistory } from 'vue-router'
// 注意路径：如果 Login.vue 在 views 文件夹下，就要写 ../views/Login.vue
import Login from '../views/Login.vue' 
import Dashboard from '../views/Dashboard.vue'

const routes = [
  { path: '/login', component: Login },
  { path: '/', component: Dashboard } // 需要登录保护的页面
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router