import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// PDF page cards are the core entry flow (#68). They used to be plain divs,
// so keyboard users could never pick a page. They must stay native buttons
// (Enter/Space come free) with a clearly visible focus ring.
const source = readFileSync(resolve(process.cwd(), 'src/views/Dashboard.vue'), 'utf8')

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

// Native button carrying the click binding (attribute order per template).
requireMatch(
  /<button\s[^>]*type="button"[^>]*class="pdf-page-card"/,
  'PDF page cards must be native <button type="button"> elements'
)
requireMatch(
  /class="pdf-page-card"[^>]*@click="selectPdfPage\(pageData\)"/,
  'PDF page card button must keep its @click="selectPdfPage(pageData)" binding'
)

// Thumbnail is decorative; the visible 第 N 页 text names the button.
requireMatch(
  /<img :src="pageData\.src"[^>]*alt=""/,
  'PDF page thumbnail img must be marked decorative with alt=""'
)

// Focus ring: :focus-visible outline on the card, never removed anywhere.
requireMatch(
  /\.pdf-page-card:focus-visible\s*\{[^}]*outline:[^;}]*solid/,
  'PDF page cards must have a .pdf-page-card:focus-visible outline rule'
)
requireAbsent(
  /\.pdf-page-card[^{]*\{[^}]*outline:\s*(none|0)/,
  'PDF page card rules must never remove the focus outline'
)

if (failures.length > 0) {
  console.error('PDF page-card keyboard a11y contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('PDF page-card keyboard a11y contract passed.')
