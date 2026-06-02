import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const authUtilPath = resolve(process.cwd(), 'src/utils/auth.js')
const mainPath = resolve(process.cwd(), 'src/main.js')
const routerPath = resolve(process.cwd(), 'src/router/index.js')

const authSource = readFileSync(authUtilPath, 'utf8')
const mainSource = readFileSync(mainPath, 'utf8')
const routerSource = readFileSync(routerPath, 'utf8')
const failures = []

if (/localStorage/.test(authSource)) {
  failures.push('auth utils still reference localStorage')
}

if (!/sessionStorage/.test(authSource)) {
  failures.push('auth utils do not persist access token in sessionStorage')
}

if (!authSource.includes('/auth/login')) {
  failures.push('new phone login endpoint is not wired in auth utils')
}

if (!authSource.includes('/auth/refresh')) {
  failures.push('refresh session endpoint is not wired in auth utils')
}

if (!authSource.includes('/auth/logout')) {
  failures.push('logout endpoint is not wired in auth utils')
}

if (!authSource.includes('/auth/change-password')) {
  failures.push('change password endpoint is not wired in auth utils')
}

if (!/withCredentials\s*=\s*true/.test(mainSource)) {
  failures.push('axios withCredentials is not enabled for refresh cookie transport')
}

if (!mainSource.includes('PASSWORD_CHANGE_REQUIRED_DETAIL')) {
  failures.push('password change required redirect handling is missing')
}

if (!routerSource.includes('/change-password')) {
  failures.push('change password route is missing')
}

if (!routerSource.includes('needsPasswordChange')) {
  failures.push('router does not guard must_change_password users')
}

if (failures.length > 0) {
  console.error('Auth session contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Auth session contract passed.')
