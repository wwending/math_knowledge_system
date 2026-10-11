import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { getQuestionPreviewSource } from '../src/utils/questionBankSearch.mjs'
import { PREVIEW_LIMITS, getQuestionListExcerpt, renderQuestionListExcerpt, createQuestionListPreviewCache } from '../src/utils/questionListPreview.mjs'

const render = (source) => renderQuestionListExcerpt(getQuestionListExcerpt(source))
for (const formula of [String.raw`$x^2\neq 0$`, String.raw`\(x\leqslant 2\)`, String.raw`\[\frac{1}{2}\]`, '$$x+1$$', '文字 $$x+1$$ 后文']) {
  assert.match(render(formula), /class="katex"/, formula)
}
for (const formula of [String.raw`$\notACommand{x}$`, String.raw`\(\frac{1}\)`, String.raw`\[\notACommand\]`]) {
  assert.ok(render(formula).includes(formula), `invalid math preserves original delimiters: ${formula}`)
  assert.doesNotMatch(render(formula), /class="katex/)
}
for (const raw of [String.raw`x^2 \neq 0`, String.raw`未闭合 \(x+1`, '未闭合 $x+1', String.raw`\$100`]) {
  // Escaped dollar is ordinary Markdown; malformed delimiters use the raw fallback.
  if (!raw.startsWith('\\$')) assert.ok(render(raw).includes(raw))
  assert.doesNotMatch(render(raw), /class="katex"/)
}
const edge = 'a'.repeat(590) + '$x+123456789$' + '尾部'
assert.equal(getQuestionListExcerpt(edge).text, 'a'.repeat(590) + '…', 'complete formula is omitted rather than split')
assert.equal(getQuestionListExcerpt('a'.repeat(580) + '$x+1$' + 'b'.repeat(1000)).text.includes('$x+1$'), true)
for (const raw of ['$' + 'x'.repeat(600) + '$', '$x$ '.repeat(100), 'a'.repeat(1_000_000), '$x' + 'a'.repeat(1_000_000)]) {
  const excerpt = getQuestionListExcerpt(raw)
  assert.ok(excerpt.text.length <= PREVIEW_LIMITS.text + 1)
}
for (const [opening, closing] of [['$', '$'], ['$$', '$$'], ['\\(', '\\)'], ['\\[', '\\]']]) {
  const complete = `${opening}x+1${closing}`
  assert.deepEqual(getQuestionListExcerpt(complete), { text: complete, plain: false })
  assert.deepEqual(getQuestionListExcerpt('前文 ' + opening + 'x'.repeat(513) + closing), { text: '前文 …', plain: false })
  assert.deepEqual(getQuestionListExcerpt('a'.repeat(596) + complete), { text: 'a'.repeat(596) + '…', plain: false })
  assert.deepEqual(getQuestionListExcerpt('前文 ' + opening + 'x'.repeat(3000) + closing), { text: '前文 …', plain: false })
  assert.deepEqual(getQuestionListExcerpt('前文 ' + opening + 'x'), { text: '前文 ' + opening + 'x', plain: true })
  const eight = (complete + ' ').repeat(8)
  assert.deepEqual(getQuestionListExcerpt(eight + complete), { text: eight + '…', plain: false })
  assert.equal((render(eight + complete).match(/class="katex"/g) || []).length, 8)
}
assert.deepEqual(getQuestionListExcerpt('$' + 'x'.repeat(600) + '$'), { text: '…', plain: false })
assert.deepEqual(getQuestionListExcerpt('a'.repeat(597) + '😀尾'), { text: 'a'.repeat(597) + '😀尾', plain: false })
assert.deepEqual(getQuestionListExcerpt('a'.repeat(599) + '😀尾'), { text: 'a'.repeat(599) + '…', plain: false })
assert.doesNotMatch(render(String.raw`\$x\$ \\(x\\)`), /class="katex"/)
assert.match(render(String.raw`$x+\$1$`), /class="katex"/)
assert.equal((render('$$x$$ $$y$$').match(/class="katex"/g) || []).length, 2)
assert.doesNotMatch(render('``code `$x$` code``'), /class="katex"/)
assert.doesNotMatch(render('~~~text\n$x$\n~~~'), /class="katex"/)
assert.deepEqual(getQuestionListExcerpt('前文 `' + 'x'.repeat(3000) + '`'), { text: '前文 …', plain: false })
assert.deepEqual(getQuestionListExcerpt('前文 `' + 'x'.repeat(601) + '`'), { text: '前文 …', plain: false })
assert.doesNotMatch(render('`$x$`'), /class="katex"/)
assert.doesNotMatch(render('```text\n$x$\n```'), /class="katex"/)
const attacks = [
  '![outer](https://example.invalid/a.png)',
  '[![nested](https://example.invalid/n.png)](https://example.invalid)',
  '![![nested](https://example.invalid/n.png)](https://example.invalid/o.png)',
  '![ref][img]\n\n[img]: https://example.invalid/ref.png',
  '<img src="https://example.invalid/a.png" onerror="alert(1)">',
  '[x](javascript:alert(1))',
  String.raw`$\includegraphics{https://example.invalid/tex.png}$`,
  String.raw`$\href{https://example.invalid}{x}$`,
  String.raw`$\htmlStyle{background-image:url(https://example.invalid/bg.png)}{x}$`
]
for (const attack of attacks) {
  assert.doesNotMatch(render(attack), /<(?:img|iframe|object|embed|video|audio|script|link)\b|\s(?:src|href|onerror|onload)=["']|style="[^"\n]*url\(/i, attack)
}
// Real source selector + cache: same ID, three different search-hit sources, then edits.
let calls = 0
const cache = createQuestionListPreviewCache((excerpt) => { calls++; return renderQuestionListExcerpt(excerpt) })
const item = { id: 7, content: '题干 $x^2$', answer: '答案 $y^2$', analysis: '解析 $z^2$' }
let result = cache.sync([item], (row) => getQuestionPreviewSource(row, '题干'))
assert.match(result.get(7), /题干/)
cache.sync([item], (row) => getQuestionPreviewSource(row, '题干'))
assert.equal(calls, 1, 'selection/dialog re-render does not reparse unchanged summaries')
for (const query of ['答案', '解析']) {
  result = cache.sync([item], (row) => getQuestionPreviewSource(row, query))
  assert.match(result.get(7), new RegExp(query))
}
assert.equal(calls, 3)
item.analysis = '解析 $w^2$'
cache.sync([item], (row) => getQuestionPreviewSource(row, '解析'))
assert.equal(calls, 4, 'same-ID source changes invalidate the result')
cache.sync([])
assert.equal(cache.size, 0, 'departed rows are pruned')
cache.sync([{ id: 9, content: '其他' }])
cache.clear()
assert.equal(cache.size, 0)
for (const name of ['BankPanel', 'HistoryPanel']) {
  const source = readFileSync(new URL(`../src/components/${name}.vue`, import.meta.url), 'utf8')
  assert.match(source, /v-html="listPreviews.get\(item.id\)"/)
  assert.match(source, /const listPreviews = computed\(/)
  assert.match(source, /previewCache.clear\(\)/)
  assert.match(source, /-webkit-line-clamp: 3/)
}
console.log('Question list preview formula, bounds, safety, source/cache regression checks passed.')
