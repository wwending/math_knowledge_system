import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const read = (relativePath) => readFileSync(resolve(process.cwd(), relativePath), 'utf8')

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

// --- config/api.js: the single source of the in-paper figure URL (#59) ---
const apiConfig = read('src/config/api.js')
requireMatch(
  apiConfig,
  /export const buildPaperItemImageUrl = \(paperId, paperItemId\) =>\s*`\$\{API_V1_BASE_URL\}\/papers\/\$\{paperId\}\/items\/\$\{paperItemId\}\/image`/,
  'api.js must export buildPaperItemImageUrl built on API_V1_BASE_URL'
)
requireMatch(apiConfig, /#59/, 'buildPaperItemImageUrl must reference the authenticated #59 channel')

// --- loader: authenticated blob prefetch keyed by paper_item_id ---
const loader = read('src/utils/paperFigureImageLoader.js')
requireMatch(loader, /createPaperFigureImageLoader/, 'loader factory must be exported')
requireMatch(
  loader,
  /buildPaperItemImageUrl\(paperId, paperItemId\)/,
  'loader must fetch through the central buildPaperItemImageUrl builder'
)
requireMatch(
  loader,
  /axios\s*\.\s*get\([\s\S]{0,200}responseType: 'blob'/,
  'figure requests must be authenticated blob fetches over the global axios instance'
)
requireMatch(loader, /URL\.createObjectURL\(blob\)/, 'figure blobs must be rendered via object URLs')
requireMatch(loader, /URL\.revokeObjectURL/, 'removed items must revoke their object URLs')
requireMatch(loader, /wantedIds\.has\(paperItemId\)/, 'late responses after removal must be dropped')
requireMatch(loader, /const dispose = \(\) =>/, 'loader must expose dispose()')

// --- PaperPreview: figure rendering + lifecycle ---
const preview = read('src/components/PaperPreview.vue')
requireMatch(preview, /createPaperFigureImageLoader/, 'PaperPreview must instantiate the figure loader')
requireMatch(
  preview,
  /<img[^>]*class="question-figure"[^>]*:src="figureUrlFor\(item\)"/s,
  'question figures must render via the loader object URL binding'
)
requireMatch(
  preview,
  /watch\(\s*\(\) => props\.renderModel,[\s\S]{0,200}syncRenderModel/,
  'render model changes must resync prefetched figures'
)
requireMatch(
  preview,
  /onBeforeUnmount\(\(\) => figureLoader\.dispose\(\)\)/,
  'PaperPreview teardown must dispose all figure object URLs'
)
requireMatch(
  preview,
  /第\$\{item\.display_number\}题配图/,
  'figure images must carry an alt text naming the question'
)
// Chromium can drop lazy images during print/PDF flows — figures must eager-load.
requireAbsent(preview, /loading="lazy"/, 'figure images must not use lazy loading')
// The API URL is built inside the loader only; the component never assembles one.
requireAbsent(
  preview,
  /\/papers\/\$\{[^}]+\}\/items\//,
  'PaperPreview must not hand-build the in-paper image URL'
)

// --- package.json wiring ---
const pkg = JSON.parse(read('package.json'))
const stage3Chain = pkg.scripts['test:stage3-contract'] || ''
if (!stage3Chain.includes('paper-figure-contract.test.mjs')) {
  failures.push('test:stage3-contract chain must run tests/paper-figure-contract.test.mjs')
}

if (failures.length > 0) {
  console.error('Paper figure contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Paper figure contract passed.')
