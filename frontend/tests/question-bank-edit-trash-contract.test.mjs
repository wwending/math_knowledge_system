import assert from 'node:assert/strict'
import fs from 'node:fs'

const bank = fs.readFileSync(new URL('../src/components/BankPanel.vue', import.meta.url), 'utf8')
const workbench = fs.readFileSync(new URL('../src/components/QuestionEditWorkbench.vue', import.meta.url), 'utf8')
const loader = fs.readFileSync(new URL('../src/utils/questionImageLoader.js', import.meta.url), 'utf8') + fs.readFileSync(new URL('../src/utils/questionImageLoaderCore.mjs', import.meta.url), 'utf8')

for (const marker of ['回收站', 'questions/trash', 'moveToTrash', 'restoreQuestion', 'permanentlyDeleteQuestion', 'deleted_at', 'purge_at', 'selectedQuestionIds.value = []', 'detailRequestToken']) assert.ok(bank.includes(marker), `BankPanel missing ${marker}`)
for (const marker of ['draft-change', 'displayItem', '题目内容', '答案', '解析', 'renderTex(displayItem.content)', 'renderTex(displayItem.answer)', 'renderTex(displayItem.analysis)']) assert.ok(bank.includes(marker), `BankPanel missing ${marker}`)
for (const marker of ['expected_revision_no', 'status === 409', 'ElMessageBox.confirm', 'questionTypes', 'draft-change', 'preview-hint']) assert.ok(workbench.includes(marker), `Workbench missing ${marker}`)
for (const marker of ['workbench-tabs', 'question-image-pane', 'preview-pane', 'imageUrl', 'activeTab']) assert.equal(workbench.includes(marker), false, `Workbench must not duplicate ${marker}`)
for (const marker of ['const remove', 'generations', 'revokeObjectURL', 'syncItems']) assert.ok(loader.includes(marker), `Image loader missing ${marker}`)
console.log('Question bank edit/trash layout contract passed.')
