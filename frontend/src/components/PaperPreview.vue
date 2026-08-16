<template>
  <div class="preview-shell">
    <div class="preview-toolbar">
      <div>
        <strong>作业预览</strong>
        <span>{{ renderModel.paper.item_count }} 题 / {{ renderModel.paper.total_score }} 分</span>
      </div>
      <div class="preview-actions">
        <el-tag size="small" effect="plain">{{ renderModel.template_type }}</el-tag>
        <el-button
          type="primary"
          size="small"
          :loading="downloadLoading"
          :disabled="downloadLoading"
          @click="handleExportPdf"
        >
          <el-icon><Printer /></el-icon>
          <span>打印/导出 PDF</span>
        </el-button>
      </div>
    </div>

    <div class="a4-page">
      <header class="paper-header">
        <h1>{{ renderModel.paper.title }}</h1>
        <p v-if="renderModel.paper.description">{{ renderModel.paper.description }}</p>
        <div class="student-line">
          <span>姓名：__________</span>
          <span>班级：__________</span>
          <span>日期：__________</span>
        </div>
      </header>

      <section
        v-for="section in renderModel.sections"
        :key="section.key"
        class="preview-section"
      >
        <h2>{{ section.title }}</h2>

        <article
          v-for="item in section.items"
          :key="item.paper_item_id"
          class="preview-item"
        >
          <div class="question-heading">
            <span>{{ item.display_number }}.</span>
            <span v-if="item.score !== null && item.score !== undefined">（{{ item.score }} 分）</span>
          </div>
          <div class="markdown-body question-content" v-html="renderContent(item.content)"></div>

          <div v-if="item.knowledge_tags.length > 0" class="preview-tags">
            <el-tag
              v-for="tag in item.knowledge_tags"
              :key="tag.label"
              size="small"
              type="info"
              effect="plain"
            >
              {{ tag.label }}
            </el-tag>
          </div>

          <div v-if="item.answer_area" class="answer-lines">
            <div
              v-for="line in item.answer_area.lines"
              :key="line"
              class="answer-line"
            ></div>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Printer } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/renderMarkdown'
import { API_V1_BASE_URL } from '../config/api'

const props = defineProps({
  renderModel: {
    type: Object,
    required: true
  }
})

const downloadLoading = ref(false)

const renderContent = (content) => content ? renderMarkdown(content) : '<span style="color:#999">暂无内容</span>'

const downloadFilename = (contentDisposition) => {
  const encoded = contentDisposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) {
    try {
      return decodeURIComponent(encoded)
    } catch {
      // Fall through to the server's ASCII-safe fallback.
    }
  }
  return contentDisposition?.match(/filename="([^"]+)"/i)?.[1] || `paper-${props.renderModel.paper.id}.pdf`
}

const handleExportPdf = async () => {
  if (downloadLoading.value) return
  downloadLoading.value = true
  let objectUrl = ''
  let downloadLink = null
  try {
    const response = await axios.post(
      `${API_V1_BASE_URL}/papers/${props.renderModel.paper.id}/pdf`,
      {
        template_type: props.renderModel.template_type,
        version: props.renderModel.version,
        paper_size: props.renderModel.paper_size,
        group_by: props.renderModel.group_by,
        sort_by: props.renderModel.sort_by,
        answer_area_mode: props.renderModel.answer_area_mode
      },
      { responseType: 'blob' }
    )
    const pdfBlob = response.data instanceof Blob
      ? response.data
      : new Blob([response.data], { type: 'application/pdf' })
    objectUrl = URL.createObjectURL(pdfBlob)
    downloadLink = document.createElement('a')
    downloadLink.href = objectUrl
    downloadLink.download = downloadFilename(response.headers?.['content-disposition'])
    document.body.appendChild(downloadLink)
    downloadLink.click()
    ElMessage.success('PDF 已生成并开始下载。')
  } catch (error) {
    console.error(error)
    const detail = error.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '导出 PDF 失败，请稍后重试。')
  } finally {
    downloadLink?.remove()
    if (objectUrl) URL.revokeObjectURL(objectUrl)
    downloadLoading.value = false
  }
}
</script>

<style scoped>
.preview-shell {
  margin-top: 18px;
}

.preview-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
  color: #536471;
  font-size: 13px;
}

.preview-toolbar strong {
  margin-right: 10px;
  color: #1f3442;
  font-size: 15px;
}

.preview-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.a4-page {
  width: min(100%, 794px);
  min-height: 1123px;
  margin: 0 auto;
  padding: 48px 56px;
  background: #fff;
  border: 1px solid #d9e2df;
  box-shadow: 0 8px 24px rgba(31, 52, 66, 0.08);
  color: #1f2933;
  box-sizing: border-box;
}

.paper-header {
  text-align: center;
  border-bottom: 1px solid #d8e2de;
  padding-bottom: 18px;
  margin-bottom: 24px;
}

.paper-header h1 {
  margin: 0 0 10px;
  font-size: 24px;
  font-weight: 700;
}

.paper-header p {
  margin: 0 0 14px;
  color: #64727a;
  line-height: 1.7;
}

.student-line {
  display: flex;
  justify-content: center;
  gap: 28px;
  flex-wrap: wrap;
  color: #334155;
  font-size: 14px;
}

.preview-section {
  margin-top: 24px;
}

.preview-section h2 {
  margin: 0 0 14px;
  font-size: 18px;
  border-left: 4px solid #409eff;
  padding-left: 10px;
}

.preview-item {
  margin-bottom: 22px;
}

.question-heading {
  display: flex;
  gap: 6px;
  align-items: baseline;
  font-weight: 700;
  margin-bottom: 8px;
}

.question-content {
  font-size: 15px;
  line-height: 1.85;
}

.preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.answer-lines {
  margin-top: 14px;
}

.answer-line {
  height: 28px;
  border-bottom: 1px solid #cbd5df;
}

@media (max-width: 840px) {
  .a4-page {
    min-height: 0;
    padding: 28px 22px;
  }

  .student-line {
    justify-content: flex-start;
    gap: 12px;
  }
}

@media print {
  @page {
    size: A4;
    margin: 0;
  }

  .preview-toolbar,
  :global(.paper-container .header-row),
  :global(.paper-list),
  :global(.detail-header),
  :global(.preview-controls),
  :global(.paper-items),
  :global(.el-menu),
  :global(.el-aside),
  :global(.el-header) {
    display: none !important;
  }

  .preview-shell {
    margin-top: 0;
  }

  :global(.paper-layout),
  :global(.paper-detail) {
    display: block !important;
    border: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    background: #fff !important;
  }

  .a4-page {
    width: 210mm;
    min-height: 297mm;
    margin: 0;
    padding: 18mm;
    border: 0;
    box-shadow: none;
  }
}
</style>
