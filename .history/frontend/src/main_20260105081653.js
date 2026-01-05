import { createApp } from 'vue'
import './style.css'
import App from './App.vue'

// --- 引入 Element Plus ---
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

// 👇 1. 引入 router
import router from './router'

import * as ElementPlusIconsVue from '@element-plus/icons-vue'

const app = createApp(App)

// 注册所有图标 (防止图标丢失)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 注册 Element Plus
app.use(ElementPlus)

app.mount('#app')

// 👇 2. 挂载 router (这一行绝不能少！)
app.use(router)

app.mount('#app')