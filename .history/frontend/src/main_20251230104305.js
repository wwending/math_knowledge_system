import { createApp } from 'vue'
import './style.css'
import App from './App.vue'

// --- 引入 Element Plus ---
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

const app = createApp(App)

// 注册 Element Plus
app.use(ElementPlus)

app.mount('#app')