import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dashboardPath = resolve(process.cwd(), 'src/views/Dashboard.vue')
const source = readFileSync(dashboardPath, 'utf8')
const failures = []

const requireMatch = (pattern, message) => {
  if (!pattern.test(source)) {
    failures.push(message)
  }
}

requireMatch(/const editMode = ref\(false\)/, 'Dashboard must track edit mode')
requireMatch(/const editContent = ref\(''\)/, 'Dashboard must track editable content')
requireMatch(/const editSaving = ref\(false\)/, 'Dashboard must track edit save progress')
requireMatch(/draftStatus === 'draft_ready' && !editMode[\s\S]*编辑识别结果/, 'draft_ready must offer manual editing')
requireMatch(/<el-input[\s\S]*v-model="editContent"[\s\S]*type="textarea"/, 'manual editor must use a textarea')
if (/contenteditable(?:=|\s)/i.test(source)) {
  failures.push('manual editor must not use contenteditable HTML')
}
requireMatch(/axios\.patch\(`\$\{API_V1_BASE_URL\}\/drafts\/\$\{draftId\.value\}`,[\s\S]*content: editContent\.value/, 'manual edit must PATCH the Draft content field')
requireMatch(/applyDraftDetail\(response\.data \|\| \{\}\)/, 'PATCH success must apply the server DraftDetail')
requireMatch(/const applyDraftDetail = \(payload\) => \{[\s\S]*ocrResult\.value = getDraftContent\(payload\)[\s\S]*qualityWarnings\.value = getQualityWarnings\(payload\)/, 'server content and quality warnings must refresh together')
requireMatch(/@click="cancelEdit">取消修改/, 'edit mode must provide cancel')
requireMatch(/@click="saveDraftEdit">[\s\S]*保存修改/, 'edit mode must provide save')
requireMatch(/distinguishCancelAndClose: true/, 'risk confirmation must distinguish cancel from close')
requireMatch(/catch \(action\) \{[\s\S]*action === 'cancel'[\s\S]*enterEditMode\(\)/, 'Return to edit must enter edit mode')
requireMatch(/const canSaveDraft = computed\([\s\S]*!editMode\.value/, 'edit mode must disable save-to-bank')
requireMatch(/draftStatus === 'draft_ready' && !editMode/, 'edit mode must hide the save-to-bank action area')
requireMatch(/const resetDraftState = \(\) => \{[\s\S]*editMode\.value = false[\s\S]*editContent\.value = ''[\s\S]*editSaving\.value = false/, 'Draft reset must clear edit state')
requireMatch(/const resetUpload = \(\) => \{[\s\S]*resetDraftState\(\)/, 'upload reset must reset Draft edit state')
requireMatch(/renderedEditPreview = computed\(\(\) => \(editContent\.value \? renderMarkdown\(editContent\.value\)/, 'manual preview must use the safe Markdown renderer')

if (failures.length > 0) {
  console.error('Draft manual edit contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Draft manual edit contract passed.')
