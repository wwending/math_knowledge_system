import { createMarkdownRenderer } from './markdownRenderer.mjs'

export const PREVIEW_LIMITS = Object.freeze({ input: 2048, text: 600, formula: 512, formulas: 8 })
const md = createMarkdownRenderer({ summary: true })
const escaped = (text, index) => {
  let count = 0
  while (index > 0 && text[--index] === '\\') count += 1
  return count % 2 === 1
}

// Only this bounded prefix is scanned/normalized/parsed; CSS is not the input bound.
export const getQuestionListExcerpt = (source) => {
  const raw = typeof source === 'string' ? source : ''
  const prefix = raw.slice(0, PREVIEW_LIMITS.input)
  let cursor = 0
  let formulas = 0
  let plain = false
  while (cursor < prefix.length && cursor < PREVIEW_LIMITS.text) {
    if (escaped(prefix, cursor)) { cursor += 1; continue }
    // Keep code literal; dollar signs inside it are not mathematical tokens.
    if (prefix[cursor] === '`') {
      const run = prefix.slice(cursor).match(/^`+/)[0]
      let end = cursor + run.length
      // Markdown code spans close only on a run of the same length.
      while (end < prefix.length) {
        end = prefix.indexOf('`', end)
        if (end < 0) break
        const candidate = prefix.slice(end).match(/^`+/)[0]
        if (candidate.length === run.length) break
        end += candidate.length
      }
      if (end < 0 || end >= prefix.length) { plain = raw.length <= prefix.length; break }
      if (end + run.length > PREVIEW_LIMITS.text) break
      cursor = end + run.length
      continue
    }
    if (prefix.startsWith('~~~', cursor) && /^(?: {0,3})$/.test(prefix.slice(prefix.lastIndexOf('\n', cursor - 1) + 1, cursor))) {
      const run = prefix.slice(cursor).match(/^~+/)[0]
      const closing = new RegExp(`\\n {0,3}~{${run.length},}[ \\t]*(?:\\n|$)`, 'g')
      closing.lastIndex = cursor + run.length
      const match = closing.exec(prefix)
      if (!match) { plain = raw.length <= prefix.length; break }
      const end = match.index + match[0].length
      if (end > PREVIEW_LIMITS.text) break
      cursor = end
      continue
    }
    const opening = prefix.startsWith('$$', cursor) ? '$$'
      : prefix[cursor] === '$' ? '$'
        : prefix.startsWith('\\(', cursor) ? '\\('
          : prefix.startsWith('\\[', cursor) ? '\\[' : null
    if (!opening) { cursor += 1; continue }
    const closing = opening === '\\(' ? '\\)' : opening === '\\[' ? '\\]' : opening
    let end = cursor + opening.length
    while (end < prefix.length && (prefix.slice(end, end + closing.length) !== closing || escaped(prefix, end) || (opening === '$' && prefix[end + 1] === '$'))) end += 1
    if (opening === '$' && prefix.slice(cursor, end).includes('\n')) {
      plain = true
      break
    }
    if (end >= prefix.length) {
      // An input budget is not evidence of malformed source; omit the token.
      plain = raw.length <= prefix.length
      break
    }
    if (end - cursor - opening.length > PREVIEW_LIMITS.formula || ++formulas > PREVIEW_LIMITS.formulas) {
      break
    }
    if (end + closing.length > PREVIEW_LIMITS.text) break
    cursor = end + closing.length
  }
  const cutoff = plain ? Math.min(prefix.length, PREVIEW_LIMITS.text) : cursor
  // Do not split a UTF-16 surrogate pair at the plain-text boundary.
  const safeCutoff = /[\uD800-\uDBFF]/.test(prefix[cutoff - 1] || '') ? cutoff - 1 : cutoff
  return { text: prefix.slice(0, safeCutoff) + (raw.length > safeCutoff ? '…' : ''), plain }
}

export const renderQuestionListExcerpt = ({ text, plain }) => {
  if (!text) return '暂无识别内容'
  if (plain) return md.utils.escapeHtml(text)
  try {
    return md.render(text)
  } catch {
    return md.utils.escapeHtml(text)
  }
}

export const createQuestionListPreviewCache = (render = renderQuestionListExcerpt) => {
  const cache = new Map()
  return {
    sync(items, sourceFor = (item) => item.content) {
      const live = new Set(items.map((item) => item.id))
      for (const id of cache.keys()) if (!live.has(id)) cache.delete(id)
      const result = new Map()
      for (const item of items) {
        const excerpt = getQuestionListExcerpt(sourceFor(item))
        const key = JSON.stringify(excerpt)
        let entry = cache.get(item.id)
        if (!entry || entry.key !== key) {
          entry = { key, html: render(excerpt) }
          cache.set(item.id, entry)
        }
        result.set(item.id, entry.html)
      }
      return result
    },
    clear() { cache.clear() },
    get size() { return cache.size }
  }
}
