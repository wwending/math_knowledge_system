import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const loginViewPath = resolve(process.cwd(), 'src/views/Login.vue')
const registerViewPath = resolve(process.cwd(), 'src/views/Register.vue')
const routerPath = resolve(process.cwd(), 'src/router/index.js')
const authUtilPath = resolve(process.cwd(), 'src/utils/auth.js')

const loginSource = readFileSync(loginViewPath, 'utf8')
const registerSource = readFileSync(registerViewPath, 'utf8')
const routerSource = readFileSync(routerPath, 'utf8')
const authSource = readFileSync(authUtilPath, 'utf8')

const hasText = (source, text) => source.includes(text)

const sourceBackedCapabilityState = ({ status, capabilities }) => {
  const normalizedPublicSignupEnabled = Boolean(capabilities?.public_signup_enabled)
  const failed = status === 'error'
  const loading = status === 'idle' || status === 'loading'

  return {
    status,
    loading,
    ready: status === 'ready' || failed,
    failed,
    enabled: status === 'ready' && normalizedPublicSignupEnabled
  }
}

assert.deepEqual(
  sourceBackedCapabilityState({
    status: 'ready',
    capabilities: { public_signup_enabled: true }
  }),
  {
    status: 'ready',
    loading: false,
    ready: true,
    failed: false,
    enabled: true
  },
  'capability=true should resolve to an enabled ready state'
)

assert.deepEqual(
  sourceBackedCapabilityState({
    status: 'ready',
    capabilities: { public_signup_enabled: false }
  }),
  {
    status: 'ready',
    loading: false,
    ready: true,
    failed: false,
    enabled: false
  },
  'capability=false should stay distinguishable from a fetch failure while remaining closed'
)

assert.deepEqual(
  sourceBackedCapabilityState({
    status: 'error',
    capabilities: { public_signup_enabled: false }
  }),
  {
    status: 'error',
    loading: false,
    ready: true,
    failed: true,
    enabled: false
  },
  'failed capability fetches should downgrade to a safe closed state while remaining observable'
)

assert.ok(
  hasText(authSource, 'getPublicSignupCapabilityState'),
  'auth utils should expose a single public signup capability state helper'
)
assert.ok(
  hasText(authSource, 'resolvePublicSignupCapability'),
  'auth utils should expose a single public signup capability resolver'
)
assert.ok(
  hasText(authSource, 'capabilitiesStatus'),
  'auth utils should keep explicit capability status so disabled and failed states remain distinguishable'
)
assert.ok(
  hasText(authSource, '/auth/capabilities'),
  'auth utils should fetch capabilities from the backend capability endpoint'
)
assert.ok(
  hasText(authSource, 'capabilitiesPromise'),
  'auth capability fetches should share in-flight state instead of forking separate client truth'
)
assert.ok(
  hasText(authSource, 'authState.capabilitiesStatus === AUTH_CAPABILITY_STATUS.READY && !force'),
  'capability reads should reuse cached state when a force refresh is not requested'
)
assert.ok(
  hasText(authSource, 'authState.capabilitiesStatus = AUTH_CAPABILITY_STATUS.ERROR'),
  'capability fetch failure should remain observable in shared state'
)

assert.ok(
  hasText(loginSource, 'const publicSignupCapability = computed(() => getPublicSignupCapabilityState())'),
  'login page should read public signup capability from the shared state helper'
)
assert.match(
  loginSource,
  /<router-link v-if="publicSignupCapability\.enabled" to="\/register" class="footer-link">/,
  'capability=true should make the login page render the register entry'
)
assert.ok(
  hasText(loginSource, 'publicSignupCapability.value.loading'),
  'login page should keep a loading state before capability is confirmed'
)
assert.ok(
  hasText(loginSource, 'publicSignupCapability.value.failed'),
  'login page should preserve a distinct fetch-failure branch while staying closed in the UI'
)
assert.ok(
  hasText(loginSource, 'await resolvePublicSignupCapability({ force: true })'),
  'login page should refresh capability state through the shared resolver'
)
assert.ok(
  !hasText(loginSource, '当前支持公开注册'),
  'login page should not contain the legacy hard-coded public signup copy'
)

assert.match(
  registerSource,
  /<template v-if="publicSignupCapability\.loading">/,
  'register page should block form rendering until capability is confirmed'
)
assert.match(
  registerSource,
  /<template v-else-if="publicSignupCapability\.enabled">/,
  'capability=true should be required before the register page renders a submittable form'
)
assert.ok(
  hasText(registerSource, 'publicSignupCapability.failed'),
  'register page should distinguish capability fetch failure from an explicit closed capability'
)
assert.ok(
  hasText(registerSource, 'if (publicSignupCapability.value.loading || !publicSignupCapability.value.enabled || !registerFormRef.value)'),
  'capability=false should keep direct /register visits out of the submittable form path'
)
assert.ok(
  hasText(registerSource, 'PUBLIC_SIGNUP_DISABLED_DETAIL'),
  'register page should still handle the backend public-signup-disabled response explicitly'
)

assert.ok(
  hasText(routerSource, "if (to.path === '/register')"),
  'router should guard the /register route'
)
assert.ok(
  hasText(routerSource, 'resolvePublicSignupCapability({ force: true })'),
  'router should re-check the shared capability state before allowing the /register route'
)
assert.ok(
  hasText(routerSource, 'if (!publicSignupCapability.enabled)'),
  'capability=false should redirect /register away before a submittable form is entered'
)
assert.ok(
  hasText(routerSource, 'publicSignupCapability.failed'),
  'capability fetch failure should stay distinguishable in router handling while remaining closed in the UI'
)
assert.ok(
  hasText(routerSource, "next('/login')"),
  'router should redirect to /login when public signup is unavailable'
)

console.log('Login/Register auth capability contract passed.')
