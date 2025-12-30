<template>
  <div class="app-container">
    <div class="main-layout">
      <el-header class="header">
        <h2>📐 数学知识点题库系统 (Pro)</h2>
      </el-header>

      <el-tabs v-model="activeTab" type="border-card" class="main-tabs" @tab-change="handleTabChange">
        
        <el-tab-pane label="📸 题目采集" name="upload">
          <el-row :gutter="20">
            <el-col :span="10">
              <el-card class="upload-card">
                <template #header>
                  <div class="card-header"><span>题目上传</span></div>
                </template>
                <el-upload
                  class="upload-demo"
                  drag
                  action="#" 
                  :auto-upload="false"
                  :on-change="handleFileChange"
                  :show-file-list="false"
                >
                  <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                  <div class="el-upload__text">拖拽或点击上传</div>
                </el-upload>
                <div v-if="previewUrl" class="image-preview">
                  <img :src="previewUrl" />
                </div>
                <div class="action-area">
                  <el-button type="primary" size="large" :loading="loading" @click="startRecognition" :disabled="!selectedFile" style="width: 100%;">
                    {{ loading ? 'AI 正在分析中...' : '开始识别并入库' }}
                  </el-button>
                </div>
              </el-card>
            </el-col>

            <el-col :span="14">
              <el-card class="result-card">
                <template #header>
                  <div class="card-header">
                    <span>当前识别结果</span>
                    <el-tag v-if="costTime" type="success" size="small">{{ costTime }}s</el-tag>
                  </div>
                </template>
                <div v-if="knowledgeTags.length" class="knowledge-area">
                  <p class="section-title">🧠 知识点标签：</p>
                  <div class="tags-wrapper">
                    <el-tag v-for="(t, i) in knowledgeTags" :key="i" :type="i===0?'success':'info'" effect="dark">
                      {{ t.label }} ({{ (t.score*100).toFixed(0) }}%)
                    </el-tag>
                  </div>
                </div>
                <div v-if="ocrResult" v-html="renderedContent" class="markdown-body"></div>
                <el-empty v-else description="等待上传..." />
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>

        <el-tab-pane label="📚 个人题库" name="history">
          <div v-if="historyList.length === 0" class="empty-history">
            <el-empty description="暂无历史题目，快去上传吧！" />
          </div>
          
          <div v-else class="history-grid">
            <el-card v-for="item in historyList" :key="item.id" class="history-item" shadow="hover">
              <div class="history-img-wrapper">
                <el-image 
                  :src="`http://127.0.0.1:8000/static/${item.image_url}`" 
                  fit="cover"
                  loading="lazy"
                  :preview-src-list="[`http://127.0.0.1:8000/static/${item.image_url}`]"
                />
              </div>
              <div class="history-info">
                <div class="tags-row">
                  <el-tag v-if="item.knowledge_tags && item.knowledge_tags.length" size="small" effect="plain">
                    {{ item.knowledge_tags[0].label }}
                  </el-tag>
                  <span class="date-text">{{ formatDate(item.created_at) }}</span>
                </div>
                <div class="content-preview">
                  {{ item.content ? item.content.slice(0, 50) + '...' : '无文本内容' }}
                </div>
              </div>
            </el-card>
          </div>
        </el-tab-pane>
      
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import axios from 'axios'
import katex from 'katex'
import 'katex/dist/katex.min.css'

// === 状态管理 ===
const activeTab = ref('upload')
const historyList = ref([]) // 历史数据

// 上传相关状态
const selectedFile = ref(null)
const previewUrl = ref('')
const loading = ref(false)
const ocrResult = ref('')
const knowledgeTags = ref([])
const costTime = ref(null)

// === 方法: 切换标签页 ===
const handleTabChange = async (tabName) => {
  if (tabName === 'history') {
    await fetchHistory()
  }
}

// === 方法: 获取历史记录 ===
const fetchHistory = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8000/api/v1/history')
    historyList.value = res.data
  } catch (e) {
    console.error("获取历史失败", e)
  }
}

// === 方法: 上传流程 (保持不变) ===
const handleFileChange = (uploadFile) => {
  selectedFile.value = uploadFile.raw
  previewUrl.value = URL.createObjectURL(uploadFile.raw)
}

const startRecognition = async () => {
  if (!selectedFile.value) return
  loading.value = true
  const formData = new FormData()
  formData.append('file', selectedFile.value)

  try {
    const response = await axios.post('http://127.0.0.1:8000/api/v1/recognize', formData)
    if (response.data.success) {
      ocrResult.value = response.data.content
      knowledgeTags.value = response.data.knowledge || []
      costTime.value = response.data.cost_seconds
      // 识别成功后，自动刷新一下历史数据(静默)
      fetchHistory() 
    }
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

// === 工具: 日期格式化 ===
const formatDate = (isoString) => {
  const date = new Date(isoString)
  return date.toLocaleString()
}

// === 工具: Markdown 渲染 (保持不变) ===
const renderedContent = computed(() => {
  if (!ocrResult.value) return ''
  let text = ocrResult.value.replace(/\n/g, '<br>')
  try {
     text = text.replace(/\$([^$]+)\$/g, (match, formula) => katex.renderToString(formula, { throwOnError: false }))
  } catch (e) {}
  return text
})
</script>

<style scoped>
.app-container { max-width: 1400px; margin: 0 auto; padding: 20px; }
.header { text-align: center; margin-bottom: 20px; }

/* 历史记录网格布局 */
.history-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}
.history-item { cursor: pointer; transition: transform 0.2s; }
.history-item:hover { transform: translateY(-5px); }
.history-img-wrapper { height: 160px; overflow: hidden; background: #f5f7fa; }
.history-img-wrapper .el-image { width: 100%; height: 100%; }
.history-info { padding: 10px; }
.tags-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.date-text { font-size: 12px; color: #999; }
.content-preview { font-size: 13px; color: #666; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 上传页原有样式 */
.upload-card, .result-card { min-height: 600px; }
.image-preview img { max-width: 100%; max-height: 300px; display: block; margin: 10px auto; }
.knowledge-area { margin-bottom: 15px; padding: 10px; background: #f0f9eb; border-radius: 4px; }
.tags-wrapper { display: flex; gap: 8px; flex-wrap: wrap; }
</style>