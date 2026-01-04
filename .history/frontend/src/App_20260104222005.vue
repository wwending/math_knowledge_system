<template>
  <div class="common-layout">
    <el-container>
      <el-aside width="220px">
        <div class="logo-area">
          <el-icon :size="24" color="#409EFF"><EditPen /></el-icon>
          <span class="logo-text">错题本 AI</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical"
          @select="handleMenuSelect"
        >
          <el-menu-item index="upload">
            <el-icon><UploadFilled /></el-icon>
            <span>题目采集</span>
          </el-menu-item>
          <el-menu-item index="bank">
            <el-icon><Collection /></el-icon>
            <span>智能题库</span>
          </el-menu-item>
          <el-menu-item index="history">
            <el-icon><Clock /></el-icon>
            <span>历史记录</span>
          </el-menu-item>
        </el-menu>
        
        <div class="user-area">
          <div v-if="isLoggedIn" class="user-info">
            <el-avatar :size="30" icon="UserFilled" />
            <span class="username">已登录</span>
            <el-button type="danger" link size="small" @click="handleLogout">退出</el-button>
          </div>
          <div v-else>
            <el-button type="primary" link @click="loginVisible = true">点击登录</el-button>
          </div>
        </div>
      </el-aside>

      <el-main>
        <div v-if="activeMenu === 'upload'" class="upload-container">
          <div class="upload-header">
            <h2>📸 题目采集</h2>
            <p class="subtitle">上传题目图片，AI 自动识别排版并提取知识点</p>
          </div>

          <div class="upload-box">
            <el-upload
              drag
              action="#"
              :auto-upload="false"
              :on-change="handleFileChange"
              :show-file-list="false"
              accept=".jpg,.jpeg,.png,.bmp,.webp,.pdf"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                将图片或PDF拖到此处，或 <em>点击上传</em>
              </div>
            </el-upload>
          </div>

          <div v-if="ocrLoading" class="loading-state">
            <el-skeleton :rows="5" animated />
            <p>正在请求 DeepSeek 进行智能分析...</p>
          </div>

          <div v-if="ocrResult && !ocrLoading" class="result-section">
            <el-row :gutter="20">
              <el-col :span="16">
                <el-card class="ocr-result-box" shadow="hover">
                  <template #header>
                    <div class="card-header">
                      <span>📐 识别结果 (预览)</span>
                      <el-tag type="success" effect="dark">MathJax 渲染</el-tag>
                    </div>
                  </template>
                  <div class="markdown-body" v-html="renderedContent"></div>
                </el-card>
              </el-col>

              <el-col :span="8">
                <el-card class="meta-box" shadow="hover">
                  <template #header>
                    <span>🧠 知识点分析</span>
                  </template>
                  <div class="tags-container">
                    <el-empty v-if="!knowledgeTags.length" description="暂无知识点" :image-size="60" />
                    <el-tag
                      v-for="(tag, index) in knowledgeTags"
                      :key="index"
                      class="knowledge-tag"
                      effect="light"
                      round
                    >
                      {{ tag.label || tag }}
                    </el-tag>
                  </div>
                  <el-divider />
                  <div class="info-item">
                    <span>耗时：</span>
                    <strong>{{ costTime }} 秒</strong>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </div>
        </div>

        <div v-else class="history-container">
          <div class="page-header">
            <h2>{{ activeMenu === 'bank' ? '📚 智能题库' : '🕒 历史记录' }}</h2>
            <el-button type="primary" @click="getHistory" :icon="Refresh">刷新列表</el-button>
          </div>

          <el-empty v-if="historyList.length === 0" description="暂无数据" />

          <div class="question-list">
            <el-card 
              v-for="item in historyList" 
              :key="item.id" 
              class="question-item" 
              shadow="hover"
              @click="openDetail(item)"
            >
              <div class="q-content">
                <div class="q-meta">
                  <el-tag size="small" type="info">{{ formatDate(item.created_at) }}</el-tag>
                  <div class="q-tags" v-if="item.knowledge_tags">
                    <el-tag 
                      v-for="(t, i) in parseTags(item.knowledge_tags)" 
                      :key="i" 
                      size="small" 
                      effect="plain"
                    >
                      {{ t.label || t }}
                    </el-tag>
                  </div>
                </div>
                <div 
                  class="markdown-body mini-preview" 
                  v-html="md.render(smartLatexFix(item.content.slice(0, 150) + (item.content.length > 150 ? '...' : '')))"
                ></div>
              </div>
              <div class="q-actions">
                <el-button type="danger" :icon="Delete" circle size="small" @click.stop="handleDelete(item.id)" />
              </div>
            </el-card>
          </div>
        </div>
      </el-main>
    </el-container>

    <el-dialog
      v-model="loginVisible"
      title="登录系统"
      width="400px"
      :close-on-click-modal="false"
      :show-close="false"
      center
    >
      <el-form :model="loginForm" label-width="60px">
        <el-form-item label="账号">
          <el-input v-model="loginForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="handleLogin" :loading="loginLoading" style="width: 100%">登 录</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailVisible"
      title="题目详情"
      width="900px"
      top="5vh"
      class="detail-dialog"
      :close-on-click-modal="false"
    >
      <div class="detail-container" v-if="currentDetailItem">
        <div class="detail-toolbar">
          <el-radio-group v-model="detailMode" size="small">
            <el-radio-button label="preview">👀 预览模式</el-radio-button>
            <el-radio-button label="edit">✏️ 编辑模式</el-radio-button>
          </el-radio-group>
          
          <el-button 
            v-if="detailMode === 'edit'" 
            type="success" 
            size="small" 
            :loading="saveLoading"
            @click="saveContent"
          >
            保存修改
          </el-button>
        </div>

        <el-divider style="margin: 15px 0" />

        <div v-if="detailMode === 'preview'" class="preview-area">
           <div class="markdown-body" v-html="detailRenderedContent"></div>
        </div>

        <div v-else class="edit-area">
           <el-input
             v-model="editingContent"
             type="textarea"
             :rows="15"
             placeholder="在此处修正 LaTeX 代码..."
             class="edit-textarea"
           />
        </div>

        <el-divider content-position="center">原始图片对照</el-divider>
        <div class="detail-image-area">
           <el-image 
            v-if="currentDetailItem.image_url"
            :src="getImageUrl(currentDetailItem.image_url)" 
            fit="contain"
            :preview-src-list="[getImageUrl(currentDetailItem.image_url)]"
          />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, EditPen, Collection, Clock, Delete, Refresh, UserFilled } from '@element-plus/icons-vue'

// 引入 Markdown 和 MathJax
import MarkdownIt from 'markdown-it'
import markdownItMathjax3 from 'markdown-it-mathjax3'

// ============================================
// 0. API 与 认证配置
// ============================================
const API_BASE = 'http://127.0.0.1:8000/api/v1'

// 配置 Axios 拦截器，自动携带 Token
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}, (error) => {
  return Promise.reject(error)
})

// 响应拦截：处理 401 过期
axios.interceptors.response.use((response) => {
  return response
}, (error) => {
  if (error.response && error.response.status === 401) {
    ElMessage.error('登录已过期，请重新登录')
    handleLogout()
  }
  return Promise.reject(error)
})

// ============================================
// 1. Markdown 引擎初始化
// ============================================
const md = new MarkdownIt({ html: true, breaks: true, linkify: true })
md.use(markdownItMathjax3, {
  tex: { inlineMath: [['$', '$'], ['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']] }
})

// ============================================
// 2. 状态变量
// ============================================
const activeMenu = ref('upload')
const ocrLoading = ref(false)
const ocrResult = ref('')
const knowledgeTags = ref([])
const costTime = ref(0)
const historyList = ref([])

// 登录相关
const loginVisible = ref(false)
const isLoggedIn = ref(false)
const loginLoading = ref(false)
const loginForm = ref({ username: '', password: '' })

// 详情页相关
const detailVisible = ref(false)
const currentDetailItem = ref(null)
const detailMode = ref('preview')
const editingContent = ref('')
const saveLoading = ref(false)

// ============================================
// 3. 工具函数
// ============================================
const smartLatexFix = (text) => {
  if (!text) return ''
  let res = text.replace(/\\\{/g, '{').replace(/\\\}/g, '}')
  res = res.replace(/（/g, '(').replace(/）/g, ')')
  return res
}

const formatDate = (val) => {
  if (!val) return ''
  const date = new Date(val)
  return date.toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-')
}

const getImageUrl = (path) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  return `http://127.0.0.1:8000/static/${path}`
}

const parseTags = (tags) => {
  if (!tags) return []
  if (typeof tags === 'string') {
    try { return JSON.parse(tags) } catch { return [] }
  }
  return tags
}

// ============================================
// 4. 认证逻辑 (Login/Logout)
// ============================================
const handleLogin = async () => {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loginLoading.value = true
  try {
    // 发送 x-www-form-urlencoded 格式
    const params = new URLSearchParams()
    params.append('username', loginForm.value.username)
    params.append('password', loginForm.value.password)

    const res = await axios.post(`${API_BASE}/auth/token`, params)
    
    // 保存 Token
    localStorage.setItem('access_token', res.data.access_token)
    isLoggedIn.value = true
    loginVisible.value = false
    ElMessage.success('登录成功')
    
    // 登录后自动刷新当前列表
    if (activeMenu.value === 'history' || activeMenu.value === 'bank') {
      getHistory()
    }
  } catch (error) {
    ElMessage.error('登录失败：账号或密码错误')
  } finally {
    loginLoading.value = false
  }
}

const handleLogout = () => {
  localStorage.removeItem('access_token')
  isLoggedIn.value = false
  loginVisible.value = true // 登出后显示登录框
  historyList.value = []    // 清空敏感数据
}

// ============================================
// 5. 业务逻辑
// ============================================
const renderedContent = computed(() => {
  if (!ocrResult.value) return ''
  return md.render(smartLatexFix(ocrResult.value))
})

const detailRenderedContent = computed(() => {
  const rawText = detailMode.value === 'edit' ? editingContent.value : (currentDetailItem.value?.content || '')
  if (!rawText) return '暂无内容'
  return md.render(smartLatexFix(rawText))
})

const handleMenuSelect = (index) => {
  activeMenu.value = index
  if (index === 'history' || index === 'bank') {
    getHistory()
  }
}

// 修改 handleFileChange 函数
const handleFileChange = async (uploadFile) => {
  if (!uploadFile.raw) return
  
  const file = uploadFile.raw
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')

  if (isPdf) {
    // === PDF 处理流程 ===
    // 1. 开启 Loading，防止用户以为没反应
    ocrLoading.value = true
    ElMessage.info('正在解析 PDF 文件...')

    const formData = new FormData()
    formData.append('file', file)
    
    try {
      // 2. 上传 PDF 到后端转换为图片
      // 注意：这里利用了 axios 拦截器，自动带了 Token
      const res = await axios.post(`${API_BASE}/upload_pdf`, formData, {
         headers: { 'Content-Type': 'multipart/form-data' }
      })
      
      if (res.data.success && res.data.images && res.data.images.length > 0) {
        // 3. 拿到第一张图片的相对路径 (例如: pdf_temp/xxx_page_0.jpg)
        const imgRelPath = res.data.images[0]
        
        // 拼接完整的图片 URL (假设后端开在 8000 端口)
        // 注意：这里硬编码了后端地址，如果你的端口变了记得改
        const imgUrl = `http://127.0.0.1:8000/static/${imgRelPath}`
        
        // 4. 将远程图片下载为 Blob 对象，伪装成一个 File
        // 这样 runRecognition 就不需要改动代码了
        const blob = await fetch(imgUrl).then(r => r.blob())
        const imgFile = new File([blob], "pdf_converted_page_1.jpg", { type: "image/jpeg" })
        
        ElMessage.success('PDF 解析成功，正在识别内容...')
        
        // 5. 走正常的图片识别流程
        runRecognition(imgFile)
      } else {
        ElMessage.warning('PDF 解析成功但未生成图片，请重试')
        ocrLoading.value = false
      }
    } catch (e) {
      console.error(e)
      ElMessage.error('PDF 上传或解析失败，请检查文件')
      ocrLoading.value = false
    }
  } else {
    // === 普通图片流程 (保持不变) ===
    runRecognition(file)
  }
}

const runRecognition = async (file) => {
  if (!isLoggedIn.value) {
    loginVisible.value = true
    return
  }
  
  ocrLoading.value = true
  ocrResult.value = ''
  knowledgeTags.value = []
  
  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await axios.post(`${API_BASE}/recognize`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    if (res.data.success) {
      ocrResult.value = res.data.content
      knowledgeTags.value = res.data.knowledge || []
      costTime.value = res.data.cost_seconds
      ElMessage.success('识别完成')
      console.log('=== DeepSeek 返回 ===', res.data.content)
    } else {
      ElMessage.error(res.data.error || '识别失败')
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('识别请求失败')
  } finally {
    ocrLoading.value = false
  }
}

const getHistory = async () => {
  if (!isLoggedIn.value) return
  try {
    const res = await axios.get(`${API_BASE}/history?limit=50`)
    historyList.value = res.data
  } catch (error) {
    console.error('获取历史失败', error)
  }
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除这道题吗？', '警告', { type: 'warning' })
    ElMessage.success('删除成功 (前端演示)')
    getHistory()
  } catch (e) { }
}

const openDetail = (item) => {
  currentDetailItem.value = item
  editingContent.value = item.content
  detailMode.value = 'preview'
  detailVisible.value = true
}

const saveContent = async () => {
  if (!currentDetailItem.value) return
  saveLoading.value = true
  try {
    await axios.put(`${API_BASE}/questions/${currentDetailItem.value.id}`, { 
      content: editingContent.value 
    })
    currentDetailItem.value.content = editingContent.value
    const listItem = historyList.value.find(i => i.id === currentDetailItem.value.id)
    if (listItem) listItem.content = editingContent.value

    ElMessage.success('修改已保存！')
    detailMode.value = 'preview'
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saveLoading.value = false
  }
}

// 初始化检查登录状态
onMounted(() => {
  const token = localStorage.getItem('access_token')
  if (token) {
    isLoggedIn.value = true
    getHistory()
  } else {
    loginVisible.value = true // 没登录直接弹窗
  }
})
</script>

<style>
/* 保持你之前的 CSS 样式不变 */
html, body, #app { height: 100%; margin: 0; padding: 0; overflow: hidden; font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif; }
.common-layout { height: 100vh; display: flex; }
.el-container { height: 100%; width: 100%; }
.el-aside { background-color: #fff; border-right: 1px solid #e6e6e6; display: flex; flex-direction: column; }
.logo-area { height: 60px; display: flex; align-items: center; justify-content: center; border-bottom: 1px solid #f0f0f0; gap: 10px; }
.logo-text { font-weight: bold; font-size: 18px; color: #303133; }
.user-area { margin-top: auto; padding: 15px; border-top: 1px solid #eee; text-align: center; }
.user-info { display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 14px; color: #606266; }
.el-main { height: 100%; overflow-y: auto !important; padding: 20px; background-color: #f5f7fa; scroll-behavior: smooth; }
.upload-header { text-align: center; margin-bottom: 30px; }
.upload-box { max-width: 600px; margin: 0 auto 30px; }
.ocr-result-box { min-height: 400px; height: auto; }
.tags-container { display: flex; flex-wrap: wrap; gap: 10px; min-height: 100px; }
.knowledge-tag { font-size: 14px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.question-list { display: grid; gap: 15px; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }
.question-item { cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }
.question-item:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.q-meta { display: flex; justify-content: space-between; margin-bottom: 10px; }
.q-tags { display: flex; gap: 5px; }
.mini-preview { font-size: 13px; color: #606266; max-height: 100px; overflow: hidden; text-overflow: ellipsis; }
.q-actions { margin-top: 10px; text-align: right; opacity: 0; transition: opacity 0.2s; }
.question-item:hover .q-actions { opacity: 1; }
.markdown-body { font-family: "Times New Roman", "SimSun", "Songti SC", serif; font-size: 18px; line-height: 2.0; color: #2c3e50; overflow-x: auto; }
.markdown-body p { margin-bottom: 16px; text-align: justify; }
mjx-container { font-size: 1.1em !important; outline: none; }
.detail-toolbar { display: flex; justify-content: space-between; align-items: center; }
.edit-textarea textarea { font-family: Consolas, Monaco, monospace; font-size: 14px; line-height: 1.5; }
.edit-tips { margin-top: 10px; font-size: 12px; color: #909399; background: #f4f4f5; padding: 10px; border-radius: 4px; }
.detail-image-area { text-align: center; margin-top: 20px; background: #fafafa; padding: 10px; border-radius: 4px; }
</style>