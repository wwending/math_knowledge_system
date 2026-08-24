import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Login/Register inputs used to rely on placeholders alone (#71): screen
// readers announced nothing and password managers could not recognize the
// forms. Every input must keep a programmatic label plus name/autocomplete
// semantics so browsers can save and refill credentials.
const loginSource = readFileSync(resolve(process.cwd(), 'src/views/Login.vue'), 'utf8')
const registerSource = readFileSync(resolve(process.cwd(), 'src/views/Register.vue'), 'utf8')

const failures = []
const requireMatch = (source, pattern, message) => {
  if (!pattern.test(source)) {
    failures.push(message)
  }
}

// Login: the phone number identifies an existing account.
requireMatch(
  loginSource,
  /v-model="loginForm\.phone"[^>]*name="phone"[^>]*autocomplete="tel"[^>]*inputmode="numeric"[^>]*:spellcheck="false"[^>]*aria-label="手机号"/,
  'Login phone input must keep name, autocomplete="tel", numeric inputmode, spellcheck=false and aria-label'
)
requireMatch(
  loginSource,
  /type="password"[^>]*name="password"[^>]*autocomplete="current-password"[^>]*aria-label="密码"/,
  'Login password input must keep name, autocomplete="current-password" and aria-label'
)

// Register: the phone becomes the saved credential username.
requireMatch(
  registerSource,
  /v-model="registerForm\.phone"[^>]*name="phone"[^>]*autocomplete="username"[^>]*inputmode="numeric"[^>]*:spellcheck="false"[^>]*aria-label="手机号"/,
  'Register phone input must keep name, autocomplete="username", numeric inputmode, spellcheck=false and aria-label'
)
requireMatch(
  registerSource,
  /v-model="registerForm\.displayName"[^>]*name="displayName"[^>]*autocomplete="name"[^>]*aria-label="显示名称"/,
  'Register display-name input must keep name, autocomplete="name" and aria-label'
)
requireMatch(
  registerSource,
  /type="password"[^>]*name="password"[^>]*autocomplete="new-password"[^>]*aria-label="密码"/,
  'Register password input must keep name, autocomplete="new-password" and aria-label'
)

if (failures.length > 0) {
  console.error('Auth form semantics a11y contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Auth form semantics a11y contract passed.')
