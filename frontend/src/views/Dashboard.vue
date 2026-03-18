<template>
  <div class="common-layout">
    <el-container>
      <el-aside width="220px" class="sidebar-aside">
        <div class="logo-area">
          <div class="logo-left">
            <el-icon :size="24" color="#409EFF"><EditPen /></el-icon>
            <span class="logo-text">错题集 AI</span>
          </div>
          <el-button text size="small" class="logout-btn" @click="handleLogout">退出登录</el-button>
        </div>
        <el-menu :default-active="activeMenu" class="el-menu-vertical sidebar-menu" @select="handleMenuSelect">
          <el-menu-item index="upload"><el-icon><UploadFilled /></el-icon><span>题目录入</span></el-menu-item>
          <el-menu-item index="bank"><el-icon><Collection /></el-icon><span>智能题库</span></el-menu-item>
          <el-menu-item index="history"><el-icon><Clock /></el-icon><span>历史记录</span></el-menu-item>
        </el-menu>
      </el-aside>

      <el-main>
        <div v-if="activeMenu === 'upload'" class="upload-container">
          <div class="upload-header">
            <h2>题目录入</h2>
            <p class="subtitle">上传图片或 PDF，失败时页面不会退出，可直接重试</p>
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
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                拖拽 PDF 或图片到此处，或<em>点击选择</em>
              </div>
            </el-upload>
          </div>

          <div v-if="step === 'preview-pdf'" class="pdf-preview-section">
            <div class="section-header">
              <h3>请选择要识别的 PDF 页面</h3>
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
              <h3>图片确认</h3>
              <el-button size="small" @click="resetUpload">取消</el-button>
            </div>

            <div class="process-options">
              <el-radio-group v-model="processMode" size="large">
                <el-radio-button label="full">整页识别</el-radio-button>
                <el-radio-button label="crop">裁剪识别</el-radio-button>
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
                />
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
            <p>正在请求 OCR / AI 服务处理图片...</p>
          </div>

          <div v-if="ocrResult && step === 'result'" class="result-section">
            <el-button @click="resetUpload" style="margin-bottom: 10px;">继续上传下一题</el-button>
            <el-alert
              v-if="recognizeWarning"
              :title="recognizeWarning"
              type="warning"
              show-icon
              :closable="false"
              style="margin-bottom: 12px;"
            />
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
import { computed, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { UploadFilled, EditPen, Collection, Clock } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import markdownItMathjax3 from 'markdown-it-mathjax3'
import 'vue-cropper/dist/index.css'
import { VueCropper } from 'vue-cropper'

import { API_V1_BASE_URL } from '../config/api'
import { clearAuthSession } from '../utils/auth'
import HistoryPanel from '../components/HistoryPanel.vue'
import BankPanel from '../components/BankPanel.vue'

import * as pdfjsLib from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker

const router = useRouter()
const API_BASE = API_V1_BASE_URL
const md = new MarkdownIt({ html: true, breaks: true, linkify: true })
md.use(markdownItMathjax3)

const activeMenu = ref('upload')
const step = ref('select-file')
const processMode = ref('full')

const currentImageUrl = ref('')
const pdfPages = ref([])
const pdfLoading = ref(false)
const ocrLoading = ref(false)
const ocrResult = ref('')
const recognizeWarning = ref('')
const cropperRef = ref(null)

const getRecognizeErrorMessage = (payload) => {
  if (!payload) {
    return '识别失败，请稍后重试'
  }
  if (typeof payload === 'string') {
    return payload
  }
  return payload.warning || payload.error || '识别失败，请稍后重试'
}

const getRequestErrorMessage = (error) => {
  const detail = error.response?.data?.detail
  if (detail && typeof detail === 'string') {
    return detail
  }
  return '请求失败，请稍后重试'
}

const handleFileSelect = async (uploadFile) => {
  const file = uploadFile.raw
  if (!file) return

  const fileType = file.name.split('.').pop().toLowerCase()
  if (fileType === 'pdf') {
    await renderPdfToImages(file)
    return
  }

  currentImageUrl.value = URL.createObjectURL(file)
  step.value = 'process-image'
  processMode.value = 'full'
}

const renderPdfToImages = async (file) => {
  step.value = 'preview-pdf'
  pdfLoading.value = true
  pdfPages.value = []

  try {
    const arrayBuffer = await file.arrayBuffer()
    const pdf = await pdfjsLib.getDocument(arrayBuffer).promise

    for (let i = 1; i <= pdf.numPages; i += 1) {
      const page = await pdf.getPage(i)
      const viewport = page.getViewport({ scale: 2.5 })

      const canvas = document.createElement('canvas')
      const context = canvas.getContext('2d')
      canvas.height = viewport.height
      canvas.width = viewport.width

      await page.render({ canvasContext: context, viewport }).promise
      pdfPages.value.push(canvas.toDataURL('image/jpeg'))
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('PDF 解析失败，可能是加密文件或文件已损坏')
    resetUpload()
  } finally {
    pdfLoading.value = false
  }
}

const selectPdfPage = (base64Img) => {
  currentImageUrl.value = base64Img
  step.value = 'process-image'
  processMode.value = 'full'
}

const confirmCropAndUpload = () => {
  if (!cropperRef.value) return
  cropperRef.value.getCropBlob((blob) => {
    const file = new File([blob], 'crop_question.jpg', { type: 'image/jpeg' })
    runRecognition(file)
  })
}

const uploadFullImage = async () => {
  try {
    const response = await fetch(currentImageUrl.value)
    const blob = await response.blob()
    const file = new File([blob], 'full_page.jpg', { type: 'image/jpeg' })
    runRecognition(file)
  } catch (error) {
    console.error(error)
    ElMessage.error('当前图片不可用，请重新选择后再试')
    step.value = 'process-image'
  }
}

const runRecognition = async (file) => {
  step.value = 'uploading'
  ocrLoading.value = true
  ocrResult.value = ''
  recognizeWarning.value = ''

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await axios.post(`${API_BASE}/recognize`, formData)
    const payload = res.data || {}

    if (payload.success) {
      ocrResult.value = payload.content || ''
      step.value = 'result'
      if (payload.partial_success) {
        recognizeWarning.value = payload.warning || 'OCR 已完成，但 AI 整理失败，当前展示原始识别结果'
        ElMessage.warning(getRecognizeErrorMessage(payload))
      } else {
        ElMessage.success('识别完成')
      }
      return
    }

    ElMessage.error(getRecognizeErrorMessage(payload))
    step.value = 'process-image'
  } catch (error) {
    console.error(error)
    ElMessage.error(getRequestErrorMessage(error))
    step.value = 'process-image'
  } finally {
    ocrLoading.value = false
  }
}

const resetUpload = () => {
  step.value = 'select-file'
  currentImageUrl.value = ''
  pdfPages.value = []
  ocrResult.value = ''
  recognizeWarning.value = ''
}

const renderedContent = computed(() => {
  return ocrResult.value ? md.render(ocrResult.value) : ''
})

const handleMenuSelect = (index) => {
  activeMenu.value = index
}

const handleLogout = () => {
  clearAuthSession()
  router.replace('/login')
}
</script>

<style scoped>
.upload-container { max-width: 900px; margin: 0 auto; padding: 20px; }
.upload-header { text-align: center; margin-bottom: 30px; }
.subtitle { color: #666; font-size: 14px; margin-top: 5px; }

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

.upload-box { border: 2px dashed #dcdfe6; padding: 40px 0; text-align: center; border-radius: 8px; cursor: pointer; transition: 0.3s; }
.upload-box:hover { border-color: #409eff; background-color: #f5f7fa; }

.pdf-preview-section {
  text-align: center;
  padding: 0 20px;
}

.pdf-grid {
  display: grid;
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
  position: relative;
}

.pdf-page-card:hover {
  border-color: #409eff;
  transform: translateY(-8px);
  box-shadow: 0 10px 20px rgba(64, 158, 255, 0.15);
}

.pdf-thumb {
  width: 100%;
  height: auto;
  border-radius: 4px;
  border: 1px solid #eee;
}

.page-number {
  margin-top: 12px;
  font-size: 14px;
  color: #606266;
  font-weight: 600;
  letter-spacing: 1px;
}

.image-process-section {
  text-align: center;
  max-width: 1000px;
  margin: 0 auto;
}

.preview-container {
  background: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 20px;
  margin-top: 10px;
  box-shadow: inset 0 0 10px rgba(0,0,0,0.05);
}

.cropper-wrapper {
  width: 100%;
  height: 70vh;
  min-height: 500px;
  position: relative;
  background-color: #333;
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

.full-preview img {
  max-width: 100%;
  height: auto;
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  margin-bottom: 20px;
  background: white;
}
</style>
