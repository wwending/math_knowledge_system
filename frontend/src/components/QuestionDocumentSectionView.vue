<template>
  <div class="question-section-view" :data-section="sectionName">
    <el-empty v-if="blocks.length === 0" :description="emptyText" :image-size="72" />
    <template v-else>
      <article v-for="block in blocks" :key="block.id" class="document-block" :data-block-id="block.id" :data-block-kind="block.kind">
        <div v-if="block.kind === 'text'" class="markdown-body text-block" v-html="renderMarkdown(block.markdown || '')"></div>
        <QuestionImageAreaCanvas
          v-else-if="block.kind === 'image_area'"
          :area="block"
          :url-for="urlFor"
          :error-for="errorFor"
        />
      </article>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '@/utils/renderMarkdown'
import QuestionImageAreaCanvas from './QuestionImageAreaCanvas.vue'

const props = defineProps({
  section: { type: Object, default: () => ({ blocks: [] }) },
  sectionName: { type: String, default: '' },
  emptyText: { type: String, default: '暂无内容' },
  urlFor: { type: Function, default: () => '' },
  errorFor: { type: Function, default: () => '' }
})
const blocks = computed(() => Array.isArray(props.section?.blocks) ? props.section.blocks : [])
</script>

<style scoped>
.question-section-view{min-height:180px}.document-block+.document-block{margin-top:16px}.text-block{font-size:16px;line-height:1.8}.text-block:empty{display:none}
</style>
