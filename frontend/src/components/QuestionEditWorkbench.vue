<template>
  <div class="question-workbench">
    <div class="workbench-tabs" role="tablist">
      <el-button v-for="tab in tabs" :key="tab" :type="activeTab === tab ? 'primary' : 'default'" @click="activeTab = tab">{{ tab }}</el-button>
    </div>
    <section :class="['question-image-pane', { 'mobile-hidden': activeTab !== '原图' }]">
      <el-image :src="imageUrl" fit="contain" class="question-region-image" :preview-src-list="imageUrl ? [imageUrl] : []" />
      <div v-if="!imageUrl" class="empty-image">暂无题目区域图</div>
    </section>
    <section :class="['question-editor-pane', { 'mobile-hidden': activeTab === '原图' }]">
      <div class="editor-fields">
        <el-form label-position="top">
          <el-form-item label="题干"><el-input v-model="draft.content" type="textarea" :rows="5" /></el-form-item>
          <el-form-item label="答案"><el-input v-model="draft.answer" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="解析"><el-input v-model="draft.analysis" type="textarea" :rows="3" /></el-form-item>
          <el-form-item label="知识点标签"><el-select v-model="draft.knowledge_tags" multiple filterable allow-create default-first-option style="width:100%" /></el-form-item>
          <el-form-item label="题型"><el-select v-model="draft.question_type" style="width:100%"><el-option v-for="item in questionTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item label="难度"><el-rate v-model="draft.difficulty_level" :max="5" /></el-form-item>
        </el-form>
        <el-button v-if="activeTab === '编辑'" type="primary" :loading="saving" :disabled="!dirty" @click="save">保存修改</el-button>
        <el-button v-if="activeTab === '编辑'" @click="discard">放弃修改</el-button>
      </div>
      <div :class="['preview-pane', { 'mobile-hidden': activeTab !== '预览' }]">
        <h4>题干预览</h4><div class="markdown-body" v-html="render(draft.content)" />
        <h4>答案预览</h4><div class="markdown-body" v-html="render(draft.answer)" />
        <h4>解析预览</h4><div class="markdown-body" v-html="render(draft.analysis)" />
      </div>
    </section>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { renderMarkdown } from '@/utils/renderMarkdown'
import { API_V1_BASE_URL } from '../config/api'
const props = defineProps({ question: { type: Object, required: true }, imageUrl: { type: String, default: '' } })
const emit = defineEmits(['saved'])
const tabs = ['原图', '编辑', '预览']
const activeTab = ref('编辑')
const saving = ref(false)
const baseline = ref(null)
const draft = ref(null)
const questionTypes = [{ value: 'single_choice', label: '单选题' }, { value: 'multiple_choice', label: '多选题' }, { value: 'fill_blank', label: '填空题' }, { value: 'solution', label: '解答题' }, { value: 'judge', label: '判断题' }, { value: 'unknown', label: '未知' }]
const normalize = (q) => ({ content: q.content || '', answer: q.answer || '', analysis: q.analysis || '', knowledge_tags: (q.knowledge_tags || []).map((x) => typeof x === 'string' ? x : x.label).filter(Boolean), question_type: q.question_type || 'unknown', difficulty_level: Number(q.difficulty_level) || 0 })
const reset = () => { draft.value = normalize(props.question); baseline.value = JSON.parse(JSON.stringify(draft.value)) }
watch(() => props.question, reset, { immediate: true, deep: true })
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(baseline.value))
const render = (value) => value ? renderMarkdown(value) : '<span class="empty-text">暂无内容</span>'
const discard = async () => { if (!dirty.value) return reset(); try { await ElMessageBox.confirm('放弃未保存的修改？', '确认', { type: 'warning' }); reset() } catch {} }
const save = async () => { if (!dirty.value || saving.value) return; saving.value = true; try { const payload = { ...draft.value, expected_revision_no: props.question.current_revision_no }; const res = await axios.put(`${API_V1_BASE_URL}/questions/${props.question.id}`, payload); const body = res.data || {}; const fresh = body.question || body; baseline.value = JSON.parse(JSON.stringify({ ...draft.value, ...normalize(fresh), current_revision_no: body.current_revision_no ?? fresh.current_revision_no })); draft.value = JSON.parse(JSON.stringify(baseline.value)); emit('saved', fresh); ElMessage.success('题目已保存') } catch (error) { if (error.response?.status === 409) ElMessage.error('题目已被其他修改更新，请保留草稿后刷新版本'); else ElMessage.error(error.response?.data?.detail || '保存题目失败') } finally { saving.value = false } }
</script>
<style scoped>
.question-workbench { display:grid; grid-template-columns:minmax(240px, .9fr) minmax(320px, 1.1fr); gap:20px; min-height:520px }
.question-image-pane { min-height:420px; display:flex; align-items:center; justify-content:center; background:#f5f7fa; border-radius:8px; padding:12px }
.question-region-image { width:100%; height:480px }
.question-editor-pane { min-width:0; display:grid; grid-template-rows:1fr auto; overflow:auto }
.mobile-hidden { display:block }
@media (min-width: 761px) { .question-workbench > .workbench-tabs { display:none } .question-editor-pane .mobile-hidden { display:block } }
.editor-fields { min-width:0 }
.preview-pane { border-top:1px solid #dcdfe6; padding-top:12px; max-height:220px; overflow:auto }
.workbench-tabs { display:none }
@media (max-width: 760px) { .mobile-hidden { display:none } .question-workbench { display:block } .workbench-tabs { display:flex; gap:8px; margin-bottom:12px } .question-image-pane { min-height:300px } .question-region-image { height:300px } }
</style>
