<template>
  <div class="app-container">
    <el-container>
      <el-header class="header">
        <h2>📐 数学题知识点识别系统 (Dev)</h2>
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
                  {{ loading ? '正在 AI 识别中...' : '开始识别' }}
                </el-button>
              </div>
            </el-card>
          </el-col>

          <el-col :span="14">
            <el-card class="result-card">
              <template #header>
                <div class="card-header">
                  <span>📝 识别结果 (Markdown + LaTeX)</span>
                  <el-tag v-if="costTime" type="success" size="small">耗时: {{ costTime }}s</el-tag>
                </div>
              </template>

              <div v-if="ocrResult" class="result-content">
                <div v-html="renderedContent" class="markdown-body"></div>
              </div>
              <el-empty v-else description="请上传图片并点击开始识别" />
              
              <el-collapse v-if="ocrResult" style="margin-top: 20px;">
                <el-collapse-item title="查看原始 Markdown 代码" name="1">
                  <pre class="raw-code">{{ ocrResult }}</pre>
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
// 引入 katex 的样式，否则公式会乱码
import 'katex/dist/katex.min.css'

// 状态变量
const selectedFile = ref(null)
const previewUrl = ref('')
const loading = ref(false)
const ocrResult = ref('')
const costTime = ref(null)

// 处理文件选择
const handleFileChange = (uploadFile) => {
  selectedFile.value = uploadFile.raw
  previewUrl.value = URL.createObjectURL(uploadFile.raw)
  ocrResult.value = '' // 清空旧结果
  costTime.value = null
}

// 核心：调用后端 API
const startRecognition = async () => {
  if (!selectedFile.value) return

  loading.value = true
  const formData = new FormData()
  formData.append('file', selectedFile.value)

  try {
    // 发送请求到 FastAPI 后端 (确保后端端口是 8000)
    const response = await axios.post('http://127.0.0.1:8000/api/v1/recognize', formData)
    
    if (response.data.success) {
      ocrResult.value = response.data.content
      costTime.value = response.data.cost_seconds
    } else {
      ocrResult.value = `❌ 识别失败: ${response.data.error}`
    }
  } catch (error) {
    console.error(error)
    ocrResult.value = "❌ 网络错误: 请检查后端服务器(port 8000)是否启动？"
  } finally {
    loading.value = false
  }
}

// LaTeX 渲染逻辑
const renderedContent = computed(() => {
  if (!ocrResult.value) return ''
  
  let text = ocrResult.value
  
  // 1. 简单换行处理
  text = text.replace(/\n/g, '<br>')

  // 2. 渲染公式：这里处理 $...$ 和 $$...$$
  // 注意：这是演示用的简单正则，生产环境建议用 markdown-it-texmath
  try {
     // 替换 $...$
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
.app-container {
  max-width: 1400px; /* 宽一点 */
  margin: 0 auto;
  padding: 20px;
}
.header {
  text-align: center;
  margin-bottom: 20px;
  border-bottom: 1px solid #eee;
}
.upload-card, .result-card {
  height: 80vh; /* 占屏幕高度的 80% */
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.image-preview img {
  max-width: 100%;
  max-height: 400px;
  margin-top: 20px;
  border: 1px dashed #ccc;
  display: block;
  margin-left: auto;
  margin-right: auto;
}
.action-area {
  margin-top: 20px;
  padding: 0 20px;
}
.result-content {
  font-size: 16px;
  line-height: 1.8;
  color: #333;
  padding: 10px;
}
.raw-code {
  background: #f4f4f4;
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
  white-space: pre-wrap;
  color: #666;
}
/* 调整 KaTeX 字体大小 */
:deep(.katex) {
  font-size: 1.1em; 
}
</style>