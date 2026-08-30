import assert from 'node:assert/strict'
import {
  DOCUMENT_MIN_CROP_AREA,
  addCropsToImageArea,
  addImageArea,
  buildQuestionDocumentPayload,
  createEditorSession,
  createQuestionDocumentEditorState,
  executeEditorCommand,
  redoEditorSession,
  removeFigurePlacement,
  restorePlacementNaturalSize,
  setImageAreaHeight,
  undoEditorSession,
  updatePlacement,
  validateQuestionDocumentDraft
} from '../src/utils/questionDocumentEditorState.mjs'

const ids = {
  text: '11111111-1111-4111-8111-111111111111',
  area: '22222222-2222-4222-8222-222222222222',
  crop1: '33333333-3333-4333-8333-333333333333',
  crop2: '44444444-4444-4444-8444-444444444444'
}
const source = {
  id: 9,
  sections: { stem: { blocks: [{ id: ids.text, kind: 'text', markdown: '题干' }] }, answer: { blocks: [] }, analysis: { blocks: [] } },
  figures: [], knowledge_tags: [], question_type: null, difficulty_level: null, has_question_image: true, image_url: '/image'
}
const baseline = createQuestionDocumentEditorState(source).draft
const withArea = addImageArea(baseline, 'stem', { createId: () => ids.area }).document
const generated = [ids.crop1, ids.crop2]
const withCrops = addCropsToImageArea(withArea, ids.area, [[0, 0, .2, .2], [.3, 0, .2, .2]], {
  canvasWidth: 1000, sourceWidth: 1000, sourceHeight: 500, createId: () => generated.shift(), gap: 10
}).document
assert.equal(withCrops.figures.length, 2)
assert.equal(withCrops.sections.stem.blocks[1].placements.length, 2)
assert.equal(validateQuestionDocumentDraft(withCrops).valid, true)
assert.equal(withCrops.sections.stem.blocks[1].placements[0].width, .2)
assert.equal(buildQuestionDocumentPayload(withCrops, 3).figures[0].kind, 'crop')
assert.deepEqual(buildQuestionDocumentPayload(withCrops, 3).figures[0].crop_bbox, [0, 0, .2, .2])

assert.ok(addCropsToImageArea(withArea, ids.area, [[0, 0, DOCUMENT_MIN_CROP_AREA / 2, 1]], { canvasWidth: 1000, sourceWidth: 1000, sourceHeight: 500 }).error)
assert.ok(addCropsToImageArea(withArea, ids.area, [[0, 0, .4, .4], [.2, .2, .4, .4]], { canvasWidth: 1000, sourceWidth: 1000, sourceHeight: 500 }).error)
assert.ok(setImageAreaHeight(withCrops, ids.area, .01, { canvasWidth: 1000 }).error)

const areaHeight = withCrops.sections.stem.blocks[1].height_ratio * 1000
const edgePlacement = updatePlacement(withCrops, ids.area, ids.crop2, {
  left: 800.25, top: areaHeight - 100 + 0.25, width: 200, height: 100
}, { canvasWidth: 1000 })
assert.equal(edgePlacement.error, null)
const bounded = edgePlacement.document.sections.stem.blocks[1].placements.find((item) => item.figure_id === ids.crop2)
assert.ok(bounded.x + bounded.width <= 1)
assert.ok(bounded.y + bounded.height <= 1)
assert.ok(updatePlacement(withCrops, ids.area, ids.crop2, {
  left: 800.75, top: 0, width: 200, height: 100
}, { canvasWidth: 1000 }).error)

const stalePlacement = structuredClone(withCrops)
stalePlacement.sections.stem.blocks[1].placements = stalePlacement.sections.stem.blocks[1].placements.filter((item) => item.figure_id !== ids.crop1)
const staleRestore = restorePlacementNaturalSize(stalePlacement, ids.area, ids.crop1, { canvasWidth: 1000 })
assert.equal(staleRestore.changed, false)
assert.match(staleRestore.error, /当前图片区中不存在/)
assert.ok(restorePlacementNaturalSize(withCrops, ids.area, crypto.randomUUID(), { canvasWidth: 1000 }).error)

const duplicate = structuredClone(withCrops)
duplicate.sections.answer.blocks.push({ id: crypto.randomUUID(), kind: 'image_area', height_ratio: 1, placements: [{ ...duplicate.sections.stem.blocks[1].placements[0] }] })
assert.equal(validateQuestionDocumentDraft(duplicate).errors.some((error) => error.code === 'duplicate_figure_placement'), true)

for (const malformed of [null, undefined, 'invalid']) {
  const malformedDraft = structuredClone(withCrops)
  malformedDraft.sections.stem.blocks[1].placements[0] = malformed
  const malformedResult = validateQuestionDocumentDraft(malformedDraft)
  const error = malformedResult.errors.find((item) => item.code === 'invalid_placement')
  assert.equal(malformedResult.valid, false)
  assert.equal(error?.section, 'stem')
  assert.equal(error?.block_id, ids.area)
  assert.equal(error?.placement_index, 0)
  assert.equal(error?.field, 'placements')
}

let session = createEditorSession(baseline)
session = executeEditorCommand(session, (document) => addImageArea(document, 'stem', { createId: () => ids.area })).session
assert.equal(session.past.length, 1)
session = undoEditorSession(session)
assert.equal(session.present.sections.stem.blocks.length, 1)
session = redoEditorSession(session)
assert.equal(session.present.sections.stem.blocks.length, 2)
session = undoEditorSession(session)
session = executeEditorCommand(session, (document) => addImageArea(document, 'answer')).session
assert.equal(session.future.length, 0)

const emptyAfterRemoval = removeFigurePlacement(withCrops, ids.area, ids.crop1).document
assert.equal(emptyAfterRemoval.figures.length, 1)

const canvasSource = await import('node:fs').then((fs) => fs.readFileSync(new URL('../src/components/QuestionImageAreaCanvas.vue', import.meta.url), 'utf8'))
assert.equal(canvasSource.includes('min-height:80px'), false, 'height_ratio=.05 must not be stretched by a minimum canvas height')
assert.ok(canvasSource.includes('aspectRatio:`1 / ${area.height_ratio}`'))
console.log('Question image area editor state passed.')
