<template>
  <div class="history-container">
    <div class="header">
      <h2>识别历史</h2>
      <el-button aria-label="刷新题目监控" @click="fetchHistory" :loading="loading" circle>
        <el-icon><Refresh /></el-icon>
      </el-button>
    </div>

    <el-alert
      v-if="!loading && list.length >= historyListLimit"
      type="warning"
      show-icon
      :closable="false"
      :title="`记录较多，仅显示前 ${historyListLimit} 条`"
      class="limit-alert"
    />

    <el-skeleton v-if="loading" :rows="3" animated />
    
    <div v-else-if="list.length === 0" class="empty-state">
      <el-empty description="数据库暂无数据" />
    </div>

    <div v-else class="history-list">
      <el-card v-for="item in list" :key="item.id" class="history-item" shadow="hover">
        <div class="list-item-content">
          <div class="thumb-box" @click="openDetail(item)">
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
          
          <div class="info-box" @click="openDetail(item)">
             <div class="meta-row">
               <el-tag size="small" type="info">ID: {{ item.id }}</el-tag>
               <span class="time">{{ formatTime(item.created_at) }}</span>
             </div>
             <div class="preview-text">
               {{ getPreviewText(item.content) }}
             </div>
             <div class="tags-row">
                <el-tag 
                  v-for="(tag, idx) in (item.knowledge || []).slice(0, 3)" 
                  :key="idx" 
                  size="small" 
                  effect="plain"
                >
                  {{ tag.label }}
                </el-tag>
             </div>
          </div>

          <div class="action-box">
             <el-button type="primary" plain round @click="openDetail(item)">
               查看详情
             </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <el-dialog
      v-model="dialogVisible"
      title="题目详情分析"
      width="80%"
      top="5vh"
      destroy-on-close
    >
      <div class="detail-layout" v-if="currentItem">
        <div class="detail-left">
          <div class="image-wrapper">
            
            <el-image
              :src="getImageUrl(currentItem)"
              :preview-src-list="previewSources"
              fit="scale-down"
              class="detail-image"


            >
               <template #error>
                 <div class="image-slot" style="display: flex; justify-content: center; align-items: center; height: 100%; background: #f5f7fa; color: #909399;">
                   <span>加载失败</span>
                 </div>
               </template>
            </el-image>
          </div>
        </div>

        <div class="detail-right">
          <el-divider content-position="left">AI 识别与分析结果</el-divider>
          
          <div class="knowledge-tags" style="margin-bottom: 20px;">
             <el-tag 
               v-for="(tag, i) in (currentItem.knowledge || [])" 
               :key="i" 
               type="success" 
               effect="dark"
               style="margin-right: 8px; margin-bottom: 5px;"
             >
               {{ tag.label }}
             </el-tag>
          </div>

          <div class="markdown-body detail-content" v-html="renderTex(currentItem.content)"></div>
        </div>
      </div>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { Refresh, Picture as IconPicture } from '@element-plus/icons-vue'
import { API_V1_BASE_URL } from '../config/api'
import { createQuestionImageLoader } from '../utils/questionImageLoader'
import { renderMarkdown } from '@/utils/renderMarkdown'

const API_BASE = API_V1_BASE_URL

// 与后端约定的列表拉取上限；达到上限时提示“仅显示前 N 条”（真分页另开 issue）。
const historyListLimit = 50

const loading = ref(false)
const list = ref([])
const dialogVisible = ref(false)
const currentItem = ref(null)

// 题目图片经鉴权接口以 blob 方式加载（#44），不再使用公开静态 URL。
const { syncItems, imageUrlFor, dispose: disposeImageLoader } = createQuestionImageLoader()

watch(list, (items) => syncItems(items))

const getImageUrl = (item) => imageUrlFor(item)

const previewSources = computed(() =>
  [imageUrlFor(currentItem.value)].filter(Boolean)
)

onBeforeUnmount(disposeImageLoader)

const fetchHistory = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/history?limit=${historyListLimit}`)
    list.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// 打开详情弹窗
const openDetail = (item) => {
  currentItem.value = item
  dialogVisible.value = true
}

// 工具函数
const renderTex = (text) => text ? renderMarkdown(text) : '<span style="color:#999">暂无内容</span>'

const getPreviewText = (text) => {
  if (!text) return '暂无识别内容'
  // 移除 markdown 符号，只取纯文本做预览
  const clean = text.replace(/[#*`$]/g, '')
  return clean.length > 50 ? clean.slice(0, 50) + '...' : clean
}

const formatTime = (str) => new Date(str).toLocaleString()

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }

/* 列表项样式 */
.list-item-content { display: flex; align-items: center; gap: 20px; padding: 5px 0; }
.thumb-box { width: 100px; height: 80px; cursor: pointer; border-radius: 6px; overflow: hidden; border: 1px solid #eee; }
.thumb-img { width: 100%; height: 100%; transition: transform 0.3s; }
.thumb-box:hover .thumb-img { transform: scale(1.1); }

/* min-width: 0 允许 flex 子项收缩到内容宽度以下，配合 ellipsis 防窄窗口横向溢出 */
.info-box { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; cursor: pointer; }
.meta-row { display: flex; gap: 10px; align-items: center; font-size: 12px; color: #999; }
.preview-text { font-size: 14px; color: #333; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 500px;}

.action-box { min-width: 100px; text-align: right; }

/* 弹窗布局 */
.detail-layout { display: flex; height: 75vh; gap: 30px; }

.limit-alert { margin-bottom: 20px; }

/* 窄屏下详情弹窗改单列，对齐 PaperPanel 的 980px 断点 */
@media (max-width: 980px) {
  .detail-layout {
    flex-direction: column;
    height: auto;
    gap: 20px;
  }
}
/* 左侧容器：负责居中内容 */
.detail-left {
  flex: 1;
  background: #eef2f7; /*稍微改个更高级的背景色*/
  /* 使用 Flex 布局绝对居中 */
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 12px; /* 圆角更大点 */
  overflow: hidden;
  padding: 20px;
  border: 1px solid #dcdfe6;
}
.detail-right { flex: 1; overflow-y: auto; padding-right: 10px; }
/* 图片包裹器：限制最大宽高，但不强制拉伸 */
.image-wrapper {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 🔥 新增：图片本身的样式 🔥 */
.detail-image {
  /* 让图片保持原始比例，最大不超过容器 */
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 70vh; /* 防止图片过高撑破弹窗 */
  
  /* 加个漂亮的阴影和圆角，看起来更清晰立体 */
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  background: white; /* 图片背景设为白，防止透明图很难看 */
}

/* 滚动条美化 */
.detail-right::-webkit-scrollbar { width: 6px; }
.detail-right::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 3px; }

/* 🔥 修改：增大详情页右侧 Markdown 内容的字体 🔥 */
.detail-content {
  font-size: 16px; /* 增大字体 */
  line-height: 1.8; /* 增加行高，提升阅读体验 */
}

/* 图片加载失败的占位符样式 */
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
