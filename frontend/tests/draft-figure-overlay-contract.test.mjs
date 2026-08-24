import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const readSource = (relativePath) => readFileSync(resolve(process.cwd(), relativePath), 'utf8')

const failures = []
const requireMatch = (source, pattern, message) => {
  if (!pattern.test(source)) {
    failures.push(message)
  }
}
const requireAbsent = (source, pattern, message) => {
  if (pattern.test(source)) {
    failures.push(message)
  }
}

const dashboard = readSource('src/views/Dashboard.vue')
const editor = readSource('src/components/FigureOverlayEditor.vue')
const util = readSource('src/utils/figureOverlay.mjs')

// Dashboard wiring (#58): detection payload lands in refs and the editor
// replaces the plain preview only when regions were actually detected.
requireMatch(
  dashboard,
  /import FigureOverlayEditor from '\.\.\/components\/FigureOverlayEditor\.vue'/,
  'Dashboard must render the figure overlay editor component'
)
requireMatch(
  dashboard,
  /const detectedFigures = ref\(\[\]\)/,
  'Dashboard must keep detected figure regions in state'
)
requireMatch(
  dashboard,
  /const confirmedFigureBbox = ref\(null\)/,
  'Dashboard must keep the user-confirmed figure bbox in state'
)
requireMatch(
  dashboard,
  /const getDetectedFigures = \(payload\) => Array\.isArray\(payload\?\.detected_figures\) \? payload\.detected_figures : \[\]/,
  'Dashboard must parse detected_figures defensively from recognize payloads'
)
requireMatch(
  dashboard,
  /detectedFigures\.value = getDetectedFigures\(payload\)/,
  'the recognize success branch must populate the detected figures'
)
requireMatch(
  dashboard,
  /const resetDraftState = \(\) => \{[\s\S]*?detectedFigures\.value = \[\][\s\S]*?confirmedFigureBbox\.value = null/,
  'draft reset must clear both detection and confirmation state'
)
requireMatch(
  dashboard,
  /<figure-overlay-editor[\s\S]*?v-if="detectedFigures\.length > 0 && resultImageSrc"/,
  'the editor must only replace the plain preview when regions were detected'
)
requireMatch(
  dashboard,
  /<figure-overlay-editor[\s\S]*?v-model="confirmedFigureBbox"[\s\S]*?:initial-boxes="detectedFigures"/,
  'the editor must receive detections and write back the confirmed bbox'
)
requireAbsent(
  dashboard,
  /<figure-overlay-editor[^>]*v-else/,
  'the editor must not hijack the no-detection branch of the reference panel'
)

// Save-to-bank always sends an explicit decision: bbox or null (无图).
requireMatch(
  dashboard,
  /save-to-bank`,\s*\{\s*figure_bbox: confirmedFigureBbox\.value\s*\}\)/,
  'save-to-bank must send the explicit figure_bbox decision'
)

// Editor interaction contract: drag/resize/select/delete plus zoom.
requireMatch(editor, /@pointerdown\.prevent="onStagePointerDown"/, 'dragging on empty stage must start a new box draft')
requireMatch(editor, /onHandlePointerDown/, 'boxes must expose a resize handle')
requireMatch(editor, /setPrimary\(/, 'users must be able to choose which box is saved as the figure')
requireMatch(editor, /removeBox\(/, 'users must be able to delete a detected box')
requireMatch(editor, /markNoFigure/, 'users must be able to mark the question as having no figure')
requireMatch(editor, /resetBoxes/, 'users must be able to restore the original detections')
requireMatch(editor, /el-image-viewer/, 'zoom check must reuse the Element Plus viewer overlay')
requireMatch(editor, /defineExpose\(\{ markNoFigure, resetBoxes \}\)/, 'editor actions stay reachable for parents/tests')
requireAbsent(
  editor,
  /el-image[^-]/,
  'the editor stage must use a plain <img> so overlay boxes can wrap it'
)
requireAbsent(editor, /\$\.(get|post|patch)\(/, 'the editor must not call APIs directly')

// Coordinate math stays in the pure util (importable by Node tests).
requireMatch(util, /export const isValidFigureBbox/, 'bbox validation lives in the shared util')
requireMatch(util, /export const pointerRectToBbox/, 'pointer math lives in the shared util')
requireMatch(util, /export const pickPrimaryBox/, 'primary-box selection lives in the shared util')

if (failures.length > 0) {
  console.error('Draft figure overlay contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Draft figure overlay contract passed.')
