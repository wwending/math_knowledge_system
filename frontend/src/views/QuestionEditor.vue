<template>
  <main class="question-editor-page">
    <header class="editor-header">
      <div><el-button @click="goBack">返回题库</el-button><strong>题目 #{{ questionId }}</strong><el-tag>Revision {{ revisionNo }}</el-tag><el-tag v-if="dirty" type="warning">未保存</el-tag></div>
      <div><el-button :disabled="!dirty || saving" @click="discard">放弃修改</el-button><el-button type="primary" :loading="saving" :disabled="!canSave" @click="saveDocument">保存整个题目</el-button></div>
    </header>
    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon />
    <el-alert v-if="conflict" title="服务器已有更新；全部本地草稿仍保留。可复制内容，或明确放弃本地修改后加载最新版。" type="warning" :closable="false" show-icon><el-button size="small" @click="reloadLatest">放弃本地并加载最新版</el-button></el-alert>
    <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" show-icon />
    <el-skeleton v-if="loading" :rows="8" animated />
    <template v-else-if="draft">
      <el-radio-group v-model="mobilePane" class="mobile-switch"><el-radio-button value="content">编辑内容</el-radio-button><el-radio-button value="source">查看来源图</el-radio-button></el-radio-group>
      <div class="editor-layout">
        <aside class="source-pane" :class="{ 'mobile-hidden': mobilePane !== 'source' }">
          <h2>题目区域图</h2>
          <el-image v-if="sourceImageUrl" :src="sourceImageUrl" :preview-src-list="[sourceImageUrl]" fit="contain" class="source-image" />
          <el-empty v-else description="暂无来源图" />
        </aside>
        <section class="content-pane" :class="{ 'mobile-hidden': mobilePane !== 'content' }">
          <el-tabs v-model="activeSection">
            <el-tab-pane v-for="section in sectionOptions" :key="section.value" :label="section.label" :name="section.value" />
          </el-tabs>
          <div v-if="activeSection === 'stem'" class="metadata-grid">
            <el-form-item label="知识点"><el-select v-model="tagLabels" multiple filterable allow-create default-first-option /></el-form-item>
            <el-form-item label="题型"><el-select v-model="draft.metadata.question_type" clearable><el-option v-for="item in questionTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
            <el-form-item label="难度"><el-select v-model="draft.metadata.difficulty_level" clearable><el-option label="未设置" :value="null"/><el-option v-for="level in 5" :key="level" :label="`${level} 星`" :value="level" /></el-select></el-form-item>
          </div>
          <el-alert v-if="validation.errors.length" :title="validation.errors[0].message" type="error" :closable="false" show-icon />
          <div class="block-list">
            <article v-for="(block, index) in activeBlocks" :key="block.id" class="block-card">
              <template v-if="block.kind === 'text'">
                <div class="block-head"><strong>文字块 {{ index + 1 }}</strong><small>{{ block.id }}</small></div>
                <el-input :model-value="block.markdown" type="textarea" :autosize="{ minRows: 4, maxRows: 16 }" @update:model-value="updateText(block.id, $event)" />
                <div class="block-actions">
                  <el-button size="small" :disabled="index === 0" @click="move(block.id, index - 1)">上移</el-button><el-button size="small" :disabled="index === activeBlocks.length - 1" @click="move(block.id, index + 1)">下移</el-button>
                  <el-button size="small" :disabled="activeBlocks[index + 1]?.kind !== 'text'" @click="merge(block.id)">与下一块合并</el-button>
                  <el-select v-model="moveTargets[block.id]" size="small" placeholder="移动到区段"><el-option v-for="item in sectionOptions.filter((item) => item.value !== activeSection)" :key="item.value" :label="item.label" :value="item.value" /></el-select><el-button size="small" @click="moveToSection(block.id)">移动</el-button>
                  <el-button size="small" type="danger" plain @click="remove(block.id)">删除</el-button>
                </div>
                <div v-if="safeParagraphs(block.markdown).length > 1" class="paragraph-actions">
                  <el-select v-model="paragraphSelections[block.id]" size="small" placeholder="选择段落">
                    <el-option v-for="paragraph in safeParagraphs(block.markdown)" :key="paragraph.index" :label="`第 ${paragraph.index + 1} 段：${paragraph.excerpt}`" :value="paragraph.index" />
                  </el-select>
                  <el-button size="small" :disabled="paragraphSelections[block.id] >= safeParagraphs(block.markdown).length - 1" @click="split(block.id)">在所选段落后拆分</el-button>
                  <el-select v-model="paragraphMoveTargets[block.id]" size="small" placeholder="段落移动到区段">
                    <el-option v-for="item in sectionOptions.filter((item) => item.value !== activeSection)" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                  <el-button size="small" @click="moveParagraph(block.id)">移动所选段落</el-button>
                </div>
                <div class="markdown-body block-preview" v-html="renderMarkdown(block.markdown)"></div>
              </template>
              <template v-else>
                <el-alert title="图片区（只读）" description="当前版本暂不支持编辑配图布局；保存文字不会改变现有图片区。" type="info" :closable="false" show-icon />
                <p>区域 ID：{{ block.id }}｜高度比例：{{ block.height_ratio }}｜配图：{{ block.placements.length }} 张</p>
              </template>
            </article>
          </div>
          <div v-if="activeBlocks.length === 0" class="empty-section"><el-empty :description="`${sectionLabel}暂无内容`" /></div>
          <div class="add-actions"><el-button type="primary" plain @click="addBlock">添加文字块</el-button><el-button disabled>添加图片区（后续支持）</el-button></div>
        </section>
      </div>
    </template>
  </main>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { API_V1_BASE_URL } from '../config/api'
import { createQuestionImageLoader } from '../utils/questionImageLoader'
import { renderMarkdown } from '@/utils/renderMarkdown'
import { addTextBlock, buildQuestionDocumentPayload, createQuestionDocumentEditorState, deleteTextBlock, editTextBlock, findSafeMarkdownParagraphs, isQuestionDocumentDirty, mergeTextBlockWithNext, moveBlockToSection, moveParagraphToSection, reorderBlock, splitTextBlockAtParagraph, validateQuestionDocumentDraft } from '../utils/questionDocumentEditorState.mjs'
const route = useRoute(); const router = useRouter(); const questionId = computed(() => Number(route.params.id));
const loading=ref(false), saving=ref(false), loadError=ref(''), saveError=ref(''), conflict=ref(false), baseline=ref(null), draft=ref(null), revisionNo=ref(0), activeSection=ref('stem'), mobilePane=ref('content'); let generation=0
const paragraphSelections=reactive({}), paragraphMoveTargets=reactive({}), moveTargets=reactive({}); const sectionOptions=[{value:'stem',label:'题干'},{value:'answer',label:'答案'},{value:'analysis',label:'解析'}]; const questionTypes=[{value:'single_choice',label:'单选题'},{value:'multiple_choice',label:'多选题'},{value:'fill_blank',label:'填空题'},{value:'solution',label:'解答题'},{value:'judge',label:'判断题'},{value:'unknown',label:'未知'}]
const loader=createQuestionImageLoader(); const sourceImageUrl=computed(()=>loader.imageUrlFor(draft.value)); const activeBlocks=computed(()=>draft.value?.sections?.[activeSection.value]?.blocks||[]); const sectionLabel=computed(()=>sectionOptions.find(x=>x.value===activeSection.value)?.label); const dirty=computed(()=>isQuestionDocumentDirty(draft.value,baseline.value)); const validation=computed(()=>validateQuestionDocumentDraft(draft.value)); const canSave=computed(()=>dirty.value&&validation.value.valid&&!saving.value)
const tagLabels=computed({get:()=>draft.value?.metadata.knowledge_tags.map(t=>t.label)||[],set:(values)=>{draft.value.metadata.knowledge_tags=values.map(label=>({label,score:1}))}})
const applyState=(doc)=>{const state=createQuestionDocumentEditorState(doc);baseline.value=state.baseline;draft.value=state.draft;revisionNo.value=doc.current_revision_no;loader.syncItems([doc]);conflict.value=false;saveError.value=''}
const loadDocument=async()=>{if(!Number.isInteger(questionId.value)||questionId.value<=0){loadError.value='题目编号无效';return}const token=++generation;loading.value=true;loadError.value='';try{const res=await axios.get(`${API_V1_BASE_URL}/questions/${questionId.value}/document`);if(token===generation)applyState(res.data)}catch(e){if(token===generation)loadError.value=e.response?.data?.detail||'加载题目失败'}finally{if(token===generation)loading.value=false}}
const updateText=(id,text)=>{draft.value=editTextBlock(draft.value,activeSection.value,id,text).document}; const move=(id,index)=>{draft.value=reorderBlock(draft.value,activeSection.value,id,index).document}; const merge=(id)=>{const r=mergeTextBlockWithNext(draft.value,activeSection.value,id);if(r.error)ElMessage.warning(r.error);else draft.value=r.document}; const remove=async(id)=>{try{await ElMessageBox.confirm('删除这个文字块？','确认',{type:'warning'});const r=deleteTextBlock(draft.value,activeSection.value,id);if(r.error)ElMessage.warning(r.error);else draft.value=r.document}catch{}}; const addBlock=()=>{const r=addTextBlock(draft.value,activeSection.value,{markdown:'请输入内容'});if(r.error)ElMessage.warning(r.error);else draft.value=r.document}; const safeParagraphs=(text)=>findSafeMarkdownParagraphs(text); const split=(id)=>{if(!Number.isInteger(paragraphSelections[id]))return ElMessage.warning('请先选择拆分段落');const r=splitTextBlockAtParagraph(draft.value,activeSection.value,id,paragraphSelections[id]+1);if(r.error)ElMessage.warning(r.error);else draft.value=r.document}; const moveToSection=(id)=>{const target=moveTargets[id];if(!target)return;const r=moveBlockToSection(draft.value,activeSection.value,id,target);if(r.error)ElMessage.warning(r.error);else draft.value=r.document}; const moveParagraph=(id)=>{const target=paragraphMoveTargets[id];if(!target||!Number.isInteger(paragraphSelections[id]))return ElMessage.warning('请选择段落和目标区段');const r=moveParagraphToSection(draft.value,activeSection.value,id,paragraphSelections[id],target);if(r.error)ElMessage.warning(r.error);else draft.value=r.document}
const saveDocument=async()=>{if(!canSave.value)return;saving.value=true;saveError.value='';try{const res=await axios.put(`${API_V1_BASE_URL}/questions/${questionId.value}/document`,buildQuestionDocumentPayload(draft.value,revisionNo.value));applyState(res.data.question);revisionNo.value=res.data.current_revision_no;saving.value=false;ElMessage.success('题目已保存');await router.push({path:'/',query:returnQuery.value})}catch(e){if(e.response?.status===409){conflict.value=true;saveError.value='版本冲突：本地草稿已完整保留。'}else saveError.value=e.response?.data?.detail?.message||e.response?.data?.detail||'保存题目失败'}finally{saving.value=false}}
const confirmDiscard=async()=>{if(!dirty.value)return true;try{await ElMessageBox.confirm('存在未保存修改，确认放弃吗？','未保存的修改',{confirmButtonText:'放弃修改',cancelButtonText:'继续编辑',type:'warning'});return true}catch{return false}}; const discard=async()=>{if(await confirmDiscard())draft.value=JSON.parse(JSON.stringify(baseline.value))}; const reloadLatest=async()=>{if(await confirmDiscard())loadDocument()}; const returnQuery=computed(()=>({tab:'bank',bank_q:route.query.bank_q||undefined,bank_question_id:route.query.bank_question_id||String(questionId.value)})); const goBack=()=>router.push({path:'/',query:returnQuery.value}); const beforeUnload=(e)=>{if(dirty.value){e.preventDefault();e.returnValue=''}}
onBeforeRouteLeave(async()=>saving.value?false:confirmDiscard()); onMounted(()=>{window.addEventListener('beforeunload',beforeUnload);loadDocument()}); onBeforeUnmount(()=>{generation+=1;window.removeEventListener('beforeunload',beforeUnload);loader.dispose()}); watch(()=>route.params.id,loadDocument)
</script>
<style scoped>
.question-editor-page{min-height:100vh;padding:16px;background:#f5f7fa}.editor-header{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px;background:white;border-bottom:1px solid #dcdfe6}.editor-header>div{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.editor-layout{display:grid;grid-template-columns:minmax(300px,40%) minmax(0,1fr);gap:16px;margin-top:16px}.source-pane,.content-pane{min-width:0;padding:16px;background:white;border-radius:10px}.source-pane{max-height:calc(100vh - 100px);overflow:auto}.source-image{width:100%;min-height:260px}.metadata-grid{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px}.block-list{display:flex;flex-direction:column;gap:12px}.block-card{padding:14px;border:1px solid #dcdfe6;border-radius:8px}.block-head,.block-actions,.paragraph-actions,.add-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.block-head{justify-content:space-between}.block-preview{margin-top:12px;padding:12px;background:#f5f7fa}.mobile-switch{display:none;margin-top:12px}.empty-section{padding:12px}@media(max-width:980px){.mobile-switch{display:flex}.editor-layout{display:block}.mobile-hidden{display:none}.metadata-grid{grid-template-columns:1fr}.source-pane,.content-pane{margin-top:12px}.editor-header{position:static}}
</style>
