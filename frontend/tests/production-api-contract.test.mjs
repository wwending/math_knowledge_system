import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const apiConfigPath = resolve(process.cwd(), 'src/config/api.js')
const source = readFileSync(apiConfigPath, 'utf8')
const failures = []

if (!source.includes("const DEFAULT_DEV_API_BASE_URL = 'http://127.0.0.1:8000'")) {
  failures.push('development fallback no longer points to the local backend')
}

if (!/import\.meta\.env\.PROD\s*\?\s*''\s*:\s*DEFAULT_DEV_API_BASE_URL/.test(source)) {
  failures.push('production fallback is not the current-page origin')
}

if (!source.includes('import.meta.env.VITE_API_BASE_URL')) {
  failures.push('VITE_API_BASE_URL override is not supported')
}

if (!source.includes("const DEFAULT_API_V1_PREFIX = '/api/v1'")) {
  failures.push('production API prefix is not /api/v1')
}

if (!source.includes("const DEFAULT_STATIC_URL_PREFIX = '/static'")) {
  failures.push('production static prefix is not /static')
}

if (failures.length > 0) {
  console.error('Production API contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Production API contract passed.')
