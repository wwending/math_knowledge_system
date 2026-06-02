import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dashboardPath = resolve(process.cwd(), 'src/views/Dashboard.vue')
const userPanelPath = resolve(process.cwd(), 'src/components/UserManagementPanel.vue')

const dashboardSource = readFileSync(dashboardPath, 'utf8')
const panelSource = readFileSync(userPanelPath, 'utf8')
const failures = []

if (!dashboardSource.includes("index=\"users\"")) {
  failures.push('dashboard is missing the user management navigation entry')
}

if (!panelSource.includes('/admin/users')) {
  failures.push('user list/create admin endpoint is not referenced')
}

if (!panelSource.includes('/reset-password')) {
  failures.push('admin reset password endpoint is not referenced')
}

if (!panelSource.includes('/status')) {
  failures.push('admin enable/disable endpoint is not referenced')
}

if (!panelSource.includes('/role')) {
  failures.push('admin role change endpoint is not referenced')
}

if (!panelSource.includes('已禁用，无法登录')) {
  failures.push('disabled user guidance is missing')
}

if (!panelSource.includes('下次登录后必须修改密码')) {
  failures.push('must_change_password guidance is missing')
}

if (!panelSource.includes('当前不开放自助找回密码，请通过管理员重置')) {
  failures.push('password recovery admin-contact guidance is missing')
}

if (failures.length > 0) {
  console.error('Admin user management contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Admin user management contract passed.')
