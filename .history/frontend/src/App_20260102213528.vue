<template>
  <div class="app-wrapper">
    
    <div v-if="!token" class="login-container">
      <div class="login-content">
        <div class="login-left">
          <h1>Math Knowledge<br>System</h1>
          <p>AI 驱动的个人数学知识库构建系统<br>OCR 识别 · 知识点分类 · 智能检索</p>
          <img src="https://illustrations.popsy.co/amber/student-going-to-school.svg" alt="Login Art" class="login-art">
        </div>
        <el-card class="login-card" shadow="always">
          <h2>欢迎回来</h2>
          <p class="login-sub">请输入您的账号信息</p>
          
          <el-form :model="loginForm" @keyup.enter="handleAuth" size="large" class="login-form">
            <el-form-item>
              <el-input 
                v-model="loginForm.username" 
                placeholder="用户名" 
                prefix-icon="User" 
              />
            </el-form-item>
            <el-form-item>
              <el-input 
                v-model="loginForm.password" 
                type="password" 
                placeholder="密码" 
                prefix-icon="Lock" 
                show-password 
              />
            </el-form-item>
            
            <el-button 
              type="primary" 
              :loading="authLoading" 
              @click="handleAuth" 
              class="login-btn"
            >
              登录 / 注册
            </el-button>
          </el-form>
          <div class="login-footer">
            <el-tag type="info" size="small">自动注册模式开启</el-tag>
          </div>
        </el-card>
      </div>
    </div>

    <el-container v-else class="main-layout">
      
      <el-header class="app-header">
        <div class="header-left">
          <div class="logo-box">📐</div>
          <div class="app-title">
            <h3>Math Knowledge Pro</h3>
            <span class="version">v1.2</span>
          </div>
        </div>
        
        <div class="header-center">
          </div>

        <div class="header-right">
          <el-tag v-if="role === 'admin'" effect="dark" round color="#626aef" style="border:none">管理员</el-tag>
          <el-tag v-else effect="dark" round type="success">普通用户</el-tag>
          <span class="username">{{ username }}</span>
          <el-divider direction="vertical" />
          <el-button type="danger" link @click="logout">退出</el-button>
        </div>
      </el-header>

      <el-main class="app-content">
        <el-tabs v-model="activeTab" class="full-height-tabs" type="border-card" @tab-change="handleTabChange">
          
          <el-tab-pane name="upload" class="workspace-pane">
            <template #label>
              <span class="custom-tab-label"><el-icon><Monitor /></el-icon> 题目采集工作台</span>
            </template>
            
            <div class="workspace-grid">
              <div class="panel-left">
                <div class="panel-header">
                  <span class="title">📄 原始文件</span>
                  <el-radio-group v-model="uploadMode" size="small">
                    <el-radio-button label="image">单图</el-radio-button>
                    <el-radio-button label="pdf">PDF 册</el-radio-button>
                  </el-radio-group>
                </div>
                
                <div class="panel-body">
                  <div v-if="uploadMode === 'image'" class="upload-wrapper">
                    <el-upload
                      class="upload-box"
                      drag
                      action="#" 
                      :auto-upload="false"
                      :on-change="handleFileChange"
                      :show-file-list="false"
                    >
                      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                      <div class="el-upload__text">拖拽图片 或 点击上传</div>
                    </el-upload>
                    
                    <div v-if="previewUrl" class="preview-area">
                      <img :src="previewUrl" class="single-preview" />
                    </div>

                    <el-button 
                      type="primary" 
                      size="large" 
                      class="action-btn"
                      :loading="loading" 
                      @click="startRecognition" 
                      :disabled="!selectedFile"
                    >
                      {{ loading ? 'AI 正在分析...' : '🚀 开始识别并入库' }}
                    </el-button>
                  </div>

                  <div v-else class="upload-wrapper">
                    <el-upload
                      class="upload-box mini"
                      drag
                      action="#"
                      :auto-upload="false"
                      :on-change="handlePdfChange"
                      :show-file-list="false"
                      accept=".pdf"
                    >
                      <div class="el-upload__text">📄 点击或拖拽上传 PDF</div>
                    </el-upload>

                    <div v-if="pdfPages.length > 0" class="pdf-list-container">
                      <div class="grid-layout">
                        <div 
                          v-for="(img, index) in pdfPages" 
                          :key="index" 
                          class="pdf-card"
                          @click="openCropper(img)"
                        >
                          <el-image 
                            :src="`http://127.0.0.1:8000/static/${img}`" 
                            fit="cover" 
                            loading="lazy"
                          />
                          <div class="pdf-overlay">
                            <span>第 {{ index + 1 }} 页</span>
                            <el-icon><Crop /></el-icon>
                          </div>
                        </div>
                      </div>
                    </div>
                    <el-empty v-else description="暂无 PDF 页面" :image-size="60" />
                  </div>
                </div>
              </div>

              <div class="panel-right">
                <div class="panel-header">
                  <span class="title">🤖 识别结果与知识点</span>
                  <el-tag v-if="costTime" type="success" size="small" effect="plain">耗时: {{ costTime }}s</el-tag>
                </div>
                
                <div class="panel-body result-body">
                  <div v-if="ocrResult">
                    <div class="knowledge-card" v-if="knowledgeTags.length">
                      <div class="k-title">🧠 知识点预测</div>
                      <div class="k-tags">
                         <el-tag 
                          v-for="(item, index) in knowledgeTags"
                          :key="index"
                          :type="index === 0 ? 'primary' : 'info'" 
                          effect="light"
                          round
                        >
                          {{ item.label }} <span style="opacity:0.6">{{ (item.score*100).toFixed(0) }}%</span>
                        </el-tag>
                      </div>
                    </div>

                    <div class="markdown-content">
                      <div v-html="renderedContent" class="markdown-body"></div>
                    </div>
                  </div>
                  
                  <el-empty v-else description="等待 AI 分析..." image="https://gw.alipayobjects.com/zos/antfincdn/ZHrcdLPrvN/empty.svg" />
                </div>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane name="history" class="bank-pane">
          <template #label>
            <span class="custom-tab-label"><el-icon><Collection /></el-icon> 智能题库</span>
          </template>
          
          <div class="bank-container">
            <div class="bank-sidebar">
              <div class="sidebar-header">
                <el-icon><files /></el-icon> 知识点目录
              </div>
              <div class="tag-list">
                <div 
                  class="tag-item" 
                  :class="{ active: !currentTagFilter }"
                  @click="handleTagFilter('')"
                >
                  <span class="dot all"></span> 全部题目
                </div>
                <div 
                  v-for="tag in allTags" 
                  :key="tag" 
                  class="tag-item"
                  :class="{ active: currentTagFilter === tag }"
                  @click="handleTagFilter(tag)"
                >
                  <span class="dot"></span> {{ tag }}
                </div>
              </div>
            </div>

            <div class="bank-main">
              <div class="filter-bar">
                <div class="filter-left">
                  <el-input 
                    v-model="searchKeyword" 
                    placeholder="🔍 搜索题干内容、公式..." 
                    class="search-input"
                    clearable
                    @clear="fetchHistory"
                    @keyup.enter="fetchHistory"
                  >
                    <template #append>
                      <el-button @click="fetchHistory">搜索</el-button>
                    </template>
                  </el-input>
                </div>
                <div class="filter-right">
                  <span class="meta-info">共找到 {{ historyList.length }} 道题</span>
                  <el-button circle icon="Refresh" @click="fetchHistory" />
                </div>
              </div>

              <div v-if="historyList.length === 0" class="empty-state">
                <el-empty description="没有找到相关题目" />
              </div>
              
              <div v-else class="question-list">
                <div 
                  v-for="item in historyList" 
                  :key="item.id" 
                  class="q-card"
                  @click="openDetail(item)"
                >
                  <div class="q-header">
                    <div class="q-tags">
                      <el-tag v-if="item.knowledge_tags?.[0]" size="small" effect="dark">{{ item.knowledge_tags[0].label }}</el-tag>
                      <el-tag v-else size="small" type="info">未分类</el-tag>
                    </div>
                    <span class="q-date">{{ formatDate(item.created_at) }}</span>
                  </div>
                  
                  <div class="q-body-preview">
                    {{ item.content ? item.content.slice(0, 60) + '...' : '[图片题目]' }}
                  </div>
                  
                  <div class="q-footer">
                     <el-image 
                        class="q-thumb"
                        :src="`http://127.0.0.1:8000/static/${item.image_url}`" 
                        fit="cover"
                        loading="lazy"
                      />
                      <el-button type="primary" link class="view-btn">查看详情 <el-icon><ArrowRight /></el-icon></el-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>
        </el-tabs>
      </el-main>
    </el-container>

    <el-dialog
      v-model="cropperVisible"
      title="✂️ 框选题目区域"
      width="900px"
      top="5vh"
      destroy-on-close
      :close-on-click-modal="false"
      @opened="initCropper"
      class="cropper-dialog"
    >
      <div class="cropper-view">
        <img ref="cropperImgRef" :src="currentCropImage" />
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="cropperVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmCrop" :loading="loading" icon="Select">
            确认并识别
          </el-button>
        </span>
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
            icon="Check" 
            @click="saveContent"
            :loading="saveLoading"
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
             placeholder="在此处修正识别错误的 LaTeX 代码..."
             class="edit-textarea"
           />
           <div class="edit-tips">
             <p>💡 常用修正：</p>
             <ul>
               <li>分数：3/16 写成 <code>$\frac{3}{16}$</code></li>
               <li>根号：根号3 写成 <code>$\sqrt{3}$</code></li>
               <li>平方：x2 写成 <code>$x^2$</code></li>
               <li>粗体：\boldsymbol{A} 改为 <code>$\mathbf{A}$</code></li>
             </ul>
           </div>
        </div>

        <el-divider content-position="center">原始图片对照</el-divider>
        
        <div class="detail-image-area">
           <el-image 
            :src="`http://127.0.0.1:8000/static/${currentDetailItem.image_url}`" 
            fit="contain"
            :preview-src-list="[`http://127.0.0.1:8000/static/${currentDetailItem.image_url}`]"
          />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { UploadFilled, User, Lock, Document, Monitor, Collection, Crop, Refresh, Select } from '@element-plus/icons-vue'
import axios from 'axios'
// import katex from 'katex'
// import 'katex/dist/katex.min.css'
import Cropper from 'cropperjs'
import 'cropperjs/dist/cropper.css'
import { ElMessage } from 'element-plus'

import { Files, ArrowRight } from '@element-plus/icons-vue'

import markdownItMathjax3 from 'markdown-it-mathjax3'
import MarkdownIt from 'markdown-it'
// import mk from 'markdown-it-katex'

//import 'katex/dist/katex.min.css'

// === 全局配置 ===
const API_BASE = 'http://127.0.0.1:8000/api/v1'

// === 状态 ===
const token = ref(localStorage.getItem('access_token') || '')
const username = ref('')
const role = ref('')
const authLoading = ref(false)
const loginForm = ref({ username: '', password: '' })
const activeTab = ref('upload')
const historyList = ref([])

// 初始化 Markdown 渲染器
const md = new MarkdownIt({
  html: true,
  breaks: true,
  linkify: true
})

// ✅ 使用 MathJax 插件
// tex 选项配置：允许单 $ 行内公式
md.use(markdownItMathjax3, {
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']]
  }
})

// 上传相关
const uploadMode = ref('image')
const selectedFile = ref(null)
const previewUrl = ref('')
const loading = ref(false)
const ocrResult = ref('')
const knowledgeTags = ref([])
const costTime = ref(null)
const pdfPages = ref([])

const allTags = ref([]) // 所有知识点
const currentTagFilter = ref('') // 当前选中的 Tag
const searchKeyword = ref('') // 搜索词

const detailVisible = ref(false)
const currentDetailItem = ref(null)

// Cropper
const cropperVisible = ref(false)
const currentCropImage = ref('')
const cropperImgRef = ref(null)
let cropperInstance = null

// ... existing refs ...
const detailMode = ref('preview') // 'preview' | 'edit'
const editingContent = ref('')    // 编辑框里的内容
const saveLoading = ref(false)

const openDetail = (item) => {
  currentDetailItem.value = item
  // 把内容复制给编辑框
  editingContent.value = item.content
  detailMode.value = 'preview' // 默认打开是预览
  detailVisible.value = true
}

// 初始化 Markdown 渲染器
const md = new MarkdownIt({
  html: true,       // 允许 HTML 标签
  breaks: true,     // 转换换行符为 <br>
  linkify: true     // 自动识别链接
})

// 使用 Katex 插件
md.use(mk)

// === 生命周期 ===
onMounted(() => {
  if (token.value) {
    parseTokenInfo(token.value)
    fetchHistory()
    fetchTags()
  }
})

// === Axios Interceptor ===
axios.interceptors.request.use((config) => {
  if (token.value) config.headers.Authorization = `Bearer ${token.value}`
  return config
}, (error) => Promise.reject(error))

// ⬇️⬇️⬇️ 新增：Response 拦截器 (自动处理 401) ⬇️⬇️⬇️
axios.interceptors.response.use(
  (response) => response, // 请求成功，直接放行
  (error) => {
    // 如果后端返回 401 (未授权)
    if (error.response && error.response.status === 401) {
      console.warn("登录过期，自动退出")
      logout() // 触发退出逻辑 (清空 Token + localStorage)
      ElMessage.error('身份验证失效，请重新登录')
    }
    return Promise.reject(error)
  }
)
// ⬆️⬆️⬆️ 新增结束 ⬆️⬆️⬆️

// === 认证逻辑 ===
const handleAuth = async () => {
  if (!loginForm.value.username || !loginForm.value.password) return ElMessage.warning('请输入完整信息')
  authLoading.value = true
  try {
    let res
    try {
      res = await axios.post(`${API_BASE}/auth/register`, loginForm.value)
      ElMessage.success('注册成功，欢迎加入')
    } catch (e) {
      const formData = new FormData()
      formData.append('username', loginForm.value.username)
      formData.append('password', loginForm.value.password)
      res = await axios.post(`${API_BASE}/auth/token`, formData)
      ElMessage.success('登录成功')
    }
    const at = res.data.access_token
    token.value = at
    localStorage.setItem('access_token', at)
    parseTokenInfo(at)
    fetchHistory()
  } catch (e) {
    ElMessage.error('认证失败，请检查账号密码')
  } finally {
    authLoading.value = false
  }
}

const logout = () => {
  token.value = ''
  username.value = ''
  role.value = ''
  localStorage.removeItem('access_token')
}

const parseTokenInfo = (t) => {
  try {
    const p = JSON.parse(atob(t.split('.')[1]))
    username.value = p.sub
    role.value = p.role
  } catch (e) { logout() }
}

// === 业务逻辑 ===
const handleTabChange = (n) => { if(n === 'history') fetchHistory() }

const fetchHistory = async () => {
  if(!token.value) return
  try {
    // 构造查询参数
    const params = {}
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (currentTagFilter.value) params.tag = currentTagFilter.value

    const res = await axios.get(`${API_BASE}/history`, { params })
    historyList.value = res.data
    
    // 顺便更新一下左侧的 Tag 列表 (保证 Tag 是最新的)
    fetchTags()
  } catch(e) { console.error(e) }
}

// === 新增：获取 Tag 列表 ===
const fetchTags = async () => {
  if(!token.value) return
  try {
    const res = await axios.get(`${API_BASE}/tags`)
    allTags.value = res.data
  } catch(e) {}
}

// === 新增：处理 Tag 点击 ===
const handleTagFilter = (tag) => {
  currentTagFilter.value = tag
  fetchHistory() // 重新加载列表
}



// === 新增：详情页的渲染计算属性 ===
// 修改渲染计算属性，依赖 editingContent 而不是 item.content
// 这样我们在编辑时切换预览能实时看到效果
const detailRenderedContent = computed(() => {
  const rawText = detailMode.value === 'edit' ? editingContent.value : (currentDetailItem.value?.content || '')
  if (!rawText) return '暂无内容'
  // 1. 修复
  const fixedText = smartLatexFix(rawText)
  // 2. 渲染
  return md.render(fixedText)
})

// 新增：保存修改到后端
const saveContent = async () => {
  if (!currentDetailItem.value) return
  saveLoading.value = true
  try {
    // 假设后端有一个更新接口 (下面我们会去后端加这个接口)
    // 这里我们先用一个临时的 PATCH 请求
    // 注意：你需要确保后端 endpoints.py 里有 update 接口，或者我们先模拟更新本地数据
    
    // 发送请求给后端更新 (Phase 2 我们再写后端接口，现在先更新前端显示)
    // TODO: 真正的后端保存逻辑
    await axios.put(`${API_BASE}/questions/${currentDetailItem.value.id}`, { content: editingContent.value })
    
    // 暂时先只更新本地数据，演示效果
    currentDetailItem.value.content = editingContent.value
    // 同时更新列表里的数据
    const listItem = historyList.value.find(i => i.id === currentDetailItem.value.id)
    if (listItem) listItem.content = editingContent.value
    
    ElMessage.success('修改已保存 (暂存本地)')
    detailMode.value = 'preview'
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saveLoading.value = false
  }
}

const handleFileChange = (f) => {
  selectedFile.value = f.raw
  previewUrl.value = URL.createObjectURL(f.raw)
  clearResult()
}

const handlePdfChange = async (f) => {
  const fd = new FormData()
  fd.append('file', f.raw)
  loading.value = true
  try {
    const res = await axios.post(`${API_BASE}/upload_pdf`, fd)
    if(res.data.success) {
      pdfPages.value = res.data.images
      ElMessage.success(`PDF 解析完成，共 ${res.data.total_pages} 页`)
    }
  } catch(e) { ElMessage.error('PDF 解析失败') }
  finally { loading.value = false }
}

const openCropper = (url) => {
  currentCropImage.value = `http://127.0.0.1:8000/static/${url}`
  cropperVisible.value = true
}

const initCropper = () => {
  nextTick(() => {
    if(cropperImgRef.value) {
      cropperInstance = new Cropper(cropperImgRef.value, { viewMode: 1, dragMode: 'move', autoCropArea: 0.6, background: false })
    }
  })
}

const confirmCrop = () => {
  if(!cropperInstance) return
  loading.value = true
  cropperInstance.getCroppedCanvas().toBlob(async (b) => {
    const f = new File([b], "crop.jpg", {type: "image/jpeg"})
    await runRecognition(f)
    cropperVisible.value = false
    loading.value = false
  }, 'image/jpeg')
}

const runRecognition = async (f) => {
  const fd = new FormData()
  fd.append('file', f)
  try {
    const res = await axios.post(`${API_BASE}/recognize`, fd)
    if(res.data.success) {
      ocrResult.value = res.data.content
      knowledgeTags.value = res.data.knowledge || []
      costTime.value = res.data.cost_seconds
      ElMessage.success('识别完成')
      if(uploadMode.value === 'pdf') previewUrl.value = URL.createObjectURL(f)
      fetchHistory()
    } else {
      ElMessage.error(res.data.error || '识别失败')
    }
  } catch(e) { ElMessage.error('网络异常') }
}

const startRecognition = async () => {
  if(!selectedFile.value) return
  loading.value = true
  await runRecognition(selectedFile.value)
  loading.value = false
}

const clearResult = () => {
  ocrResult.value = ''
  knowledgeTags.value = []
}

// 🔥🔥🔥 核心：前端智能 LaTeX 修复工具 🔥🔥🔥
const smartLatexFix = (text) => {
  if (!text) return ''

  // 1. 基础清理
  let res = text
    .replace(/\\\{/g, '{') // 去掉多余的转义花括号
    .replace(/\\\}/g, '}')
    .replace(/（/g, '(').replace(/）/g, ')')

  // 2. 暴力修复常见 OCR 错误
  // 修复 x_2 -> x^2 (忽略已经是公式的情况)
  res = res.replace(/([a-zA-Z])_2(?![0-9])/g, '$1^2')
  
  // 3. 智能包裹逻辑：寻找裸露的 LaTeX 命令
  // 我们定义一个超级正则，匹配常见的数学特征
  // 比如：\frac, \sqrt, \left, \begin, ^, =, \alpha, ...
  
  // 先把已有的 $ 保护起来，用占位符替换，避免重复包裹
  const placeholders = []
  res = res.replace(/\$\$.+?\$\$|\$.+?\$/g, (match) => {
    placeholders.push(match)
    return `__MATH_PLACEHOLDER_${placeholders.length - 1}__`
  })

  // === 开始对裸露文本进行手术 ===

  // A. 修复断裂的分数 (1. \n 16 \n 3)
  // 如果遇到：数字(可能带点) 换行 数字 换行 数字
  res = res.replace(/^(\d+\.?)\s*\n\s*(\d+)\s*\n\s*(\d+)\s*$/gm, '**$1** $$\\frac{$2}{$3}$$')
  // 修复两行分数
  res = res.replace(/^(\d+)\s*\n\s*(\d+)\s*$/gm, '$$\\frac{$1}{$2}$$')

  // B. 自动包裹 LaTeX 命令
  // 只要看到 \xxx 或者 运算符号，就认为它是数学
  const mathPattern = /\\(frac|sqrt|left|right|begin|end|mathbf|boldsymbol|textcircled|sin|cos|tan|ln|log|vec|alpha|beta|theta|lambda|mu|pi|triangle|angle|perp|circ|prime)|[a-zA-Z]\^2|y\s*=|x\s*=|f\(x\)/g
  
  // 我们按行处理，防止跨行搞乱
  res = res.split('\n').map(line => {
    // 如果这一行包含数学特征，且不是纯文字描述
    if (mathPattern.test(line)) {
      // 简单策略：如果这一行包含 \命令，且没有汉字（或者汉字很少），整行包裹 $$
      // 或者：用正则替换具体的数学部分
      
      // 策略：替换具体的数学片段为行内公式 $...$
      // 1. 替换 \command{...}
      line = line.replace(/\\(frac|sqrt|textcircled|vec|boldsymbol|mathbf)\s*\{.+?\}(\{.+\})?/g, (m) => ` $${m}$ `)
      // 2. 替换 \left( ... \right)
      line = line.replace(/\\left\(.+?\\right\)/g, (m) => ` $$${m}$$ `) // 这种一般比较长，用 $$
      // 3. 替换 包含 ^ 或 _ 的单词
      line = line.replace(/[a-zA-Z0-9]+[\^_][a-zA-Z0-9\{\}]+/g, (m) => ` $${m}$ `)
      // 4. 修复孤立的根号 \sqrt 3
      line = line.replace(/\\sqrt\s+(\d+|[a-x])/g, (m) => ` $${m}$ `)
    }
    return line
  }).join('\n')

  // C. 还原占位符
  res = res.replace(/__MATH_PLACEHOLDER_(\d+)__/g, (_, index) => placeholders[index])

  return res
}

// === 工具 ===
const renderedContent = computed(() => {
  if (!ocrResult.value) return ''
  // 1. 先用我们的智能修复工具处理一遍
  const fixedText = smartLatexFix(ocrResult.value)
  // 2. 再交给 MathJax 渲染
  return md.render(fixedText)
})
</script>

<style>
/* === 🚨 强制重置根节点 (解决右侧留白问题的核心) === */
#app {
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
  text-align: left !important;
  width: 100vw !important;
  height: 100vh !important;
}
/* === 全局重置 (关键) === */
html, body, #app {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
  background: #f0f2f5;
  overflow: hidden; /* 禁止整个页面出现滚动条 */
}

/* 确保所有元素不因为 padding/border 撑大 */
*, *::before, *::after {
  box-sizing: border-box;
}

/* === 登录页样式 === */
.login-container { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
.login-content { display: flex; width: 900px; height: 500px; background: white; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); overflow: hidden; }
.login-left { flex: 1; background: #3b82f6; padding: 40px; color: white; display: flex; flex-direction: column; justify-content: center; position: relative; }
.login-left h1 { font-size: 32px; margin-bottom: 10px; line-height: 1.2; }
.login-left p { opacity: 0.9; line-height: 1.6; }
.login-art { position: absolute; bottom: -20px; right: -20px; width: 80%; opacity: 0.2; }
.login-card { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 40px; border: none; box-shadow: none !important; }
.login-sub { color: #999; margin-bottom: 30px; }
.login-btn { width: 100%; height: 44px; font-size: 16px; margin-top: 10px; background: linear-gradient(to right, #3b82f6, #2563eb); border: none; }
.login-footer { margin-top: 20px; text-align: center; }

/* === 主界面布局 (Flex 纵向) === */
.main-layout {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

/* === 顶部导航 === */
.app-header {
  height: 60px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0; /* 防止被压缩 */
  z-index: 10;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.logo-box { width: 36px; height: 36px; background: #eff6ff; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.app-title h3 { margin: 0; font-size: 18px; color: #1f2937; }
.version { font-size: 12px; color: #9ca3af; background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }
.header-right { display: flex; align-items: center; gap: 16px; }
.username { font-weight: 500; color: #374151; }

/* === 内容区域 === */
.app-content {
  flex: 1; /* 占据剩余高度 */
  padding: 16px;
  overflow: hidden; /* 防止内容溢出导致整体滚动 */
  position: relative;
}

/* Tabs 容器撑满 */
.full-height-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: none;
  box-shadow: 0 4px 6px rgba(0,0,0,0.02);
  border-radius: 12px;
  overflow: hidden;
  background: white;
}
.full-height-tabs .el-tabs__header { margin: 0; padding: 0 20px; border-bottom: 1px solid #f0f0f0; background: #fff; flex-shrink: 0; }
.full-height-tabs .el-tabs__content { flex: 1; padding: 0 !important; overflow: hidden; position: relative; }
/* 强制 Tab Pane 撑满 */
.full-height-tabs .el-tabs__content > .el-tab-pane { width: 100%; height: 100%; }

.custom-tab-label { display: flex; align-items: center; gap: 6px; padding: 10px 0; }

/* === 工作台 (左右布局核心) === */
.workspace-pane { width: 100%; height: 100%; display: flex; flex-direction: column; }
.workspace-grid {
  display: flex;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

/* 左侧面板：固定宽度 */
.panel-left {
  width: 450px;       /* 设定固定宽度，操作更舒适 */
  flex: 0 0 450px;    /* 禁止伸缩，保持固定 */
  background: #f9fafb;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  z-index: 2;
}

/* 右侧面板：自动填满剩余空间 */
.panel-right {
  flex: 1;            /* 自动占据剩余宽度 */
  width: 0;           /* 【关键 Hack】强制 Flex 子元素宽度计算不溢出 */
  min-width: 0;       /* 防止内部长文本撑破容器 */
  background: white;
  display: flex;
  flex-direction: column;
  position: relative;
}

.panel-header {
  height: 50px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
  flex-shrink: 0;
}
.panel-header .title { font-weight: 600; color: #374151; font-size: 14px; }
.panel-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;   /* 内部独立滚动 */
  overflow-x: hidden;
}

/* 上传样式 */
.upload-wrapper { display: flex; flex-direction: column; height: 100%; }
.upload-box .el-upload-dragger { width: 100%; border: 2px dashed #d1d5db; background: #f9fafb; transition: all 0.3s; }
.upload-box.mini .el-upload-dragger { height: 80px; padding: 20px; }
.preview-area { margin-top: 20px; border-radius: 8px; overflow: hidden; border: 1px solid #e5e7eb; max-height: 300px; display: flex; justify-content: center; background: #000; flex-shrink: 0; }
.single-preview { max-height: 300px; width: auto; }
.action-btn { margin-top: auto; width: 100%; margin-top: 20px; font-weight: 600; letter-spacing: 1px; flex-shrink: 0; }

/* PDF 网格 */
.pdf-list-container { margin-top: 20px; flex: 1; overflow-y: auto; padding-right: 5px; }
.grid-layout { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 12px; }
.pdf-card { aspect-ratio: 3/4; background: #e5e7eb; border-radius: 8px; overflow: hidden; position: relative; cursor: pointer; border: 2px solid transparent; transition: all 0.2s; }
.pdf-card:hover { border-color: #3b82f6; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(59,130,246,0.2); }
.pdf-card .el-image { width: 100%; height: 100%; }
.pdf-overlay { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.7); color: white; font-size: 10px; padding: 4px; text-align: center; }

/* 结果区样式 */
.knowledge-card { background: linear-gradient(to right, #eff6ff, #fff); padding: 15px; border-radius: 8px; border: 1px solid #dbeafe; margin-bottom: 20px; flex-shrink: 0; }
.k-title { font-size: 12px; font-weight: 700; color: #2563eb; margin-bottom: 8px; text-transform: uppercase; }
.k-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.markdown-content { font-size: 15px; line-height: 1.7; color: #1f2937; background: #fff; padding: 20px; border-radius: 8px; }

/* 历史记录 */
.history-pane { width: 100%; height: 100%; display: flex; flex-direction: column; }
.history-toolbar { padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f0f0f0; flex-shrink: 0; }
.history-waterfall { flex: 1; overflow-y: auto; padding: 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 20px; align-content: start; }
.h-card { border: none; border-radius: 12px; transition: transform 0.2s; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.h-card:hover { transform: translateY(-4px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
.h-img-box { height: 140px; position: relative; }
.h-status { position: absolute; top: 8px; right: 8px; font-size: 10px; padding: 2px 6px; border-radius: 4px; color: white; font-weight: 600; }
.h-status.approved { background: #10b981; }
.h-status.pending { background: #f59e0b; }
.h-content { padding: 12px; }
.h-tags { margin-bottom: 8px; }
.h-text { font-size: 13px; color: #4b5563; margin-bottom: 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.h-date { font-size: 11px; color: #9ca3af; }

/* 裁剪弹窗 */
.cropper-view { height: 60vh; background: #1f2937; display: flex; align-items: center; justify-content: center; }
.cropper-view img { max-width: 100%; max-height: 100%; }

/* 滚动条美化 */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #9ca3af; }

/* === 题库布局 === */
.bank-pane { width: 100%; height: 100%; display: flex; flex-direction: column; }
.bank-container { display: flex; width: 100%; height: 100%; background: #f5f7fa; }

/* 左侧侧边栏 */
.bank-sidebar {
  width: 240px;
  background: white;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.sidebar-header {
  height: 50px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  font-weight: 600;
  color: #374151;
  border-bottom: 1px solid #f0f0f0;
  gap: 8px;
}
.tag-list { flex: 1; overflow-y: auto; padding: 10px; }
.tag-item {
  padding: 10px 15px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  color: #606266;
  font-size: 14px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 10px;
}
.tag-item:hover { background: #f0f7ff; color: #409EFF; }
.tag-item.active { background: #ecf5ff; color: #409EFF; font-weight: 500; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: #dcdfe6; }
.tag-item.active .dot { background: #409EFF; }
.dot.all { background: #909399; }

/* 右侧主区域 */
.bank-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

/* 筛选栏 */
.filter-bar {
  height: 60px;
  background: white;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}
.search-input { width: 300px; }
.filter-right { display: flex; align-items: center; gap: 15px; color: #909399; font-size: 13px; }

/* 题目列表 */
.question-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  align-content: start;
}

/* 题目卡片 */
.q-card {
  background: white;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  padding: 15px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  height: 180px;
}
.q-card:hover { transform: translateY(-4px); box-shadow: 0 8px 16px rgba(0,0,0,0.08); border-color: #c6e2ff; }
.q-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
.q-date { font-size: 12px; color: #c0c4cc; }
.q-body-preview {
  flex: 1;
  font-size: 14px;
  color: #303133;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  margin-bottom: 10px;
}
.q-footer { display: flex; justify-content: space-between; align-items: center; border-top: 1px dashed #f0f0f0; padding-top: 10px; }
.q-thumb { width: 40px; height: 40px; border-radius: 4px; border: 1px solid #f0f0f0; }

/* 详情弹窗 */
.detail-text-area { font-size: 18px; line-height: 1.8; padding: 10px; background: #fafafa; border-radius: 8px; min-height: 100px; }
.detail-image-area { text-align: center; margin-top: 20px; }
.detail-image-area .el-image { max-height: 400px; }

/* Markdown 内容样式优化 */
.markdown-body {
  font-family: "Times New Roman", "SimSun", serif;
  font-size: 18px;     /* 字号加大，如果是高中生用，大点好 */
  line-height: 2.0;    /* 行高设为 2倍，给分数留空间 */
  color: #2c3e50;
  padding: 10px;
}

.markdown-body p {
  overflow-x: auto; /* 允许横向滚动 */
  margin-bottom: 20px;
}

/* 选项加粗样式 */
.markdown-body strong {
  color: #409EFF; /* 选项 A. B. C. D. 显示为蓝色 */
  font-weight: bold;
}

/* 公式样式微调 */
.katex {
  font-size: 1.2em !important; /* 公式比文字大 20% */
  font-weight: 500 !important; /* 字体加粗一点点，更清晰 */
  color: black !important;
}
/* 独立行公式 */
.katex-display {
  margin: 1em 0;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 10px 0;
}

.katex .frac-line {
  border-bottom-width: 0.08em !important;
}

/* 遇到超长公式允许横向滚动 */
.markdown-body .katex-display {
  overflow-x: auto;
  overflow-y: hidden;
  padding: 10px 0;
}

/* 针对截图里提到的“分数变成两行”的问题 */
/* 强制行内块元素对齐 */
.katex .base {
  margin-top: -2px; 
}
</style>