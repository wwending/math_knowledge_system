import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// 题库/历史列表面板的 UX 契约（#74）：
// 1. 列表 flex 子项可收缩，窄窗口不横向溢出；
// 2. 详情弹窗 980px 以下单列；
// 3. 达到列表拉取上限时给出「仅显示前 N 条」提示；
// 4. 已选题数对读屏器可感知；
// 5. 空态 CTA 直达「题目录入」页签，术语与侧边栏一致。
const bankSource = readFileSync(resolve(process.cwd(), 'src/components/BankPanel.vue'), 'utf8')
const historySource = readFileSync(resolve(process.cwd(), 'src/components/HistoryPanel.vue'), 'utf8')
const dashboardSource = readFileSync(resolve(process.cwd(), 'src/views/Dashboard.vue'), 'utf8')

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

// 1. info-box 必须允许收缩（min-width: 0），否则 nowrap 内容把列表撑出横向滚动。
for (const [name, source] of [['BankPanel', bankSource], ['HistoryPanel', historySource]]) {
  requireMatch(
    source,
    /\.info-box\s*\{[^}]*min-width:\s*0/,
    `${name} .info-box must declare min-width: 0 so the list can shrink on narrow windows`
  )
}

// 2. 详情弹窗在 980px 断点下改单列，对齐 PaperPanel。
for (const [name, source] of [['BankPanel', bankSource], ['HistoryPanel', historySource]]) {
  requireMatch(
    source,
    /@media \(max-width:\s*980px\)\s*\{[^@]*\.detail-layout\s*\{[^}]*flex-direction:\s*column/,
    `${name} must collapse .detail-layout to a single column under the 980px breakpoint`
  )
}

// 3. 列表静默截断：达到上限时必须出现「仅显示前 N 条」提示。
requireMatch(
  bankSource,
  /v-if="!loading && list\.length >= questionListLimit"/,
  'BankPanel must show the limit alert once the question list reaches its fetch limit'
)
requireMatch(
  bankSource,
  /仅显示前 \$\{questionListLimit\} 条/,
  'BankPanel limit alert must state 仅显示前 N 条'
)
requireMatch(
  bankSource,
  /questions\?limit=\$\{questionListLimit\}/,
  'BankPanel must fetch questions with the questionListLimit constant'
)
requireMatch(
  historySource,
  /v-if="!loading && list\.length >= historyListLimit"/,
  'HistoryPanel must show the limit alert once the history list reaches its fetch limit'
)
requireMatch(
  historySource,
  /仅显示前 \$\{historyListLimit\} 条/,
  'HistoryPanel limit alert must state 仅显示前 N 条'
)
requireMatch(
  historySource,
  /history\?limit=\$\{historyListLimit\}/,
  'HistoryPanel must fetch history with the historyListLimit constant'
)

// 4. 已选题数变化必须对辅助技术可感知。
requireMatch(
  bankSource,
  /class="selection-summary" aria-live="polite"/,
  'BankPanel selection summary must carry aria-live="polite"'
)

// 5. 空态 CTA 一键切到「题目录入」页签；不得再出现旧术语「题目采集」，也不得只弹 toast。
requireMatch(
  bankSource,
  /defineEmits\(\['paper-created', 'go-upload'\]\)/,
  'BankPanel must emit go-upload from defineEmits'
)
requireMatch(
  bankSource,
  />去题目录入<\/el-button>/,
  'BankPanel empty-state CTA must read 去题目录入 and trigger the tab switch'
)
requireAbsent(
  bankSource,
  /题目采集/,
  'BankPanel must not use the outdated term 题目采集; the sidebar calls it 题目录入'
)
requireMatch(
  dashboardSource,
  /<bank-panel @paper-created="activeMenu = 'papers'" @go-upload="activeMenu = 'upload'" \/>/,
  'Dashboard must switch to the upload tab when BankPanel emits go-upload'
)

if (failures.length > 0) {
  console.error('List panel UX contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('List panel UX contract passed.')
