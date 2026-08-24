import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Dashboard 主工作流 UX 契约（#73）：
// 1. 当前页签同步到 ?tab= 查询参数：进入时读取恢复、切换时写回 URL，
//    直链 /?tab=bank 可直达对应页签，刷新后停留原页签；
// 2. 非 admin 访问 users 页签维持回落「题目录入」，并把 URL 归一化；
// 3. 识别进度文案与结果状态 alert 集中在 aria-live="polite" 容器内，
//    键盘/读屏操作时状态变化可感知；
// 4. 保存成功文案讲人话，question_id 等技术编号折叠为可复制的次要信息；
// 5. 窄屏（≤1180px）侧栏改为抽屉导航：汉堡入口带可达性标注，
//    默认移出视口，不占据首屏主体。
const dashboardSource = readFileSync(resolve(process.cwd(), 'src/views/Dashboard.vue'), 'utf8')

const failures = []

const requireMatch = (pattern, message) => {
  if (!pattern.test(dashboardSource)) {
    failures.push(message)
  }
}
const requireAbsent = (pattern, message) => {
  if (pattern.test(dashboardSource)) {
    failures.push(message)
  }
}

// 1. 页签 ↔ ?tab= 双向同步。
requireMatch(
  /const DASHBOARD_TABS = \['upload', 'bank', 'history', 'papers', 'users'\]/,
  'Dashboard must declare the full valid tab list for ?tab= resolution'
)
requireMatch(
  /resolveRequestedTab\(route\.query\.tab\)/,
  'Dashboard must restore the initial tab from route.query.tab'
)
requireMatch(
  /watch\(activeMenu/,
  'Dashboard must watch activeMenu so tab changes are written back to the URL'
)
requireMatch(
  /router\.replace\(\{ query:/,
  'Dashboard must persist the active tab via router.replace({ query: ... })'
)

// 2. 非 admin 的 users 回落 + 挂载后 URL 归一化。
requireMatch(
  /tab === 'users' && !adminMode\.value/,
  'resolveRequestedTab must reject the users tab for non-admin users'
)
requireMatch(
  /if \(!adminMode\.value && activeMenu\.value === 'users'\)/,
  'Dashboard must keep the existing non-admin users fallback in onMounted'
)
requireMatch(
  /\n\s{2}syncTabQuery\(\)/,
  'onMounted must normalize ?tab= after auth/fallback resolution'
)

// 3. 异步识别状态对读屏器可感知。
requireMatch(
  /class="loading-state" aria-live="polite"/,
  'Recognition progress text must live inside an aria-live="polite" region'
)
requireMatch(
  /class="result-status-region" aria-live="polite"/,
  'Result status alerts must be wrapped in an aria-live="polite" container'
)

// 4. 保存成功文案去技术 ID，编号折叠为可复制次要信息。
requireAbsent(
  /保存成功，question_id/,
  'Save success message must not concatenate raw question_id into teacher-facing text'
)
requireMatch(
  /保存成功，题目已存入题库/,
  'Save success message must read naturally without technical identifiers'
)
requireMatch(
  /save-result-meta/,
  'The saved question id must be surfaced as secondary meta info'
)
requireMatch(
  /copyQuestionId/,
  'The saved question id must be copyable'
)
requireMatch(
  />复制编号<\/el-button>/,
  'The copy control must be labelled 复制编号'
)

// 5. 窄屏抽屉导航。
requireMatch(
  /:aria-expanded="mobileNavOpen"/,
  'The nav toggle button must expose aria-expanded'
)
requireMatch(
  /aria-controls="dashboard-sidebar"/,
  'The nav toggle button must point at the sidebar via aria-controls'
)
requireMatch(
  /:class="\{ 'is-open': mobileNavOpen \}"/,
  'The sidebar must bind its drawer state to the is-open class'
)
requireMatch(
  /@click="closeMobileNav\(\)"/,
  'The drawer backdrop must close the navigation on click'
)
requireMatch(
  /\.sidebar-backdrop\s*\{[^}]*display:\s*none/,
  'The backdrop must stay out of the desktop layout entirely'
)
requireMatch(
  /@media \(max-width:\s*1180px\)\s*\{[\s\S]*?transform:\s*translateX\(-105%\)/,
  'Under the 1180px breakpoint the sidebar must be moved off-canvas by default'
)
requireMatch(
  /\.nav-toggle\s*\{[^}]*display:\s*none/,
  'The hamburger toggle must be hidden on desktop widths'
)

if (failures.length > 0) {
  console.error('Dashboard workflow UX contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Dashboard workflow UX contract passed.')
