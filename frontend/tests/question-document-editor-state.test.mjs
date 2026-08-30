import assert from 'node:assert/strict'
import {
  MAX_BLOCKS_PER_SECTION,
  addTextBlock,
  buildQuestionDocumentPayload,
  createQuestionDocumentEditorState,
  deleteTextBlock,
  editTextBlock,
  findSafeMarkdownParagraphs,
  isQuestionDocumentDirty,
  mergeTextBlockWithNext,
  moveBlockToSection,
  moveParagraphToSection,
  reorderBlock,
  splitTextBlockAtParagraph,
  validateQuestionDocumentDraft
} from '../src/utils/questionDocumentEditorState.mjs'

const ids = {
  stem: '11111111-1111-4111-8111-111111111111',
  answer: '22222222-2222-4222-8222-222222222222',
  image: '33333333-3333-4333-8333-333333333333',
  figure: '44444444-4444-4444-8444-444444444444',
  added: '55555555-5555-4555-8555-555555555555',
  split: '66666666-6666-4666-8666-666666666666',
  moved: '77777777-7777-4777-8777-777777777777'
}

const source = {
  id: 7,
  current_revision_no: 2,
  sections: {
    stem: {
      blocks: [
        { id: ids.stem, kind: 'text', markdown: '第一段\n\n第二段' },
        { id: ids.image, kind: 'image_area', height_ratio: 1, placements: [{ figure_id: ids.figure, x: 0, y: 0, width: 1, height: 1 }] }
      ]
    },
    answer: { blocks: [{ id: ids.answer, kind: 'text', markdown: '答案' }] },
    analysis: { blocks: [] }
  },
  figures: [{ id: ids.figure, url: '/x', mime: 'image/jpeg', size_bytes: 12 }],
  knowledge_tags: [{ label: '函数', score: 1 }],
  question_type: 'solution',
  difficulty_level: 3,
  image_url: '/api/v1/questions/7/image',
  has_question_image: true
}

const state = createQuestionDocumentEditorState(source)
state.draft.sections.stem.blocks[0].markdown = '改'
assert.equal(state.baseline.sections.stem.blocks[0].markdown, '第一段\n\n第二段')
assert.equal(isQuestionDocumentDirty(state.draft, state.baseline), true)
assert.deepEqual(state.baseline.sections.stem.blocks[1], source.sections.stem.blocks[1])

const payload = buildQuestionDocumentPayload(state.baseline, 2)
assert.deepEqual(payload.figures, [{ id: ids.figure, kind: 'existing' }])
assert.equal(payload.expected_revision_no, 2)
assert.equal('url' in payload.figures[0], false)
assert.deepEqual(payload.sections.stem.blocks[1], source.sections.stem.blocks[1])

const added = addTextBlock(state.baseline, 'analysis', { markdown: '解析', createId: () => ids.added }).document
assert.equal(added.sections.analysis.blocks[0].id, ids.added)
assert.equal(editTextBlock(added, 'analysis', ids.added, '新解析').document.sections.analysis.blocks[0].markdown, '新解析')
assert.equal(deleteTextBlock(added, 'analysis', ids.added).document.sections.analysis.blocks.length, 0)

const split = splitTextBlockAtParagraph(state.baseline, 'stem', ids.stem, 1, { createId: () => ids.split }).document
assert.equal(split.sections.stem.blocks[0].id, ids.stem)
assert.equal(split.sections.stem.blocks[1].id, ids.split)
assert.equal(split.sections.stem.blocks[1].markdown, '第二段')
assert.deepEqual(split.sections.stem.blocks[2], source.sections.stem.blocks[1])

const merged = mergeTextBlockWithNext(split, 'stem', ids.stem).document
assert.equal(merged.sections.stem.blocks[0].id, ids.stem)
assert.equal(merged.sections.stem.blocks[0].markdown, '第一段\n\n第二段')

const reordered = reorderBlock(split, 'stem', ids.image, 0).document
assert.equal(reordered.sections.stem.blocks[0].id, ids.image)
const movedBlock = moveBlockToSection(state.baseline, 'answer', ids.answer, 'analysis').document
assert.equal(movedBlock.sections.analysis.blocks[0].id, ids.answer)
assert.equal(moveBlockToSection(state.baseline, 'stem', ids.stem, 'analysis').error, null)

const movedParagraph = moveParagraphToSection(
  state.baseline,
  'stem',
  ids.stem,
  1,
  'analysis',
  { createId: () => ids.moved }
).document
assert.equal(movedParagraph.sections.stem.blocks[0].id, ids.stem)
assert.equal(movedParagraph.sections.stem.blocks[0].markdown, '第一段')
assert.deepEqual(movedParagraph.sections.analysis.blocks[0], { id: ids.moved, kind: 'text', markdown: '第二段' })
assert.deepEqual(movedParagraph.sections.stem.blocks[1], source.sections.stem.blocks[1])

assert.equal(findSafeMarkdownParagraphs('前文\n\n```js\na\n\nb\n```\n\n后文').length, 3)
assert.equal(findSafeMarkdownParagraphs('前文\n\n`a\n\nb`\n\n后文').length, 3)
assert.equal(findSafeMarkdownParagraphs('前文\n\n$$\na\n\nb\n$$\n\n后文').length, 3)
assert.equal(findSafeMarkdownParagraphs('前文\n\n$a\n\nb$\n\n后文').length, 3)
assert.equal(findSafeMarkdownParagraphs('前文 \\$5\n\n后文').length, 2)
assert.equal(findSafeMarkdownParagraphs('前文\n\n```\n未闭合').length, 1)
assert.equal(findSafeMarkdownParagraphs('前文\n\n$未闭合').length, 1)

const rawHtmlAndTex = '<b>原始 HTML</b>\n\n\\[x^2 + y^2 = 1\\]'
const rawDocument = createQuestionDocumentEditorState({
  ...source,
  sections: { ...source.sections, stem: { blocks: [{ ...source.sections.stem.blocks[0], markdown: rawHtmlAndTex }] } }
}).baseline
const rawSplit = splitTextBlockAtParagraph(rawDocument, 'stem', ids.stem, 1, { createId: () => ids.split }).document
assert.equal(rawSplit.sections.stem.blocks[0].markdown, '<b>原始 HTML</b>')
assert.equal(rawSplit.sections.stem.blocks[1].markdown, '\\[x^2 + y^2 = 1\\]')

const invalidId = structuredClone(state.baseline)
invalidId.sections.answer.blocks[0].id = 'not-a-uuid'
assert.equal(validateQuestionDocumentDraft(invalidId).errors.some((error) => error.code === 'invalid_id'), true)
const duplicateId = structuredClone(state.baseline)
duplicateId.sections.answer.blocks[0].id = ids.stem
assert.equal(validateQuestionDocumentDraft(duplicateId).errors.some((error) => error.code === 'duplicate_id'), true)
const invalidMetadata = structuredClone(state.baseline)
invalidMetadata.metadata.difficulty_level = 6
assert.equal(validateQuestionDocumentDraft(invalidMetadata).errors.some((error) => error.code === 'invalid_difficulty'), true)

const full = structuredClone(state.baseline)
full.sections.analysis.blocks = Array.from({ length: MAX_BLOCKS_PER_SECTION }, (_, index) => ({
  id: `aaaaaaaa-aaaa-4aaa-8aaa-${String(index).padStart(12, '0')}`,
  kind: 'text',
  markdown: `段落 ${index}`
}))
assert.ok(addTextBlock(full, 'analysis').error)
assert.ok(moveBlockToSection(state.baseline, 'answer', ids.answer, 'analysis').changed)

console.log('Question document editor state passed.')
