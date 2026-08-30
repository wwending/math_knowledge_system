import assert from 'node:assert/strict'
import fs from 'node:fs'

const bank = fs.readFileSync(new URL('../src/components/BankPanel.vue', import.meta.url), 'utf8')
const sectionView = fs.readFileSync(new URL('../src/components/QuestionDocumentSectionView.vue', import.meta.url), 'utf8')
const loader = fs.readFileSync(new URL('../src/utils/questionImageLoaderCore.mjs', import.meta.url), 'utf8')

for (const marker of [
  '回收站',
  'questions/trash',
  'moveToTrash',
  'restoreQuestion',
  'permanentlyDeleteQuestion',
  'detailRequestToken',
  'question-editor',
  'bank_question_id',
  'consumePendingQuestionDetail',
  '/document',
  'QuestionDocumentSectionView',
  'createQuestionFigurePreviewRegistry',
  'ensureQuestionImage(item)',
  'sectionFigureIds',
  '题干/答案/解析/知识点',
  '搜索命中位置'
]) {
  assert.ok(bank.includes(marker), `BankPanel missing ${marker}`)
}
assert.equal(bank.includes('QuestionEditWorkbench'), false)
assert.equal(bank.includes('renderTex'), false)
assert.match(bank, /openingTab === 'trash'[\s\S]*questions\/trash\/\$\{item\.id\}[\s\S]*questions\/\$\{item\.id\}\/document/)
assert.match(bank, /const handleBankTabChange = \(\) => \{[\s\S]*resetDetailState\(\)[\s\S]*fetchQuestions\(\)/, 'tab changes must invalidate pending detail requests through the shared reset')
assert.match(bank, /if \(!item\) \{[\s\S]*axios\.get\(`\$\{API_BASE\}\/questions\/\$\{id\}`\)/, 'route return must fetch an owner-scoped question when it is outside the current 100-row/search result')
assert.match(bank, /const result = await openDetail\(item\)[\s\S]*result === 'opened'[\s\S]*bank_question_id: null/, 'the pending route query must only be consumed after opening or a confirmed 404')

for (const marker of ['renderMarkdown', "block.kind === 'text'", "block.kind === 'image_area'", 'QuestionImageAreaCanvas', 'el-empty']) {
  assert.ok(sectionView.includes(marker), `Section view missing ${marker}`)
}
for (const marker of ['const remove', 'generations', 'revokeObjectURL', 'syncItems']) {
  assert.ok(loader.includes(marker), `Image loader missing ${marker}`)
}

console.log('Question bank read-only detail and trash contract passed.')
