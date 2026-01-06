<template>
  <div class="history-container">
    <div class="header">
      <h2>📜 历史记录</h2>
      <el-button @click="fetchHistory" :loading="loading" circle><el-icon><Refresh /></el-icon></el-button>
    </div>

    <el-skeleton v-if="loading" :rows="3" animated />
    
    <div v-else-if="list.length === 0" class="empty-state">
      <el-empty description="暂无记录，快去上传题目吧！" />
    </div>

    <div v-else class="history-list">
      <el-card v-for="item in list" :key="item.id" class="history-item" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="time">{{ formatTime(item.created_at) }}</span>
            <el-tag v-if="item.knowledge_tags" size="small">
               {{ item.knowledge_tags.length }} 个知识点
            </el-tag>
          </div>
        </template>
        
        <div class="content-wrapper">
          <div class="image-box">
             <el-image 
                :src="getImageUrl(item.origin_image)" 
                :preview-src-list="[getImageUrl(item.origin_image)]"
                fit="cover"
                class="thumb"
             />
          </div>
          <div class="text-box">
             <div class="markdown-body" v-html="renderTex(item.content)"></div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { Refresh } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import markdownItMathjax3 from 'markdown-it-mathjax3'

// Markdown 配置
const md = new MarkdownIt({ html: true }).use(markdownItMathjax3)
const API_BASE = 'http://127.0.0.1:8000/api/v1'

const loading = ref(false)
const list = ref([])

const fetchHistory = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/history?limit=20`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    })
    list.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const renderTex = (text) => {
  if (!text) return ''
  // 简单截取前 100 字用于预览
  const preview = text.length > 100 ? text.slice(0, 100) + '...' : text
  return md.render(preview)
}

const formatTime = (str) => {
  return new Date(str).toLocaleString()
}

const getImageUrl = (path) => {
  if (!path) return ''
  return `http://127.0.0.1:8000/static/uploads/${path}`
}

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.history-item { margin-bottom: 15px; }
.card-header { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #666; }
.content-wrapper { display: flex; gap: 15px; }
.image-box .thumb { width: 80px; height: 80px; border-radius: 4px; border: 1px solid #eee; }
.text-box { flex: 1; font-size: 14px; overflow: hidden; height: 80px; }
</style>