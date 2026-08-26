<template>
  <section class="batch-review" aria-labelledby="batch-review-title">
    <div class="batch-review-head">
      <div><h3 id="batch-review-title">分题识别结果</h3><p>每道题可独立核对原图、编辑、重试或保存；失败不会影响其他题目。</p></div>
      <el-button @click="$emit('back')">返回分题框选</el-button>
    </div>
    <div class="batch-summary" aria-live="polite">{{ summary }}</div>
    <article v-for="job in jobs" :key="job.id" class="batch-card">
      <header><h4>第 {{ job.number }} 题</h4><el-tag :type="tagType(job.status)">{{ statusText(job.status) }}</el-tag></header>
      <el-alert v-if="job.error" :title="job.error" type="error" :closable="false" show-icon />
      <el-alert v-if="job.warning" :title="job.warning" type="warning" :closable="false" show-icon />
      <div v-if="isBusy(job.status)" v-loading="true" class="batch-loading" aria-live="polite">正在处理第 {{ job.number }} 题…</div>
      <template v-else-if="job.status === 'draft_ready' || job.status === 'saved_to_bank'">
        <div class="batch-result-grid">
          <aside class="batch-reference">
            <h5>本题原图</h5>
            <div v-loading="imageState(job).loading" class="batch-image-wrap">
              <figure-overlay-editor
                v-if="job.detectedFigures?.length > 0 && imageState(job).url"
                :model-value="job.confirmedFigureBbox"
                :image-url="imageState(job).url"
                :initial-boxes="job.detectedFigures"
                @update:model-value="$emit('update-figure', job, $event)"
              />
              <el-image v-else-if="imageState(job).url" :src="imageState(job).url" :preview-src-list="[imageState(job).url]" fit="scale-down" class="batch-reference-image" />
              <div v-else-if="imageState(job).error" class="image-error">原图加载失败，仍可编辑或重试。</div>
            </div>
          </aside>
          <div class="batch-content">
            <el-input v-if="job.editing" :model-value="job.editContent" type="textarea" :autosize="{ minRows: 6, maxRows: 18 }" :disabled="job.saving" :aria-label="`第 ${job.number} 题编辑内容`" @update:model-value="$emit('update-content', job, $event)" />
            <div v-else class="markdown-body" v-html="renderMarkdown(job.content)"></div>
          </div>
        </div>
        <div class="batch-actions">
          <template v-if="job.status === 'draft_ready'">
            <el-button v-if="!job.editing" :disabled="job.saving" @click="$emit('edit', job)">编辑</el-button>
            <el-button v-else :disabled="job.saving" @click="$emit('cancel-edit', job)">取消修改</el-button>
            <el-button v-if="job.editing" type="primary" :loading="job.saving" @click="$emit('save-edit', job)">保存修改</el-button>
            <el-button v-else type="success" :loading="job.saving" @click="$emit('save-bank', job)">保存入题库</el-button>
          </template>
          <span v-else>已保存至题库<span v-if="job.saveResult?.question_id">（编号 {{ job.saveResult.question_id }}）</span></span>
        </div>
      </template>
      <div v-else-if="job.status === 'failed'" class="batch-actions"><el-button type="primary" @click="$emit('retry', job)">重试此题</el-button></div>
    </article>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, watch } from 'vue'
import axios from 'axios'
import { renderMarkdown } from '@/utils/renderMarkdown'
import { buildDraftImageUrl } from '../config/api'
import FigureOverlayEditor from './FigureOverlayEditor.vue'

const props = defineProps({ jobs: { type: Array, required: true } })
defineEmits(['back', 'retry', 'edit', 'cancel-edit', 'update-content', 'update-figure', 'save-edit', 'save-bank'])
const images = reactive(new Map())
let imageRequestGeneration = 0
const emptyImageState = { url: '', loading: false, error: false }
const imageState = (job) => images.get(job.id) || emptyImageState
const revokeImage = (state) => { if (state?.url) URL.revokeObjectURL(state.url) }
const loadDraftImage = async (job, generation) => {
  if (!job.draftId || images.get(job.id)?.url || images.get(job.id)?.loading) return
  images.set(job.id, { url: '', loading: true, error: false })
  try {
    const response = await axios.get(buildDraftImageUrl(job.draftId), { responseType: 'blob' })
    if (generation !== imageRequestGeneration) return
    images.set(job.id, { url: URL.createObjectURL(response.data), loading: false, error: false })
  } catch (error) {
    if (generation === imageRequestGeneration) images.set(job.id, { url: '', loading: false, error: true })
    console.warn('Failed to load batch Draft image.', error)
  }
}
watch(() => props.jobs.map((job) => `${job.id}:${job.draftId || ''}:${job.status}`).join('|'), () => {
  const generation = imageRequestGeneration
  const activeIds = new Set(props.jobs.map((job) => job.id))
  for (const [id, state] of images) { if (!activeIds.has(id)) { revokeImage(state); images.delete(id) } }
  props.jobs.filter((job) => job.draftId && ['draft_ready', 'saved_to_bank'].includes(job.status)).forEach((job) => loadDraftImage(job, generation))
}, { immediate: true })
onBeforeUnmount(() => { imageRequestGeneration += 1; for (const state of images.values()) revokeImage(state); images.clear() })

const isBusy = (status) => ['queued', 'creating_draft', 'recognizing', 'reconciling'].includes(status)
const statusText = (status) => ({ queued: '等待中', creating_draft: '创建草稿', recognizing: '识别中', reconciling: '核对状态', draft_ready: '待确认', failed: '失败', saved_to_bank: '已入库' }[status] || status)
const tagType = (status) => status === 'saved_to_bank' ? 'success' : status === 'failed' ? 'danger' : status === 'draft_ready' ? 'warning' : 'info'
const summary = computed(() => `共 ${props.jobs.length} 题，已就绪 ${props.jobs.filter((job) => job.status === 'draft_ready').length} 题，已入库 ${props.jobs.filter((job) => job.status === 'saved_to_bank').length} 题，失败 ${props.jobs.filter((job) => job.status === 'failed').length} 题。`)
</script>

<style scoped>
.batch-review { display: flex; flex-direction: column; gap: 14px; }
.batch-review-head, .batch-card header, .batch-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
h3, h4, h5, p { margin: 0; } p { margin-top: 6px; color: var(--el-text-color-secondary); }
.batch-summary { color: var(--el-text-color-regular); }
.batch-card { display: flex; flex-direction: column; gap: 12px; padding: 16px; border: 1px solid var(--el-border-color); border-radius: 12px; background: var(--el-fill-color-blank); }
.batch-loading { min-height: 110px; display: grid; place-items: center; color: var(--el-text-color-secondary); }
.batch-result-grid { display: grid; grid-template-columns: minmax(260px, 38%) minmax(0, 1fr); gap: 16px; align-items: start; }
.batch-reference, .batch-content { min-width: 0; }
.batch-reference { display: flex; flex-direction: column; gap: 8px; }
.batch-image-wrap { min-height: 140px; max-height: 52vh; overflow: auto; border: 1px solid var(--el-border-color); border-radius: 8px; background: var(--el-fill-color-light); }
.batch-reference-image { display: block; width: 100%; }
.image-error { padding: 20px; color: var(--el-text-color-secondary); text-align: center; }
.markdown-body { padding: 12px; border-radius: 8px; background: var(--el-fill-color-light); }
@media (max-width: 860px) { .batch-result-grid { grid-template-columns: 1fr; } }
</style>
