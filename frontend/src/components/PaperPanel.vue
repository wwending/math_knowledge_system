<template>
  <div class="paper-container">
    <div class="header-row">
      <div><h2>组卷中心</h2><p class="subtitle">查看和编辑当前登录用户创建的试卷草稿</p></div>
      <el-button aria-label="刷新试卷列表" @click="fetchPapers" :loading="listLoading" circle><el-icon><Refresh /></el-icon></el-button>
    </div>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="state-alert" />
    <el-skeleton v-if="listLoading" :rows="4" animated />
    <div v-else-if="papers.length === 0" class="empty-state"><el-empty description="暂无试卷" /></div>

    <div v-else class="paper-layout">
      <div class="paper-list">
        <!-- #69: native buttons so keyboard users can open any paper detail
             (Enter/Space for free); name comes from the visible paper title. -->
        <button v-for="paper in papers" :key="paper.id" type="button" class="paper-card" :class="{ active: selectedPaperId === paper.id }" @click="openPaperDetail(paper.id)">
          <span class="paper-title-row"><strong>{{ paper.title }}</strong><el-tag size="small" type="info">{{ paper.status }}</el-tag></span>
          <span class="paper-meta-grid"><span>题数：{{ paper.item_count }}</span><span>总分：{{ paper.total_score }}</span><span>创建：{{ formatTime(paper.created_at) }}</span></span>
        </button>
      </div>

      <div class="paper-detail">
        <el-skeleton v-if="detailLoading" :rows="6" animated />
        <el-empty v-else-if="!currentPaper" description="请选择试卷查看详情" />
        <div v-else>
          <div v-if="editMode" class="edit-paper-meta">
            <el-form label-position="top" @submit.prevent>
              <el-form-item label="试卷标题"><el-input v-model="editDraft.title" maxlength="80" show-word-limit /></el-form-item>
              <el-form-item label="试卷描述"><el-input v-model="editDraft.description" type="textarea" :rows="3" maxlength="300" show-word-limit /></el-form-item>
            </el-form>
            <div class="edit-actions">
              <el-button @click="openQuestionDialog">从题库添加题目</el-button>
              <div><el-button :disabled="saveLoading" @click="cancelEditing">取消修改</el-button><el-button type="primary" :loading="saveLoading" :disabled="saveLoading" @click="savePaper">保存修改</el-button></div>
            </div>
          </div>

          <div v-else class="detail-header">
            <div><h3>{{ currentPaper.title }}</h3><p v-if="currentPaper.description">{{ currentPaper.description }}</p></div>
            <div class="detail-stats">
              <el-tag type="info">{{ currentPaper.status }}</el-tag><span>{{ currentPaper.item_count }} 题</span><span>{{ currentPaper.total_score }} 分</span>
              <el-button v-if="currentPaper.status === 'draft'" type="primary" plain @click="startEditing">编辑试卷</el-button>
            </div>
          </div>

          <div v-if="!editMode" class="preview-controls">
            <div class="preview-config"><span>模板：HOMEWORK</span><span>版本：学生版</span><el-radio-group v-model="answerAreaMode" size="small"><el-radio-button label="none">无答题区</el-radio-button><el-radio-button label="after_each_question">每题后留白</el-radio-button></el-radio-group><el-switch v-model="currentPaper.show_answer" active-text="显示答案" @change="saveDisplayOptions"/><el-switch v-model="currentPaper.show_analysis" active-text="显示解析" @change="saveDisplayOptions"/></div>
            <el-button type="primary" :loading="previewLoading" @click="fetchPaperRenderModel">预览作业</el-button>
          </div>
          <el-alert v-if="previewErrorMessage" :title="previewErrorMessage" type="error" show-icon class="state-alert" />
          <el-skeleton v-if="previewLoading" :rows="5" animated />
          <paper-preview v-else-if="paperRenderModel && !editMode" :render-model="paperRenderModel" />

          <div v-if="editMode" class="paper-items edit-items">
            <el-card v-for="(item, index) in editDraft.items" :key="item.localKey" class="paper-item" shadow="never">
              <div class="item-heading edit-item-heading">
                <span>第 {{ index + 1 }} 题</span><el-tag size="small" type="info" effect="plain">题目 ID：{{ item.question_id }}</el-tag>
                <div class="reorder-actions"><el-button size="small" :disabled="index === 0" @click="moveItem(index, -1)">↑ 上移</el-button><el-button size="small" :disabled="index === editDraft.items.length - 1" @click="moveItem(index, 1)">↓ 下移</el-button><el-button size="small" type="danger" plain @click="removeItem(index)">删除</el-button></div>
              </div>
              <el-form label-position="top" class="item-edit-form" @submit.prevent>
                <el-form-item label="分值"><el-input-number v-model="item.score" :min="0" :precision="1" controls-position="right" /></el-form-item>
                <el-alert title="题目内容为不可变快照；如需新版，请移除后从题库重新添加。" type="info" :closable="false" />
                <div class="snapshot-preview markdown-body" v-html="renderSnapshot(item.content_snapshot)"></div>
              </el-form>
            </el-card>
          </div>

          <div v-else class="paper-items">
            <el-card v-for="item in currentPaper.items" :key="item.id" class="paper-item" shadow="never">
              <div class="item-heading"><span>第 {{ item.position }} 题</span><el-tag size="small" effect="plain">分值：{{ item.score ?? 0 }}</el-tag><el-tag size="small" type="info" effect="plain">题目 ID：{{ item.question_id }}</el-tag><el-tag size="small" type="warning" effect="plain">{{ formatQuestionType(item.question_type_snapshot) }}</el-tag><span class="difficulty-text">难度：{{ formatDifficultyStars(item.difficulty_level_snapshot) }}</span></div>
              <el-button link type="primary" @click="openSourceQuestion(item.question_id)">在题库中查看源题</el-button><span class="source-note">修改源题不会同步当前试卷</span>
              <el-divider content-position="left">题目内容</el-divider><PaperSectionSnapshot v-if="item.section_snapshot" :paper-id="currentPaper.id" :item="item" section-name="stem"/><div v-else class="markdown-body item-content" v-html="renderSnapshot(item.content_snapshot)"></div>
              <template v-if="paperItemSectionHasContent(item, 'answer')"><el-divider content-position="left">答案</el-divider><PaperSectionSnapshot v-if="item.section_snapshot" :paper-id="currentPaper.id" :item="item" section-name="answer"/><div v-else class="markdown-body item-content" v-html="renderSnapshot(item.answer_snapshot)"></div></template>
              <template v-if="paperItemSectionHasContent(item, 'analysis')"><el-divider content-position="left">解析</el-divider><PaperSectionSnapshot v-if="item.section_snapshot" :paper-id="currentPaper.id" :item="item" section-name="analysis"/><div v-else class="markdown-body item-content" v-html="renderSnapshot(item.analysis_snapshot)"></div></template>
              <template v-if="getTags(item).length > 0"><el-divider content-position="left">知识点</el-divider><div class="knowledge-tags"><el-tag v-for="(tag, index) in getTags(item)" :key="index" size="small" type="success" effect="plain">{{ tag.label }}</el-tag></div></template>
            </el-card>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="questionDialogVisible" title="从题库添加题目" width="720px" destroy-on-close>
      <el-input v-model="questionKeyword" placeholder="搜索题干" clearable class="question-search" />
      <el-skeleton v-if="questionLoading" :rows="5" animated />
      <el-empty v-else-if="filteredQuestions.length === 0" description="暂无可用题目" />
      <div v-else class="question-picker-list">
        <div v-for="question in filteredQuestions" :key="question.id" class="question-picker-item" @click="onPickerItemClick($event, question.id)">
          <el-checkbox :aria-label="`选择题目 #${question.id}`" :model-value="questionSelection.includes(question.id)" :disabled="draftQuestionIds.has(question.id)" @change="toggleQuestionSelection(question.id)" />
          <div class="question-picker-content"><div class="markdown-body" v-html="renderSnapshot(question.content)"></div><el-tag v-if="draftQuestionIds.has(question.id)" size="small" type="info">已添加</el-tag></div>
        </div>
      </div>
      <template #footer><el-button @click="questionDialogVisible = false">取消</el-button><el-button type="primary" :disabled="questionSelection.length === 0" @click="addSelectedQuestions">添加所选题目</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { API_V1_BASE_URL } from '../config/api'
import { readStringQuery, replaceQueryValues } from '../utils/urlQueryState'
import { renderMarkdown } from '@/utils/renderMarkdown'
import { formatDateTime } from '../utils/formatDateTime'
import PaperPreview from './PaperPreview.vue'
import PaperSectionSnapshot from './PaperSectionSnapshot.vue'

const API_BASE = API_V1_BASE_URL
const route = useRoute()
const router = useRouter()
const papers = ref([])
const currentPaper = ref(null)
const selectedPaperId = ref(null)
const listLoading = ref(false)
const detailLoading = ref(false)
const previewLoading = ref(false)
const saveLoading = ref(false)
const errorMessage = ref('')
const previewErrorMessage = ref('')
const paperRenderModel = ref(null)
const answerAreaMode = ref('after_each_question')
// #77: 答题区模式变更后旧预览仍基于旧设置，直接失效待重新生成。
watch(answerAreaMode, () => {
  if (paperRenderModel.value) paperRenderModel.value = null
})
const editMode = ref(false)
const editDraft = ref(null)
const editBaseline = ref('')
const questionDialogVisible = ref(false)
const questionLoading = ref(false)
const questions = ref([])
const questionKeyword = ref('')
const questionSelection = ref([])

const clone = (value) => JSON.parse(JSON.stringify(value))
const draftQuestionIds = computed(() => new Set((editDraft.value?.items || []).map((item) => item.question_id)))
const filteredQuestions = computed(() => {
  const keyword = questionKeyword.value.trim().toLowerCase()
  return keyword ? questions.value.filter((question) => (question.content || '').toLowerCase().includes(keyword)) : questions.value
})
const getErrorMessage = (error, fallback) => {
  const detail = error.response?.data?.detail
  if (error.response?.status === 401 || error.response?.status === 403) return '登录状态或权限异常，请重新登录后再试。'
  if (Array.isArray(detail)) return detail[0]?.msg || fallback
  return detail || fallback
}

const fetchPapers = async () => {
  listLoading.value = true
  errorMessage.value = ''
  try {
    const response = await axios.get(`${API_BASE}/papers`)
    papers.value = response.data || []
    if (selectedPaperId.value && !papers.value.some((paper) => paper.id === selectedPaperId.value)) {
      selectedPaperId.value = null
      currentPaper.value = null
      editMode.value = false
    }
  } catch (error) {
    console.error(error)
    errorMessage.value = getErrorMessage(error, '加载试卷列表失败。')
    ElMessage.error(errorMessage.value)
  } finally { listLoading.value = false }
}

// #75：选中试卷同步到 ?paper_id=。深链指向不存在/无权试卷时，fetchPapers 的
// 陈旧校验会把选中清空，本 watcher 随之把该参数从 URL 移除，链接自动自愈。
watch(selectedPaperId, (paperId) => {
  replaceQueryValues(router, route, { paper_id: paperId ?? '' })
})
const confirmDiscard = async () => {
  if (!editMode.value || JSON.stringify(editDraft.value) === editBaseline.value) return true
  try {
    await ElMessageBox.confirm('存在未保存修改，确认放弃吗？', '取消编辑', { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning' })
    return true
  } catch { return false }
}
const openPaperDetail = async (paperId) => {
  if (paperId === selectedPaperId.value && currentPaper.value) return
  if (!(await confirmDiscard())) return
  editMode.value = false
  editDraft.value = null
  selectedPaperId.value = paperId
  detailLoading.value = true
  errorMessage.value = ''
  previewErrorMessage.value = ''
  paperRenderModel.value = null
  try {
    const response = await axios.get(`${API_BASE}/papers/${paperId}`)
    currentPaper.value = response.data
  } catch (error) {
    console.error(error)
    errorMessage.value = getErrorMessage(error, '加载试卷详情失败。')
    ElMessage.error(errorMessage.value)
  } finally { detailLoading.value = false }
}
const fetchPaperRenderModel = async () => {
  if (!selectedPaperId.value) return
  previewLoading.value = true
  previewErrorMessage.value = ''
  try {
    const response = await axios.post(`${API_BASE}/papers/${selectedPaperId.value}/render-model`, { template_type: 'homework', version: 'student', paper_size: 'A4', group_by: 'question_type', sort_by: 'position', answer_area_mode: answerAreaMode.value })
    paperRenderModel.value = response.data
  } catch (error) {
    console.error(error)
    previewErrorMessage.value = getErrorMessage(error, '生成作业预览失败。')
    ElMessage.error(previewErrorMessage.value)
  } finally { previewLoading.value = false }
}

const startEditing = () => {
  editDraft.value = { title: currentPaper.value.title, description: currentPaper.value.description || '', items: currentPaper.value.items.map((item) => ({ ...clone(item), kind: 'existing', localKey: `existing-${item.id}` })) }
  editBaseline.value = JSON.stringify(editDraft.value)
  editMode.value = true
  paperRenderModel.value = null
  previewErrorMessage.value = ''
}
const cancelEditing = async () => {
  if (!(await confirmDiscard())) return
  editMode.value = false
  editDraft.value = null
  editBaseline.value = ''
}
const moveItem = (index, offset) => {
  const target = index + offset
  if (target < 0 || target >= editDraft.value.items.length) return
  const items = [...editDraft.value.items]
  ;[items[index], items[target]] = [items[target], items[index]]
  editDraft.value.items = items
}
const removeItem = async (index) => {
  if (editDraft.value.items.length === 1) return ElMessage.warning('试卷至少需要保留一道题。')
  try {
    await ElMessageBox.confirm('确认从当前试卷中删除这道题吗？题库原题不会被删除。', '删除题目', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    editDraft.value.items.splice(index, 1)
  } catch { /* User cancelled. */ }
}
const loadQuestions = async () => {
  questionLoading.value = true
  try {
    const response = await axios.get(`${API_BASE}/questions?limit=100`)
    questions.value = response.data || []
  } catch (error) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '加载题库失败。'))
  } finally { questionLoading.value = false }
}
const openQuestionDialog = async () => {
  questionSelection.value = []
  questionKeyword.value = ''
  questionDialogVisible.value = true
  await loadQuestions()
}
const toggleQuestionSelection = (questionId) => {
  if (draftQuestionIds.value.has(questionId)) return
  questionSelection.value = questionSelection.value.includes(questionId) ? questionSelection.value.filter((id) => id !== questionId) : [...questionSelection.value, questionId]
}
const onPickerItemClick = (event, questionId) => {
  // Clicks inside the checkbox are handled by its own change event; handling them here too would toggle twice.
  if (event.target.closest('.el-checkbox')) return
  toggleQuestionSelection(questionId)
}
const addSelectedQuestions = () => {
  for (const questionId of questionSelection.value) {
    if (draftQuestionIds.value.has(questionId)) continue
    const question = questions.value.find((item) => item.id === questionId)
    editDraft.value.items.push({ kind: 'question', localKey: `question-${questionId}`, question_id: questionId, score: 0, content_snapshot: question?.content || '' })
  }
  questionDialogVisible.value = false
  questionSelection.value = []
}
const buildUpdateItem = (item) => {
  if (item.kind === 'existing' || item.id) return { kind: 'existing', id: item.id, question_id: item.question_id, score: Number(item.score) || 0 }
  return { kind: 'question', question_id: item.question_id, score: Number(item.score) || 0 }
}
const savePaper = async () => {
  const title = editDraft.value.title.trim()
  if (!title) return ElMessage.warning('试卷标题不能为空。')
  if (editDraft.value.items.length === 0) return ElMessage.warning('试卷至少需要保留一道题。')
  saveLoading.value = true
  try {
    const response = await axios.patch(`${API_BASE}/papers/${currentPaper.value.id}`, { title, description: editDraft.value.description.trim() || null, show_answer: currentPaper.value.show_answer, show_analysis: currentPaper.value.show_analysis, items: editDraft.value.items.map(buildUpdateItem) })
    currentPaper.value = response.data
    papers.value = papers.value.map((paper) => paper.id === response.data.id ? { ...paper, title: response.data.title, status: response.data.status, item_count: response.data.item_count, total_score: response.data.total_score, updated_at: response.data.updated_at } : paper)
    paperRenderModel.value = null
    editMode.value = false
    editDraft.value = null
    editBaseline.value = ''
    ElMessage.success('试卷修改已保存。')
  } catch (error) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '保存试卷修改失败。'))
  } finally { saveLoading.value = false }
}
const saveDisplayOptions = async () => {
  if (!currentPaper.value || editMode.value) return
  const payload = {
    title: currentPaper.value.title,
    description: currentPaper.value.description,
    show_answer: currentPaper.value.show_answer,
    show_analysis: currentPaper.value.show_analysis,
    items: currentPaper.value.items.map(buildUpdateItem)
  }
  try {
    const response = await axios.patch(`${API_BASE}/papers/${currentPaper.value.id}`, payload)
    currentPaper.value = response.data
    paperRenderModel.value = null
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '保存显示设置失败。'))
    const response = await axios.get(`${API_BASE}/papers/${currentPaper.value.id}`)
    currentPaper.value = response.data
  }
}
const openSourceQuestion = (questionId) => replaceQueryValues(router, route, { tab: 'bank', bank_question_id: questionId })

const handlePaperCreated = async () => fetchPapers()
const renderSnapshot = (content) => content ? renderMarkdown(content) : '<span style="color:#767676">暂无内容</span>'
const paperItemSectionHasContent = (item, name) => item.section_snapshot
  ? (item.section_snapshot.sections?.[name]?.blocks?.length || 0) > 0
  : Boolean(item[`${name}_snapshot`])
const getTags = (item) => (item?.knowledge_tags_snapshot || []).map((tag) => typeof tag === 'string' ? { label: tag } : tag && typeof tag === 'object' ? { label: tag.label || tag.name || String(tag) } : { label: String(tag) })
const questionTypeLabels = { single_choice: '单选题', multiple_choice: '多选题', fill_blank: '填空题', solution: '解答题', judge: '判断题', unknown: '未知' }
const formatQuestionType = (questionType) => questionTypeLabels[questionType] || '未知'
const formatDifficultyStars = (difficultyLevel) => {
  const level = Number(difficultyLevel)
  return Number.isInteger(level) && level >= 1 && level <= 5 ? `${'★'.repeat(level)}${'☆'.repeat(5 - level)}` : '未评估'
}
const formatTime = (value) => formatDateTime(value)
onMounted(() => {
  fetchPapers()
  window.addEventListener('paper-created', handlePaperCreated)
  // #75：从 ?paper_id= 恢复选中的试卷；非法值直接忽略。
  const requestedPaperId = Number.parseInt(readStringQuery(route, 'paper_id'), 10)
  if (Number.isInteger(requestedPaperId) && requestedPaperId > 0) {
    openPaperDetail(requestedPaperId)
  }
})
onBeforeUnmount(() => window.removeEventListener('paper-created', handlePaperCreated))
</script>

<style scoped>
.paper-container { padding: 20px; }
.header-row, .detail-header, .edit-actions, .edit-item-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.header-row { margin-bottom: 16px; }
.subtitle { color: #666; font-size: 13px; margin-top: 6px; }
.state-alert { margin-bottom: 16px; }
.empty-state { margin-top: 30px; text-align: center; }
.paper-layout { display: grid; grid-template-columns: minmax(260px, 360px) minmax(0, 1fr); gap: 18px; align-items: start; }
.paper-list, .paper-items { display: flex; flex-direction: column; gap: 12px; }
/* #69: replaces the old clickable el-card; resets the button UA defaults so
   the card looks unchanged, and keeps the focus outline for keyboard users. */
.paper-card { display: block; width: 100%; cursor: pointer; font: inherit; color: inherit; text-align: left; padding: 20px; background: #fff; border: 1px solid transparent; border-radius: 4px; }
.paper-card:hover { box-shadow: var(--el-box-shadow-light); }
.paper-card:focus-visible { outline: 2px solid #409eff; outline-offset: 2px; }
.paper-card.active { border-color: #409eff; }
.paper-title-row { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
.paper-title-row strong { color: #1f3442; word-break: break-word; }
.paper-meta-grid { display: grid; gap: 6px; margin-top: 12px; color: #667780; font-size: 13px; font-variant-numeric: tabular-nums; /* 题数/总分/时间列（#76） */ }
.paper-detail { min-height: 360px; padding: 18px; border: 1px solid #e5ece9; border-radius: 8px; background: #fff; }
.detail-header { margin-bottom: 18px; align-items: flex-start; }
.detail-header h3 { margin: 0 0 8px; color: #1f3442; }
.detail-header p { margin: 0; color: #667780; line-height: 1.7; }
.detail-stats { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: flex-end; color: #667780; font-size: 13px; font-variant-numeric: tabular-nums; }
.preview-controls { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px; margin-bottom: 16px; border: 1px solid #e5ece9; border-radius: 8px; background: #f8fbfa; }
.preview-config, .item-heading, .knowledge-tags, .reorder-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.preview-config { color: #536471; font-size: 13px; }
.paper-item { border-radius: 8px; }
.item-heading { color: #243846; font-weight: 600; }
.difficulty-text { color: #8a6d1f; font-size: 13px; white-space: nowrap; }
.item-content { font-size: 15px; line-height: 1.8; }
.source-note { margin-left: 8px; color: #7a8790; font-size: 12px; }
.edit-paper-meta { padding: 16px; margin-bottom: 16px; border: 1px solid #d9ecff; border-radius: 8px; background: #f5faff; }
.edit-actions { margin-top: 8px; }
.edit-items { gap: 16px; }
.reorder-actions { margin-left: auto; }
.item-edit-form { margin-top: 16px; }
.snapshot-preview { padding: 10px 12px; margin: -8px 0 18px; border-left: 3px solid #d9ecff; background: #fafcfe; }
.question-search { margin-bottom: 12px; }
.question-picker-list { max-height: 460px; overflow: auto; display: flex; flex-direction: column; gap: 8px; }
.question-picker-item { display: flex; gap: 10px; align-items: flex-start; padding: 10px; border: 1px solid #e5ece9; border-radius: 6px; cursor: pointer; }
.question-picker-content { min-width: 0; flex: 1; }
@media (max-width: 980px) {
  .paper-layout { grid-template-columns: 1fr; }
  .detail-header, .edit-actions, .edit-item-heading { flex-direction: column; align-items: flex-start; }
  .detail-stats { justify-content: flex-start; }
  .preview-controls { flex-direction: column; align-items: flex-start; }
  .reorder-actions { margin-left: 0; }
}
</style>
