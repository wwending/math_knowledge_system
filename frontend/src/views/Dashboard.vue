<template>
  <div class="dashboard-layout">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-icon">
          <el-icon :size="24"><DataAnalysis /></el-icon>
        </div>
        <div>
          <strong>Math Knowledge</strong>
          <span>生产鉴权后台</span>
        </div>
      </div>

      <el-menu :default-active="activeMenu" class="sidebar-menu" @select="handleMenuSelect">
        <el-menu-item index="upload">
          <el-icon><UploadFilled /></el-icon>
          <span>题目录入</span>
        </el-menu-item>
        <el-menu-item index="bank">
          <el-icon><Collection /></el-icon>
          <span>智能题库</span>
        </el-menu-item>
        <el-menu-item index="history">
          <el-icon><Clock /></el-icon>
          <span>历史记录</span>
        </el-menu-item>
        <el-menu-item v-if="adminMode" index="users">
          <el-icon><UserFilled /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <div class="main-shell">
      <header class="topbar">
        <div>
          <h1>{{ pageTitle }}</h1>
          <p>{{ pageDescription }}</p>
        </div>
        <div class="topbar-actions">
          <div class="identity-card">
            <div class="identity-name">
              <strong>{{ currentUser?.display_name || '当前用户' }}</strong>
              <span>{{ currentUser?.phone || '-' }}</span>
            </div>
            <div class="identity-tags">
              <el-tag :type="adminMode ? 'warning' : 'info'">{{ roleLabel(currentUser?.role) }}</el-tag>
              <el-tag :type="statusTagType(currentUser?.status)">{{ statusLabel(currentUser?.status) }}</el-tag>
            </div>
          </div>
          <el-button @click="handleChangePassword">修改密码</el-button>
          <el-button type="danger" plain @click="handleLogout">退出登录</el-button>
        </div>
      </header>

      <main class="main-content">
        <section v-if="activeMenu === 'upload'" class="content-panel">
          <div class="section-heading">
            <h2>题目录入</h2>
            <p>上传图片或 PDF 进入 OCR / AI 识别流程。鉴权失效时会自动清理会话并重新登录。</p>
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
                拖拽 PDF 或图片到此处，或 <em>点击选择文件</em>
              </div>
            </el-upload>
          </div>

          <div v-if="step === 'preview-pdf'" class="pdf-preview-section">
            <div class="section-toolbar">
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
            <div class="section-toolbar">
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
                <el-button
                  type="primary"
                  class="confirm-btn"
                  :loading="ocrLoading"
                  :disabled="isDraftBusy"
                  @click="confirmCropAndUpload"
                >
                  确认裁剪并上传
                </el-button>
              </div>

              <div v-else class="full-preview">
                <img :src="currentImageUrl" />
                <el-button type="primary" :loading="ocrLoading" :disabled="isDraftBusy" @click="uploadFullImage">
                  确认整页上传
                </el-button>
              </div>
            </div>
          </div>

          <div v-if="ocrLoading && step === 'uploading'" class="loading-state">
            <el-skeleton :rows="5" animated />
            <p>{{ draftStatusText || '正在请求 OCR / AI 服务处理图片，请稍候...' }}</p>
          </div>

          <div
            v-if="step === 'result' && (ocrResult || draftError || draftStatus === 'saved_to_bank')"
            class="result-section"
          >
            <el-button class="reset-result-btn" @click="resetUpload">继续录入下一题</el-button>
            <el-alert
              v-if="draftStatusText"
              :title="draftStatusText"
              :type="draftStatusAlertType"
              show-icon
              :closable="false"
              class="result-alert"
            />
            <el-alert
              v-if="recognizeWarning"
              :title="recognizeWarning"
              type="warning"
              show-icon
              :closable="false"
              class="result-alert"
            />
            <el-card v-if="ocrResult" shadow="hover">
              <div class="markdown-body" v-html="renderedContent"></div>
            </el-card>
            <div v-if="draftStatus === 'draft_ready'" class="result-actions">
              <el-button type="primary" :loading="saveLoading" :disabled="!canSaveDraft" @click="saveDraftToBank">
                保存入题库
              </el-button>
            </div>
            <div v-if="draftStatus === 'saved_to_bank'" class="result-actions">
              <el-button type="primary" plain @click="resetUpload">继续录入</el-button>
              <el-button type="success" @click="activeMenu = 'bank'">切换到题库</el-button>
            </div>
          </div>
        </section>

        <section v-else-if="activeMenu === 'bank'" class="content-panel">
          <bank-panel />
        </section>

        <section v-else-if="activeMenu === 'history'" class="content-panel">
          <history-panel />
        </section>

        <section v-else-if="activeMenu === 'users'" class="content-panel">
          <user-management-panel />
        </section>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Clock, Collection, DataAnalysis, UploadFilled, UserFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import markdownItMathjax3 from 'markdown-it-mathjax3'
import 'vue-cropper/dist/index.css'
import { VueCropper } from 'vue-cropper'

import { API_V1_BASE_URL } from '../config/api'
import {
  authState,
  fetchCurrentUser,
  isAdminUser,
  logout
} from '../utils/auth'
import HistoryPanel from '../components/HistoryPanel.vue'
import BankPanel from '../components/BankPanel.vue'
import UserManagementPanel from '../components/UserManagementPanel.vue'

import * as pdfjsLib from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker

const router = useRouter()
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
const draftStatus = ref('')
const draftId = ref(null)
const sourceAssetId = ref(null)
const draftError = ref('')
const saveLoading = ref(false)
const saveResult = ref(null)

const currentUser = computed(() => authState.currentUser)
const adminMode = computed(() => isAdminUser(currentUser.value))

const pageTitle = computed(() => {
  if (activeMenu.value === 'bank') {
    return '智能题库'
  }
  if (activeMenu.value === 'history') {
    return '历史记录'
  }
  if (activeMenu.value === 'users') {
    return '用户管理'
  }
  return '题目录入'
})

const pageDescription = computed(() => {
  if (activeMenu.value === 'users') {
    return '管理员可以创建账号、调整角色、启停用和重置密码。'
  }
  if (activeMenu.value === 'bank') {
    return '查看已沉淀的题库内容。'
  }
  if (activeMenu.value === 'history') {
    return '查看近期识别与处理历史。'
  }
  return '上传题目素材并进入识别工作流。'
})

const roleLabel = (role) => {
  if (role === 'super_admin') {
    return '超级管理员'
  }
  if (role === 'admin') {
    return '管理员'
  }
  return '普通用户'
}

const statusLabel = (status) => {
  if (status === 'disabled') {
    return '已禁用'
  }
  if (status === 'pending_password_change') {
    return '待改密'
  }
  return '已启用'
}

const statusTagType = (status) => {
  if (status === 'disabled') {
    return 'danger'
  }
  if (status === 'pending_password_change') {
    return 'warning'
  }
  return 'success'
}

const getRecognizeErrorMessage = (payload) => {
  if (!payload) {
    return '识别失败，请稍后重试。'
  }
  if (typeof payload === 'string') {
    return payload
  }
  const errorText = payload.error || payload.warning || ''
  if (payload.error_type && errorText) {
    return `${payload.error_type}: ${errorText}`
  }
  return errorText || '识别失败，请稍后重试。'
}

const getRequestErrorMessage = (error) => {
  const data = error.response?.data || {}
  const detail = data.detail
  if (detail && typeof detail === 'string') {
    return detail
  }
  if (data.error_type || data.error) {
    return getRecognizeErrorMessage(data)
  }
  return '请求失败，请稍后重试。'
}

const resetDraftState = () => {
  draftStatus.value = ''
  draftId.value = null
  sourceAssetId.value = null
  draftError.value = ''
  saveLoading.value = false
  saveResult.value = null
}

const extractId = (payload, fields) => {
  for (const field of fields) {
    if (payload?.[field] !== undefined && payload[field] !== null) {
      return payload[field]
    }
  }
  return null
}

const getDraftContent = (payload) => payload?.content || payload?.current_content?.text || ''

const isDraftBusy = computed(() => ocrLoading.value || draftStatus.value === 'recognizing')
const canSaveDraft = computed(
  () => draftStatus.value === 'draft_ready' && Boolean(draftId.value) && !ocrLoading.value && !saveLoading.value
)

const draftStatusText = computed(() => {
  if (draftStatus.value === 'draft_created') {
    return '草稿已创建，准备识别'
  }
  if (draftStatus.value === 'recognizing') {
    return '正在识别'
  }
  if (draftStatus.value === 'draft_ready') {
    return '识别结果已就绪'
  }
  if (draftStatus.value === 'failed') {
    return draftError.value || '识别失败，请重新上传。'
  }
  if (draftStatus.value === 'saved_to_bank') {
    const questionId = saveResult.value?.question_id || '-'
    const revisionId = saveResult.value?.question_revision_id || '-'
    return `保存成功，question_id: ${questionId}，question_revision_id: ${revisionId}`
  }
  return ''
})

const draftStatusAlertType = computed(() => {
  if (draftStatus.value === 'failed') {
    return 'error'
  }
  if (draftStatus.value === 'saved_to_bank') {
    return 'success'
  }
  return 'info'
})

const handleMenuSelect = (index) => {
  if (index === 'users' && !adminMode.value) {
    return
  }
  activeMenu.value = index
}

const handleFileSelect = async (uploadFile) => {
  const file = uploadFile.raw
  if (!file) {
    return
  }

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

    for (let index = 1; index <= pdf.numPages; index += 1) {
      const page = await pdf.getPage(index)
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
    ElMessage.error('PDF 解析失败，可能是加密文件或文件损坏。')
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
  if (!cropperRef.value) {
    return
  }

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
    ElMessage.error('当前图片不可用，请重新选择后再试。')
    step.value = 'process-image'
  }
}

const runRecognition = async (file) => {
  step.value = 'uploading'
  ocrLoading.value = true
  ocrResult.value = ''
  recognizeWarning.value = ''
  resetDraftState()

  try {
    const assetFormData = new FormData()
    assetFormData.append('file', file)
    const assetResponse = await axios.post(`${API_V1_BASE_URL}/assets`, assetFormData)
    const uploadedAssetId = extractId(assetResponse.data, ['source_asset_id', 'asset_id', 'id'])

    if (!uploadedAssetId) {
      throw new Error('素材上传成功，但响应中缺少 source_asset_id。')
    }

    sourceAssetId.value = uploadedAssetId
    const draftResponse = await axios.post(`${API_V1_BASE_URL}/drafts`, {
      source_asset_id: uploadedAssetId
    })
    const createdDraftId = extractId(draftResponse.data, ['draft_id', 'id'])

    if (!createdDraftId) {
      throw new Error('草稿创建成功，但响应中缺少 draft_id。')
    }

    draftId.value = createdDraftId
    draftStatus.value = draftResponse.data?.status || 'draft_created'
    await Promise.resolve()
    draftStatus.value = 'recognizing'

    const recognizeResponse = await axios.post(`${API_V1_BASE_URL}/drafts/${createdDraftId}/recognize`)
    const payload = recognizeResponse.data || {}
    draftStatus.value = payload.status || (payload.success ? 'draft_ready' : 'failed')

    if (draftStatus.value === 'draft_ready' && payload.success !== false) {
      ocrResult.value = getDraftContent(payload)
      step.value = 'result'
      if (payload.partial_success) {
        recognizeWarning.value = 'OCR 已完成，但 AI 整理部分失败，当前展示降级结果，请核对后再保存'
        ElMessage.warning(recognizeWarning.value)
      } else {
        ElMessage.success('识别完成。')
      }
      return
    }

    draftStatus.value = 'failed'
    draftError.value = getRecognizeErrorMessage(payload)
    ElMessage.error(draftError.value)
    step.value = 'result'
  } catch (error) {
    console.error(error)
    draftStatus.value = 'failed'
    draftError.value = error.message || getRequestErrorMessage(error)
    if (error.response?.status === 409 && error.response?.data?.detail === 'Asset already exists') {
      draftError.value = '素材上传失败：Asset already exists，请更换图片或重新裁剪后再试。'
    } else if (error.response) {
      draftError.value = getRequestErrorMessage(error)
    }
    ElMessage.error(draftError.value)
    step.value = 'result'
  } finally {
    ocrLoading.value = false
  }
}

const runLegacyRecognition = async (file) => {
  step.value = 'uploading'
  ocrLoading.value = true
  ocrResult.value = ''
  recognizeWarning.value = ''
  resetDraftState()

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await axios.post(`${API_V1_BASE_URL}/recognize`, formData)
    const payload = response.data || {}

    if (payload.success) {
      ocrResult.value = payload.content || ''
      step.value = 'result'
      if (payload.partial_success) {
        recognizeWarning.value = payload.warning || 'OCR 已完成，但 AI 整理失败，当前展示 OCR 原始结果。'
        ElMessage.warning(getRecognizeErrorMessage(payload))
      } else {
        ElMessage.success('识别完成。')
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

const saveDraftToBank = async () => {
  if (!canSaveDraft.value) {
    return
  }

  saveLoading.value = true
  try {
    const response = await axios.post(`${API_V1_BASE_URL}/drafts/${draftId.value}/save-to-bank`)
    saveResult.value = {
      question_id: response.data?.question_id,
      question_revision_id: response.data?.question_revision_id
    }
    draftStatus.value = response.data?.status || 'saved_to_bank'
    ElMessage.success(draftStatusText.value)
  } catch (error) {
    console.error(error)
    ElMessage.error(getRequestErrorMessage(error))
  } finally {
    saveLoading.value = false
  }
}

const resetUpload = () => {
  step.value = 'select-file'
  currentImageUrl.value = ''
  pdfPages.value = []
  ocrResult.value = ''
  recognizeWarning.value = ''
  resetDraftState()
}

const renderedContent = computed(() => (ocrResult.value ? md.render(ocrResult.value) : ''))

const handleLogout = async () => {
  await logout()
  router.replace('/login')
}

const handleChangePassword = () => {
  router.push('/change-password')
}

onMounted(async () => {
  if (!currentUser.value) {
    await fetchCurrentUser()
  }

  if (!adminMode.value && activeMenu.value === 'users') {
    activeMenu.value = 'upload'
  }
})
</script>

<style scoped lang="scss">
.dashboard-layout {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  background: linear-gradient(180deg, #f4efe5 0%, #f7faf8 100%);
}

.sidebar {
  padding: 20px 16px;
  border-right: 1px solid rgba(20, 51, 66, 0.08);
  background:
    radial-gradient(circle at top, rgba(41, 132, 103, 0.16), transparent 24%),
    linear-gradient(180deg, #143142 0%, #163746 100%);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 22px;
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.08);
  color: #f7fbfb;

  strong,
  span {
    display: block;
  }

  span {
    margin-top: 4px;
    font-size: 12px;
    opacity: 0.8;
  }
}

.brand-icon {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.14);
}

:deep(.sidebar-menu) {
  border-right: none;
  background: transparent;
}

:deep(.sidebar-menu .el-menu-item) {
  margin-bottom: 8px;
  height: 46px;
  line-height: 46px;
  border-radius: 14px;
  color: rgba(247, 251, 251, 0.8);
}

:deep(.sidebar-menu .el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.12);
}

:deep(.sidebar-menu .el-menu-item.is-active) {
  background: #f5eee3;
  color: #123142;
  font-weight: 600;
}

.main-shell {
  padding: 24px;
}

.topbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  padding: 24px 26px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 18px 48px rgba(18, 49, 66, 0.08);

  h1 {
    margin: 0 0 8px;
    font-size: 30px;
    color: #173242;
  }

  p {
    margin: 0;
    color: #5b7078;
    line-height: 1.7;
  }
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.identity-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 14px;
  border-radius: 18px;
  background: #f5f7f3;
}

.identity-name {
  display: flex;
  flex-direction: column;
  gap: 4px;

  strong {
    color: #193243;
  }

  span {
    color: #60737b;
    font-size: 13px;
  }
}

.identity-tags {
  display: flex;
  gap: 8px;
}

.main-content {
  min-width: 0;
}

.content-panel {
  padding: 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 18px 48px rgba(18, 49, 66, 0.08);
}

.section-heading {
  margin-bottom: 20px;

  h2 {
    margin: 0 0 8px;
    font-size: 26px;
    color: #173242;
  }

  p {
    margin: 0;
    color: #5c7078;
    line-height: 1.7;
  }
}

.section-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.upload-box {
  border: 2px dashed #c6d4d2;
  padding: 44px 0;
  text-align: center;
  border-radius: 18px;
  cursor: pointer;
  transition: 0.2s ease;
}

.upload-box:hover {
  border-color: #2d7a67;
  background-color: #f5faf8;
}

.pdf-preview-section {
  padding: 0 8px;
}

.pdf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 24px;
}

.pdf-page-card {
  cursor: pointer;
  border: 1px solid #e6ece9;
  border-radius: 16px;
  padding: 14px;
  background: #fff;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 10px 24px rgba(18, 49, 66, 0.05);
}

.pdf-page-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 16px 36px rgba(18, 49, 66, 0.12);
}

.pdf-thumb {
  width: 100%;
  border-radius: 10px;
  border: 1px solid #edf1f0;
}

.page-number {
  margin-top: 10px;
  text-align: center;
  color: #5f7077;
  font-weight: 600;
}

.image-process-section {
  max-width: 1080px;
}

.process-options {
  margin-bottom: 14px;
}

.preview-container {
  background: #f5f7f6;
  border: 1px solid #dce5e1;
  border-radius: 18px;
  padding: 20px;
}

.cropper-wrapper {
  width: 100%;
  height: 70vh;
  min-height: 480px;
  position: relative;
  background-color: #233843;
  border-radius: 16px;
  overflow: hidden;
}

.confirm-btn {
  position: absolute;
  right: 22px;
  bottom: 22px;
  z-index: 10;
}

.full-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.full-preview img {
  max-width: 100%;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 28px rgba(18, 49, 66, 0.08);
}

.loading-state {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.reset-result-btn {
  width: fit-content;
}

.result-alert {
  margin-bottom: 4px;
}

.result-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

@media (max-width: 1180px) {
  .dashboard-layout {
    grid-template-columns: 1fr;
  }

  .sidebar {
    padding-bottom: 8px;
  }

  .main-shell {
    padding-top: 0;
  }
}

@media (max-width: 900px) {
  .topbar {
    flex-direction: column;
  }

  .topbar-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .identity-card {
    width: 100%;
    justify-content: space-between;
  }
}

@media (max-width: 640px) {
  .main-shell {
    padding: 16px;
  }

  .content-panel,
  .topbar {
    padding: 18px;
    border-radius: 20px;
  }

  .identity-card {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
