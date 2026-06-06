<template>
  <div class="preview-shell">
    <div class="preview-toolbar">
      <div>
        <strong>作业预览</strong>
        <span>{{ renderModel.paper.item_count }} 题 / {{ renderModel.paper.total_score }} 分</span>
      </div>
      <el-tag size="small" effect="plain">{{ renderModel.template_type }}</el-tag>
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
import { renderMarkdown } from '@/utils/renderMarkdown'

defineProps({
  renderModel: {
    type: Object,
    required: true
  }
})

const renderContent = (content) => content ? renderMarkdown(content) : '<span style="color:#999">暂无内容</span>'
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
</style>
