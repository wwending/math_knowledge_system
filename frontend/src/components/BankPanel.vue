<template>
  <div class="bank-container">
    <div class="header-row">
      <div>
        <h2>📚 智能题库</h2>
        <p class="subtitle">仅显示当前登录用户的题目</p>
      </div>
      <div class="header-actions">
        <el-input
          v-model="keyword"
          placeholder="关键词搜索（内容/知识点）"
          clearable
          :prefix-icon="Search"
          class="search-input"
        />
        <el-button @click="fetchQuestions" :loading="loading" circle>
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <el-alert
      title="说明"
      type="info"
      description="当前页面仅展示当前登录用户题目"
      show-icon
      class="info-alert"
    />

    <el-skeleton v-if="loading" :rows="4" animated />

    <div v-else-if="filteredList.length === 0" class="empty-state">
      <el-empty description="暂无题目">
        <el-button type="primary" @click="handleGoUpload">去题目采集上传</el-button>
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
          <div class="thumb-box" v-if="item.image_url">
            <el-image
              :src="getImageUrl(item.image_url)"
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
              <span class="time">{{ formatTime(item.created_at) }}</span>
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
          <div class="image-wrapper" v-if="currentItem.image_url">
            <el-image
              :src="getImageUrl(currentItem.image_url)"
              :preview-src-list="[getImageUrl(currentItem.image_url)]"
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
          <div class="detail-meta">
            <el-tag size="small" type="info">ID: {{ currentItem.id }}</el-tag>
            <span class="time">{{ formatTime(currentItem.created_at) }}</span>
          </div>
          <el-divider content-position="left">知识点</el-divider>
          <div class="knowledge-tags">
            <el-tag
              v-for="(tag, i) in getTags(currentItem)"
              :key="i"
              type="success"
              effect="dark"
            >
              {{ tag.label }}
            </el-tag>
            <span v-if="getTags(currentItem).length === 0" class="empty-text">暂无知识点</span>
          </div>
          <el-divider content-position="left">题目内容</el-divider>
          <div class="markdown-body detail-content" v-html="renderTex(currentItem.content)"></div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Refresh, Search, Picture as IconPicture } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import markdownItMathjax3 from 'markdown-it-mathjax3'

const md = new MarkdownIt({ html: true }).use(markdownItMathjax3)
const API_BASE = 'http://127.0.0.1:8000/api/v1'

const loading = ref(false)
const detailLoading = ref(false)
const list = ref([])
const keyword = ref('')
const dialogVisible = ref(false)
const currentItem = ref(null)

const fetchQuestions = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/history?limit=100`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    })
    list.value = res.data || []
  } catch (error) {
    console.error(error)
    ElMessage.error('获取题目列表失败')
  } finally {
    loading.value = false
  }
}


const openDetail = (item) => {
  currentItem.value = item
  dialogVisible.value = true
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

const renderTex = (text) => text ? md.render(text) : '<span style="color:#999">暂无内容</span>'

const getPreviewText = (text) => {
  if (!text) return '暂无识别内容'
  const clean = text.replace(/[#*`$]/g, '')
  return clean.length > 60 ? `${clean.slice(0, 60)}...` : clean
}

const formatTime = (value) => value ? new Date(value).toLocaleString() : '-'

const getImageUrl = (path) => path ? `http://127.0.0.1:8000/static/uploads/${path}` : ''

const handleGoUpload = () => {
  ElMessage.info('请切换到“题目采集”上传题目')
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

.search-input {
  width: 260px;
}

.info-alert {
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
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meta-row {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 12px;
  color: #999;
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
  color: #999;
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
  color: #999;
  font-size: 12px;
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
  color: #999;
}

.image-slot {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
  background: #f5f7fa;
  color: #909399;
  font-size: 14px;
}
</style>
