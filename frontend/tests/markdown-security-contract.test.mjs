import assert from 'node:assert/strict'

import {
  createMarkdownRenderer,
  normalizeLatexDelimiters
} from '../src/utils/markdownRenderer.mjs'

const md = createMarkdownRenderer()
const renderMarkdown = (content) => md.render(normalizeLatexDelimiters(content))

const rawHtmlVectors = [
  '<script>alert(1)</script>',
  '<img src=x onerror="alert(1)">',
  '<svg onload="alert(1)"></svg>',
  '<a href="javascript:alert(1)">x</a>'
]

for (const vector of rawHtmlVectors) {
  const rendered = renderMarkdown(vector)
  assert.match(rendered, /&lt;/, `raw HTML must be escaped: ${vector}`)
  assert.doesNotMatch(rendered, /<(?:script|img|svg|a)\b/i, `raw HTML must not create DOM: ${vector}`)
  assert.doesNotMatch(rendered, /<[^>]+\son(?:error|load)\s*=/i, `event handlers must not be executable: ${vector}`)
  assert.doesNotMatch(rendered, /href\s*=\s*["']?(?:javascript|vbscript|file|data):/i, `dangerous href must not be emitted: ${vector}`)
}

const dangerousMarkdownLinks = [
  '[x](javascript:alert(1))',
  '[x](vbscript:msgbox(1))',
  '[x](file:///etc/passwd)',
  '[x](data:text/html;base64,PHNjcmlwdD4=)',
  '![x](data:image/png;base64,iVBORw0KGgo=)'
]

for (const vector of dangerousMarkdownLinks) {
  const rendered = renderMarkdown(vector)
  assert.doesNotMatch(rendered, /(?:href|src)\s*=\s*["']?(?:javascript|vbscript|file|data):/i, `dangerous URL must not be emitted: ${vector}`)
}

const safeMarkdown = renderMarkdown(`# 标题

**加粗**

- 列表

行内公式：$x^2 + y^2$

块公式：

$$
a^2+b^2=c^2
$$`)

assert.match(safeMarkdown, /<h1>标题<\/h1>/)
assert.match(safeMarkdown, /<strong>加粗<\/strong>/)
assert.match(safeMarkdown, /<ul>[\s\S]*<li>列表<\/li>[\s\S]*<\/ul>/)
assert.match(safeMarkdown, /<mjx-container[^>]*>/)
assert.match(safeMarkdown, /<msup><mi>x<\/mi><mn>2<\/mn><\/msup>/)
assert.match(safeMarkdown, /<mjx-container[^>]*display="true"/)
assert.match(safeMarkdown, /<msup><mi>a<\/mi><mn>2<\/mn><\/msup>/)

const bareUrl = renderMarkdown('访问 https://example.com')
assert.doesNotMatch(bareUrl, /<a\b/i, 'bare URLs must not be linkified')
assert.match(bareUrl, /https:\/\/example\.com/)

const safeLink = renderMarkdown('[示例](https://example.com)')
assert.match(safeLink, /<a href="https:\/\/example\.com">示例<\/a>/)
assert.doesNotMatch(safeLink, /target="_blank"/)

console.log('Markdown security contract passed')
