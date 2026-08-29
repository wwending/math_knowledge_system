import assert from 'node:assert/strict'; import fs from 'node:fs'
const router=fs.readFileSync(new URL('../src/router/index.js',import.meta.url),'utf8'), editor=fs.readFileSync(new URL('../src/views/QuestionEditor.vue',import.meta.url),'utf8'), bank=fs.readFileSync(new URL('../src/components/BankPanel.vue',import.meta.url),'utf8')
for(const marker of ["/questions/:id/edit","name: 'question-editor'",'QuestionEditor']) assert.ok(router.includes(marker),`router missing ${marker}`)
for(const marker of ['/document','buildQuestionDocumentPayload','onBeforeRouteLeave','beforeunload','createQuestionImageLoader','renderMarkdown','moveParagraphToSection','题干','答案','解析','图片区（只读）','status===409','conflict.value=true','mobile-switch']) assert.ok(editor.replaceAll(' ','').includes(marker.replaceAll(' ','')),`editor missing ${marker}`)
for(const marker of ['question-editor','bank_question_id','consumePendingQuestionDetail','replaceQueryValues','route.query.bank_question_id']) assert.ok(bank.includes(marker),`bank missing ${marker}`)
assert.equal(bank.includes('QuestionEditWorkbench'),false); assert.equal(editor.includes('/questions/${questionId.value}`'),false)
console.log('Question document editor contract passed.')
