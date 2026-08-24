import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Paper cards are the only entry to a paper's detail (#69). The card used to
// be a clickable el-card, so keyboard users could never open any paper. It
// must stay a native button (Enter/Space come free) with a visible focus ring.
const source = readFileSync(resolve(process.cwd(), 'src/components/PaperPanel.vue'), 'utf8')

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
  /<button v-for="paper in papers"[^>]*type="button"[^>]*class="paper-card"/,
  'Paper list cards must be native <button type="button"> elements'
)
requireMatch(
  /class="paper-card"[^>]*@click="openPaperDetail\(paper\.id\)"/,
  'Paper card button must keep its @click="openPaperDetail(paper.id)" binding'
)

// Focus ring: :focus-visible outline on the card, never removed anywhere.
requireMatch(
  /\.paper-card:focus-visible\s*\{[^}]*outline:[^;}]*solid/,
  'Paper cards must have a .paper-card:focus-visible outline rule'
)
requireAbsent(
  /\.paper-card[^{]*\{[^}]*outline:\s*(none|0)/,
  'Paper card rules must never remove the focus outline'
)

if (failures.length > 0) {
  console.error('Paper card keyboard a11y contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Paper card keyboard a11y contract passed.')
