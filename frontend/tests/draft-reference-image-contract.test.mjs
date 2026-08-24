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

// Split layout: recognition content stays left, reference image stays right (#22).
requireMatch(/class="result-split-layout"/, 'recognition result must use the split layout container')
requireMatch(/class="result-main-column"/, 'split layout must keep the main content column')
requireMatch(/class="result-image-column"/, 'split layout must provide the reference image column')
requireMatch(/题目原图/, 'reference image panel must be labelled 题目原图')
requireMatch(/v-loading="draftImageLoading"/, 'reference image must expose its loading state')

// Click-to-zoom uses the Element Plus preview overlay instead of custom viewers.
requireMatch(
  /preview-src-list="\[resultImageSrc\]"/,
  'reference image must support click-to-zoom via preview-src-list'
)

// The image must come from the authenticated draft endpoint as a blob — never
// a bare <img> pointing straight at the API URL (#44 channel contract).
requireMatch(
  /buildDraftImageUrl\(draftId\.value\)/,
  'reference image must be fetched from GET /drafts/{id}/image'
)
requireMatch(
  /responseType: 'blob'[\s\S]{0,200}URL\.createObjectURL\(response\.data\)/,
  'draft image must be fetched as an authenticated blob and rendered via object URL'
)
requireAbsent(
  /<img[^>]*resultImageSrc/,
  'reference image must not be a bare <img> bound to the API URL'
)

// Server asset first, local full-page fallback second.
requireMatch(
  /const resultImageSrc = computed\(\(\) => draftImageObjectUrl\.value \|\| currentImageUrl\.value\)/,
  'reference image must prefer the draft asset blob and fall back to the local preview'
)

// Object URL lifecycle: released on draft reset, on draft change, and unmount.
requireMatch(
  /const releaseDraftImageObjectUrl = \(\) => \{[\s\S]*?URL\.revokeObjectURL/,
  'object URL release helper must revoke the URL'
)
requireMatch(
  /const resetDraftState = \(\) => \{[\s\S]*?releaseDraftImageObjectUrl\(\)/,
  'draft reset must release the reference image object URL'
)
requireMatch(
  /watch\(draftId, \(value\) => \{[\s\S]*?releaseDraftImageObjectUrl\(\)/,
  'draft change must release the previous object URL before prefetching'
)
requireMatch(
  /onBeforeUnmount\(\(\) => \{[\s\S]*?releaseDraftImageObjectUrl\(\)/,
  'component teardown must release the reference image object URL'
)

// Narrow viewports stack the columns with the image on top.
requireMatch(
  /@media \(max-width: 900px\) \{[\s\S]*?\.result-split-layout \{\s*flex-direction: column;/,
  'below 900px the split layout must stack vertically'
)

if (failures.length > 0) {
  console.error('Draft reference image contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Draft reference image contract passed.')
