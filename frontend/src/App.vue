<template>
  <div class="app-container">
    <el-container>
      <el-header class="header">
        <h2>📐 数学题知识点识别系统 (v0.2 NLP版)</h2>
      </el-header>

      <el-main>
        <el-row :gutter="20">
          <el-col :span="10">
            <el-card class="upload-card">
              <template #header>
                <div class="card-header">
                  <span>📸 题目上传</span>
                </div>
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
                <div class="el-upload__text">
                  拖拽图片到这里 或 <em>点击上传</em>
                </div>
              </el-upload>

              <div v-if="previewUrl" class="image-preview">
                <img :src="previewUrl" alt="题目预览" />
              </div>

              <div class="action-area">
                <el-button 
                  type="primary" 
                  size="large" 
                  :loading="loading" 
                  @click="startRecognition" 
                  :disabled="!selectedFile"
                  style="width: 100%;"
                >
                  {{ loading ? '正在 AI 分析中 (OCR + NLP)...' : '开始智能识别' }}
                </el-button>
              </div>
            </el-card>
          </el-col>

          <el-col :span="14">
            <el-card class="result-card">
              <template #header>
                <div class="card-header">
                  <span>📝 识别结果</span>
                  <div class="header-tags">
                     <el-tag v-if="costTime" type="info" size="small">总耗时: {{ costTime }}s</el-tag>
                  </div>
                </div>
              </template>

              <div v-if="knowledgeTags && knowledgeTags.length > 0" class="knowledge-area">
                <p class="section-title">🧠 AI 知识点预测：</p>
                <div class="tags-wrapper">
                  <el-tooltip
                    v-for="(item, index) in knowledgeTags"
                    :key="index"
                    :content="`置信度: ${(item.score * 100).toFixed(1)}%`"
                    placement="top"
                  >
                    <el-tag 
                      :type="index === 0 ? 'success' : 'primary'" 
                      effect="dark"
                      class="k-tag"
                      size="large"
                    >
                      {{ item.label }}
                    </el-tag>
                  </el-tooltip>
                </div>
                <el-divider />
              </div>

              <div v-if="ocrResult" class="result-content">
                <div v-html="renderedContent" class="markdown-body"></div>
              </div>
              <el-empty v-else description="请上传图片，AI 将自动分析知识点" />
              
              <el-collapse v-if="ocrResult" style="margin-top: 20px;">
                <el-collapse-item title="查看原始数据 (JSON)" name="1">
                  <pre class="raw-code">{{ rawResponse }}</pre>
                </el-collapse-item>
              </el-collapse>
            </el-card>
          </el-col>
        </el-row>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import axios from 'axios'
import katex from 'katex'
import 'katex/dist/katex.min.css'

// 状态变量
const selectedFile = ref(null)
const previewUrl = ref('')
const loading = ref(false)
const ocrResult = ref('')
const knowledgeTags = ref([]) // 存储知识点
const costTime = ref(null)
const rawResponse = ref(null)

const handleFileChange = (uploadFile) => {
  selectedFile.value = uploadFile.raw
  previewUrl.value = URL.createObjectURL(uploadFile.raw)
  // 重置状态
  ocrResult.value = ''
  knowledgeTags.value = []
  costTime.value = null
  rawResponse.value = null
}

const startRecognition = async () => {
  if (!selectedFile.value) return

  loading.value = true
  const formData = new FormData()
  formData.append('file', selectedFile.value)

  try {
    const response = await axios.post('http://127.0.0.1:8000/api/v1/recognize', formData)
    
    // 保存原始响应供调试
    rawResponse.value = response.data

    if (response.data.success) {
      ocrResult.value = response.data.content
      costTime.value = response.data.cost_seconds
      // 获取知识点列表
      knowledgeTags.value = response.data.knowledge || []
    } else {
      ocrResult.value = `❌ 识别失败: ${response.data.error}`
    }
  } catch (error) {
    console.error(error)
    ocrResult.value = "❌ 网络错误: 请检查后端服务器是否启动"
  } finally {
    loading.value = false
  }
}

// 渲染逻辑 (保持不变)
const renderedContent = computed(() => {
  if (!ocrResult.value) return ''
  let text = ocrResult.value
  text = text.replace(/\n/g, '<br>')
  try {
     text = text.replace(/\$([^$]+)\$/g, (match, formula) => {
       try {
         return katex.renderToString(formula, { throwOnError: false })
       } catch (e) {
         return match
       }
     })
  } catch (e) {
    console.error("渲染出错", e)
  }
  return text
})
</script>

<style scoped>
.app-container { max-width: 1400px; margin: 0 auto; padding: 20px; }
.header { text-align: center; margin-bottom: 20px; border-bottom: 1px solid #eee; }
.upload-card, .result-card { height: 85vh; overflow-y: auto; display: flex; flex-direction: column; }
.image-preview img { max-width: 100%; max-height: 400px; margin-top: 20px; border: 1px dashed #ccc; display: block; margin: 20px auto; }
.action-area { margin-top: 20px; padding: 0 20px; }
.result-content { font-size: 16px; line-height: 1.8; color: #333; padding: 10px; }
.raw-code { background: #f4f4f4; padding: 10px; font-size: 12px; white-space: pre-wrap; color: #666; }

/* 知识点样式 */
.knowledge-area { background: #f0f9eb; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
.section-title { font-weight: bold; margin-bottom: 10px; color: #529b2e; }
.tags-wrapper { display: flex; gap: 10px; flex-wrap: wrap; }
.k-tag { font-size: 14px; padding: 8px 15px; }
</style>