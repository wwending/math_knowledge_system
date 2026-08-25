import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// 反馈收件箱（#98）契约：
// 1. Dashboard 接线：菜单项全员可见（无 v-if 门禁）、面板挂载、页签白名单、标题分支；
// 2. 提交表单：正文限长、类型三选一、截图非自动上传且上限与后端一致；
// 3. 权限分叉：普通用户走 /feedback，管理员走 /admin/feedback 且以 isAdminUser 判定；
// 4. 撤回等破坏性操作必须先 ElMessageBox.confirm。

const dashboardSource = readFileSync(resolve(process.cwd(), 'src/views/Dashboard.vue'), 'utf8')
const panelSource = readFileSync(resolve(process.cwd(), 'src/components/FeedbackInboxPanel.vue'), 'utf8')

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

// 1. Dashboard 接线。
requireMatch(
  dashboardSource,
  /<el-menu-item index="feedback">/,
  'Dashboard must register the feedback tab as a sidebar menu item'
)
requireAbsent(
  dashboardSource,
  /v-if=[^\n]*index="feedback"/,
  'Dashboard must not role-gate the feedback menu item; every logged-in user can submit feedback'
)
requireMatch(
  dashboardSource,
  /import FeedbackInboxPanel from '\.\.\/components\/FeedbackInboxPanel\.vue'/,
  'Dashboard must import FeedbackInboxPanel'
)
requireMatch(
  dashboardSource,
  /<feedback-inbox-panel \/>/,
  'Dashboard must mount <feedback-inbox-panel />'
)
requireMatch(
  dashboardSource,
  /const DASHBOARD_TABS = \[[^\]]*'feedback'[^\]]*\]/,
  "DASHBOARD_TABS must include 'feedback' so ?tab=feedback deep links resolve"
)
requireMatch(
  dashboardSource,
  /activeMenu\.value === 'feedback'\)\s*\{\s*return '反馈中心'/,
  'pageTitle must map the feedback tab to 反馈中心'
)

// 2. 提交表单。
requireMatch(
  panelSource,
  /const FEEDBACK_MAX_SCREENSHOTS = 5/,
  'FeedbackInboxPanel must mirror the backend MAX_FEEDBACK_SCREENSHOTS limit of 5'
)
requireMatch(
  panelSource,
  /:maxlength="500"/,
  'FeedbackInboxPanel must cap feedback text at 500 characters'
)
requireMatch(
  panelSource,
  /show-word-limit/,
  'FeedbackInboxPanel must surface the remaining character budget via show-word-limit'
)
for (const [value, label] of [
  ['bug', '问题'],
  ['feature', '需求'],
  ['suggestion', '建议']
]) {
  requireMatch(
    panelSource,
    new RegExp(`<el-radio-button value="${value}">${label}<\\/el-radio-button>`),
    `FeedbackInboxPanel must offer the ${value}（${label}）category radio option`
  )
}
for (const uploadAttr of ['action="#"', ':auto-upload="false"', 'multiple', 'accept=".jpg,.jpeg,.png"']) {
  requireMatch(
    panelSource,
    new RegExp(uploadAttr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')),
    `FeedbackInboxPanel el-upload must declare ${uploadAttr} (files submit with the form, never auto-uploaded)`
  )
}
requireMatch(
  panelSource,
  /appendScreenshots\(formData, createFileList\.value, 'screenshots'\)/,
  "FeedbackInboxPanel must append screenshot files under the 'screenshots' field on create"
)
requireMatch(
  panelSource,
  /appendScreenshots\(formData, editFileList\.value, 'new_screenshots'\)/,
  "FeedbackInboxPanel must append edited screenshots under the 'new_screenshots' field"
)
requireMatch(
  panelSource,
  /append\('remove_screenshot_ids',/,
  "FeedbackInboxPanel must send removals via the 'remove_screenshot_ids' field"
)

// 3. 权限分叉。
requireMatch(
  panelSource,
  /isAdminUser\(currentUser\.value\)/,
  'FeedbackInboxPanel must derive admin mode from isAdminUser(authState.currentUser)'
)
requireMatch(
  panelSource,
  /axios\.post\(`\$\{API_V1_BASE_URL\}\/feedback`, formData\)/,
  'FeedbackInboxPanel must POST multipart form data to /feedback for submissions'
)
requireMatch(
  panelSource,
  /axios\.patch\(\s*`\$\{API_V1_BASE_URL\}\/feedback\/\$\{editTarget\.value\.id\}`, formData\)/,
  'FeedbackInboxPanel must PATCH own feedback edits as multipart form data'
)
requireMatch(
  panelSource,
  /\/admin\/feedback\/\$\{reviewTarget\.value\.id\}\/status/,
  'FeedbackInboxPanel must route review actions through /admin/feedback/{id}/status'
)
requireMatch(
  panelSource,
  /row\.user_id == null \|\| row\.user_id === currentUserId\.value/,
  'FeedbackInboxPanel must restrict edit/withdraw actions to the submitter while pending'
)

// 4. 破坏性操作确认与状态文案。
requireMatch(
  panelSource,
  /ElMessageBox\.confirm\(/,
  'FeedbackInboxPanel must confirm before destructive actions such as withdrawing feedback'
)
for (const label of ['待处理', '已采纳', '已拒绝']) {
  requireMatch(
    panelSource,
    new RegExp(label),
    `FeedbackInboxPanel must render the ${label} status label in Chinese`
  )
}

if (failures.length > 0) {
  console.error('Feedback panel contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Feedback panel contract passed.')
