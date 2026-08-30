import assert from 'node:assert/strict'; import fs from 'node:fs'
const router=fs.readFileSync(new URL('../src/router/index.js',import.meta.url),'utf8'), editor=fs.readFileSync(new URL('../src/views/QuestionEditor.vue',import.meta.url),'utf8'), bank=fs.readFileSync(new URL('../src/components/BankPanel.vue',import.meta.url),'utf8')
for(const marker of ["/questions/:id/edit","name: 'question-editor'",'QuestionEditor']) assert.ok(router.includes(marker),`router missing ${marker}`)
for(const marker of ['/document','buildQuestionDocumentPayload','onBeforeRouteLeave','beforeunload','createQuestionImageLoader','createQuestionFigurePreviewRegistry','QuestionFigureCropOverlay','QuestionImageAreaEditor','QuestionDraftPreview','QuestionDocumentErrorNavigator','undoEditorSession','redoEditorSession','reachableFigureIds','题干','答案','解析','status===409','conflict.value=true','mobile-switch']) assert.ok(editor.replaceAll(' ','').includes(marker.replaceAll(' ','')),`editor missing ${marker}`)
assert.match(editor.replaceAll(' ',''),/constresult=execute\([\s\S]*?if\(result\.changed\)cropDialog\.value=false/, 'failed crop commands must keep the dialog and selected boxes open')
assert.equal(editor.includes('图片区（只读）'),false)
for(const marker of ['question-editor','bank_question_id','consumePendingQuestionDetail','replaceQueryValues','route.query.bank_question_id']) assert.ok(bank.includes(marker),`bank missing ${marker}`)
assert.equal(bank.includes('QuestionEditWorkbench'),false); assert.equal(editor.includes('/questions/${questionId.value}`'),false)
console.log('Question document editor contract passed.')
