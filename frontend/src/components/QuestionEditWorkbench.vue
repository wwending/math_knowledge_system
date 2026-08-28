<template>
  <div class="question-editor-pane">
    <div class="editor-fields">
      <el-form label-position="top">
        <el-form-item label="题干"><el-input v-model="draft.content" type="textarea" :rows="5" /></el-form-item>
        <el-form-item label="答案"><el-input v-model="draft.answer" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="解析"><el-input v-model="draft.analysis" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="知识点标签"><el-select v-model="draft.knowledge_tags" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item>
        <el-form-item label="题型"><el-select v-model="draft.question_type" style="width:100%"><el-option v-for="item in questionTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
        <el-form-item label="难度"><el-rate v-model="draft.difficulty_level" :max="5" /></el-form-item>
      </el-form>
      <div class="actions">
        <el-button type="primary" :loading="saving" :disabled="!dirty" @click="save">保存修改</el-button>
        <el-button @click="discard">放弃修改</el-button>
      </div>
    </div>
    <p class="preview-hint">下方题目内容、答案和解析会实时显示当前草稿。</p>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { API_V1_BASE_URL } from '../config/api'

const props = defineProps({ question: { type: Object, required: true } })
const emit = defineEmits(['saved', 'draft-change'])
const saving = ref(false)
const baseline = ref(null)
const draft = ref(null)
const questionTypes = [
  { value: 'single_choice', label: '单选题' },
  { value: 'multiple_choice', label: '多选题' },
  { value: 'fill_blank', label: '填空题' },
  { value: 'solution', label: '解答题' },
  { value: 'judge', label: '判断题' },
  { value: 'unknown', label: '未知' }
]

const normalize = (q) => ({
  content: q.content || '',
  answer: q.answer || '',
  analysis: q.analysis || '',
  knowledge_tags: (q.knowledge_tags || []).map((x) => typeof x === 'string' ? x : x.label).filter(Boolean),
  question_type: q.question_type || 'unknown',
  difficulty_level: Number(q.difficulty_level) || 0
})
const clone = (value) => JSON.parse(JSON.stringify(value))
const emitDraft = () => emit('draft-change', clone(draft.value))
const reset = () => {
  draft.value = normalize(props.question)
  baseline.value = clone(draft.value)
  emitDraft()
}
watch(() => props.question, reset, { immediate: true, deep: true })
watch(draft, emitDraft, { deep: true })
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(baseline.value))

const discard = async () => {
  if (!dirty.value) return reset()
  try {
    await ElMessageBox.confirm('放弃未保存的修改？', '确认', { type: 'warning' })
    reset()
  } catch {}
}

const save = async () => {
  if (!dirty.value || saving.value) return
  saving.value = true
  try {
    const payload = { ...draft.value, expected_revision_no: props.question.current_revision_no }
    const res = await axios.put(`${API_V1_BASE_URL}/questions/${props.question.id}`, payload)
    const body = res.data || {}
    const fresh = body.question || body
    const revision = body.current_revision_no ?? fresh.current_revision_no
    baseline.value = clone({ ...draft.value, ...normalize(fresh) })
    draft.value = clone(baseline.value)
    emit('saved', { question: fresh, current_revision_no: revision })
    emitDraft()
    ElMessage.success('题目已保存')
  } catch (error) {
    if (error.response?.status === 409) ElMessage.error('题目已被其他修改更新，请保留草稿后刷新版本')
    else ElMessage.error(error.response?.data?.detail || '保存题目失败')
  } finally {
    saving.value = false
  }
}
</script>
<style scoped>
.question-editor-pane { min-width: 0; }
.editor-fields { min-width: 0; }
.actions { display: flex; gap: 10px; }
.preview-hint { margin: 12px 0 0; color: #909399; font-size: 12px; }
</style>
