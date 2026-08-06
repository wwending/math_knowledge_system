import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'

import { KATEX_OPTIONS, renderMarkdown } from '../src/utils/markdownRenderer.mjs'

assert.deepEqual(KATEX_OPTIONS, {
  throwOnError: false,
  trust: false,
  strict: 'warn',
  maxSize: 10,
  maxExpand: 1000,
  globalGroup: false,
  output: 'htmlAndMathml'
})
assert.equal(Object.isFrozen(KATEX_OPTIONS), true)

const assertNoExecutableHtml = (rendered, vector) => {
  assert.doesNotMatch(rendered, /<script\b|<[^>]+\son(?:error|load)\s*=/i, `executable HTML must not be emitted: ${vector}`)
  assert.doesNotMatch(rendered, /(?:href|src)\s*=\s*["']?(?:javascript|vbscript|file|data):/i, `dangerous URL must not be emitted: ${vector}`)
}

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
  assertNoExecutableHtml(rendered, vector)
}

const dangerousMarkdownLinks = [
  '[x](javascript:alert(1))',
  '[x](vbscript:msgbox(1))',
  '[x](file:///etc/passwd)',
  '[x](data:text/html;base64,PHNjcmlwdD4=)',
  '![x](data:image/png;base64,iVBORw0KGgo=)'
]

for (const vector of dangerousMarkdownLinks) {
  assertNoExecutableHtml(renderMarkdown(vector), vector)
}

const dangerousTexVectors = [
  String.raw`$\href{javascript:alert(1)}{x}$`,
  String.raw`$\href{data:text/html;base64,PHNjcmlwdD4=}{x}$`,
  String.raw`$\href{file:///etc/passwd}{x}$`,
  String.raw`$\url{javascript:alert(1)}$`,
  String.raw`$\includegraphics{https://attacker.example/image.png}$`,
  String.raw`$\htmlClass{evil-overlay}{x}$`,
  String.raw`$\htmlId{application-root}{x}$`,
  String.raw`$\htmlStyle{position:fixed;top:0;left:0;width:100%;height:100%}{x}$`,
  String.raw`$\htmlData{payload=evil}{x}$`
]

for (const vector of dangerousTexVectors) {
  const rendered = renderMarkdown(vector)
  assertNoExecutableHtml(rendered, vector)
  assert.doesNotMatch(rendered, /href="(?:javascript|data|file):/i)
  assert.doesNotMatch(rendered, /src="https:\/\/attacker\.example/i)
  assert.doesNotMatch(rendered, /class="evil-overlay"/i)
  assert.doesNotMatch(rendered, /id="application-root"/i)
  assert.doesNotMatch(rendered, /style="[^"]*position\s*:\s*fixed/i)
  assert.doesNotMatch(rendered, /data-payload\s*=/i)
}

for (const vector of [String.raw`$\require{html}x$`, String.raw`$\require{physics}\qty{x}$`]) {
  const rendered = renderMarkdown(vector)
  assert.match(rendered, /\\require/, `dynamic package command must remain unsupported: ${vector}`)
  assertNoExecutableHtml(rendered, vector)
}

const oversizedRule = renderMarkdown(String.raw`$\rule{500em}{500em}$`)
assert.doesNotMatch(oversizedRule, /style="[^"]*(?:width|height)\s*:\s*500em/i)
assert.doesNotMatch(oversizedRule, /position\s*:\s*(?:fixed|absolute)/i)

const hugeText = renderMarkdown(String.raw`$\Huge x$`)
assert.match(hugeText, /class="katex"/)
assert.doesNotMatch(hugeText, /position\s*:\s*(?:fixed|absolute)/i)

const recursiveMacro = String.raw`$\def\a{\a}\a$`
const macroResult = spawnSync(
  process.execPath,
  [
    '--input-type=module',
    '--eval',
    "import { renderMarkdown } from './src/utils/markdownRenderer.mjs'; process.stdout.write(renderMarkdown(String.raw`$\\def\\a{\\a}\\a$`))"
  ],
  { cwd: new URL('..', import.meta.url), encoding: 'utf8', timeout: 2_000 }
)
assert.equal(macroResult.error, undefined, 'recursive macro rendering must finish before timeout')
assert.equal(macroResult.status, 0)
assert.match(macroResult.stdout, /katex-error/)
assertNoExecutableHtml(macroResult.stdout, recursiveMacro)

const validFormulae = [
  ['$x^2+y^2$', false],
  [String.raw`$$
\frac{-b\pm\sqrt{b^2-4ac}}{2a}
$$`, true],
  [String.raw`$$
\begin{aligned}
a+b &= c \\
c+d &= e
\end{aligned}
$$`, true],
  [String.raw`$$
f(x)=
\begin{cases}
x^2, & x\ge 0 \\
-x, & x<0
\end{cases}
$$`, true],
  [String.raw`$$
\begin{pmatrix}
1 & 2 \\
3 & 4
\end{pmatrix}
$$`, true],
  [String.raw`$\text{函数在区间内单调递增}$`, false]
]

for (const [formula, displayMode] of validFormulae) {
  const rendered = renderMarkdown(formula)
  assert.match(rendered, /class="katex"/)
  if (displayMode) {
    assert.match(rendered, /class="katex-display"/)
  }
  assert.doesNotMatch(rendered, /katex-error/, `valid formula must render: ${formula}`)
}

const normalizedDelimiters = renderMarkdown(String.raw`行内：\(x+1\)

\[
\frac{a}{b}
\]`)
assert.match(normalizedDelimiters, /class="katex"/)
assert.match(normalizedDelimiters, /class="katex-display"/)

const codeSpan = renderMarkdown('代码：`$not_math$`')
assert.match(codeSpan, /<code>\$not_math\$<\/code>/)
assert.doesNotMatch(codeSpan, /class="katex"/)

const fencedCode = renderMarkdown('```text\n$x+1$\n```')
assert.match(fencedCode, /<code class="language-text">\$x\+1\$/)
assert.doesNotMatch(fencedCode, /class="katex"/)

const escapedDollar = renderMarkdown(String.raw`转义美元：\$100`)
assert.match(escapedDollar, /转义美元：\$100/)
assert.doesNotMatch(escapedDollar, /class="katex"/)

const unclosedMath = renderMarkdown('未闭合：$x + 1')
assert.match(unclosedMath, /未闭合：\$x \+ 1/)
assert.doesNotMatch(unclosedMath, /class="katex"/)

const safeMarkdown = renderMarkdown(`# 标题

**加粗**

- 列表

正常：$x+1$`)
assert.match(safeMarkdown, /<h1>标题<\/h1>/)
assert.match(safeMarkdown, /<strong>加粗<\/strong>/)
assert.match(safeMarkdown, /<ul>[\s\S]*<li>列表<\/li>[\s\S]*<\/ul>/)
assert.match(safeMarkdown, /class="katex"/)

const bareUrl = renderMarkdown('访问 https://example.com')
assert.doesNotMatch(bareUrl, /<a\b/i, 'bare URLs must not be linkified')
assert.match(bareUrl, /https:\/\/example\.com/)

const safeLink = renderMarkdown('[示例](https://example.com)')
assert.match(safeLink, /<a href="https:\/\/example.com">示例<\/a>/)
assert.doesNotMatch(safeLink, /target="_blank"/)

console.log('Markdown security contract passed')
