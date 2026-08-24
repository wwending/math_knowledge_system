import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// 面板状态深链（#75）：搜索词/筛选条件/选中试卷同步到 URL query，
// 刷新与分享可恢复，且不产生中间态历史。
// 契约：
// 1. 各面板使用带前缀的专属键（bank_ / user_ / paper_），互不冲突；
//    `tab` 键保留给 Dashboard 页签深链（#73），面板不得占用；
// 2. 挂载时从 URL 读取恢复，状态变化时回写；
// 3. 只允许经 urlQueryState 走 router.replace，禁止 router.push；
// 4. 枚举筛选（角色/状态）必须按合法值校验；试卷 ID 必须做数值解析。

const utilSource = readFileSync(resolve(process.cwd(), 'src/utils/urlQueryState.js'), 'utf8')
const bankSource = readFileSync(resolve(process.cwd(), 'src/components/BankPanel.vue'), 'utf8')
const usersSource = readFileSync(resolve(process.cwd(), 'src/components/UserManagementPanel.vue'), 'utf8')
const paperSource = readFileSync(resolve(process.cwd(), 'src/components/PaperPanel.vue'), 'utf8')

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

// 1. 同步工具统一走 router.replace，空值删除键，并声明 tab 键保留给 #73。
requireMatch(
  utilSource,
  /return router\.replace\(\{ query \}\)/,
  'urlQueryState must persist state via router.replace({ query })'
)
requireMatch(
  utilSource,
  /delete query\[key\]/,
  'urlQueryState must remove the query key for empty values'
)
requireMatch(
  utilSource,
  /`tab` 键保留给 Dashboard 页签深链（#73）/,
  'urlQueryState must document that the tab key is reserved for the #73 dashboard deep link'
)

for (const [name, source] of [
  ['BankPanel', bankSource],
  ['UserManagementPanel', usersSource],
  ['PaperPanel', paperSource]
]) {
  requireMatch(
    source,
    /import \{ readStringQuery, replaceQueryValues \} from '\.\.\/utils\/urlQueryState'/,
    `${name} must go through the shared urlQueryState helpers`
  )
  // 3. 禁止绕过工具直接 push 历史；replace 只允许出现在工具内部。
  requireAbsent(
    source,
    /router\.push\(/,
    `${name} must not use router.push; URL sync must not create intermediate history entries`
  )
  requireAbsent(
    source,
    /router\.replace\(/,
    `${name} must not call router.replace directly; use replaceQueryValues so empty values drop keys`
  )
  // 1. 面板不得读写保留键 tab。
  requireAbsent(
    source,
    /['"]tab['"]/,
    `${name} must not touch the reserved "tab" query key owned by #73`
  )
}

// 2a. BankPanel：?bank_q= 恢复 + 回写。
requireMatch(
  bankSource,
  /readStringQuery\(route, 'bank_q'\)/,
  'BankPanel must restore its search keyword from ?bank_q='
)
requireMatch(
  bankSource,
  /watch\(keyword, \(value\) => \{\s*replaceQueryValues\(router, route, \{ bank_q: value \}\)/,
  'BankPanel must write the search keyword back to ?bank_q= on change'
)

// 2b. UserManagementPanel：三个筛选键恢复 + 回写 + 枚举校验。
requireMatch(
  usersSource,
  /readStringQuery\(route, 'user_q'\)/,
  'UserManagementPanel must restore the keyword filter from ?user_q='
)
requireMatch(
  usersSource,
  /readStringQuery\(route, 'user_role'\)/,
  'UserManagementPanel must restore the role filter from ?user_role='
)
requireMatch(
  usersSource,
  /readStringQuery\(route, 'user_status'\)/,
  'UserManagementPanel must restore the status filter from ?user_status='
)
requireMatch(
  usersSource,
  /roleOptions\.some\(\(item\) => item\.value === queryRole\) \? queryRole : ''/,
  'UserManagementPanel must reject unknown role values from the URL'
)
requireMatch(
  usersSource,
  /statusOptions\.some\(\(item\) => item\.value === queryStatus\) \? queryStatus : ''/,
  'UserManagementPanel must reject unknown status values from the URL'
)
requireMatch(
  usersSource,
  /watch\(filters, \(\) => \{\s*replaceQueryValues\(router, route, \{\s*user_q: filters\.q,\s*user_role: filters\.role,\s*user_status: filters\.status\s*\}\)/,
  'UserManagementPanel must write all three filters back to the URL on change'
)

// 2c. PaperPanel：?paper_id= 数值解析恢复 + 选中变化回写。
requireMatch(
  paperSource,
  /Number\.parseInt\(readStringQuery\(route, 'paper_id'\), 10\)/,
  'PaperPanel must parse ?paper_id= as an integer instead of trusting the raw string'
)
requireMatch(
  paperSource,
  /Number\.isInteger\(requestedPaperId\) && requestedPaperId > 0/,
  'PaperPanel must ignore non-positive or unparsable paper ids'
)
requireMatch(
  paperSource,
  /watch\(selectedPaperId, \(paperId\) => \{\s*replaceQueryValues\(router, route, \{ paper_id: paperId \?\? '' \}\)/,
  'PaperPanel must write the selected paper back to ?paper_id= and clear it when deselected'
)

if (failures.length > 0) {
  console.error('URL state sync contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('URL state sync contract passed.')
