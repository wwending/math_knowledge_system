export const SECTION_NAMES = ['stem', 'answer', 'analysis']
export const MAX_BLOCKS_PER_SECTION = 50

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const defaultId = () => globalThis.crypto.randomUUID()
const operationResult = (document, error = null) => ({ document, changed: !error, error })
const sectionBlocks = (document, name) => document?.sections?.[name]?.blocks

export const cloneQuestionDocument = (value) => JSON.parse(JSON.stringify(value))

export const createQuestionDocumentEditorState = (source = {}) => {
  const sections = Object.fromEntries(
    SECTION_NAMES.map((name) => [name, cloneQuestionDocument(source.sections?.[name] || { blocks: [] })])
  )
  const draft = {
    schema_version: 2,
    sections,
    figures: cloneQuestionDocument(source.figures || []),
    metadata: {
      knowledge_tags: cloneQuestionDocument(source.knowledge_tags || []),
      question_type: source.question_type ?? null,
      difficulty_level: source.difficulty_level ?? null
    },
    id: source.id,
    image_url: source.image_url,
    has_question_image: source.has_question_image
  }
  return {
    baseline: cloneQuestionDocument(draft),
    draft: cloneQuestionDocument(draft)
  }
}

export const isQuestionDocumentDirty = (draft, baseline) => (
  Boolean(draft && baseline) && JSON.stringify(draft) !== JSON.stringify(baseline)
)

export const validateQuestionDocumentDraft = (draft) => {
  const errors = []
  const sectionNames = draft?.sections && typeof draft.sections === 'object'
    ? Object.keys(draft.sections)
    : []

  if (
    !draft
    || sectionNames.length !== SECTION_NAMES.length
    || !SECTION_NAMES.every((name) => Array.isArray(sectionBlocks(draft, name)))
  ) {
    errors.push({ code: 'invalid_sections', message: '题目必须且只能包含题干、答案和解析三个区段' })
  }

  const ids = new Set()
  for (const name of SECTION_NAMES) {
    const blocks = sectionBlocks(draft, name) || []
    if (blocks.length > MAX_BLOCKS_PER_SECTION) {
      errors.push({ code: 'too_many_blocks', section: name, message: `每个区段最多 ${MAX_BLOCKS_PER_SECTION} 个内容块` })
    }
    for (const block of blocks) {
      if (!UUID_PATTERN.test(String(block?.id || ''))) {
        errors.push({ code: 'invalid_id', section: name, message: '内容块 ID 必须是 UUID' })
      } else if (ids.has(block.id.toLowerCase())) {
        errors.push({ code: 'duplicate_id', section: name, message: '内容块 ID 必须全题唯一' })
      } else {
        ids.add(block.id.toLowerCase())
      }
      if (block?.kind === 'text' && !String(block.markdown || '').trim()) {
        errors.push({ code: 'empty_text', section: name, message: '文字块不能为空' })
      }
    }
  }

  if (!(sectionBlocks(draft, 'stem') || []).some(
    (block) => block.kind === 'text' && String(block.markdown || '').trim()
  )) {
    errors.push({ code: 'empty_stem', section: 'stem', message: '题干必须保留至少一个非空文字块' })
  }

  const metadata = draft?.metadata
  if (!metadata || !Array.isArray(metadata.knowledge_tags)) {
    errors.push({ code: 'invalid_metadata', message: '题目元数据无效' })
  } else {
    for (const tag of metadata.knowledge_tags) {
      if (!tag || typeof tag.label !== 'string' || !tag.label.trim() || !Number.isFinite(tag.score)) {
        errors.push({ code: 'invalid_tag', message: '知识点标签必须包含非空名称和有效分数' })
        break
      }
    }
    if (metadata.question_type !== null && typeof metadata.question_type !== 'string') {
      errors.push({ code: 'invalid_question_type', message: '题型必须是字符串或空值' })
    }
    if (
      metadata.difficulty_level !== null
      && (!Number.isInteger(metadata.difficulty_level) || metadata.difficulty_level < 1 || metadata.difficulty_level > 5)
    ) {
      errors.push({ code: 'invalid_difficulty', message: '难度必须是 1 到 5 的整数或空值' })
    }
  }

  return { valid: errors.length === 0, errors }
}

export const buildQuestionDocumentPayload = (draft, expectedRevisionNo) => ({
  schema_version: 2,
  expected_revision_no: expectedRevisionNo,
  sections: cloneQuestionDocument(draft.sections),
  figures: draft.figures.map(({ id }) => ({ id, kind: 'existing' })),
  metadata: cloneQuestionDocument(draft.metadata)
})

const mutate = (draft, callback) => {
  const next = cloneQuestionDocument(draft)
  callback(next)
  return next
}

const locateBlock = (draft, name, id) => {
  const blocks = sectionBlocks(draft, name)
  const index = blocks?.findIndex((block) => block.id === id) ?? -1
  return { blocks, index, block: index >= 0 ? blocks[index] : null }
}

export const addTextBlock = (
  draft,
  name,
  { markdown = '请输入内容', index, createId = defaultId } = {}
) => {
  const blocks = sectionBlocks(draft, name)
  if (!blocks) return operationResult(draft, '目标区段不存在')
  if (blocks.length >= MAX_BLOCKS_PER_SECTION) return operationResult(draft, `每个区段最多 ${MAX_BLOCKS_PER_SECTION} 个内容块`)
  const insertionIndex = index === undefined
    ? blocks.length
    : Math.max(0, Math.min(index, blocks.length))
  return operationResult(mutate(draft, (next) => {
    sectionBlocks(next, name).splice(insertionIndex, 0, {
      id: createId(),
      kind: 'text',
      markdown
    })
  }))
}

export const editTextBlock = (draft, name, id, markdown) => {
  const { block } = locateBlock(draft, name, id)
  if (block?.kind !== 'text') return operationResult(draft, '文字块不存在')
  return operationResult(mutate(draft, (next) => {
    locateBlock(next, name, id).block.markdown = markdown
  }))
}

export const deleteTextBlock = (draft, name, id) => {
  const { index, block } = locateBlock(draft, name, id)
  if (index < 0 || block?.kind !== 'text') return operationResult(draft, '文字块不存在')
  const next = mutate(draft, (document) => sectionBlocks(document, name).splice(index, 1))
  const validation = validateQuestionDocumentDraft(next)
  const stemError = validation.errors.find((error) => error.code === 'empty_stem')
  return stemError ? operationResult(draft, stemError.message) : operationResult(next)
}

export const reorderBlock = (draft, name, id, targetIndex) => {
  const { blocks, index } = locateBlock(draft, name, id)
  if (!blocks || index < 0) return operationResult(draft, '内容块不存在')
  const boundedIndex = Math.max(0, Math.min(targetIndex, blocks.length - 1))
  if (boundedIndex === index) return operationResult(draft)
  return operationResult(mutate(draft, (next) => {
    const nextBlocks = sectionBlocks(next, name)
    const [block] = nextBlocks.splice(index, 1)
    nextBlocks.splice(boundedIndex, 0, block)
  }))
}

export const mergeTextBlockWithNext = (draft, name, id) => {
  const { blocks, index, block } = locateBlock(draft, name, id)
  if (block?.kind !== 'text' || blocks[index + 1]?.kind !== 'text') {
    return operationResult(draft, '只能合并相邻文字块')
  }
  return operationResult(mutate(draft, (next) => {
    const nextBlocks = sectionBlocks(next, name)
    nextBlocks[index].markdown += `\n\n${nextBlocks[index + 1].markdown}`
    nextBlocks.splice(index + 1, 1)
  }))
}

export const moveBlockToSection = (draft, from, id, to, targetIndex) => {
  if (from === to) return operationResult(draft, '请选择其他区段')
  const source = locateBlock(draft, from, id)
  const destination = sectionBlocks(draft, to)
  if (source.index < 0 || !destination) return operationResult(draft, '内容块或目标区段不存在')
  if (destination.length >= MAX_BLOCKS_PER_SECTION) return operationResult(draft, `每个区段最多 ${MAX_BLOCKS_PER_SECTION} 个内容块`)

  const next = mutate(draft, (document) => {
    const sourceBlocks = sectionBlocks(document, from)
    const destinationBlocks = sectionBlocks(document, to)
    const [block] = sourceBlocks.splice(source.index, 1)
    const insertionIndex = targetIndex === undefined
      ? destinationBlocks.length
      : Math.max(0, Math.min(targetIndex, destinationBlocks.length))
    destinationBlocks.splice(insertionIndex, 0, block)
  })
  const stemError = validateQuestionDocumentDraft(next).errors.find((error) => error.code === 'empty_stem')
  return stemError ? operationResult(draft, stemError.message) : operationResult(next)
}

const isEscaped = (source, index) => {
  let backslashes = 0
  for (let cursor = index - 1; cursor >= 0 && source[cursor] === '\\'; cursor -= 1) backslashes += 1
  return backslashes % 2 === 1
}

const lineFenceMarker = (line) => line.match(/^\s{0,3}(`{3,}|~{3,})/)?.[1] || null

export const findSafeMarkdownParagraphs = (markdown = '') => {
  const source = String(markdown)
  if (!source.trim()) return []

  const boundaries = []
  let fence = null
  let inlineTicks = 0
  let mathDelimiter = null
  let lineStart = 0
  let index = 0

  while (index < source.length) {
    if (index === lineStart && !inlineTicks && !mathDelimiter) {
      const lineEnd = source.indexOf('\n', index)
      const line = source.slice(index, lineEnd < 0 ? source.length : lineEnd).replace(/\r$/, '')
      const marker = lineFenceMarker(line)
      if (marker) {
        if (!fence) fence = marker[0]
        else if (marker[0] === fence && marker.length >= 3) fence = null
        if (lineEnd < 0) break
        index = lineEnd
        continue
      }
    }

    const character = source[index]
    if (!fence && character === '`' && !isEscaped(source, index)) {
      let run = 1
      while (source[index + run] === '`') run += 1
      if (!inlineTicks) inlineTicks = run
      else if (run === inlineTicks) inlineTicks = 0
      index += run
      continue
    }

    if (!fence && !inlineTicks && character === '$' && !isEscaped(source, index)) {
      const delimiter = source[index + 1] === '$' ? '$$' : '$'
      if (!mathDelimiter) mathDelimiter = delimiter
      else if (mathDelimiter === delimiter) mathDelimiter = null
      index += delimiter.length
      continue
    }

    if (character === '\n') {
      const blankStart = index
      let cursor = index + 1
      while (cursor < source.length) {
        const nextLineEnd = source.indexOf('\n', cursor)
        const end = nextLineEnd < 0 ? source.length : nextLineEnd
        if (source.slice(cursor, end).replace(/\r$/, '').trim()) break
        cursor = end + (nextLineEnd < 0 ? 0 : 1)
      }
      const nextLineEnd = source.indexOf('\n', cursor)
      const nextLine = source.slice(cursor, nextLineEnd < 0 ? source.length : nextLineEnd).replace(/\r$/, '')
      if (!fence && !inlineTicks && !mathDelimiter && cursor > index + 1 && nextLine.trim()) {
        boundaries.push({ separatorStart: blankStart, separatorEnd: cursor })
        index = cursor
        lineStart = cursor
        continue
      }
      lineStart = index + 1
    }
    index += 1
  }

  // 不平衡的代码或公式分隔符意味着边界存在歧义；保守地把全文视为一段。
  if (fence || inlineTicks || mathDelimiter) {
    return [{ index: 0, start: 0, end: source.length, excerpt: source.trim().slice(0, 40) }]
  }

  const spans = []
  let start = 0
  for (const boundary of boundaries) {
    const text = source.slice(start, boundary.separatorStart)
    if (text.trim()) {
      spans.push({
        index: spans.length,
        start,
        end: boundary.separatorStart,
        separatorEnd: boundary.separatorEnd,
        excerpt: text.trim().slice(0, 40)
      })
    }
    start = boundary.separatorEnd
  }
  const text = source.slice(start)
  if (text.trim()) {
    spans.push({ index: spans.length, start, end: source.length, separatorEnd: source.length, excerpt: text.trim().slice(0, 40) })
  }
  return spans
}

export const splitTextBlockAtParagraph = (
  draft,
  name,
  id,
  rightIndex,
  { createId = defaultId } = {}
) => {
  const { block, index } = locateBlock(draft, name, id)
  const paragraphs = findSafeMarkdownParagraphs(block?.markdown)
  if (block?.kind !== 'text' || rightIndex <= 0 || rightIndex >= paragraphs.length) {
    return operationResult(draft, '没有安全的段落拆分位置')
  }
  if (sectionBlocks(draft, name).length >= MAX_BLOCKS_PER_SECTION) {
    return operationResult(draft, `每个区段最多 ${MAX_BLOCKS_PER_SECTION} 个内容块`)
  }
  const boundary = paragraphs[rightIndex]
  return operationResult(mutate(draft, (next) => {
    const blocks = sectionBlocks(next, name)
    const original = blocks[index]
    blocks.splice(
      index,
      1,
      { ...original, markdown: original.markdown.slice(0, boundary.start).trimEnd() },
      { id: createId(), kind: 'text', markdown: original.markdown.slice(boundary.start).trimStart() }
    )
  }))
}

export const moveParagraphToSection = (
  draft,
  from,
  id,
  paragraphIndex,
  to,
  { createId = defaultId, targetIndex } = {}
) => {
  if (from === to) return operationResult(draft, '请选择其他区段')
  const { block, index } = locateBlock(draft, from, id)
  const destination = sectionBlocks(draft, to)
  const paragraphs = findSafeMarkdownParagraphs(block?.markdown)
  const paragraph = paragraphs[paragraphIndex]
  if (block?.kind !== 'text' || !paragraph || !destination) {
    return operationResult(draft, '没有可安全移动的完整段落')
  }
  if (destination.length >= MAX_BLOCKS_PER_SECTION) {
    return operationResult(draft, `每个区段最多 ${MAX_BLOCKS_PER_SECTION} 个内容块`)
  }

  const movedMarkdown = block.markdown.slice(paragraph.start, paragraph.end).trim()
  const before = block.markdown.slice(0, paragraph.start).trimEnd()
  const after = block.markdown.slice(paragraph.separatorEnd ?? paragraph.end).trimStart()
  const remainingMarkdown = [before, after].filter(Boolean).join('\n\n')

  if (!remainingMarkdown && from === 'stem') {
    const otherStemText = sectionBlocks(draft, 'stem').some(
      (candidate, candidateIndex) => candidateIndex !== index && candidate.kind === 'text' && candidate.markdown.trim()
    )
    if (!otherStemText) return operationResult(draft, '题干必须保留至少一个非空文字块')
  }

  return operationResult(mutate(draft, (next) => {
    const sourceBlocks = sectionBlocks(next, from)
    if (remainingMarkdown) sourceBlocks[index].markdown = remainingMarkdown
    else sourceBlocks.splice(index, 1)
    const destinationBlocks = sectionBlocks(next, to)
    const insertionIndex = targetIndex === undefined
      ? destinationBlocks.length
      : Math.max(0, Math.min(targetIndex, destinationBlocks.length))
    destinationBlocks.splice(insertionIndex, 0, {
      id: createId(),
      kind: 'text',
      markdown: movedMarkdown
    })
  }))
}
