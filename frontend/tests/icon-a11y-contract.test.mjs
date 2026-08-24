import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Icon-only controls must expose an accessible name (#70): screen-reader users
// otherwise get an unnamed button/checkbox with no clue about its purpose.
const readSource = (relPath) => readFileSync(resolve(process.cwd(), relPath), 'utf8')

const failures = []
const requireMatch = (source, pattern, message) => {
  if (!pattern.test(source)) {
    failures.push(message)
  }
}

// Refresh buttons: icon-only el-button, name lands on the native <button> root.
requireMatch(
  readSource('src/components/HistoryPanel.vue'),
  /<el-button aria-label="刷新题目监控"[^>]*@click="fetchHistory"/,
  'HistoryPanel refresh button must carry aria-label 刷新题目监控'
)
requireMatch(
  readSource('src/components/BankPanel.vue'),
  /<el-button aria-label="刷新题库列表"[^>]*@click="fetchQuestions"/,
  'BankPanel refresh button must carry aria-label 刷新题库列表'
)
requireMatch(
  readSource('src/components/PaperPanel.vue'),
  /<el-button aria-label="刷新试卷列表"[^>]*@click="fetchPapers"/,
  'PaperPanel refresh button must carry aria-label 刷新试卷列表'
)

// Question-selection checkboxes: aria-label is an Element Plus prop rendered on
// the inner <input>, and must include the question id for disambiguation.
requireMatch(
  readSource('src/components/BankPanel.vue'),
  /<el-checkbox\s+:aria-label="`选择题目 #\$\{item\.id\}`"/,
  'BankPanel question checkbox must bind aria-label 选择题目 #<id>'
)
requireMatch(
  readSource('src/components/PaperPanel.vue'),
  /<el-checkbox :aria-label="`选择题目 #\$\{question\.id\}`"/,
  'PaperPanel question-picker checkbox must bind aria-label 选择题目 #<id>'
)

if (failures.length > 0) {
  console.error('Icon a11y contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Icon a11y contract passed.')
