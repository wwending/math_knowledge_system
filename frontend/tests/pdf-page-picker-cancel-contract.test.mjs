import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dashboardPath = resolve(process.cwd(), 'src/views/Dashboard.vue')
const source = readFileSync(dashboardPath, 'utf8')
const failures = []

const requireMatch = (pattern, message) => {
  if (!pattern.test(source)) {
    failures.push(message)
  }
}

const requireAbsent = (pattern, message) => {
  if (pattern.test(source)) {
    failures.push(message)
  }
}

// #62: canceling the confirm step after picking a PDF page must keep the parsed
// pages alive and return to the picker; only a non-PDF image falls back to the
// full upload reset.
const cancelHandler = source.match(/const cancelProcessStep = \(\) => \{([\s\S]*?)\n\}/)?.[1] || ''
if (!cancelHandler) {
  failures.push('cancelProcessStep handler must exist')
} else {
  if (!cancelHandler.includes('pdfPages.value.length > 0')) {
    failures.push('cancelProcessStep must branch on pdfPages.value.length > 0 (PDF-sourced confirm step)')
  }
  if (!cancelHandler.includes("step.value = 'preview-pdf'")) {
    failures.push('PDF-sourced cancel must return to the preview-pdf picker keeping parsed pages')
  }
  if (!cancelHandler.includes("setCurrentImageSource('')") || !cancelHandler.includes("setCropPreviewSource('')")) {
    failures.push('cancelProcessStep must clear per-selection image state before returning to the picker')
  }
  if (!cancelHandler.includes('resetUpload()')) {
    failures.push('non-PDF (direct image upload) cancel must fall back to the full resetUpload()')
  }
  const pickerReturn = cancelHandler.indexOf("step.value = 'preview-pdf'")
  const fullReset = cancelHandler.indexOf('resetUpload()')
  if (pickerReturn === -1 || fullReset === -1 || pickerReturn > fullReset) {
    failures.push('the PDF early-return must precede the resetUpload() fallback')
  }
}

// The confirm-step button binds to the new handler with a PDF-aware label.
requireMatch(
  /class="image-process-section"[\s\S]*?@click="cancelProcessStep">\{\{ pdfPages\.length > 0 \? '重新选页' : '取消' \}\}/,
  'confirm-step cancel must bind cancelProcessStep and show 重新选页 when pages come from a PDF'
)

// Old wiring — a bare 取消 bound straight to the destructive full reset — must be gone.
requireAbsent(
  /@click="resetUpload">取消</,
  'the old direct 取消 -> resetUpload binding must be removed'
)

// The picker keeps its explicit escape hatch for switching to another file.
requireMatch(
  /@click="resetUpload">重新上传</,
  'picker toolbar must keep 重新上传 as an explicit full re-upload'
)

// Invariant underpinning the branch: pdfPages non-empty <=> current image came
// from a PDF page. Direct image uploads must clear stale parsed pages...
const fileSelect = source.match(/const handleFileSelect = async \(uploadFile\) => \{([\s\S]*?)\n\}/)?.[1] || ''
if (!fileSelect.includes('pdfPages.value = []')) {
  failures.push('image uploads must clear pdfPages so pdfPages non-empty always means PDF-sourced')
}
// ...and any new file selection must void an in-flight PDF render session.
if (!fileSelect.includes('pdfRenderGeneration += 1')) {
  failures.push('file selection must bump pdfRenderGeneration to void in-flight renders')
}

// Render sessions own their writes and the shared loading flag: a stale session
// must neither push pages, run the failure path, nor kill a newer spinner.
const renderFn = source.match(/const renderPdfToImages = async \(file\) => \{([\s\S]*?)\n\}/)?.[1] || ''
if (!renderFn.includes('++pdfRenderGeneration')) {
  failures.push('renderPdfToImages must open its own pdfRenderGeneration session')
}
if ((renderFn.match(/generation !== pdfRenderGeneration/g) || []).length < 3) {
  failures.push('stale render sessions must bail before page writes, error handling, and loading reset')
}

if (failures.length > 0) {
  console.error('PDF page-picker cancel contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('PDF page-picker cancel contract passed.')
