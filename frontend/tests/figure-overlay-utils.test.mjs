import assert from 'node:assert/strict'

import {
  FIGURE_BBOX_MIN_AREA,
  bboxToStylePx,
  clamp01,
  isValidFigureBbox,
  pickPrimaryBox,
  pointerRectToBbox
} from '../src/utils/figureOverlay.mjs'

// -- clamp01 ------------------------------------------------------------------

assert.equal(clamp01(0.5), 0.5)
assert.equal(clamp01(-0.3), 0)
assert.equal(clamp01(1.7), 1)
assert.equal(clamp01('0.25'), 0.25)
assert.equal(clamp01('nope'), 0)

// -- isValidFigureBbox ----------------------------------------------------------

assert.ok(isValidFigureBbox([0.1, 0.2, 0.5, 0.5]), 'a normal bbox is valid')
assert.ok(!isValidFigureBbox(null), 'missing bbox is invalid')
assert.ok(!isValidFigureBbox([0, 0, 1]), 'bbox must have four components')
assert.ok(!isValidFigureBbox([0, 0, 'x', 1]), 'non-numeric parts are invalid')
assert.ok(!isValidFigureBbox([-0.1, 0, 0.5, 0.5]), 'negative origin is invalid')
assert.ok(!isValidFigureBbox([0, 0, 0, 0.5]), 'zero width is invalid')
assert.ok(!isValidFigureBbox([0.9, 0, 0.2, 0.5]), 'overflow beyond the right edge is invalid')
assert.ok(
  !isValidFigureBbox([0, 0, 0.05, 0.05]),
  `regions under ${FIGURE_BBOX_MIN_AREA} area are invalid`
)
assert.ok(isValidFigureBbox([0, 0, 0.08, 0.08]), 'small-but-meaningful regions are valid')

// -- pointerRectToBbox ----------------------------------------------------------

const drag = pointerRectToBbox(10, 20, 110, 70, 200, 100)
assert.deepEqual(drag.map((v) => Math.round(v * 100) / 100), [0.05, 0.2, 0.5, 0.5], 'drag rect maps to normalized xywh')
assert.deepEqual(pointerRectToBbox(110, 70, 10, 20, 200, 100), drag, 'drag direction does not matter')
assert.equal(pointerRectToBbox(10, 20, 11, 21, 200, 100), null, 'a near-zero drag produces no box')
assert.equal(pointerRectToBbox(10, 20, 110, 70, 0, 100), null, 'degenerate display size yields null')

// -- bboxToStylePx ---------------------------------------------------------------

const style = bboxToStylePx([0.25, 0.5, 0.5, 0.25], 200, 100)
assert.deepEqual(style, {
  left: '50.00px',
  top: '50.00px',
  width: '100.00px',
  height: '25.00px'
})
assert.equal(bboxToStylePx([0, 0, 2, 1], 200, 100), null, 'invalid bboxes produce no style')

// -- pickPrimaryBox ---------------------------------------------------------------

assert.equal(pickPrimaryBox([]), null)
assert.equal(pickPrimaryBox([{ bbox: [0, 0, 99, 99] }]), null, 'detections without a valid bbox are ignored')

const low = { bbox: [0.1, 0.6, 0.3, 0.3], score: 0.55 }
const high = { bbox: [0.4, 0.1, 0.3, 0.3], score: 0.91 }
assert.equal(pickPrimaryBox([low, high]), high, 'the highest-score detection wins')

const tieA = { bbox: [0.4, 0.1, 0.3, 0.3], score: 0.8 }
const tieB = { bbox: [0.1, 0.1, 0.3, 0.3], score: 0.8 }
assert.equal(pickPrimaryBox([tieA, tieB]), tieB, 'score ties break by reading order (top-left first)')

console.log('Figure overlay utils tests passed.')
