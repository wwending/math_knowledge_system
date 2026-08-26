import assert from 'node:assert/strict'
import { createConcurrencyGate, createQuestionJobs, normalizeQuestionBbox, reconcileDraftStatus, runWithConcurrency, sortQuestionBoxes } from '../src/utils/questionSegmentation.mjs'

assert.deepEqual(normalizeQuestionBbox([0.1, 0.2, 0.3, 0.4]), [0.1, 0.2, 0.3, 0.4])
assert.equal(normalizeQuestionBbox([0, 0, 0.01, 0.01]), null)
const manualBoxes = [{ id: 2, bbox: [0, 0.6, 1, 0.2] }, { id: 1, bbox: [0, 0.1, 1, 0.2] }]
assert.deepEqual(createQuestionJobs(manualBoxes).map((job) => job.id), [2, 1])
assert.deepEqual(sortQuestionBoxes(manualBoxes).map((box) => box.id), [1, 2])
const previousJobs = [
  { id: 1, bbox: [0, 0.1, 1, 0.2], draftId: 101, status: 'saved_to_bank', content: '已保存题', saveResult: { question_id: 7 } },
  { id: 2, bbox: [0, 0.6, 1, 0.2], draftId: 102, status: 'draft_ready', content: '待确认题', confirmedFigureBbox: [0.1, 0.1, 0.3, 0.2] },
]
const reused = createQuestionJobs(manualBoxes, previousJobs)
assert.equal(reused.find((job) => job.id === 1).status, 'saved_to_bank')
assert.equal(reused.find((job) => job.id === 1).draftId, 101)
assert.deepEqual(reused.find((job) => job.id === 1).saveResult, { question_id: 7 })
assert.equal(reused.find((job) => job.id === 2).draftId, 102)
assert.equal(reused.find((job) => job.id === 2).status, 'queued')
const moved = createQuestionJobs([{ id: 2, bbox: [0.2, 0.6, 1, 0.2] }], previousJobs)
assert.equal(moved[0].draftId, null)
assert.deepEqual(reconcileDraftStatus({ status: 'draft_ready' }), { terminal: true, succeeded: true, status: 'draft_ready' })
assert.equal(reconcileDraftStatus({ status: 'recognizing' }).terminal, false)

let active = 0
let maximum = 0
await runWithConcurrency([1, 2, 3, 4, 5], async () => {
  active += 1
  maximum = Math.max(maximum, active)
  await new Promise((resolve) => setTimeout(resolve, 5))
  active -= 1
}, 2)
assert.equal(maximum, 2)
active = 0
maximum = 0
const gate = createConcurrencyGate(2)
await Promise.all([1, 2, 3, 4].map(() => gate(async () => {
  active += 1
  maximum = Math.max(maximum, active)
  await new Promise((resolve) => setTimeout(resolve, 5))
  active -= 1
})))
assert.equal(maximum, 2)
console.log('Question segmentation utility tests passed.')
