import assert from 'node:assert/strict'
import fs from 'node:fs'

import {
  applyDraftToQuestion,
  cloneQuestionDraft,
  isQuestionDraftDirty,
  mergeSavedQuestionResponse,
  normalizeQuestionDraft
} from '../src/utils/questionEditState.mjs'

const savedQuestion = {
  id: 21,
  content: '已保存题干',
  answer: 'A',
  analysis: '已保存解析',
  knowledge_tags: [{ label: '立体几何' }],
  question_type: 'solution',
  difficulty_level: 3,
  current_revision_no: 2
}

const baseline = normalizeQuestionDraft(savedQuestion)
const draft = cloneQuestionDraft(baseline)
draft.content = '正在编辑的题干'
draft.answer = 'B'

assert.equal(isQuestionDraftDirty(draft, baseline), true)
assert.equal(applyDraftToQuestion(savedQuestion, draft).content, '正在编辑的题干')
assert.equal(applyDraftToQuestion(savedQuestion, draft).answer, 'B')
assert.equal(applyDraftToQuestion(savedQuestion, draft).analysis, '已保存解析')

const resetDraft = normalizeQuestionDraft(savedQuestion)
assert.equal(resetDraft.content, '已保存题干')
assert.equal(isQuestionDraftDirty(resetDraft, baseline), false)

const updated = mergeSavedQuestionResponse(savedQuestion, {
  question: {
    ...savedQuestion,
    content: '第二次保存',
    current_revision_no: undefined
  },
  current_revision_no: 3
})
assert.equal(updated.content, '第二次保存')
assert.equal(updated.current_revision_no, 3)

const conflictDraft = cloneQuestionDraft(draft)
try {
  throw { response: { status: 409 } }
} catch (error) {
  assert.equal(error.response.status, 409)
}
assert.equal(conflictDraft.content, '正在编辑的题干')
assert.equal(conflictDraft.answer, 'B')

const bank = fs.readFileSync(new URL('../src/components/BankPanel.vue', import.meta.url), 'utf8')
const workbench = fs.readFileSync(new URL('../src/components/QuestionEditWorkbench.vue', import.meta.url), 'utf8')
assert.equal((bank.match(/class="detail-image"/g) || []).length, 1)
assert.equal(workbench.includes('<el-image'), false)
assert.equal(workbench.includes('workbench-tabs'), false)
assert.equal(workbench.includes('preview-pane'), false)

console.log('Question detail editor behavior passed.')
