import assert from 'node:assert/strict'
import {
  flatQuestionSections,
  getQuestionPreviewSource,
  getQuestionSearchMatch,
  normalizeQuestionTags,
  questionSearchLocationLabel,
  sectionFigureIds
} from '../src/utils/questionBankSearch.mjs'

const question = {
  id: 12,
  content: '求函数的定义域',
  answer: '定义域为 R',
  analysis: '先检查分母是否为零',
  knowledge_tags: [{ label: '函数', score: 0.9 }, '定义域']
}

assert.deepEqual(getQuestionSearchMatch(question, '定义域'), {
  matched: true,
  locations: ['stem', 'answer', 'knowledge'],
  primarySection: 'stem'
})
assert.deepEqual(getQuestionSearchMatch(question, '分母'), {
  matched: true,
  locations: ['analysis'],
  primarySection: 'analysis'
})
assert.equal(getQuestionPreviewSource(question, '分母'), question.analysis)
assert.equal(getQuestionSearchMatch(question, '不存在').matched, false)
assert.deepEqual(normalizeQuestionTags(question), [
  { label: '函数', score: 0.9 },
  { label: '定义域', score: 1 }
])
assert.equal(questionSearchLocationLabel('answer'), '答案')

const section = {
  blocks: [
    { kind: 'text', markdown: '文字' },
    { kind: 'image_area', placements: [{ figure_id: 'a' }, { figure_id: 'b' }] },
    { kind: 'image_area', placements: [{ figure_id: 'a' }, {}] }
  ]
}
assert.deepEqual([...sectionFigureIds(section)], ['a', 'b'])
assert.deepEqual([...sectionFigureIds({ blocks: [{ kind: 'text' }] })], [])

const trash = flatQuestionSections(question)
assert.equal(trash.stem.blocks[0].markdown, question.content)
assert.equal(trash.answer.blocks[0].kind, 'text')
assert.equal(flatQuestionSections({ id: 1 }).analysis.blocks.length, 0)

console.log('Question bank search helpers passed.')
