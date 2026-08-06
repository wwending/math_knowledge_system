import katex from 'katex'
import MarkdownIt from 'markdown-it'

export const KATEX_OPTIONS = Object.freeze({
  throwOnError: false,
  trust: false,
  strict: 'warn',
  maxSize: 10,
  maxExpand: 1000,
  globalGroup: false,
  output: 'htmlAndMathml'
})

const MAX_INLINE_MATH_LENGTH = 10_000
const MAX_BLOCK_MATH_LENGTH = 100_000
const MAX_BLOCK_MATH_LINES = 200

const isEscaped = (source, position) => {
  let backslashes = 0
  for (let index = position - 1; index >= 0 && source[index] === '\\'; index -= 1) {
    backslashes += 1
  }
  return backslashes % 2 === 1
}

const findInlineClosingDelimiter = (source, start) => {
  const limit = Math.min(source.length, start + MAX_INLINE_MATH_LENGTH)

  for (let index = start; index < limit; index += 1) {
    if (source[index] === '\n') {
      return -1
    }
    if (
      source[index] === '$' &&
      source[index + 1] !== '$' &&
      !isEscaped(source, index)
    ) {
      return index
    }
  }

  return -1
}

const mathInlineRule = (state, silent) => {
  const start = state.pos
  if (
    state.src[start] !== '$' ||
    state.src[start + 1] === '$' ||
    isEscaped(state.src, start)
  ) {
    return false
  }

  const end = findInlineClosingDelimiter(state.src, start + 1)
  if (end < 0) {
    return false
  }

  if (!silent) {
    const token = state.push('math_inline', 'math', 0)
    token.content = state.src.slice(start + 1, end)
    token.markup = '$'
  }
  state.pos = end + 1
  return true
}

const findBlockClosingDelimiter = (source, from, to) => {
  let trimmedEnd = to
  while (
    trimmedEnd > from &&
    (source[trimmedEnd - 1] === ' ' || source[trimmedEnd - 1] === '\t')
  ) {
    trimmedEnd -= 1
  }

  const delimiterStart = trimmedEnd - 2
  if (
    delimiterStart >= from &&
    source[delimiterStart] === '$' &&
    source[delimiterStart + 1] === '$' &&
    !isEscaped(source, delimiterStart)
  ) {
    return delimiterStart
  }

  return -1
}

const mathBlockRule = (state, startLine, endLine, silent) => {
  const start = state.bMarks[startLine] + state.tShift[startLine]
  const firstLineEnd = state.eMarks[startLine]
  if (state.src.slice(start, start + 2) !== '$$') {
    return false
  }

  const contentParts = []
  let contentLength = 0
  let line = startLine
  let contentStart = start + 2
  let closingPosition = -1
  let exceedsLength = false

  while (line < endLine && line - startLine < MAX_BLOCK_MATH_LINES) {
    const lineEnd = line === startLine ? firstLineEnd : state.eMarks[line]
    closingPosition = findBlockClosingDelimiter(state.src, contentStart, lineEnd)

    if (!exceedsLength) {
      const contentEnd = closingPosition >= 0 ? closingPosition : lineEnd
      const separatorLength = contentParts.length > 0 ? 1 : 0
      const nextContentLength = contentLength + separatorLength + contentEnd - contentStart

      if (nextContentLength > MAX_BLOCK_MATH_LENGTH) {
        exceedsLength = true
        contentParts.length = 0
      } else {
        contentLength = nextContentLength
        contentParts.push(state.src.slice(contentStart, contentEnd))
      }
    }

    if (closingPosition >= 0) {
      break
    }

    line += 1
    if (line < endLine) {
      contentStart = state.bMarks[line] + state.tShift[line]
    }
  }

  if (closingPosition < 0) {
    return false
  }
  if (silent) {
    return true
  }

  const token = state.push(exceedsLength ? 'math_block_fallback' : 'math_block', 'math', 0)
  token.block = true
  token.content = exceedsLength
    ? state.src.slice(start, state.eMarks[line])
    : contentParts.join('\n')
  token.map = [startLine, line + 1]
  token.markup = '$$'
  state.line = line + 1
  return true
}

const renderMath = (tex, displayMode) => katex.renderToString(tex, {
  ...KATEX_OPTIONS,
  displayMode
})

const markdownItKatex = (md) => {
  md.inline.ruler.after('escape', 'math_inline', mathInlineRule)
  md.block.ruler.before('fence', 'math_block', mathBlockRule, {
    alt: ['paragraph', 'reference', 'blockquote', 'list']
  })
  md.renderer.rules.math_inline = (tokens, index) => renderMath(tokens[index].content, false)
  md.renderer.rules.math_block = (tokens, index) => `${renderMath(tokens[index].content, true)}\n`
  md.renderer.rules.math_block_fallback = (tokens, index) => {
    return `<p>${md.utils.escapeHtml(tokens[index].content)}</p>\n`
  }
}

export const createMarkdownRenderer = () => {
  const md = new MarkdownIt({
    html: false,
    breaks: true,
    linkify: false
  })
  const validateMarkdownItLink = md.validateLink.bind(md)

  // The question bank has no data-URL use case, including inline data images.
  md.validateLink = (url) => !/^\s*data:/i.test(url) && validateMarkdownItLink(url)

  return md.use(markdownItKatex)
}

const replaceLatexDelimiterPair = (source, opening, closing, markdownDelimiter) => {
  let result = ''
  let cursor = 0

  while (cursor < source.length) {
    const start = source.indexOf(opening, cursor)
    if (start < 0) {
      result += source.slice(cursor)
      break
    }
    if (isEscaped(source, start)) {
      result += source.slice(cursor, start + opening.length)
      cursor = start + opening.length
      continue
    }

    const end = source.indexOf(closing, start + opening.length)
    if (end < 0) {
      result += source.slice(cursor)
      break
    }

    result += source.slice(cursor, start)
    result += `${markdownDelimiter}${source.slice(start + opening.length, end)}${markdownDelimiter}`
    cursor = end + closing.length
  }

  return result
}

export const normalizeLatexDelimiters = (text) => {
  if (!text) {
    return ''
  }

  return replaceLatexDelimiterPair(
    replaceLatexDelimiterPair(text, '\\[', '\\]', '$$'),
    '\\(',
    '\\)',
    '$'
  )
}

const sharedMarkdownRenderer = createMarkdownRenderer()

export const renderMarkdown = (content) => {
  return sharedMarkdownRenderer.render(normalizeLatexDelimiters(content))
}
