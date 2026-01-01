<template>
  <div class="app-container">
    
    <div v-if="!token" class="login-container">
      <el-card class="login-card" shadow="hover">
        <template #header>
          <div class="login-header">
            <h2>🔐 数学知识库系统</h2>
            <p>Math Knowledge System v1.1</p>
          </div>
        </template>

        <el-form :model="loginForm" @keyup.enter="handleAuth">
          <el-form-item>
            <el-input 
              v-model="loginForm.username" 
              placeholder="请输入用户名" 
              prefix-icon="User"
              size="large"
            />
          </el-form-item>
          <el-form-item>
            <el-input 
              v-model="loginForm.password" 
              type="password" 
              placeholder="请输入密码" 
              prefix-icon="Lock"
              size="large"
              show-password
            />
          </el-form-item>
          
          <div class="login-tips">
            <el-alert title="输入新账号将自动注册，旧账号自动登录" type="info" :closable="false" center show-icon />
          </div>

          <el-button 
            type="primary" 
            size="large" 
            :loading="authLoading" 
            @click="handleAuth" 
            style="width: 100%; margin-top: 20px;"
          >
            登录 / 注册
          </el-button>
        </el-form>
      </el-card>
    </div>

    <div v-else class="main-layout">
      
      <div class="top-bar">
        <div class="brand">
          <h2>📐 个人题库 Pro</h2>
          <el-tag v-if="role === 'admin'" type="danger" effect="dark" size="small">管理员模式</el-tag>
          <el-tag v-else type="success" effect="dark" size="small">普通用户</el-tag>
        </div>
        <div class="user-info">
          <span>👤 {{ username }}</span>
          <el-button type="info" link @click="logout">退出登录</el-button>
        </div>
      </div>

      <el-tabs v-model="activeTab" type="border-card" class="main-tabs" @tab-change="handleTabChange">
        
        <el-tab-pane label="📸 题目采集" name="upload">
          <el-row :gutter="20">
            <el-col :span="10">
              <el-card class="upload-card">
                <template #header>
                  <div class="card-header"><span>题目上传</span></div>
                </template>

                <el-tabs v-model="uploadMode" class="upload-mode-tabs" stretch>
                  
                  <el-tab-pane label="🖼️ 单图模式" name="image">
                    <el-upload
                      class="upload-demo"
                      drag
                      action="#" 
                      :auto-upload="false"
                      :on-change="handleFileChange"
                      :show-file-list="false"
                    >
                      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                      <div class="el-upload__text">拖拽或点击上传图片</div>
                    </el-upload>
                    
                    <div v-if="previewUrl" class="image-preview">
                      <img :src="previewUrl" alt="预览" />
                    </div>
                    
                    <el-button 
                      type="primary" 
                      size="large" 
                      :loading="loading" 
                      @click="startRecognition" 
                      :disabled="!selectedFile"
                      style="width: 100%; margin-top: 20px;"
                    >
                      {{ loading ? 'AI 分析中...' : '开始识别' }}
                    </el-button>
                  </el-tab-pane>

                  <el-tab-pane label="📄 PDF 模式" name="pdf">
                    <el-upload
                      class="upload-demo"
                      drag
                      action="#"
                      :auto-upload="false"
                      :on-change="handlePdfChange"
                      :show-file-list="false"
                      accept=".pdf"
                    >
                      <el-icon class="el-icon--upload"><document /></el-icon>
                      <div class="el-upload__text">拖拽 PDF 文件到此处</div>
                    </el-upload>

                    <div v-if="pdfPages.length > 0" class="pdf-gallery-area">
                      <p class="gallery-tip">👇 点击页面进行框选识别：</p>
                      <div class="pdf-grid">
                        <div 
                          v-for="(img, index) in pdfPages" 
                          :key="index" 
                          class="pdf-page-item"
                          @click="openCropper(img)"
                        >
                          <el-image 
                            :src="`http://127.0.0.1:8000/static/${img}`" 
                            fit="cover" 
                            loading="lazy"
                          />
                          <div class="page-badge">{{ index + 1 }}</div>
                        </div>
                      </div>
                    </div>
                  </el-tab-pane>

                </el-tabs>
              </el-card>
            </el-col>

            <el-col :span="14">
              <el-card class="result-card">
                <template #header>
                  <div class="card-header">
                    <span>识别结果</span>
                    <el-tag v-if="costTime" type="info" size="small">耗时: {{ costTime }}s</el-tag>
                  </div>
                </template>

                <div v-if="knowledgeTags && knowledgeTags.length > 0" class="knowledge-area">
                  <p class="section-title">🧠 AI 知识点预测：</p>
                  <div class="tags-wrapper">
                    <el-tooltip
                      v-for="(item, index) in knowledgeTags"
                      :key="index"
                      :content="`置信度: ${(item.score * 100).toFixed(1)}%`"
                      placement="top"
                    >
                      <el-tag 
                        :type="index === 0 ? 'success' : 'primary'" 
                        effect="dark"
                        class="k-tag"
                        size="large"
                      >
                        {{ item.label }}
                      </el-tag>
                    </el-tooltip>
                  </div>
                  <el-divider />
                </div>

                <div v-if="ocrResult" class="result-content">
                  <div v-html="renderedContent" class="markdown-body"></div>
                </div>
                <el-empty v-else description="请上传图片，AI 将自动归档到您的账号下" />
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="📚 我的题库" name="history">
          <div v-if="historyList.length === 0" class="empty-history">
            <el-empty description="暂无历史题目，快去上传第一道题吧！" />
          </div>
          
          <div v-else class="history-grid">
            <el-card v-for="item in historyList" :key="item.id" class="history-item" shadow="hover">
              <div class="history-img-wrapper">
                <el-image 
                  :src="`http://127.0.0.1:8000/static/${item.image_url}`" 
                  fit="cover"
                  loading="lazy"
                  :preview-src-list="[`http://127.0.0.1:8000/static/${item.image_url}`]"
                />
              </div>
              <div class="history-info">
                <div class="tags-row">
                  <el-tag v-if="item.knowledge_tags && item.knowledge_tags.length" size="small" effect="plain">
                    {{ item.knowledge_tags[0].label }}
                  </el-tag>
                  <el-tag v-if="item.status === 'pending'" type="warning" size="small" effect="dark">审核中</el-tag>
                  <el-tag v-else-if="item.status === 'approved'" type="success" size="small" effect="dark">已通过</el-tag>
                </div>
                <div class="meta-row">
                  <span class="date-text">{{ formatDate(item.created_at) }}</span>
                </div>
                <div class="content-preview">
                  {{ item.content ? item.content.slice(0, 40) + '...' : '无文本内容' }}
                </div>
              </div>
            </el-card>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog
      v-model="cropperVisible"
      title="✂️ 请框选题目区域"
      width="80%"
      top="5vh"
      destroy-on-close
      :close-on-click-modal="false"
      @opened="initCropper"
    >
      <div class="cropper-container" style="height: 60vh; background: #333;">
        <img ref="cropperImgRef" :src="currentCropImage" style="max-width: 100%; display: block;" />
      </div>
      <template #footer>
        <el-button @click="cropperVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmCrop" :loading="loading">
          确认框选并识别
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { UploadFilled, User, Lock, Document } from '@element-plus/icons-vue'
import axios from 'axios'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import Cropper from 'cropperjs'
import 'cropperjs/dist/cropper.css'
import { ElMessage } from 'element-plus'

// === 全局配置 ===
const API_BASE = 'http://127.0.0.1:8000/api/v1'

// === 状态: 认证 ===
const token = ref(localStorage.getItem('access_token') || '')
const username = ref('')
const role = ref('')
const authLoading = ref(false)
const loginForm = ref({ username: '', password: '' })

// === 状态: 应用 ===
const activeTab = ref('upload')
const historyList = ref([])

// === 状态: 题目上传 (通用) ===
const uploadMode = ref('image') // 'image' | 'pdf'
const selectedFile = ref(null)
const previewUrl = ref('')
const loading = ref(false)
const ocrResult = ref('')
const knowledgeTags = ref([])
const costTime = ref(null)

// === 状态: PDF & Cropper ===
const pdfPages = ref([])
const cropperVisible = ref(false)
const currentCropImage = ref('')
const cropperImgRef = ref(null)
let cropperInstance = null

// === 初始化 ===
onMounted(() => {
  if (token.value) {
    parseTokenInfo(token.value)
    fetchHistory()
  }
})

// === Axios 拦截器 ===
axios.interceptors.request.use(
  (config) => {
    if (token.value) {
      config.headers.Authorization = `Bearer ${token.value}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// === 功能 1: 登录/注册 ===
const handleAuth = async () => {
  if (!loginForm.value.username || !loginForm.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  authLoading.value = true
  try {
    let res
    try {
      res = await axios.post(`${API_BASE}/auth/register`, loginForm.value)
      ElMessage.success('🎉 新用户注册成功！已自动登录')
    } catch (regError) {
      const formData = new FormData()
      formData.append('username', loginForm.value.username)
      formData.append('password', loginForm.value.password)
      res = await axios.post(`${API_BASE}/auth/token`, formData)
      ElMessage.success('欢迎回来！登录成功')
    }
    const accessToken = res.data.access_token
    token.value = accessToken
    localStorage.setItem('access_token', accessToken)
    parseTokenInfo(accessToken)
    fetchHistory()
  } catch (error) {
    ElMessage.error('登录失败：用户名或密码错误')
  } finally {
    authLoading.value = false
  }
}

const logout = () => {
  token.value = ''
  username.value = ''
  role.value = ''
  localStorage.removeItem('access_token')
  ElMessage.info('已退出登录')
}

const parseTokenInfo = (jwtToken) => {
  try {
    const payload = JSON.parse(atob(jwtToken.split('.')[1]))
    username.value = payload.sub
    role.value = payload.role
  } catch (e) { logout() }
}

const handleTabChange = (tabName) => {
  if (tabName === 'history') fetchHistory()
}

const fetchHistory = async () => {
  if (!token.value) return
  try {
    const res = await axios.get(`${API_BASE}/history`)
    historyList.value = res.data
  } catch (e) { console.error("History Error", e) }
}

// === 功能 2: 单图上传 ===
const handleFileChange = (uploadFile) => {
  selectedFile.value = uploadFile.raw
  previewUrl.value = URL.createObjectURL(uploadFile.raw)
  ocrResult.value = ''
  knowledgeTags.value = []
}

// === 功能 3: PDF 上传 ===
const handlePdfChange = async (file) => {
  const formData = new FormData()
  formData.append('file', file.raw)
  loading.value = true
  try {
    const res = await axios.post(`${API_BASE}/upload_pdf`, formData)
    if (res.data.success) {
      pdfPages.value = res.data.images
      ElMessage.success(`PDF 解析成功，共 ${res.data.total_pages} 页`)
    }
  } catch (e) {
    ElMessage.error('PDF 上传失败')
  } finally {
    loading.value = false
  }
}

// === 功能 4: 裁剪与识别 ===
const openCropper = (imgPath) => {
  currentCropImage.value = `http://127.0.0.1:8000/static/${imgPath}`
  cropperVisible.value = true
}

const initCropper = () => {
  nextTick(() => {
    if (cropperImgRef.value) {
      cropperInstance = new Cropper(cropperImgRef.value, {
        viewMode: 1,
        dragMode: 'move',
        autoCropArea: 0.6,
        background: false,
      })
    }
  })
}

const confirmCrop = () => {
  if (!cropperInstance) return
  loading.value = true
  cropperInstance.getCroppedCanvas().toBlob(async (blob) => {
    const file = new File([blob], "cropped_question.jpg", { type: "image/jpeg" })
    await runRecognition(file)
    cropperVisible.value = false
    loading.value = false
  }, 'image/jpeg')
}

// === 核心: 通用识别逻辑 ===
const runRecognition = async (fileRaw) => {
  const formData = new FormData()
  formData.append('file', fileRaw)
  
  try {
    const response = await axios.post(`${API_BASE}/recognize`, formData)
    if (response.data.success) {
      ocrResult.value = response.data.content
      knowledgeTags.value = response.data.knowledge || []
      costTime.value = response.data.cost_seconds
      ElMessage.success('识别成功！')
      
      if (uploadMode.value === 'pdf') {
         previewUrl.value = URL.createObjectURL(fileRaw)
      }
      fetchHistory()
    } else {
      ocrResult.value = `❌ 识别失败: ${response.data.error}`
    }
  } catch (error) {
    ElMessage.error('识别出错')
  }
}

// 单图模式按钮调用
const startRecognition = async () => {
  if (!selectedFile.value) return
  loading.value = true
  await runRecognition(selectedFile.value)
  loading.value = false
}

// === 工具函数 ===
const formatDate = (isoString) => {
  const date = new Date(isoString)
  return date.toLocaleString()
}

const renderedContent = computed(() => {
  if (!ocrResult.value) return ''
  let text = ocrResult.value.replace(/\n/g, '<br>')
  try {
     text = text.replace(/\$([^$]+)\$/g, (match, formula) => katex.renderToString(formula, { throwOnError: false }))
  } catch (e) {}
  return text
})
</script>

<style scoped>
/* 全局 */
.app-container { max-width: 1400px; margin: 0 auto; padding: 20px; min-height: 100vh; font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif; }

/* 登录 */
.login-container { display: flex; justify-content: center; align-items: center; height: 80vh; background-color: #f5f7fa; }
.login-card { width: 400px; padding: 20px; border-radius: 12px; }
.login-header { text-align: center; margin-bottom: 20px; }
.login-header h2 { margin: 0; color: #409EFF; }
.login-tips { margin-top: 15px; }

/* 主界面 */
.top-bar { display: flex; justify-content: space-between; align-items: center; padding: 0 10px 20px 10px; border-bottom: 1px solid #ebeef5; margin-bottom: 20px; }
.brand { display: flex; align-items: center; gap: 10px; }
.brand h2 { margin: 0; color: #303133; }
.user-info { display: flex; align-items: center; gap: 15px; font-size: 14px; color: #606266; }

/* 上传卡片 */
.upload-card, .result-card { height: 80vh; overflow-y: auto; display: flex; flex-direction: column; }
.image-preview img { max-width: 100%; max-height: 300px; margin-top: 20px; border: 1px dashed #dcdfe6; border-radius: 6px; display: block; margin: 20px auto; }

/* 知识点标签 */
.knowledge-area { background: #f0f9eb; padding: 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #e1f3d8; }
.section-title { font-weight: bold; margin-bottom: 10px; color: #529b2e; font-size: 14px; }
.tags-wrapper { display: flex; gap: 10px; flex-wrap: wrap; }
.k-tag { font-size: 14px; padding: 8px 15px; }

/* 历史记录 */
.history-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
.history-item { cursor: pointer; transition: all 0.3s; border-radius: 8px; overflow: hidden; }
.history-item:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
.history-img-wrapper { height: 160px; overflow: hidden; background: #f5f7fa; }
.history-img-wrapper .el-image { width: 100%; height: 100%; }
.history-info { padding: 15px; }
.tags-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.meta-row { margin-bottom: 8px; font-size: 12px; color: #909399; }
.content-preview { font-size: 13px; color: #606266; line-height: 1.5; height: 40px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }

/* Result */
.result-content { font-size: 16px; line-height: 1.8; color: #303133; padding: 10px; }

/* PDF 画廊 */
.pdf-gallery-area { margin-top: 20px; border-top: 1px dashed #dcdfe6; padding-top: 15px; }
.gallery-tip { font-size: 13px; color: #909399; margin-bottom: 10px; }
.pdf-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; max-height: 400px; overflow-y: auto; padding-right: 5px; }
.pdf-page-item { position: relative; cursor: pointer; border: 2px solid transparent; border-radius: 4px; overflow: hidden; transition: all 0.2s; }
.pdf-page-item:hover { border-color: #409EFF; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.page-badge { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.6); color: white; font-size: 12px; text-align: center; padding: 2px 0; }
</style>