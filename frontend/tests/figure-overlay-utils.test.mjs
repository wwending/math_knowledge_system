import assert from 'node:assert/strict'

import {
  FIGURE_BBOX_MIN_AREA,
  bboxToStylePx,
  clamp01,
  figureBboxesOverlap,
  findOverlappingFigureBboxes,
  isValidFigureBbox,
  sortFigureBboxesReadingOrder,
} from '../src/utils/figureOverlay.mjs'

assert.equal(clamp01(0.5), 0.5)
assert.equal(clamp01(-0.3), 0)
assert.equal(clamp01(1.7), 1)
assert.equal(clamp01('0.25'), 0.25)
assert.equal(clamp01('nope'), 0)

assert.ok(isValidFigureBbox([0.1, 0.2, 0.5, 0.5]), 'a normal bbox is valid')
assert.ok(!isValidFigureBbox(null), 'missing bbox is invalid')
assert.ok(!isValidFigureBbox([0, 0, 1]), 'bbox must have four components')
assert.ok(!isValidFigureBbox([0, 0, 'x', 1]), 'non-numeric parts are invalid')
assert.ok(!isValidFigureBbox([-0.1, 0, 0.5, 0.5]), 'negative origin is invalid')
assert.ok(!isValidFigureBbox([0, 0, 0, 0.5]), 'zero width is invalid')
assert.ok(!isValidFigureBbox([0.9, 0, 0.2, 0.5]), 'overflow beyond the right edge is invalid')
assert.equal(FIGURE_BBOX_MIN_AREA, 0.01, 'upload confirmation must match the save-to-bank endpoint threshold')
assert.ok(!isValidFigureBbox([0, 0, 0.09, 0.09]), `regions under ${FIGURE_BBOX_MIN_AREA} area are invalid`)
assert.ok(isValidFigureBbox([0, 0, 0.1, 0.1]), 'the exact backend boundary is valid')

const style = bboxToStylePx([0.25, 0.5, 0.5, 0.25], 200, 100)
assert.deepEqual(style, {
  left: '50.00px',
  top: '50.00px',
  width: '100.00px',
  height: '25.00px',
})
assert.equal(bboxToStylePx([0, 0, 2, 1], 200, 100), null, 'invalid bboxes produce no style')

const unsorted = [
  [0.55, 0.5, 0.2, 0.2],
  [0.5, 0.1, 0.2, 0.2],
  [0.1, 0.105, 0.2, 0.2],
]
const sorted = sortFigureBboxesReadingOrder(unsorted)
assert.deepEqual(sorted, [unsorted[2], unsorted[1], unsorted[0]], 'boxes sort by row then left edge')
assert.deepEqual(unsorted[0], [0.55, 0.5, 0.2, 0.2], 'sorting does not mutate input')
assert.notEqual(sorted[0], unsorted[2], 'sorting deep-copies bbox arrays')

assert.ok(figureBboxesOverlap([0, 0, 0.6, 0.5], [0.5, 0, 0.5, 0.5]))
assert.ok(!figureBboxesOverlap([0, 0, 0.5, 0.5], [0.5, 0, 0.5, 0.5]), 'touching edges are valid')
assert.deepEqual(
  findOverlappingFigureBboxes([
    [0, 0, 0.6, 0.5],
    [0.5, 0, 0.5, 0.5],
    [0, 0.6, 0.4, 0.4],
  ]),
  [[0, 1]],
  'conflict indices are deterministic'
)

console.log('Figure overlay utils tests passed.')
