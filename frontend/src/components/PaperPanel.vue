<template>
  <div class="paper-container">
    <div class="header-row">
      <div>
        <h2>组卷中心</h2>
        <p class="subtitle">查看当前登录用户创建的试卷草稿</p>
      </div>
      <el-button @click="fetchPapers" :loading="listLoading" circle>
        <el-icon><Refresh /></el-icon>
      </el-button>
    </div>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      class="state-alert"
    />

    <el-skeleton v-if="listLoading" :rows="4" animated />

    <div v-else-if="papers.length === 0" class="empty-state">
      <el-empty description="暂无试卷" />
    </div>

    <div v-else class="paper-layout">
      <div class="paper-list">
        <el-card
          v-for="paper in papers"
          :key="paper.id"
          class="paper-card"
          :class="{ active: selectedPaperId === paper.id }"
          shadow="hover"
          @click="openPaperDetail(paper.id)"
        >
          <div class="paper-title-row">
            <strong>{{ paper.title }}</strong>
            <el-tag size="small" type="info">{{ paper.status }}</el-tag>
          </div>
          <div class="paper-meta-grid">
            <span>题数：{{ paper.item_count }}</span>
            <span>总分：{{ paper.total_score }}</span>
            <span>创建：{{ formatTime(paper.created_at) }}</span>
          </div>
        </el-card>
      </div>

      <div class="paper-detail">
        <el-skeleton v-if="detailLoading" :rows="6" animated />

        <el-empty v-else-if="!currentPaper" description="请选择试卷查看详情" />

        <div v-else>
          <div class="detail-header">
            <div>
              <h3>{{ currentPaper.title }}</h3>
              <p v-if="currentPaper.description">{{ currentPaper.description }}</p>
            </div>
            <div class="detail-stats">
              <el-tag type="info">{{ currentPaper.status }}</el-tag>
              <span>{{ currentPaper.item_count }} 题</span>
              <span>{{ currentPaper.total_score }} 分</span>
            </div>
          </div>

          <div class="preview-controls">
            <div class="preview-config">
              <span>模板：HOMEWORK</span>
              <span>版本：学生版</span>
              <el-radio-group v-model="answerAreaMode" size="small">
                <el-radio-button label="none">无答题区</el-radio-button>
                <el-radio-button label="after_each_question">每题后留白</el-radio-button>
              </el-radio-group>
            </div>
            <el-button type="primary" :loading="previewLoading" @click="fetchPaperRenderModel">
              预览作业
            </el-button>
          </div>

          <el-alert
            v-if="previewErrorMessage"
            :title="previewErrorMessage"
            type="error"
            show-icon
            class="state-alert"
          />

          <el-skeleton v-if="previewLoading" :rows="5" animated />
          <paper-preview v-else-if="paperRenderModel" :render-model="paperRenderModel" />

          <div class="paper-items">
            <el-card
              v-for="item in currentPaper.items"
              :key="item.id"
              class="paper-item"
              shadow="never"
            >
              <div class="item-heading">
                <span>第 {{ item.position }} 题</span>
                <el-tag size="small" effect="plain">分值：{{ item.score ?? 0 }}</el-tag>
                <el-tag size="small" type="info" effect="plain">题目 ID：{{ item.question_id }}</el-tag>
                <el-tag size="small" type="warning" effect="plain">
                  {{ formatQuestionType(item.question_type_snapshot) }}
                </el-tag>
                <span class="difficulty-text">难度：{{ formatDifficultyStars(item.difficulty_level_snapshot) }}</span>
              </div>

              <el-divider content-position="left">题目内容</el-divider>
              <div class="markdown-body item-content" v-html="renderSnapshot(item.content_snapshot)"></div>

              <template v-if="item.answer_snapshot">
                <el-divider content-position="left">答案</el-divider>
                <div class="markdown-body item-content" v-html="renderSnapshot(item.answer_snapshot)"></div>
              </template>

              <template v-if="item.analysis_snapshot">
                <el-divider content-position="left">解析</el-divider>
                <div class="markdown-body item-content" v-html="renderSnapshot(item.analysis_snapshot)"></div>
              </template>

              <template v-if="getTags(item).length > 0">
                <el-divider content-position="left">知识点</el-divider>
                <div class="knowledge-tags">
                  <el-tag
                    v-for="(tag, index) in getTags(item)"
                    :key="index"
                    size="small"
                    type="success"
                    effect="plain"
                  >
                    {{ tag.label }}
                  </el-tag>
                </div>
              </template>
            </el-card>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { API_V1_BASE_URL } from '../config/api'
import { renderMarkdown } from '@/utils/renderMarkdown'
import PaperPreview from './PaperPreview.vue'

const API_BASE = API_V1_BASE_URL

const papers = ref([])
const currentPaper = ref(null)
const selectedPaperId = ref(null)
const listLoading = ref(false)
const detailLoading = ref(false)
const previewLoading = ref(false)
const errorMessage = ref('')
const previewErrorMessage = ref('')
const paperRenderModel = ref(null)
const answerAreaMode = ref('after_each_question')

const getErrorMessage = (error, fallback) => {
  const detail = error.response?.data?.detail
  if (error.response?.status === 401 || error.response?.status === 403) {
    return '登录状态或权限异常，请重新登录后再试。'
  }
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
    }
  } catch (error) {
    console.error(error)
    errorMessage.value = getErrorMessage(error, '加载试卷列表失败。')
    ElMessage.error(errorMessage.value)
  } finally {
    listLoading.value = false
  }
}

const openPaperDetail = async (paperId) => {
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
  } finally {
    detailLoading.value = false
  }
}

const fetchPaperRenderModel = async () => {
  if (!selectedPaperId.value) return
  previewLoading.value = true
  previewErrorMessage.value = ''
  try {
    const response = await axios.post(`${API_BASE}/papers/${selectedPaperId.value}/render-model`, {
      template_type: 'homework',
      version: 'student',
      paper_size: 'A4',
      group_by: 'question_type',
      sort_by: 'position',
      answer_area_mode: answerAreaMode.value
    })
    paperRenderModel.value = response.data
  } catch (error) {
    console.error(error)
    previewErrorMessage.value = getErrorMessage(error, '生成作业预览失败。')
    ElMessage.error(previewErrorMessage.value)
  } finally {
    previewLoading.value = false
  }
}

const handlePaperCreated = async () => {
  await fetchPapers()
}

const renderSnapshot = (content) => content ? renderMarkdown(content) : '<span style="color:#999">暂无内容</span>'

const getTags = (item) => {
  const rawTags = item?.knowledge_tags_snapshot || []
  return rawTags.map((tag) => {
    if (typeof tag === 'string') {
      return { label: tag }
    }
    if (tag && typeof tag === 'object') {
      return { label: tag.label || tag.name || String(tag) }
    }
    return { label: String(tag) }
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

const formatTime = (value) => value ? new Date(value).toLocaleString() : '-'

onMounted(() => {
  fetchPapers()
  window.addEventListener('paper-created', handlePaperCreated)
})

onBeforeUnmount(() => {
  window.removeEventListener('paper-created', handlePaperCreated)
})
</script>

<style scoped>
.paper-container {
  padding: 20px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 16px;
}

.subtitle {
  color: #666;
  font-size: 13px;
  margin-top: 6px;
}

.state-alert {
  margin-bottom: 16px;
}

.empty-state {
  margin-top: 30px;
  text-align: center;
}

.paper-layout {
  display: grid;
  grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.paper-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.paper-card {
  cursor: pointer;
  border: 1px solid transparent;
}

.paper-card.active {
  border-color: #409eff;
}

.paper-title-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.paper-title-row strong {
  color: #1f3442;
  word-break: break-word;
}

.paper-meta-grid {
  display: grid;
  gap: 6px;
  margin-top: 12px;
  color: #667780;
  font-size: 13px;
}

.paper-detail {
  min-height: 360px;
  padding: 18px;
  border: 1px solid #e5ece9;
  border-radius: 8px;
  background: #fff;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.detail-header h3 {
  margin: 0 0 8px;
  color: #1f3442;
}

.detail-header p {
  margin: 0;
  color: #667780;
  line-height: 1.7;
}

.detail-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
  color: #667780;
  font-size: 13px;
}

.preview-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px;
  margin-bottom: 16px;
  border: 1px solid #e5ece9;
  border-radius: 8px;
  background: #f8fbfa;
}

.preview-config {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  color: #536471;
  font-size: 13px;
}

.paper-items {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.paper-item {
  border-radius: 8px;
}

.item-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: #243846;
  font-weight: 600;
}

.difficulty-text {
  color: #8a6d1f;
  font-size: 13px;
  white-space: nowrap;
}

.item-content {
  font-size: 15px;
  line-height: 1.8;
}

.knowledge-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 980px) {
  .paper-layout {
    grid-template-columns: 1fr;
  }

  .detail-header {
    flex-direction: column;
  }

  .detail-stats {
    justify-content: flex-start;
  }

  .preview-controls {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
