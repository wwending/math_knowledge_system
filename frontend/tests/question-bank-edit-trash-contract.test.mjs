import assert from 'node:assert/strict'; import fs from 'node:fs'
const bank=fs.readFileSync(new URL('../src/components/BankPanel.vue',import.meta.url),'utf8'); const loader=fs.readFileSync(new URL('../src/utils/questionImageLoaderCore.mjs',import.meta.url),'utf8')
for(const marker of ['回收站','questions/trash','moveToTrash','restoreQuestion','permanentlyDeleteQuestion','detailRequestToken','question-editor','bank_question_id','consumePendingQuestionDetail']) assert.ok(bank.includes(marker),`BankPanel missing ${marker}`)
assert.equal(bank.includes('QuestionEditWorkbench'),false)
for(const marker of ['const remove','generations','revokeObjectURL','syncItems']) assert.ok(loader.includes(marker),`Image loader missing ${marker}`)
console.log('Question bank edit/trash layout contract passed.')
