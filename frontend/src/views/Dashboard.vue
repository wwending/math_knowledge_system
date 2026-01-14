<template>
  <div class="common-layout">
    <el-container>
      <el-aside width="220px" class="sidebar-aside">
        <div class="logo-area">
          <div class="logo-left">
            <el-icon :size="24" color="#409EFF"><EditPen /></el-icon>
            <span class="logo-text">错题本 AI</span>
          </div>
          <el-button text size="small" class="logout-btn" @click="handleLogout">退出登录</el-button>
        </div>
        <el-menu :default-active="activeMenu" class="el-menu-vertical sidebar-menu" @select="handleMenuSelect">
           <el-menu-item index="upload"><el-icon><UploadFilled /></el-icon><span>题目采集</span></el-menu-item>
           <el-menu-item index="bank"><el-icon><Collection /></el-icon><span>智能题库</span></el-menu-item>
           <el-menu-item index="history"><el-icon><Clock /></el-icon><span>历史记录</span></el-menu-item>
        </el-menu>
      </el-aside>

      <el-main>
        <div v-if="activeMenu === 'upload'" class="upload-container">
          
          <div class="upload-header">
            <h2>📸 题目采集</h2>
            <p class="subtitle">第一步：上传 图片 或 PDF</p>
          </div>

          <div v-if="step === 'select-file'" class="upload-box">
            <el-upload
              drag
              action="#"
              :auto-upload="false"
              :on-change="handleFileSelect"
              :show-file-list="false"
              accept=".jpg,.jpeg,.png,.pdf"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                拖拽 PDF 或 图片 到此处，或 <em>点击选择</em>
              </div>
            </el-upload>
          </div>

          <div v-if="step === 'preview-pdf'" class="pdf-preview-section">
            <div class="section-header">
              <h3>📄 请选择要识别的那一页</h3>
              <el-button size="small" @click="resetUpload">重新上传</el-button>
            </div>
            
            <div v-loading="pdfLoading" class="pdf-grid">
              <div 
                v-for="(pageData, index) in pdfPages" 
                :key="index" 
                class="pdf-page-card"
                @click="selectPdfPage(pageData)"
              >
                <img :src="pageData" class="pdf-thumb" />
                <div class="page-number">第 {{ index + 1 }} 页</div>
              </div>
            </div>
          </div>

          <div v-if="step === 'process-image'" class="image-process-section">
            <div class="section-header">
               <h3>🖼️ 图片确认</h3>
               <el-button size="small" @click="resetUpload">取消</el-button>
            </div>

            <div class="process-options">
               <el-radio-group v-model="processMode" size="large">
                 <el-radio-button label="full">📄 整页识别</el-radio-button>
                 <el-radio-button label="crop">✂️ 裁剪部分</el-radio-button>
               </el-radio-group>
            </div>

            <div class="preview-container">
               <div v-if="processMode === 'crop'" class="cropper-wrapper">
                  <vue-cropper
                    ref="cropperRef"
                    :img="currentImageUrl"
                    :output-size="1"
                    output-type="jpeg"
                    :auto-crop="true"
                    :center-box="true"
                    :fixed-box="false"
                    
                    :full="true"   
                    :high="true"
                    mode="contain"
                  ></vue-cropper>
                  <el-button type="primary" class="confirm-btn" @click="confirmCropAndUpload" :loading="ocrLoading">
                    确认裁剪并上传
                  </el-button>
               </div>

               <div v-else class="full-preview">
                  <img :src="currentImageUrl" />
                  <div style="margin-top: 15px;">
                    <el-button type="primary" @click="uploadFullImage" :loading="ocrLoading">
                      确认整页上传
                    </el-button>
                  </div>
               </div>
            </div>
          </div>

          <div v-if="ocrLoading && step === 'uploading'" class="loading-state">
             <el-skeleton :rows="5" animated />
             <p>正在请求 AI 进行智能分析...</p>
          </div>

          <div v-if="ocrResult && step === 'result'" class="result-section">
              <el-button @click="resetUpload" style="margin-bottom: 10px;">继续上传下一题</el-button>
              <el-card shadow="hover">
                  <div class="markdown-body" v-html="renderedContent"></div>
              </el-card>
          </div>
        </div>

        <div v-else-if="activeMenu === 'bank'">
          <bank-panel />
        </div>

        <div v-else-if="activeMenu === 'history'">
          <history-panel />
        </div>

      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { UploadFilled, EditPen, Collection, Clock } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import markdownItMathjax3 from 'markdown-it-mathjax3'
import 'vue-cropper/dist/index.css'
import { VueCropper } from "vue-cropper"

// 引入BankPanel和HistoryPanel组件
import HistoryPanel from '../components/HistoryPanel.vue'
import BankPanel from '../components/BankPanel.vue'

// 🔥 引入 PDF.js
import * as pdfjsLib from 'pdfjs-dist'
// 设置 worker (必须步骤，否则 PDF 无法解析)
import pdfWorker from 'pdfjs-dist/build/pdf.worker.mjs?url'
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker
//pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`

const router = useRouter()
const API_BASE = 'http://127.0.0.1:8000/api/v1'
const md = new MarkdownIt({ html: true, breaks: true, linkify: true })
md.use(markdownItMathjax3)

// 状态控制
const activeMenu = ref('upload')
const step = ref('select-file') // 状态: select-file | preview-pdf | process-image | uploading | result
const processMode = ref('full') // full | crop

// 数据变量
const currentImageUrl = ref('') // 当前待处理的图片 Blob URL
const pdfPages = ref([])        // PDF 每一页转成的图片 Base64 数组
const pdfLoading = ref(false)
const ocrLoading = ref(false)
const ocrResult = ref('')
const cropperRef = ref(null)

// -----------------------------------------------------------
// 1. 文件选择处理
// -----------------------------------------------------------
const handleFileSelect = async (uploadFile) => {
  const file = uploadFile.raw
  if (!file) return

  const fileType = file.name.split('.').pop().toLowerCase()

  if (fileType === 'pdf') {
    // === PDF 处理流程 ===
    await renderPdfToImages(file)
  } else {
    // === 图片 处理流程 ===
    currentImageUrl.value = URL.createObjectURL(file)
    step.value = 'process-image'
    processMode.value = 'full' // 默认整页，用户可切裁剪
  }
}

// -----------------------------------------------------------
// 2. PDF 解析核心逻辑 (PDF -> 图片数组)
// -----------------------------------------------------------
const renderPdfToImages = async (file) => {
  step.value = 'preview-pdf'
  pdfLoading.value = true
  pdfPages.value = []

  try {
    const arrayBuffer = await file.arrayBuffer()
    const pdf = await pdfjsLib.getDocument(arrayBuffer).promise
    
    // 循环读取每一页
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i)
      const viewport = page.getViewport({ scale: 2.5 }) // 1.5倍清晰度
      
      const canvas = document.createElement('canvas')
      const context = canvas.getContext('2d')
      canvas.height = viewport.height
      canvas.width = viewport.width

      await page.render({ canvasContext: context, viewport: viewport }).promise
      
      // 转为 Base64 图片用于展示
      pdfPages.value.push(canvas.toDataURL('image/jpeg'))
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('PDF 解析失败，可能是加密文件')
    resetUpload()
  } finally {
    pdfLoading.value = false
  }
}

// 用户点击了 PDF 的某一页
const selectPdfPage = (base64Img) => {
  currentImageUrl.value = base64Img
  step.value = 'process-image'
  processMode.value = 'full'
}

// -----------------------------------------------------------
// 3. 上传逻辑
// -----------------------------------------------------------

// 场景 A: 确认裁剪并上传
const confirmCropAndUpload = () => {
  if (!cropperRef.value) return
  cropperRef.value.getCropBlob((blob) => {
    const file = new File([blob], "crop_question.jpg", { type: "image/jpeg" })
    runRecognition(file)
  })
}

// 场景 B: 确认整页上传 (需要把 blob URL 转回 File 对象)
const uploadFullImage = async () => {
  // fetch 拿回 blob
  const response = await fetch(currentImageUrl.value)
  const blob = await response.blob()
  const file = new File([blob], "full_page.jpg", { type: "image/jpeg" })
  runRecognition(file)
}

// 统一后的 API 调用
const runRecognition = async (file) => {
  step.value = 'uploading'
  ocrLoading.value = true
  ocrResult.value = ''

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await axios.post(`${API_BASE}/recognize`, formData, {
      headers: { 
        'Authorization': `Bearer ${localStorage.getItem('token')}` 
      }
    })

    if (res.data.success) {
      ocrResult.value = res.data.content
      step.value = 'result'
      ElMessage.success('识别完成')
    } else {
      ElMessage.error(res.data.error || '识别失败')
      step.value = 'process-image' // 失败后退回图片确认页
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('请求失败')
    step.value = 'process-image'
  } finally {
    ocrLoading.value = false
  }
}

// 重置流程
const resetUpload = () => {
  step.value = 'select-file'
  currentImageUrl.value = ''
  pdfPages.value = []
  ocrResult.value = ''
}

// 路由与渲染
const renderedContent = computed(() => {
  return ocrResult.value ? md.render(ocrResult.value) : ''
})
const handleMenuSelect = (index) => {
  // 我们不再 router.push，而是直接切换 activeMenu 变量
  // 这样侧边栏就不会消失了
  activeMenu.value = index
}


const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.push('/login')
}
</script>

<style scoped>
/* 布局样式 */
.upload-container { max-width: 900px; margin: 0 auto; padding: 20px; }
.upload-header { text-align: center; margin-bottom: 30px; }
.subtitle { color: #666; font-size: 14px; margin-top: 5px; }

/* Sidebar */
.sidebar-aside {
  background: #f8fafc;
  border-right: 1px solid #e6e8eb;
  padding: 16px 12px;
  box-sizing: border-box;
}

.logo-area {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 8px 18px;
  margin-bottom: 6px;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08);
}

.logo-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logout-btn {
  color: #d14343;
}


.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #2b3a4a;
  letter-spacing: 0.3px;
}

:deep(.sidebar-menu) {
  border-right: none;
  background: transparent;
  padding-top: 4px;
}

:deep(.sidebar-menu .el-menu-item) {
  height: 48px;
  line-height: 48px;
  font-size: 15px;
  margin: 4px 6px;
  border-radius: 10px;
  padding-left: 16px;
  padding-right: 12px;
  color: #2b3a4a;
  position: relative;
  transition: background-color 0.2s ease, box-shadow 0.2s ease, color 0.2s ease;
}

:deep(.sidebar-menu .el-menu-item .el-icon) {
  font-size: 19px;
  margin-right: 10px;
  color: #5b6b7a;
}

:deep(.sidebar-menu .el-menu-item:hover) {
  background: #eef4ff;
}

:deep(.sidebar-menu .el-menu-item.is-active) {
  background: #e6f0ff;
  color: #1f5fbf;
  box-shadow: 0 6px 14px rgba(31, 95, 191, 0.12);
  font-weight: 600;
}

:deep(.sidebar-menu .el-menu-item.is-active .el-icon) {
  color: #1f5fbf;
}

:deep(.sidebar-menu .el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: -6px;
  top: 8px;
  width: 4px;
  height: 32px;
  border-radius: 4px;
  background: #1f5fbf;
}

/* 文件选择框 */
.upload-box { border: 2px dashed #dcdfe6; padding: 40px 0; text-align: center; border-radius: 8px; cursor: pointer; transition: 0.3s; }
.upload-box:hover { border-color: #409eff; background-color: #f5f7fa; }

/* PDF 预览网格 */
.pdf-preview-section { 
  text-align: center; 
  padding: 0 20px; /* 给两边留点空隙 */
}

.pdf-grid { 
  display: grid; 
  /* 🔥 修改点：最小宽度从 150px 增大到 240px，让预览图更大 */
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); 
  gap: 30px; 
  margin-top: 25px; 
}

.pdf-page-card { 
  cursor: pointer; 
  border: 1px solid #e4e7ed; 
  border-radius: 8px; 
  padding: 15px; 
  background: white;
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
  position: relative; /* 为了放页码 */
}

/* 悬停效果：上浮 + 阴影加深 + 边框变蓝 */
.pdf-page-card:hover { 
  border-color: #409eff; 
  transform: translateY(-8px); 
  box-shadow: 0 10px 20px rgba(64, 158, 255, 0.15);
}

.pdf-thumb { 
  width: 100%; 
  height: auto;
  border-radius: 4px; 
  /* 给图片加一点边框，像A4纸的感觉 */
  border: 1px solid #eee; 
}

.page-number { 
  margin-top: 12px; 
  font-size: 14px; 
  color: #606266; 
  font-weight: 600; 
  letter-spacing: 1px;
}

/* =========================================
   图片处理区 (裁剪/整页预览) - 加大
   ========================================= */
.image-process-section { 
  text-align: center; 
  /* 限制最大宽度，防止在大屏上太宽 */
  max-width: 1000px; 
  margin: 0 auto;
}

.preview-container { 
  /* 🔥 修改点：移除之前的 min-height，改用 Flex 或直接撑开 */
  background: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 8px; 
  padding: 20px; 
  margin-top: 10px;
  box-shadow: inset 0 0 10px rgba(0,0,0,0.05);
}

/* 裁剪器容器：高度设为屏幕高度的 70%，保证操作空间 */
.cropper-wrapper { 
  width: 100%; 
  height: 70vh; /* 🔥 关键：使用视口高度，让它尽可能大 */
  min-height: 500px;
  position: relative; 
  background-color: #333; /* 裁剪时背景深色更专业 */
}

.confirm-btn { 
  position: absolute; 
  bottom: 30px; 
  right: 30px; 
  z-index: 999; 
  padding: 12px 24px;
  font-size: 16px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

/* 整页预览模式：让图片宽一点 */
.full-preview img {
  max-width: 100%; 
  /* 🔥 修改点：移除 max-height: 500px 限制，让它自然长高 */
  height: auto; 
  box-shadow: 0 4px 16px rgba(0,0,0,0.1); /* 纸张阴影 */
  margin-bottom: 20px;
  background: white;
}
</style>