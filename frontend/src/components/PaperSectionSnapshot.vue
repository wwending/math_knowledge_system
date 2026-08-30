<template>
  <QuestionDocumentSectionView
    :section="section"
    :section-name="sectionName"
    :empty-text="emptyText"
    :url-for="urlFor"
    :error-for="errorFor"
  />
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, watch } from 'vue'
import axios from 'axios'
import QuestionDocumentSectionView from './QuestionDocumentSectionView.vue'
import { buildPaperItemFigureUrl } from '../config/api'

const props = defineProps({
  paperId: { type: Number, required: true },
  item: { type: Object, required: true },
  sectionName: { type: String, required: true },
  emptyText: { type: String, default: '暂无内容' }
})
const state = reactive({ urls: {}, errors: {} })
let generation = 0
const dispose = () => {
  generation += 1
  Object.values(state.urls).forEach((url) => { if (url) URL.revokeObjectURL(url) })
  state.urls = {}
  state.errors = {}
}
const sync = async () => {
  dispose()
  const current = generation
  const blocks = props.item.section_snapshot?.sections?.[props.sectionName]?.blocks || []
  const figureIds = [...new Set(blocks.flatMap((block) => (block.placements || []).map((placement) => placement.figure_id)))]
  await Promise.all(figureIds.map(async (figureId) => {
    try {
      const response = await axios.get(
        buildPaperItemFigureUrl(props.paperId, props.item.id || props.item.paper_item_id, figureId),
        { responseType: 'blob' }
      )
      if (current !== generation) return
      state.urls[figureId] = URL.createObjectURL(response.data)
    } catch {
      if (current === generation) state.errors[figureId] = '快照配图加载失败'
    }
  }))
}
watch(() => [props.paperId, props.item], sync, { immediate: true, deep: true })
onBeforeUnmount(dispose)
const section = computed(() => props.item.section_snapshot?.sections?.[props.sectionName] || { blocks: [] })
const urlFor = (id) => state.urls[id] || ''
const errorFor = (id) => state.errors[id] || ''
</script>

<style scoped>
:deep(.image-area-canvas) { break-inside: avoid; page-break-inside: avoid; }
</style>
