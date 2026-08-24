<template>
  <div class="dashboard-layout">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-icon">
          <el-icon :size="24"><DataAnalysis /></el-icon>
        </div>
        <div>
          <strong>Math Knowledge</strong>
          <span>高中数学错题与知识图谱系统</span>
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
        <el-menu-item index="papers">
          <el-icon><Document /></el-icon>
          <span>组卷</span>
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
            <p>上传图片或 PDF，系统将自动识别并整理题目内容。登录状态失效时会提示重新登录。</p>
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
              <!-- #68: native buttons so keyboard users can pick a page
                   (Enter/Space for free); name comes from the visible 第 N 页 text. -->
              <button
                v-for="(pageData, index) in pdfPages"
                :key="index"
                type="button"
                class="pdf-page-card"
                @click="selectPdfPage(pageData)"
              >
                <img :src="pageData.src" class="pdf-thumb" alt="" />
                <span class="page-number">第 {{ index + 1 }} 页</span>
              </button>
            </div>
          </div>

          <div v-if="step === 'process-image'" class="image-process-section">
            <div class="section-toolbar">
              <h3>图片确认</h3>
              <el-button size="small" @click="cancelProcessStep">{{ pdfPages.length > 0 ? '重新选页' : '取消' }}</el-button>
            </div>

            <div class="process-options">
              <el-radio-group v-model="processMode" size="large">
                <el-radio-button label="full">整页识别</el-radio-button>
                <el-radio-button label="crop">裁剪识别</el-radio-button>
              </el-radio-group>
            </div>

            <div class="preview-container">
              <!-- #31: the toolbar stays in normal flow ABOVE the viewport so it can
                   never cover the question; overlay bars used to hide top-of-page crops. -->
              <div v-if="processMode === 'crop'" class="cropper-block">
                <div class="cropper-toolbar">
                  <div class="cropper-hints">
                    <span>拖动图片定位题目，可使用滚轮或 +/- 缩放。</span>
                    <span class="cropper-hint-image">一页多题请逐题框选录入；题目含图可直接框入，识别时自动检出图形区域，确认页可修正后入库。</span>
                  </div>
                  <el-button-group>
                    <el-button aria-label="缩小裁剪图片" @click="changeCropperScale(-10)">−</el-button>
                    <el-button aria-label="放大裁剪图片" @click="changeCropperScale(10)">+</el-button>
                  </el-button-group>
                </div>
                <div class="cropper-wrapper">
                  <vue-cropper
                    ref="cropperRef"
                    :img="currentImageUrl"
                    :output-size="1"
                    :output-type="CROP_OUTPUT_TYPE"
                    :max-img-size="cropperMaxImgSize"
                    :auto-crop="true"
                    :center-box="true"
                    :can-move="true"
                    :can-move-box="true"
                    :can-scale="true"
                    :fixed-box="false"
                    :full="true"
                    :high="true"
                    :info-true="true"
                    mode="cover"
                  />
                  <el-button
                    type="primary"
                    class="confirm-btn"
                    :loading="ocrLoading || cropEncoding"
                    :disabled="isDraftBusy"
                    @click="confirmCropAndUpload"
                  >
                    确认裁剪并上传
                  </el-button>
                </div>
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
            <p>{{ draftOperationText }}</p>
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
            <el-alert
              v-if="draftError && draftStatus !== 'failed'"
              :title="draftError"
              type="error"
              show-icon
              :closable="false"
              class="result-alert"
            />
            <!-- #61 confirmation preview: shown while recognition runs; once the
                 result arrives the split layout below takes over and the same
                 pixels stay visible in the persistent reference panel. -->
            <el-card v-if="resultImageUrl && !ocrResult" shadow="never" class="result-image-card">
              <div class="result-image-head">
                <h3>本次录入图</h3>
                <span class="result-image-caption">{{ resultImageCaption }}</span>
              </div>
              <el-image
                :src="resultImageUrl"
                :preview-src-list="[resultImageUrl]"
                :preview-teleported="true"
                fit="scale-down"
                class="result-image"
              >
                <template #error>
                  <div class="result-image-slot">
                    <el-icon><Picture /></el-icon>
                    <span>预览加载失败，请重新上传。</span>
                  </div>
                </template>
              </el-image>
            </el-card>
            <div v-if="ocrResult" class="result-split-layout">
              <!-- #31: reference image leads on the LEFT at readable size; the
                   panel scrolls internally so full-page captures stay legible
                   without click-to-zoom round trips while editing. -->
              <aside class="result-image-column">
                <div class="result-image-panel">
                  <h3>题目原图</h3>
                  <p class="result-image-hint">与送识别素材一致，栏内可滚动查看；点击可放大核对。</p>
                  <div v-loading="draftImageLoading" class="result-image-scroll">
                    <!-- #58: with detected figure regions the editable overlay
                         replaces the plain preview; without them the panel is
                         unchanged from #63. -->
                    <figure-overlay-editor
                      v-if="detectedFigures.length > 0 && resultImageSrc"
                      v-model="confirmedFigureBbox"
                      :image-url="resultImageSrc"
                      :initial-boxes="detectedFigures"
                      class="result-figure-editor"
                    />
                    <el-image
                      v-else-if="resultImageSrc"
                      :src="resultImageSrc"
                      :preview-src-list="[resultImageSrc]"
                      fit="scale-down"
                      class="result-reference-image"
                    >
                      <template #error>
                        <div class="result-image-slot">原图加载失败</div>
                      </template>
                    </el-image>
                    <div v-else class="result-image-empty">暂无原图</div>
                  </div>
                </div>
              </aside>
              <div class="result-main-column">
                <el-card shadow="hover">
                  <div v-if="editMode" class="draft-edit-panel">
                    <h3>编辑内容</h3>
                    <p class="draft-edit-hint">可直接修改题干、选项和 Markdown / LaTeX。</p>
                    <el-input
                      v-model="editContent"
                      type="textarea"
                      :autosize="{ minRows: 8, maxRows: 24 }"
                      :disabled="editSaving"
                      placeholder="请输入题目正文"
                    />
                    <h3>预览</h3>
                    <div class="markdown-body draft-edit-preview" v-html="renderedEditPreview"></div>
                    <div class="result-actions">
                      <el-button :disabled="editSaving" @click="cancelEdit">取消修改</el-button>
                      <el-button type="primary" :loading="editSaving" @click="saveDraftEdit">
                        {{ editSaving ? '正在保存...' : '保存修改' }}
                      </el-button>
                    </div>
                  </div>
                  <div v-else class="markdown-body" v-html="renderedContent"></div>
                </el-card>
                <el-collapse v-if="recognitionDebug" class="recognition-debug-collapse">
                  <el-collapse-item title="识别调试信息" name="recognition-debug">
                    <el-alert
                      v-if="recognitionDebug.ocr_error"
                      type="error"
                      :closable="false"
                      class="recognition-debug-alert"
                    >
                      OCR 错误：{{ recognitionDebug.ocr_error }}
                    </el-alert>
                    <el-alert
                      v-if="recognitionDebug.llm_error"
                      type="warning"
                      :closable="false"
                      class="recognition-debug-alert"
                    >
                      LLM 错误：{{ recognitionDebug.llm_error }}
                    </el-alert>
                    <div class="recognition-debug-grid">
                      <section class="recognition-debug-block">
                        <h4>原始 OCR 文本</h4>
                        <pre>{{ recognitionDebug.ocr_raw_text || '暂无原始 OCR 文本' }}</pre>
                      </section>
                      <section class="recognition-debug-block">
                        <h4>LLM 清洗文本</h4>
                        <pre>{{ recognitionDebug.llm_cleaned_text || '暂无 LLM 清洗文本' }}</pre>
                      </section>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
            <el-alert
              v-if="qualityWarnings.length > 0"
              title="识别风险提示"
              type="warning"
              show-icon
              :closable="false"
              class="result-alert quality-warning-alert"
            >
              <ul class="quality-warning-list">
                <li v-for="warning in qualityWarnings" :key="warning.code">
                  {{ formatQualityWarning(warning) }}
                </li>
              </ul>
            </el-alert>
            <div v-if="draftStatus === 'draft_ready' && !editMode" class="result-actions">
              <el-button :disabled="saveLoading" @click="enterEditMode">编辑识别结果</el-button>
              <el-button type="primary" :loading="saveLoading" :disabled="!canSaveDraft" @click="saveDraftToBank">
                {{ saveLoading ? '正在保存...' : '保存入题库' }}
              </el-button>
            </div>
            <div v-if="draftStatus === 'saved_to_bank'" class="result-actions">
              <el-button type="primary" plain @click="resetUpload">继续录入</el-button>
              <el-button type="success" @click="activeMenu = 'bank'">切换到题库</el-button>
            </div>
          </div>
        </section>

        <section v-else-if="activeMenu === 'bank'" class="content-panel">
          <bank-panel @paper-created="activeMenu = 'papers'" />
        </section>

        <section v-else-if="activeMenu === 'history'" class="content-panel">
          <history-panel />
        </section>

        <section v-else-if="activeMenu === 'papers'" class="content-panel">
          <paper-panel />
        </section>

        <section v-else-if="activeMenu === 'users'" class="content-panel">
          <user-management-panel />
        </section>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Clock, Collection, DataAnalysis, Document, Picture, UploadFilled, UserFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import 'vue-cropper/dist/index.css'
import { VueCropper } from 'vue-cropper'

import { API_V1_BASE_URL, buildDraftImageUrl } from '../config/api'
import { renderMarkdown } from '@/utils/renderMarkdown'
import {
  CROPPER_MAX_EDGE,
  CROP_OUTPUT_TYPE,
  CropImageTooLargeError,
  calculateCropperMaxImageSize,
  createCropUploadFile,
  createImageUploadFile
} from '../utils/imageProcessing.mjs'
import {
  authState,
  fetchCurrentUser,
  isAdminUser,
  logout
} from '../utils/auth'
import HistoryPanel from '../components/HistoryPanel.vue'
import BankPanel from '../components/BankPanel.vue'
import FigureOverlayEditor from '../components/FigureOverlayEditor.vue'
import PaperPanel from '../components/PaperPanel.vue'
import UserManagementPanel from '../components/UserManagementPanel.vue'

import * as pdfjsLib from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker

const router = useRouter()

const activeMenu = ref('upload')
const step = ref('select-file')
const processMode = ref('full')

const currentImageUrl = ref('')
const cropPreviewUrl = ref('')
const pdfPages = ref([])
const pdfLoading = ref(false)
const ocrLoading = ref(false)
const ocrResult = ref('')
const recognizeWarning = ref('')
const cropperRef = ref(null)
const draftStatus = ref('')
const draftStage = ref('idle')
const draftId = ref(null)
const sourceAssetId = ref(null)
const draftError = ref('')
const saveLoading = ref(false)
const saveBlocked = ref(false)
const saveResult = ref(null)
const recognitionDebug = ref(null)
const qualityWarnings = ref([])
const cropperMaxImgSize = ref(CROPPER_MAX_EDGE)
const cropEncoding = ref(false)
let cropEncodingGeneration = 0
// #62: PDF 渲染会话代号，新文件选择即作废在途渲染，防止过期页面回填。
let pdfRenderGeneration = 0
const editMode = ref(false)
const editContent = ref('')
const editSaving = ref(false)
// Draft reference image (#22): authenticated blob of the SourceAsset behind the
// current draft, shown next to the recognition result for visual comparison.
const draftImageObjectUrl = ref('')
const draftImageLoading = ref(false)
let draftImageRequestId = 0
// Figure detection (#58): regions auto-detected in the draft asset, and the
// user-confirmed bbox sent to save-to-bank (null = save without a figure).
const detectedFigures = ref([])
const confirmedFigureBbox = ref(null)

const changeCropperScale = (amount) => {
  cropperRef.value?.changeScale(amount)
}

const currentUser = computed(() => authState.currentUser)
const adminMode = computed(() => isAdminUser(currentUser.value))

const pageTitle = computed(() => {
  if (activeMenu.value === 'bank') {
    return '智能题库'
  }
  if (activeMenu.value === 'history') {
    return '历史记录'
  }
  if (activeMenu.value === 'papers') {
    return '组卷'
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
  if (activeMenu.value === 'papers') {
    return '查看已创建的试卷草稿和题目快照。'
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

const getDetailText = (detail) => {
  if (!detail) {
    return ''
  }
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item?.message || String(item)).join('；')
  }
  return detail.message || detail.error || JSON.stringify(detail)
}

const getRequestErrorMessage = (error) => {
  if (!error.response) {
    return '网络请求失败，请检查后端服务或网络连接后重试。'
  }

  const status = error.response.status
  const data = error.response?.data || {}
  const detail = getDetailText(data.detail)
  const combinedText = `${detail} ${data.error || ''} ${data.warning || ''}`.toLowerCase()

  if (status === 400) {
    if (combinedText.includes('non-image') || combinedText.includes('image') || combinedText.includes('图片')) {
      return '当前 Draft recognize 仅支持图片素材。'
    }
    return detail || '请求参数不正确，请检查上传素材后重试。'
  }
  if (status === 401) {
    return '登录状态已失效，请重新登录。'
  }
  if (status === 403) {
    return '当前账号无权限或登录状态异常，请重新登录。'
  }
  if (status === 404) {
    if (combinedText.includes('asset') || combinedText.includes('素材')) {
      return '素材不存在，请重新上传后再试。'
    }
    if (combinedText.includes('draft') || combinedText.includes('草稿')) {
      return '草稿不存在，请重新上传后再试。'
    }
    return '请求的素材或草稿不存在，请重新上传后再试。'
  }
  if (status === 409) {
    return '当前草稿已保存或状态不允许重复保存。'
  }
  if (status >= 500) {
    if (data.request_id) {
      return `服务端处理失败，请稍后重试或联系管理员。（请求编号：${data.request_id}，可提供给管理员用于日志排查）`
    }
    return '服务端处理失败，请稍后重试或联系管理员。'
  }
  if (data.error_type || data.error) {
    return getRecognizeErrorMessage(data)
  }
  return detail || '请求失败，请稍后重试。'
}

const resetDraftState = () => {
  draftStatus.value = ''
  draftStage.value = 'idle'
  draftId.value = null
  sourceAssetId.value = null
  draftError.value = ''
  saveLoading.value = false
  saveBlocked.value = false
  saveResult.value = null
  recognitionDebug.value = null
  qualityWarnings.value = []
  editMode.value = false
  editContent.value = ''
  editSaving.value = false
  detectedFigures.value = []
  confirmedFigureBbox.value = null
  releaseDraftImageObjectUrl()
}

const setStageMessage = (stage) => {
  draftStage.value = stage
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
const getRecognitionDebug = (payload) => payload?.recognition_debug || null
const getQualityWarnings = (payload) => Array.isArray(payload?.quality_warnings) ? payload.quality_warnings : []
const getDetectedFigures = (payload) => Array.isArray(payload?.detected_figures) ? payload.detected_figures : []
const applyDraftDetail = (payload) => {
  ocrResult.value = getDraftContent(payload)
  recognitionDebug.value = getRecognitionDebug(payload)
  qualityWarnings.value = getQualityWarnings(payload)
  detectedFigures.value = getDetectedFigures(payload)
  draftStatus.value = payload?.status || draftStatus.value
}
const formatQualityWarning = (warning) => {
  if (warning?.code === 'choice_options_incomplete') {
    return warning.message || '疑似选择题选项不完整，请核对 A/B/C/D 是否齐全。'
  }
  return warning?.message || '识别结果存在风险，请保存前核对。'
}

const isDraftBusy = computed(() => cropEncoding.value || ocrLoading.value || draftStatus.value === 'recognizing')
const canSaveDraft = computed(
  () =>
    draftStatus.value === 'draft_ready' &&
    Boolean(draftId.value) &&
    !ocrLoading.value &&
    !saveLoading.value &&
    !saveBlocked.value &&
    !editMode.value &&
    !editSaving.value
)

const draftOperationText = computed(() => {
  if (draftStage.value === 'uploading_asset') {
    return '正在上传素材...'
  }
  if (draftStage.value === 'creating_draft') {
    return '正在创建草稿...'
  }
  if (draftStage.value === 'recognizing') {
    return '正在识别题目，请稍候...'
  }
  if (draftStage.value === 'saving_to_bank') {
    return '正在保存入题库...'
  }
  return '正在处理，请稍候...'
})

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

  // #62：任何新的文件选择都作废仍在进行的 PDF 渲染。
  pdfRenderGeneration += 1

  const fileType = file.name.split('.').pop().toLowerCase()
  if (fileType === 'pdf') {
    await renderPdfToImages(file)
    return
  }

  const objectUrl = URL.createObjectURL(file)
  try {
    const dimensions = await loadImageDimensions(objectUrl)
    cropperMaxImgSize.value = calculateCropperMaxImageSize(dimensions.width, dimensions.height)
    setCurrentImageSource(objectUrl)
    // 图片路径清掉可能残留的已解析 PDF 页面，
    // 维持「pdfPages 非空 ⇔ 当前图来自 PDF 选页」的不变量。
    pdfPages.value = []
    step.value = 'process-image'
    processMode.value = 'full'
  } catch (error) {
    URL.revokeObjectURL(objectUrl)
    console.error(error)
    ElMessage.error('图片解析失败，请重新选择有效的图片文件。')
  }
}

const loadImageDimensions = (source) => new Promise((resolve, reject) => {
  const image = new Image()
  image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight })
  image.onerror = () => reject(new Error('Unable to decode image dimensions'))
  image.src = source
})

const revokeImageObjectUrl = (source) => {
  if (typeof source === 'string' && source.startsWith('blob:')) {
    URL.revokeObjectURL(source)
  }
}

const setCurrentImageSource = (source) => {
  if (currentImageUrl.value !== source) {
    revokeImageObjectUrl(currentImageUrl.value)
  }
  currentImageUrl.value = source
}

const setCropPreviewSource = (source) => {
  if (cropPreviewUrl.value !== source) {
    revokeImageObjectUrl(cropPreviewUrl.value)
  }
  cropPreviewUrl.value = source
}

const renderPdfToImages = async (file) => {
  const generation = ++pdfRenderGeneration
  setCurrentImageSource('')
  step.value = 'preview-pdf'
  pdfLoading.value = true
  pdfPages.value = []

  try {
    const arrayBuffer = await file.arrayBuffer()
    const pdf = await pdfjsLib.getDocument(arrayBuffer).promise

    for (let index = 1; index <= pdf.numPages; index += 1) {
      if (generation !== pdfRenderGeneration) {
        return
      }
      const page = await pdf.getPage(index)
      const viewport = page.getViewport({ scale: 2.5 })
      const canvas = document.createElement('canvas')
      const context = canvas.getContext('2d')
      canvas.height = viewport.height
      canvas.width = viewport.width

      await page.render({ canvasContext: context, viewport }).promise
      if (generation !== pdfRenderGeneration) {
        return
      }
      pdfPages.value.push({
        src: canvas.toDataURL('image/jpeg'),
        width: canvas.width,
        height: canvas.height
      })
    }
  } catch (error) {
    if (generation !== pdfRenderGeneration) {
      return
    }
    console.error(error)
    ElMessage.error('PDF 解析失败，可能是加密文件或文件损坏。')
    resetUpload()
  } finally {
    if (generation === pdfRenderGeneration) {
      pdfLoading.value = false
    }
  }
}

const selectPdfPage = (pageData) => {
  setCurrentImageSource(pageData.src)
  cropperMaxImgSize.value = calculateCropperMaxImageSize(pageData.width, pageData.height)
  step.value = 'process-image'
  processMode.value = 'full'
}

const confirmCropAndUpload = () => {
  if (!cropperRef.value || isDraftBusy.value) {
    return
  }

  const generation = ++cropEncodingGeneration
  cropEncoding.value = true
  cropperRef.value.getCropBlob(async (blob) => {
    try {
      if (!blob) {
        throw new Error('Cropper returned an empty Blob')
      }
      const { file } = await createCropUploadFile(blob)
      if (generation !== cropEncodingGeneration) {
        return
      }
      setCropPreviewSource(URL.createObjectURL(blob))
      runRecognition(file)
    } catch (error) {
      if (generation !== cropEncodingGeneration) {
        return
      }
      console.error(error)
      if (error instanceof CropImageTooLargeError) {
        ElMessage.error('裁剪图片过大，请缩小裁剪范围后重试。')
      } else {
        ElMessage.error('裁剪图片处理失败，请调整裁剪区域后重试。')
      }
    } finally {
      if (generation === cropEncodingGeneration) {
        cropEncoding.value = false
      }
    }
  })
}

const uploadFullImage = async () => {
  if (isDraftBusy.value) {
    return
  }

  try {
    const response = await fetch(currentImageUrl.value)
    const blob = await response.blob()
    const file = createImageUploadFile(blob, 'full_page')
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
    setStageMessage('uploading_asset')
    const assetFormData = new FormData()
    assetFormData.append('file', file)
    const assetResponse = await axios.post(`${API_V1_BASE_URL}/assets`, assetFormData)
    const assetPayload = assetResponse.data || {}
    const uploadedAssetId = extractId(assetPayload, ['source_asset_id', 'asset_id', 'existing_asset_id', 'id'])

    if (!uploadedAssetId) {
      throw new Error('素材上传成功，但响应中缺少 source_asset_id。')
    }

    if (assetPayload.deduplicated || assetPayload.existing_asset_id) {
      ElMessage.info('素材已存在，已复用已有素材继续录入。')
    }

    sourceAssetId.value = uploadedAssetId
    setStageMessage('creating_draft')
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
    setStageMessage('recognizing')
    draftStatus.value = 'recognizing'

    const recognizeResponse = await axios.post(`${API_V1_BASE_URL}/drafts/${createdDraftId}/recognize`)
    const payload = recognizeResponse.data || {}
    draftStatus.value = payload.status || (payload.success ? 'draft_ready' : 'failed')

    if (draftStatus.value === 'draft_ready' && payload.success !== false) {
      ocrResult.value = getDraftContent(payload)
      recognitionDebug.value = getRecognitionDebug(payload)
      qualityWarnings.value = getQualityWarnings(payload)
      detectedFigures.value = getDetectedFigures(payload)
      step.value = 'result'
      if (payload.partial_success) {
        recognizeWarning.value =
          payload.warning || 'OCR 已完成，但 AI 整理部分失败，当前展示降级结果，请核对后再保存。'
        ElMessage.warning(recognizeWarning.value)
      } else {
        ElMessage.success('识别完成。')
      }
      return
    }

    draftStatus.value = 'failed'
    recognitionDebug.value = getRecognitionDebug(payload)
    qualityWarnings.value = getQualityWarnings(payload)
    draftError.value = getRecognizeErrorMessage(payload)
    ElMessage.error(draftError.value)
    step.value = 'result'
  } catch (error) {
    console.error(error)
    draftStatus.value = 'failed'
    draftError.value = getRequestErrorMessage(error)
    if (!error.response && !error.isAxiosError && error.message) {
      draftError.value = error.message
    }
    ElMessage.error(draftError.value)
    step.value = 'result'
  } finally {
    ocrLoading.value = false
    setStageMessage('idle')
  }
}

// Legacy compatibility path. Do not use for Dashboard main Draft flow.
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

const enterEditMode = () => {
  if (draftStatus.value !== 'draft_ready' || !draftId.value) {
    return
  }
  editContent.value = ocrResult.value
  editMode.value = true
}

const cancelEdit = () => {
  editContent.value = ocrResult.value
  editMode.value = false
}

const saveDraftEdit = async () => {
  if (!editMode.value || editSaving.value || !draftId.value) {
    return
  }
  if (!editContent.value.trim()) {
    ElMessage.warning('题目正文不能为空。')
    return
  }

  editSaving.value = true
  draftError.value = ''
  try {
    const response = await axios.patch(`${API_V1_BASE_URL}/drafts/${draftId.value}`, {
      content: editContent.value
    })
    applyDraftDetail(response.data || {})
    editContent.value = ocrResult.value
    editMode.value = false
    ElMessage.success('识别结果已更新')
  } catch (error) {
    console.error(error)
    draftError.value = getRequestErrorMessage(error)
    ElMessage.error(draftError.value)
  } finally {
    editSaving.value = false
  }
}

const saveDraftToBank = async () => {
  if (!canSaveDraft.value) {
    return
  }

  if (qualityWarnings.value.length > 0) {
    try {
      await ElMessageBox.confirm(
        '当前识别结果存在风险提示。建议先核对原图、原始 OCR 文本和 LLM 清洗文本，确认题干与选项完整后再保存。',
        '保存前确认',
        {
          confirmButtonText: '仍然保存',
          cancelButtonText: '返回编辑',
          distinguishCancelAndClose: true,
          type: 'warning'
        }
      )
    } catch (action) {
      if (action === 'cancel') {
        enterEditMode()
      }
      return
    }
  }

  saveLoading.value = true
  draftError.value = ''
  setStageMessage('saving_to_bank')
  try {
    // #58: always send the explicit figure decision — confirmed bbox or null
    // (no figure) — so the backend crops from the original asset on save.
    const response = await axios.post(`${API_V1_BASE_URL}/drafts/${draftId.value}/save-to-bank`, {
      figure_bbox: confirmedFigureBbox.value
    })
    saveResult.value = {
      question_id: response.data?.question_id,
      question_revision_id: response.data?.question_revision_id
    }
    draftStatus.value = response.data?.status || 'saved_to_bank'
    ElMessage.success(draftStatusText.value)
  } catch (error) {
    console.error(error)
    draftError.value = getRequestErrorMessage(error)
    if (error.response?.status === 409) {
      saveBlocked.value = true
    }
    ElMessage.error(draftError.value)
  } finally {
    saveLoading.value = false
    setStageMessage('idle')
  }
}

const resetUpload = () => {
  cropEncodingGeneration += 1
  step.value = 'select-file'
  setCurrentImageSource('')
  setCropPreviewSource('')
  cropperMaxImgSize.value = CROPPER_MAX_EDGE
  cropEncoding.value = false
  pdfPages.value = []
  ocrResult.value = ''
  recognizeWarning.value = ''
  resetDraftState()
}

// #62：图片确认的取消若来自 PDF 选页，保留已解析页面并回到选页器，
// 用户换页不再需要重新上传和重新解析；普通图片上传保持原全量重置。
const cancelProcessStep = () => {
  if (pdfPages.value.length > 0) {
    cropEncodingGeneration += 1
    cropEncoding.value = false
    setCurrentImageSource('')
    setCropPreviewSource('')
    cropperMaxImgSize.value = CROPPER_MAX_EDGE
    step.value = 'preview-pdf'
    return
  }
  resetUpload()
}

const renderedContent = computed(() => (ocrResult.value ? renderMarkdown(ocrResult.value) : ''))
const renderedEditPreview = computed(() => (editContent.value ? renderMarkdown(editContent.value) : ''))

const resultImageUrl = computed(() => (processMode.value === 'crop' ? cropPreviewUrl.value : currentImageUrl.value))
const resultImageCaption = computed(() =>
  processMode.value === 'crop'
    ? '裁剪识别：显示本次框选并送识别的内容'
    : '整页识别：显示本次上传的整页原图'
)

// Prefer the persisted SourceAsset behind the draft (the exact recognized
// region); fall back to the local capture preview (framed crop in crop mode,
// full page otherwise) while the blob loads or when it is unavailable
// (legacy flow or load failure).
const resultImageSrc = computed(() => draftImageObjectUrl.value || resultImageUrl.value)

const releaseDraftImageObjectUrl = () => {
  if (draftImageObjectUrl.value) {
    URL.revokeObjectURL(draftImageObjectUrl.value)
    draftImageObjectUrl.value = ''
  }
}

const loadDraftReferenceImage = async () => {
  if (!draftId.value) {
    return
  }
  const requestId = ++draftImageRequestId
  draftImageLoading.value = true
  try {
    const response = await axios.get(buildDraftImageUrl(draftId.value), { responseType: 'blob' })
    if (requestId !== draftImageRequestId) {
      return
    }
    const objectUrl = URL.createObjectURL(response.data)
    releaseDraftImageObjectUrl()
    draftImageObjectUrl.value = objectUrl
  } catch (error) {
    console.warn('Failed to load draft reference image; falling back to the local preview.', error)
  } finally {
    if (requestId === draftImageRequestId) {
      draftImageLoading.value = false
    }
  }
}

watch(draftId, (value) => {
  draftImageRequestId += 1
  releaseDraftImageObjectUrl()
  draftImageLoading.value = false
  if (value) {
    loadDraftReferenceImage()
  }
})

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

onBeforeUnmount(() => {
  cropEncodingGeneration += 1
  revokeImageObjectUrl(currentImageUrl.value)
  revokeImageObjectUrl(cropPreviewUrl.value)
  draftImageRequestId += 1
  releaseDraftImageObjectUrl()
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
  font: inherit; /* button UA reset: keep the page's type, not the small system font */
  color: inherit; /* button UA reset: keep inherited text color */
  border: 1px solid #e6ece9;
  border-radius: 16px;
  padding: 14px;
  background: #fff;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 10px 24px rgba(18, 49, 66, 0.05);
}

.pdf-page-card:hover,
.pdf-page-card:focus-visible {
  transform: translateY(-4px);
  box-shadow: 0 16px 36px rgba(18, 49, 66, 0.12);
}

.pdf-page-card:focus-visible {
  outline: 2px solid #1f3d35;
  outline-offset: 3px;
}

.pdf-thumb {
  width: 100%;
  border-radius: 10px;
  border: 1px solid #edf1f0;
}

.page-number {
  display: block; /* span inside <button>: keep the old div's block layout */
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

.cropper-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Normal-flow bar above the viewport — never overlays the image (#31). */
.cropper-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px 8px 14px;
  color: #33473f;
  background: #eef4f1;
  border: 1px solid #dce5e1;
  border-radius: 10px;
}

.cropper-toolbar .el-button-group {
  flex: none;
}

.cropper-hints {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.cropper-hints .cropper-hint-image {
  font-size: 12px;
  opacity: 0.82;
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

.result-split-layout {
  display: flex;
  /* align-items: flex-start keeps the sticky image column from stretching. */
  align-items: flex-start;
  gap: 16px;
}

.result-main-column {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-image-column {
  /* #31: readable width (~40%) instead of the old fixed 300px rail. */
  flex: 0 0 min(42%, 560px);
  position: sticky;
  top: 16px;
}

.result-image-scroll {
  overflow: auto;
  max-height: 72vh;
  border-radius: 8px;
}

.result-image-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border: 1px solid #dbe7e2;
  border-radius: 12px;
  background: #fbfdfc;

  h3 {
    margin: 0;
    font-size: 15px;
    color: #1f3d35;
  }
}

.result-image-hint {
  margin: 0;
  font-size: 12px;
  color: #667a73;
}

.result-reference-image {
  display: block;
  width: 100%;
  cursor: zoom-in;

  /* No height cap here: the scroll container above bounds the panel, and the
     image keeps its natural aspect so scrolling reaches the full pixels (#31). */
  :deep(.el-image__inner) {
    width: 100%;
    height: auto;
    object-fit: scale-down;
  }
}

/* #58 figure overlay editor takes the same full width as the plain preview. */
.result-figure-editor {
  width: 100%;
}

/* Shared placeholder look for the confirmation preview error slot (#61) and
   the reference panel error/empty states (#22). */
.result-image-slot,
.result-image-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 160px;
  padding: 16px;
  color: #8a9a94;
  font-size: 13px;
  border: 1px dashed #dbe7e2;
  border-radius: 8px;
}

.reset-result-btn {
  width: fit-content;
}

.result-alert {
  margin-bottom: 4px;
}

.quality-warning-list {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #7a4d00;
  line-height: 1.7;
}

.result-image-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-image-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.result-image-head h3 {
  margin: 0;
  font-size: 15px;
}

.result-image-caption {
  color: #667a73;
  font-size: 12px;
}

.result-image {
  display: block;
  width: 100%;
  max-height: 420px;
  border-radius: 10px;
  background: #f5f7f6;
}

.draft-edit-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.draft-edit-panel h3,
.draft-edit-hint {
  margin: 0;
}

.draft-edit-hint {
  color: #667a73;
}

.draft-edit-preview {
  min-height: 120px;
  padding: 14px;
  border: 1px solid #dbe7e2;
  border-radius: 8px;
  background: #fbfdfc;
}

.result-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.recognition-debug-collapse {
  border: 1px solid #dbe7e2;
  border-radius: 8px;
  background: #fbfdfc;
  overflow: hidden;
}

.recognition-debug-alert {
  margin-bottom: 12px;
}

.recognition-debug-alert + .recognition-debug-alert {
  margin-top: -4px;
}

.recognition-debug-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.recognition-debug-block h4 {
  margin: 0 0 8px;
  color: #1f3d35;
  font-size: 14px;
}

.recognition-debug-block pre {
  min-height: 120px;
  max-height: 280px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  border-radius: 8px;
  background: #eef5f2;
  color: #253a35;
  font-family: Consolas, "Courier New", monospace;
  font-size: 13px;
  line-height: 1.6;
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

  .result-split-layout {
    flex-direction: column;
  }

  .result-image-column {
    order: -1;
    position: static;
    flex: none;
    width: 100%;
  }

  .result-image-scroll {
    max-height: 40vh;
  }

  .recognition-debug-grid {
    grid-template-columns: 1fr;
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
