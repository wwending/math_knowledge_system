<template>
  <div class="common-layout">
    <el-container>
      <el-aside width="220px">
        <div class="logo-area">
          <el-icon :size="24" color="#409EFF"><EditPen /></el-icon>
          <span class="logo-text">错题本 AI</span>
        </div>
        <el-menu
          default-active="upload"
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
              accept=".jpg,.jpeg,.png,.bmp,.webp"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                将图片拖到此处，或 <em>点击上传</em>
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
                      v-for="(t, i) in (typeof item.knowledge_tags === 'string' ? JSON.parse(item.knowledge_tags) : item.knowledge_tags)" 
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
             placeholder="在此处修正识别错误的 LaTeX 代码..."
             class="edit-textarea"
           />
           <div class="edit-tips">
             <p>💡 提示：DeepSeek 已尽力修复格式。如仍有错，请手动修正 LaTeX 代码。</p>
             <p>例如：分数用 <code>$\frac{a}{b}$</code>，根号用 <code>$\sqrt{x}$</code></p>
           </div>
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
import { UploadFilled, EditPen, Collection, Clock, Delete, Refresh } from '@element-plus/icons-vue'

// 引入 Markdown 和 MathJax
import MarkdownIt from 'markdown-it'
import markdownItMathjax3 from 'markdown-it-mathjax3'

// ============================================
// 1. 初始化 Markdown 渲染引擎
// ============================================
const md = new MarkdownIt({
  html: true,
  breaks: true,
  linkify: true
})

// 使用 MathJax3 插件
md.use(markdownItMathjax3, {
  tex: {
    // 配置行内和块级公式的定界符
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']]
  }
})

// ============================================
// 2. 状态变量定义
// ============================================
const activeMenu = ref('upload')
const ocrLoading = ref(false)
const ocrResult = ref('')       // 当前识别出的文本
const knowledgeTags = ref([])   // 当前识别出的标签
const costTime = ref(0)
const historyList = ref([])     // 历史记录列表

// 详情页相关
const detailVisible = ref(false)
const currentDetailItem = ref(null)
const detailMode = ref('preview') // 'preview' | 'edit'
const editingContent = ref('')    // 编辑框内容
const saveLoading = ref(false)

// API 基础地址
const API_BASE = 'http://127.0.0.1:8000/api/v1'

// ============================================
// 3. 核心工具函数
// ============================================

// ✅ 极简版预处理函数 (配合 DeepSeek)
// 因为后端已经返回了标准的 LaTeX，前端只需做最基本的防错
const smartLatexFix = (text) => {
  if (!text) return ''
  // 简单去转义，防止 DeepSeek 偶尔漏掉
  let res = text.replace(/\\\{/g, '{').replace(/\\\}/g, '}')
  // 统一括号
  res = res.replace(/（/g, '(').replace(/）/g, ')')
  return res
}

// 格式化时间
const formatDate = (val) => {
  if (!val) return ''
  const date = new Date(val)
  return date.toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-')
}

// 获取图片完整 URL
const getImageUrl = (path) => {
  if (!path) return ''
  // 如果已经是 http 开头就不拼接
  if (path.startsWith('http')) return path
  return `http://127.0.0.1:8000/static/${path}`
}

// ============================================
// 4. 计算属性
// ============================================

// 采集页的渲染结果
const renderedContent = computed(() => {
  if (!ocrResult.value) return ''
  // 清洗 -> 渲染
  return md.render(smartLatexFix(ocrResult.value))
})

// 详情页的渲染结果
const detailRenderedContent = computed(() => {
  // 如果是编辑模式，渲染编辑框里的内容；否则渲染原内容
  const rawText = detailMode.value === 'edit' ? editingContent.value : (currentDetailItem.value?.content || '')
  if (!rawText) return '暂无内容'
  return md.render(smartLatexFix(rawText))
})

// ============================================
// 5. 业务逻辑方法
// ============================================

// 切换菜单
const handleMenuSelect = (index) => {
  activeMenu.value = index
  if (index === 'history' || index === 'bank') {
    getHistory()
  }
}

// 文件上传处理
const handleFileChange = (uploadFile) => {
  if (!uploadFile.raw) return
  // 立即触发识别
  runRecognition(uploadFile.raw)
}

// 调用识别 API
const runRecognition = async (file) => {
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
      ElMessage.success('识别分析完成！')
      
      // 控制台打印原始数据，方便调试
      console.log('=== DeepSeek 原始返回 ===')
      console.log(res.data.content)
    } else {
      ElMessage.error(res.data.error || '识别失败')
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('请求服务器失败')
  } finally {
    ocrLoading.value = false
  }
}

// 获取历史记录
const getHistory = async () => {
  try {
    const res = await axios.get(`${API_BASE}/history?limit=50`)
    historyList.value = res.data
  } catch (error) {
    ElMessage.error('获取历史记录失败')
  }
}

// 删除题目
const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除这道题吗？', '警告', { type: 'warning' })
    // 这里假设后端有 DELETE /questions/{id} 接口，如果没有请自行添加
    // await axios.delete(`${API_BASE}/questions/${id}`)
    ElMessage.success('删除成功 (前端演示)')
    // 刷新列表
    getHistory()
  } catch (e) {
    // 取消或失败
  }
}

// 打开详情弹窗
const openDetail = (item) => {
  currentDetailItem.value = item
  editingContent.value = item.content // 复制内容到编辑框
  detailMode.value = 'preview'        // 默认预览
  detailVisible.value = true
}

// 保存修改内容
const saveContent = async () => {
  if (!currentDetailItem.value) return
  saveLoading.value = true
  try {
    // 调用更新接口
    await axios.put(`${API_BASE}/questions/${currentDetailItem.value.id}`, { 
      content: editingContent.value 
    })
    
    // 更新本地数据
    currentDetailItem.value.content = editingContent.value
    // 同时更新列表中的数据
    const listItem = historyList.value.find(i => i.id === currentDetailItem.value.id)
    if (listItem) {
      listItem.content = editingContent.value
    }

    ElMessage.success('修改已保存！')
    detailMode.value = 'preview' // 切回预览
  } catch (e) {
    console.error(e)
    ElMessage.error('保存失败，请检查后端接口')
  } finally {
    saveLoading.value = false
  }
}

// 初始化加载历史
onMounted(() => {
  getHistory()
})
</script>

<style>
/* === 全局布局修复 === */
html, body, #app {
  height: 100%;
  margin: 0;
  padding: 0;
  overflow: hidden; /* 禁止最外层滚动 */
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif;
}

.common-layout {
  height: 100vh;
  display: flex;
}

.el-container {
  height: 100%;
  width: 100%;
}

.el-aside {
  background-color: #fff;
  border-right: 1px solid #e6e6e6;
  display: flex;
  flex-direction: column;
}

.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #f0f0f0;
  gap: 10px;
}
.logo-text {
  font-weight: bold;
  font-size: 18px;
  color: #303133;
}

/* 🔥 核心修复：主内容区滚动 */
.el-main {
  height: 100%;
  overflow-y: auto !important; /* 开启垂直滚动 */
  padding: 20px;
  background-color: #f5f7fa;
  scroll-behavior: smooth;
}

/* === 采集页样式 === */
.upload-header {
  text-align: center;
  margin-bottom: 30px;
}
.upload-box {
  max-width: 600px;
  margin: 0 auto 30px;
}
.ocr-result-box {
  min-height: 400px;
  /* 🔥 这里的 height: auto 很重要，让它被内容撑开 */
  height: auto; 
}
.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  min-height: 100px;
}
.knowledge-tag {
  font-size: 14px;
}

/* === 历史列表样式 === */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.question-list {
  display: grid;
  gap: 15px;
  /* 响应式 Grid */
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
}
.question-item {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.question-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.q-meta {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}
.q-tags {
  display: flex;
  gap: 5px;
}
.mini-preview {
  font-size: 13px;
  color: #606266;
  max-height: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.q-actions {
  margin-top: 10px;
  text-align: right;
  opacity: 0; /* 默认隐藏删除按钮 */
  transition: opacity 0.2s;
}
.question-item:hover .q-actions {
  opacity: 1;
}

/* === Markdown 渲染样式 (试卷风格) === */
.markdown-body {
  font-family: "Times New Roman", "SimSun", "Songti SC", serif;
  font-size: 18px;
  line-height: 2.0; /* 宽松行高 */
  color: #2c3e50;
  overflow-x: auto; /* 公式太长可横向滚动 */
}
.markdown-body p {
  margin-bottom: 16px;
  text-align: justify;
}
/* MathJax 字体优化 */
mjx-container {
  font-size: 1.1em !important;
  outline: none;
}

/* === 详情弹窗样式 === */
.detail-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.edit-textarea textarea {
  font-family: Consolas, Monaco, monospace;
  font-size: 14px;
  line-height: 1.5;
}
.edit-tips {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
  background: #f4f4f5;
  padding: 10px;
  border-radius: 4px;
}
.detail-image-area {
  text-align: center;
  margin-top: 20px;
  background: #fafafa;
  padding: 10px;
  border-radius: 4px;
}
</style>