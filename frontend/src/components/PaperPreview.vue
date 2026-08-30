<template>
  <div class="preview-shell">
    <div class="preview-toolbar">
      <div>
        <strong>作业预览</strong>
        <span>{{ renderModel.paper.item_count }} 题 / {{ renderModel.paper.total_score }} 分</span>
      </div>
      <div class="preview-actions">
        <el-tag size="small" effect="plain">{{ formatTemplateType(renderModel.template_type) }}</el-tag>
        <el-button
          type="primary"
          size="small"
          :loading="downloadLoading"
          :disabled="downloadLoading || hasUnsavedChanges"
          @click="handleExportPdf"
        >
          <el-icon><Printer /></el-icon>
          <span>打印/导出 PDF</span>
        </el-button>
        <span v-if="hasUnsavedChanges" class="unsaved-export-hint">请先保存修改后再导出 PDF</span>
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
          <PaperSectionSnapshot v-if="item.section_snapshot" :paper-id="renderModel.paper.id" :item="item" section-name="stem" class="question-content" />
          <div v-else class="markdown-body question-content" v-html="renderContent(item.content)"></div>
          <img
            v-if="figureUrlFor(item)"
            class="question-figure"
            :src="figureUrlFor(item)"
            :alt="`第${item.display_number}题配图`"
          >

          <section v-if="renderModel.layout.show_answers && sectionHasContent(item, 'answer')" class="answer-section"><h3>答案</h3><PaperSectionSnapshot v-if="item.section_snapshot" :paper-id="renderModel.paper.id" :item="item" section-name="answer"/><div v-else v-html="renderContent(item.answer)"></div></section>
          <section v-if="renderModel.layout.show_analysis && sectionHasContent(item, 'analysis')" class="analysis-section"><h3>解析</h3><PaperSectionSnapshot v-if="item.section_snapshot" :paper-id="renderModel.paper.id" :item="item" section-name="analysis"/><div v-else v-html="renderContent(item.analysis)"></div></section>

          <div
            v-if="item.knowledge_tags.length > 0 || item.answer_area"
            :class="{ 'question-tail': item.answer_area }"
          >
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

            <div
              v-if="item.answer_area"
              class="answer-area"
              :style="{ height: `${item.answer_area.height_mm}mm` }"
            ></div>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Printer } from '@element-plus/icons-vue'
import { renderMarkdown } from '@/utils/renderMarkdown'
import { createPaperFigureImageLoader } from '@/utils/paperFigureImageLoader'
import { API_V1_BASE_URL } from '../config/api'
import PaperSectionSnapshot from './PaperSectionSnapshot.vue'

const props = defineProps({
  renderModel: {
    type: Object,
    required: true
  },
  hasUnsavedChanges: { type: Boolean, default: false }
})

// Figures frozen in the paper items arrive via authenticated blob prefetch (#59);
// object URLs are released when the preview unmounts or items disappear.
const figureLoader = createPaperFigureImageLoader()
const { figureUrlFor } = figureLoader

watch(
  () => props.renderModel,
  (model) => figureLoader.syncRenderModel(model),
  { immediate: true }
)

onBeforeUnmount(() => figureLoader.dispose())

const downloadLoading = ref(false)

// #77: 模板类型做中文映射，未知类型回退显示原始值。
const templateTypeLabels = { homework: '作业' }
const formatTemplateType = (templateType) => templateTypeLabels[templateType] || templateType

const renderContent = (content) => content ? renderMarkdown(content) : '<span style="color:#767676">暂无内容</span>'
const sectionHasContent = (item, name) => item.section_snapshot
  ? (item.section_snapshot.sections?.[name]?.blocks?.length || 0) > 0
  : Boolean(item[name])

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
  if (props.hasUnsavedChanges) return ElMessage.warning('请先保存修改后再导出 PDF')
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
.unsaved-export-hint { color: #b45309; }

.a4-page {
  width: min(100%, 794px);
  min-height: 1123px;
  margin: 0 auto;
  padding: 18mm 16mm;
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
.answer-section, .analysis-section { margin-top: 12px; }
.answer-section h3, .analysis-section h3 { margin: 0 0 6px; font-size: 15px; }

.question-content > :last-child {
  break-after: avoid;
  page-break-after: avoid;
}

.question-figure {
  display: block;
  max-width: 100%;
  height: auto;
  margin-top: 8px;
  break-inside: avoid;
  page-break-inside: avoid;
}

.preview-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.question-tail {
  break-before: avoid;
  page-break-before: avoid;
  break-inside: avoid;
  page-break-inside: avoid;
}

.answer-area {
  margin-top: 4mm;
  break-inside: avoid;
  page-break-inside: avoid;
  background: #fff;
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
