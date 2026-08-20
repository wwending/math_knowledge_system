import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const readSource = (path) => readFileSync(resolve(process.cwd(), path), 'utf8')
const getTemplate = (source) => source.slice(
  source.indexOf('<template>') + '<template>'.length,
  source.indexOf('<script setup>')
)

const indexSource = readSource('index.html')
const dashboardSource = readSource('src/views/Dashboard.vue')
const loginSource = readSource('src/views/Login.vue')
const registerSource = readSource('src/views/Register.vue')
const registerTemplate = getTemplate(registerSource)
const registerVisibleText = registerTemplate
  .replace(/<[^>]+>/g, ' ')
  .replace(/{{[\s\S]*?}}/g, ' ')

assert.match(indexSource, /<html lang="zh-CN">/, 'document language should be zh-CN')
assert.match(
  indexSource,
  /<title>Math Knowledge - 高中数学错题与知识图谱系统<\/title>/,
  'browser title should use the product name and description'
)
assert.match(
  indexSource,
  /<link rel="icon" type="image\/svg\+xml" href="\/favicon\.svg" \/>/,
  'browser favicon should reference the project favicon'
)
assert.ok(!indexSource.includes('/vite.svg'), 'browser metadata should not reference the Vite favicon')
assert.ok(!indexSource.includes('<title>frontend</title>'), 'browser title should not expose the package name')

assert.ok(
  !dashboardSource.includes('生产鉴权后台'),
  'Dashboard should not expose the internal authentication-backend subtitle'
)
assert.ok(
  dashboardSource.includes('高中数学错题与知识图谱系统'),
  'Dashboard should show the Chinese product description'
)
assert.ok(
  dashboardSource.includes('上传图片或 PDF，系统将自动识别并整理题目内容。登录状态失效时会提示重新登录。'),
  'Dashboard upload guidance should use user-facing language'
)

assert.ok(
  loginSource.includes('整理错题、识别知识点、沉淀题库并快速组卷。'),
  'Login should describe the product workflow'
)
for (const statusCopy of [
  '正在获取注册状态，请稍后。',
  '当前支持自主注册，可直接创建账号。',
  '当前暂未开放自主注册，请联系管理员开通账号。',
  '暂时无法获取注册状态，请稍后重试或联系管理员。'
]) {
  assert.ok(loginSource.includes(statusCopy), `Login should include signup status copy: ${statusCopy}`)
}

assert.ok(
  registerTemplate.includes('创建账号后即可使用题目录入、题库和组卷功能。'),
  'Register should describe the features available after signup'
)
assert.ok(
  registerTemplate.includes('正在确认注册状态'),
  'Register should use a user-facing loading title'
)
assert.ok(
  registerTemplate.includes('正在确认当前是否开放注册，请稍后。'),
  'Register should use user-facing loading guidance'
)
assert.ok(
  !/capability/i.test(registerVisibleText),
  'Register user-visible template should not expose capability terminology'
)
assert.ok(
  registerSource.includes('publicSignupCapability'),
  'Register should preserve the internal signup capability contract'
)

console.log('Product branding and copy contract passed.')
