import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const readSource = (relativePath) => readFileSync(resolve(process.cwd(), relativePath), 'utf8')
const failures = []
const requireMatch = (source, pattern, message) => { if (!pattern.test(source)) failures.push(message) }
const requireAbsent = (source, pattern, message) => { if (pattern.test(source)) failures.push(message) }

const dashboard = readSource('src/views/Dashboard.vue')
const editor = readSource('src/components/FigureOverlayEditor.vue')
const util = readSource('src/utils/figureOverlay.mjs')

requireMatch(dashboard, /const detectedFigures = ref\(\[\]\)/, 'Dashboard must retain detection results')
requireMatch(dashboard, /const confirmedFigureBboxes = ref\(\[\]\)/, 'Dashboard must keep all confirmed boxes')
requireMatch(dashboard, /confirmedFigureBboxes\.value = getConfirmedFigureBboxes\(payload\)/, 'recognition must confirm every detection by default')
requireMatch(dashboard, /v-model="confirmedFigureBboxes"/, 'the editor must bind the complete confirmed collection')
requireMatch(dashboard, /figure_bboxes: sortFigureBboxesReadingOrder\(confirmedFigureBboxes\.value\)/, 'single save must send all confirmed boxes')
requireMatch(dashboard, /figure_bboxes: sortFigureBboxesReadingOrder\(job\.confirmedFigureBboxes\)/, 'batch save must send all confirmed boxes')
requireAbsent(dashboard, /figure_bbox:/, 'the public frontend must not send the deprecated singular field')
requireMatch(dashboard, /confirmedFiguresError/, 'overlap and count errors must gate single save')
requireMatch(dashboard, /未检测到配图或检测服务暂不可用/, 'zero detection must have an explicit text-only state')

requireMatch(editor, /onBoxPointerDown/, 'confirmed boxes remain movable')
requireMatch(editor, /onHandlePointerDown/, 'confirmed boxes remain resizable')
requireMatch(editor, /removeBox/, 'detected boxes remain deletable')
requireMatch(editor, /markNoFigure/, 'all boxes can be cleared')
requireMatch(editor, /resetBoxes/, 'original detections can be restored')
requireMatch(editor, /findOverlappingFigureBboxes/, 'overlap conflicts must be highlighted')
requireMatch(editor, /emit\('update:modelValue', sortFigureBboxesReadingOrder/, 'editor must emit the full ordered array')
requireMatch(editor, /el-image-viewer/, 'zoom check remains available')
requireAbsent(editor, /onStagePointerDown|mode:\s*'draw'|figure-draft/, 'upload confirmation must not draw new boxes')
requireAbsent(editor, /primaryId|setPrimary|主图|设为主图|pickPrimaryBox/, 'primary-figure semantics must be removed')
requireAbsent(editor, /\$\.(get|post|patch)\(/, 'the editor must not call APIs directly')

requireMatch(util, /export const sortFigureBboxesReadingOrder/, 'reading-order sorting belongs in the pure util')
requireMatch(util, /export const findOverlappingFigureBboxes/, 'overlap detection belongs in the pure util')
requireAbsent(util, /pickPrimaryBox|pointerRectToBbox/, 'obsolete primary and draw helpers must be removed')

if (failures.length > 0) {
  console.error('Draft figure overlay contract failed:')
  failures.forEach((failure) => console.error(`- ${failure}`))
  process.exit(1)
}
console.log('Draft figure overlay contract passed.')
