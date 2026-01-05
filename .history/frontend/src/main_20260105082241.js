import { createApp } from 'vue'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import router from './router'
import axios from 'axios' // 1. 引入 axios

// 2. 配置 Axios 全局拦截器 (核心代码)
// 设置后端地址 (根据你实际情况调整)
axios.defaults.baseURL = 'http://127.0.0.1:8000' 

axios.interceptors.request.use(config => {
  // 每次发送请求前，去 localStorage 拿 token
  const token = localStorage.getItem('token')
  if (token) {
    // 如果有 token，就放到 Header 里
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}, error => {
  return Promise.reject(error)
})

// 3. 拦截 401 响应 (可选：Token 过期自动踢回登录页)
axios.interceptors.response.use(response => {
  return response
}, error => {
  if (error.response && error.response.status === 401) {
    localStorage.removeItem('token')
    router.push('/login')
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