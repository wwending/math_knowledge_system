<template>
  <div class="bank-container">
    <div class="header-row">
      <div>
        <h2>智能题库</h2>
        <p class="subtitle">仅显示当前登录用户的题目</p>
      </div>
      <div class="header-actions">
        <div class="selection-summary" aria-live="polite">
          已选 {{ selectedQuestionIds.length }} 题
        </div>
        <el-button
          type="success"
          :disabled="selectedQuestionIds.length === 0"
          @click="openCreatePaperDialog"
        >
          创建试卷
        </el-button>
        <el-input
          v-model="keyword"
          placeholder="关键词搜索（内容/知识点）"
          clearable
          :prefix-icon="Search"
          class="search-input"
        />
        <el-button aria-label="刷新题库列表" @click="fetchQuestions" :loading="loading" circle>
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <el-tabs v-model="activeBankTab" class="bank-tabs" @tab-change="handleBankTabChange">
      <el-tab-pane label="题库" name="active" />
      <el-tab-pane label="回收站" name="trash" />
    </el-tabs>

    <el-alert
      title="说明"
      type="info"
      description="当前页面仅展示当前登录用户题目"
      show-icon
      class="info-alert"
    />

    <el-alert
      v-if="!loading && list.length >= questionListLimit"
      type="warning"
      show-icon
      :closable="false"
      :title="`题目较多，仅显示前 ${questionListLimit} 条，可使用关键词搜索缩小范围`"
      class="limit-alert"
    />

    <el-skeleton v-if="loading" :rows="4" animated />

    <div v-else-if="filteredList.length === 0" class="empty-state">
      <el-empty description="暂无题目">
        <el-button type="primary" @click="handleGoUpload">去题目录入</el-button>
      </el-empty>
    </div>

    <div v-else class="question-list">
      <el-card
        v-for="item in filteredList"
        :key="item.id"
        class="question-item"
        shadow="hover"
      >
        <div class="list-item-content" @click="openDetail(item)">
          <div class="select-box" @click.stop>
            <el-checkbox
              :aria-label="`选择题目 #${item.id}`"
              v-if="activeBankTab === 'active'"
              :model-value="isQuestionSelected(item.id)"
              @change="toggleQuestionSelection(item.id)"
            />
          </div>

          <div class="thumb-box" v-if="hasImageField(item)">
            <el-image
              :src="getImageUrl(item)"
              fit="cover"
              class="thumb-img"
            >
              <template #error>
                <div class="image-slot">
                  <el-icon><icon-picture /></el-icon>
                </div>
              </template>
            </el-image>
          </div>

          <div class="info-box">
            <div class="meta-row">
              <el-tag size="small" type="info">ID: {{ item.id }}</el-tag>
              <el-tag size="small" type="warning" effect="plain">
                {{ formatQuestionType(item.question_type) }}
              </el-tag>
              <span class="difficulty-text">难度：{{ formatDifficultyStatus(item) }}</span>
              <span class="time">{{ activeBankTab === 'trash' ? `删除：${formatTime(item.deleted_at)}｜到期：${formatTime(item.purge_at)}` : formatTime(item.created_at) }}</span>
            </div>
            <div class="preview-text">
              {{ getPreviewText(item.content) }}
            </div>
            <div class="tags-row">
              <el-tag
                v-for="(tag, idx) in getTags(item).slice(0, 3)"
                :key="idx"
                size="small"
                effect="plain"
              >
                {{ tag.label }}
              </el-tag>
            </div>
          </div>

          <div class="action-box">
            <el-button type="primary" plain round @click.stop="openDetail(item)">
              查看详情
            </el-button>
            <el-button v-if="activeBankTab === 'active'" type="danger" plain round @click.stop="moveToTrash(item)">
              删除
            </el-button>
            <template v-else>
              <el-button type="success" plain round @click.stop="restoreQuestion(item)">恢复</el-button>
              <el-button type="danger" plain round @click.stop="permanentlyDeleteQuestion(item)">永久删除</el-button>
            </template>
          </div>
        </div>
      </el-card>
    </div>

    <el-dialog
      v-model="dialogVisible"
      title="题目详情"
      width="80%"
      top="5vh"
      destroy-on-close
    >
      <el-skeleton v-if="detailLoading" :rows="6" animated />

      <div class="detail-layout" v-else-if="currentItem">
        <div class="detail-left">
          <div class="image-wrapper" v-if="hasImageField(currentItem)">
            <el-image
              :src="getImageUrl(currentItem)"
              :preview-src-list="previewSources"
              fit="scale-down"
              class="detail-image"
            >
              <template #error>
                <div class="image-slot">
                  <span>加载失败</span>
                </div>
              </template>
            </el-image>
          </div>
          <div v-else class="image-placeholder">暂无原图</div>
        </div>

        <div class="detail-right">
          <div class="detail-actions">
            <el-button v-if="activeBankTab === 'active'" type="primary" @click="editing = true">编辑题目</el-button>
            <el-button v-if="activeBankTab === 'trash'" type="success" @click="restoreQuestion(currentItem)">恢复题目</el-button>
            <el-button v-if="activeBankTab === 'trash'" type="danger" @click="permanentlyDeleteQuestion(currentItem)">永久删除</el-button>
          </div>
          <QuestionEditWorkbench
            v-if="editing"
            :question="currentItem"
            @saved="handleQuestionSaved"
            @draft-change="handleDraftChange"
          />
          <div class="detail-meta">
            <el-tag size="small" type="info">ID: {{ currentItem.id }}</el-tag>
            <el-tag size="small" type="warning" effect="plain">
              {{ formatQuestionType(displayItem.question_type) }}
            </el-tag>
            <span class="difficulty-text">难度：{{ formatDifficultyStatus(displayItem) }}</span>
            <span class="time">{{ formatTime(currentItem.created_at) }}</span>
          </div>
          <el-divider content-position="left">知识点</el-divider>
          <div class="knowledge-tags">
            <el-tag
              v-for="(tag, i) in getTags(displayItem)"
              :key="i"
              type="success"
              effect="dark"
            >
              {{ tag.label }}
            </el-tag>
            <span v-if="getTags(displayItem).length === 0" class="empty-text">暂无知识点</span>
          </div>
          <el-divider content-position="left">题目内容</el-divider>
          <div class="markdown-body detail-content" v-html="renderTex(displayItem.content)"></div>
          <el-divider content-position="left">答案</el-divider>
          <div class="markdown-body detail-content" v-html="renderTex(displayItem.answer)"></div>
          <el-divider content-position="left">解析</el-divider>
          <div class="markdown-body detail-content" v-html="renderTex(displayItem.analysis)"></div>
        </div>
      </div>
    </el-dialog>

    <el-dialog
      v-model="createPaperDialogVisible"
      title="创建试卷"
      width="520px"
      destroy-on-close
    >
      <el-alert
        :title="`将使用当前已选 ${selectedQuestionIds.length} 道题创建试卷`"
        type="info"
        show-icon
        :closable="false"
        class="paper-dialog-alert"
      />
      <el-form label-position="top" class="paper-form" @submit.prevent>
        <el-form-item label="标题（必填）">
          <el-input v-model="paperForm.title" maxlength="80" show-word-limit />
        </el-form-item>
        <el-form-item label="说明（可选）">
          <el-input
            v-model="paperForm.description"
            type="textarea"
            :rows="3"
            maxlength="300"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createPaperDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="creatingPaper"
          :disabled="!canSubmitPaper"
          @click="createPaper"
        >
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search, Picture as IconPicture } from '@element-plus/icons-vue'
import { API_V1_BASE_URL } from '../config/api'
import { createQuestionImageLoader } from '../utils/questionImageLoader'
import { readStringQuery, replaceQueryValues } from '../utils/urlQueryState'
import { renderMarkdown } from '@/utils/renderMarkdown'
import { useRoute, useRouter } from 'vue-router'
import { formatDateTime } from '../utils/formatDateTime'
import QuestionEditWorkbench from './QuestionEditWorkbench.vue'

const API_BASE = API_V1_BASE_URL
const emit = defineEmits(['paper-created', 'go-upload'])

// 与后端约定的列表拉取上限；达到上限时提示“仅显示前 N 条”（真分页另开 issue）。
const questionListLimit = 100

const loading = ref(false)
const activeBankTab = ref('active')
const detailLoading = ref(false)
const detailRequestToken = ref(0)
const list = ref([])
// #75：搜索词与 ?bank_q= 同步——初始值从 URL 恢复，输入变化时 replace 回写。
const route = useRoute()
const router = useRouter()
const keyword = ref(readStringQuery(route, 'bank_q'))
const dialogVisible = ref(false)
const currentItem = ref(null)
const detailDraft = ref(null)
const displayItem = computed(() => {
  if (!currentItem.value || !detailDraft.value) return currentItem.value
  return { ...currentItem.value, ...detailDraft.value }
})
const editing = ref(false)
const selectedQuestionIds = ref([])
const createPaperDialogVisible = ref(false)
const creatingPaper = ref(false)
const paperForm = ref({
  title: '',
  description: ''
})

// 题目图片经鉴权接口以 blob 方式加载（#44），不再使用公开静态 URL。
const { hasImageField, syncItems, imageUrlFor, remove: imageLoaderRemove, dispose: disposeImageLoader } = createQuestionImageLoader()

watch(list, (items) => syncItems(items))
watch(keyword, (value) => {
  replaceQueryValues(router, route, { bank_q: value })
})

const getImageUrl = (item) => imageUrlFor(item)

const previewSources = computed(() =>
  [imageUrlFor(currentItem.value)].filter(Boolean)
)

onBeforeUnmount(disposeImageLoader)

const canSubmitPaper = computed(() => {
  return selectedQuestionIds.value.length > 0 && paperForm.value.title.trim().length > 0 && !creatingPaper.value
})

const listRequestToken = ref(0)
const fetchQuestions = async () => {
  const token = ++listRequestToken.value
  loading.value = true
  try {
    const endpoint = activeBankTab.value === 'trash' ? `${API_BASE}/questions/trash?limit=${questionListLimit}` : `${API_BASE}/questions?limit=${questionListLimit}`
    const res = await axios.get(endpoint)
    if (token === listRequestToken.value) list.value = res.data || []
  } catch (error) {
    console.error(error)
    ElMessage.error('获取题目列表失败')
  } finally {
    if (token === listRequestToken.value) loading.value = false
  }
}


const openDetail = async (item) => {
  const token = ++detailRequestToken.value
  dialogVisible.value = true
  detailLoading.value = true
  currentItem.value = item
  detailDraft.value = null
  try {
    const endpoint = activeBankTab.value === 'trash' ? `${API_BASE}/questions/trash/${item.id}` : `${API_BASE}/questions/${item.id}`
    const res = await axios.get(endpoint)
    if (token === detailRequestToken.value) currentItem.value = res.data
  } catch (error) {
    console.error(error)
    ElMessage.error('获取题目详情失败')
  } finally {
    if (token === detailRequestToken.value) detailLoading.value = false
  }
}

const handleQuestionSaved = (saved) => {
  const question = saved?.question || saved
  const revision = saved?.current_revision_no ?? question?.current_revision_no
  if (question && typeof question === 'object') {
    currentItem.value = {
      ...currentItem.value,
      ...question,
      current_revision_no: revision ?? currentItem.value?.current_revision_no
    }
  }
  detailDraft.value = null
  editing.value = false
  fetchQuestions()
}

const handleDraftChange = (draft) => {
  detailDraft.value = draft
}

const handleBankTabChange = () => {
  selectedQuestionIds.value = []
  currentItem.value = null
  detailDraft.value = null
  editing.value = false
  dialogVisible.value = false
  fetchQuestions()
}

const cleanupQuestion = (id) => {
  selectedQuestionIds.value = selectedQuestionIds.value.filter((questionId) => questionId !== id)
  imageLoaderRemove?.(id)
  if (currentItem.value?.id === id) {
    currentItem.value = null
    detailDraft.value = null
    editing.value = false
    dialogVisible.value = false
  }
}

const confirmAction = async (message) => {
  try { await ElMessageBox.confirm(message, '请确认操作', { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }); return true } catch { return false }
}

const moveToTrash = async (item) => {
  if (!(await confirmAction('删除后题目将进入回收站，保留 30 天。'))) return
  try { await axios.post(`${API_BASE}/questions/${item.id}/trash`); cleanupQuestion(item.id); ElMessage.success('题目已移入回收站'); fetchQuestions() } catch (error) { ElMessage.error(error.response?.data?.detail || '删除题目失败') }
}
const restoreQuestion = async (item) => {
  if (!(await confirmAction('恢复这道题目？'))) return
  try { await axios.post(`${API_BASE}/questions/${item.id}/restore`); cleanupQuestion(item.id); ElMessage.success('题目已恢复'); fetchQuestions() } catch (error) { ElMessage.error(error.response?.data?.detail || '恢复题目失败') }
}
const permanentlyDeleteQuestion = async (item) => {
  if (!(await confirmAction('永久删除后将无法从回收站恢复。'))) return
  try { await axios.delete(`${API_BASE}/questions/${item.id}/permanent`); cleanupQuestion(item.id); ElMessage.success('题目已永久删除'); fetchQuestions() } catch (error) { ElMessage.error(error.response?.data?.detail || '永久删除题目失败') }
}

const isQuestionSelected = (questionId) => selectedQuestionIds.value.includes(questionId)

const toggleQuestionSelection = (questionId) => {
  if (isQuestionSelected(questionId)) {
    selectedQuestionIds.value = selectedQuestionIds.value.filter((id) => id !== questionId)
    return
  }
  selectedQuestionIds.value = [...selectedQuestionIds.value, questionId]
}

const openCreatePaperDialog = () => {
  if (selectedQuestionIds.value.length === 0) {
    ElMessage.warning('请先选择至少一道题。')
    return
  }
  paperForm.value = {
    title: '',
    description: ''
  }
  createPaperDialogVisible.value = true
}

const getPaperErrorMessage = (error) => {
  const status = error.response?.status
  const detail = error.response?.data?.detail
  if (status === 409) {
    return detail || '试卷中存在重复题目，请调整后重试。'
  }
  if (status === 404) {
    return detail || '题目不存在或无权访问，请刷新题库后重试。'
  }
  if (status === 400) {
    return detail || '试卷信息不完整，请检查标题和题目。'
  }
  if (status === 401 || status === 403) {
    return '登录状态或权限异常，请重新登录后再试。'
  }
  return detail || '创建试卷失败，请稍后重试。'
}

const createPaper = async () => {
  if (!canSubmitPaper.value) {
    if (selectedQuestionIds.value.length === 0) {
      ElMessage.warning('请先选择至少一道题。')
    } else {
      ElMessage.warning('请填写试卷标题。')
    }
    return
  }

  creatingPaper.value = true
  try {
    await axios.post(`${API_BASE}/papers`, {
      title: paperForm.value.title.trim(),
      description: paperForm.value.description.trim() || null,
      items: selectedQuestionIds.value.map((questionId) => ({
        question_id: questionId,
        score: 0
      }))
    })
    selectedQuestionIds.value = []
    createPaperDialogVisible.value = false
    ElMessage.success('试卷创建成功。')
    emit('paper-created')
    window.dispatchEvent(new CustomEvent('paper-created'))
  } catch (error) {
    console.error(error)
    ElMessage.error(getPaperErrorMessage(error))
  } finally {
    creatingPaper.value = false
  }
}

const filteredList = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return list.value
  return list.value.filter((item) => {
    const contentText = (item.content || '').toLowerCase()
    const tagText = getTags(item).map((t) => t.label).join(' ').toLowerCase()
    return contentText.includes(q) || tagText.includes(q)
  })
})

const getTags = (item) => {
  const rawTags = (item && (item.knowledge_tags || item.knowledge)) ? (item.knowledge_tags || item.knowledge) : []
  return rawTags.map((tag) => {
    if (typeof tag === 'string') return { label: tag, score: 1.0 }
    if (tag && typeof tag === 'object') {
      return { label: tag.label || String(tag), score: tag.score ?? 1.0 }
    }
    return { label: String(tag), score: 1.0 }
  })
}

const questionTypeLabels = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  fill_blank: '填空题',
  solution: '解答题',
  judge: '判断题',
  unknown: '未知'
}

const formatQuestionType = (questionType) => questionTypeLabels[questionType] || '未知'

const formatDifficultyStars = (difficultyLevel) => {
  const level = Number(difficultyLevel)
  if (!Number.isInteger(level) || level < 1 || level > 5) return '未评估'
  return `${'★'.repeat(level)}${'☆'.repeat(5 - level)}`
}

const formatDifficultyStatus = (item) => {
  const status = item?.metadata_status
  if (status === 'pending' || status === 'processing') return '元数据评估中'
  if (status === 'failed') return '难度评估失败'
  if (status === 'ready' && item?.difficulty_level) return formatDifficultyStars(item.difficulty_level)
  return formatDifficultyStars(item?.difficulty_level)
}

const renderTex = (text) => text ? renderMarkdown(text) : '<span style="color:#767676">暂无内容</span>'

const getPreviewText = (text) => {
  if (!text) return '暂无识别内容'
  const clean = text.replace(/[#*`$]/g, '')
  return clean.length > 60 ? `${clean.slice(0, 60)}…` : clean
}

const formatTime = (value) => formatDateTime(value)

const handleGoUpload = () => {
  emit('go-upload')
}

onMounted(() => {
  fetchQuestions()
})
</script>

<style scoped>
.bank-container {
  padding: 20px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 10px;
}

.subtitle {
  color: #666;
  font-size: 13px;
  margin-top: 6px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.selection-summary {
  min-width: 92px;
  color: #48626b;
  font-size: 14px;
  white-space: nowrap;
}

.search-input {
  width: 260px;
}

.info-alert {
  margin-bottom: 20px;
}

.limit-alert {
  margin-bottom: 20px;
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.question-item {
  cursor: pointer;
}

.list-item-content {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 6px 0;
}

.select-box {
  width: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thumb-box {
  width: 100px;
  height: 80px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #eee;
  background: #f5f7fa;
}

.thumb-img {
  width: 100%;
  height: 100%;
}

.info-box {
  flex: 1;
  /* 允许 flex 子项收缩到内容宽度以下，配合 ellipsis 防窄窗口横向溢出 */
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  font-size: 12px;
  color: #767676;
  /* ID/时间等数字列用等宽数字（#76） */
  font-variant-numeric: tabular-nums;
}

.difficulty-text {
  color: #8a6d1f;
  white-space: nowrap;
}

.preview-text {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 520px;
}

.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.action-box {
  min-width: 100px;
  text-align: right;
}

.empty-state {
  margin-top: 30px;
  text-align: center;
}

.detail-layout {
  display: flex;
  height: 75vh;
  gap: 30px;
}

.detail-left {
  flex: 1;
  background: #eef2f7;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  overflow: hidden;
  padding: 20px;
  border: 1px solid #dcdfe6;
}

.image-wrapper {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.detail-image {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 70vh;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  background: white;
}

.image-placeholder {
  color: #767676;
}

.detail-right {
  flex: 1;
  overflow-y: auto;
  padding-right: 10px;
}

.detail-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  color: #767676;
  font-size: 12px;
  font-variant-numeric: tabular-nums; /* ID/时间等数字列（#76） */
  margin-bottom: 8px;
}

.knowledge-tags {
  margin-bottom: 18px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-content {
  font-size: 16px;
  line-height: 1.8;
}

.empty-text {
  color: #767676;
}

.image-slot {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
  background: #f5f7fa;
  color: #767676;
  font-size: 14px;
}

.paper-dialog-alert {
  margin-bottom: 16px;
}

.paper-form {
  margin-top: 8px;
}

/* 窄屏下详情弹窗改单列，对齐 PaperPanel 的 980px 断点 */
@media (max-width: 980px) {
  .detail-layout {
    flex-direction: column;
    height: auto;
    gap: 20px;
  }
}
</style>
