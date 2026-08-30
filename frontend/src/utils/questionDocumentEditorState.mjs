export const SECTION_NAMES = ['stem', 'answer', 'analysis']
export const MAX_BLOCKS_PER_SECTION = 50
export const MAX_FIGURES_PER_IMAGE_AREA = 10
export const MAX_FIGURES_PER_QUESTION = 20
export const DOCUMENT_MIN_CROP_AREA = 0.01
export const IMAGE_AREA_GAP_PX = 12
export const HISTORY_LIMIT = 100

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
    figures: cloneQuestionDocument(source.figures || []).map((figure) => ({
      ...figure,
      kind: figure.kind === 'crop' ? 'crop' : 'existing'
    })),
    metadata: {
      knowledge_tags: cloneQuestionDocument(source.knowledge_tags || []),
      question_type: source.question_type ?? null,
      difficulty_level: source.difficulty_level ?? null
    },
    id: source.id,
    image_url: source.image_url,
    has_question_image: source.has_question_image,
    source_image: cloneQuestionDocument(source.source_image || null)
  }
  return {
    baseline: cloneQuestionDocument(draft),
    draft: cloneQuestionDocument(draft)
  }
}

export const isQuestionDocumentDirty = (draft, baseline) => (
  Boolean(draft && baseline) && JSON.stringify(draft) !== JSON.stringify(baseline)
)

const placementOverlap = (a, b, epsilon = 1e-9) => (
  Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) > epsilon
  && Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) > epsilon
)

export const validateQuestionDocumentDraft = (draft) => {
  const errors = []
  const sectionNames = draft?.sections && typeof draft.sections === 'object' ? Object.keys(draft.sections) : []
  if (!draft || sectionNames.length !== SECTION_NAMES.length || !SECTION_NAMES.every((name) => Array.isArray(sectionBlocks(draft, name)))) {
    errors.push({ code: 'invalid_sections', message: '题目必须且只能包含题干、答案和解析三个区段', field: 'sections' })
  }

  const blockIds = new Set()
  const placedFigures = new Set()
  const referencedFigures = new Set()
  for (const name of SECTION_NAMES) {
    const blocks = sectionBlocks(draft, name) || []
    if (blocks.length > MAX_BLOCKS_PER_SECTION) errors.push({ code: 'too_many_blocks', section: name, message: `每个区段最多 ${MAX_BLOCKS_PER_SECTION} 个内容块` })
    blocks.forEach((block, blockIndex) => {
      const location = { section: name, block_id: block?.id, block_index: blockIndex }
      if (!UUID_PATTERN.test(String(block?.id || ''))) errors.push({ code: 'invalid_id', ...location, message: '内容块 ID 必须是 UUID' })
      else if (blockIds.has(block.id.toLowerCase())) errors.push({ code: 'duplicate_id', ...location, message: '内容块 ID 必须全题唯一' })
      else blockIds.add(block.id.toLowerCase())
      if (block?.kind === 'text') {
        if (!String(block.markdown || '').trim()) errors.push({ code: 'empty_text', ...location, field: 'markdown', message: '文字块不能为空' })
        return
      }
      if (block?.kind !== 'image_area') {
        errors.push({ code: 'invalid_block_kind', ...location, field: 'kind', message: '内容块类型无效' })
        return
      }
      if (!Number.isFinite(block.height_ratio) || block.height_ratio <= 0) errors.push({ code: 'invalid_height_ratio', ...location, field: 'height_ratio', message: '图片区高度比例必须是正数' })
      if (!Array.isArray(block.placements) || block.placements.length === 0) {
        errors.push({ code: 'empty_image_area', ...location, field: 'placements', message: '图片区至少需要一张配图' })
        return
      }
      if (block.placements.length > MAX_FIGURES_PER_IMAGE_AREA) errors.push({ code: 'too_many_placements', ...location, message: `每个图片区最多 ${MAX_FIGURES_PER_IMAGE_AREA} 张配图` })
      block.placements.forEach((placement, placementIndex) => {
        const figureId = String(placement?.figure_id || '')
        const placementLocation = { ...location, figure_id: figureId, placement_index: placementIndex }
        if (!placement || typeof placement !== 'object' || Array.isArray(placement)) {
          errors.push({ code: 'invalid_placement', ...placementLocation, field: 'placements', message: '配图摆放必须是对象' })
          return
        }
        if (!UUID_PATTERN.test(figureId)) errors.push({ code: 'invalid_figure_id', ...placementLocation, field: 'figure_id', message: '配图 ID 必须是 UUID' })
        if (placedFigures.has(figureId)) errors.push({ code: 'duplicate_figure_placement', ...placementLocation, field: 'figure_id', message: '同一配图在整题中只能摆放一次' })
        placedFigures.add(figureId); referencedFigures.add(figureId)
        const values = ['x', 'y', 'width', 'height'].map((field) => placement[field])
        if (values.some((value) => !Number.isFinite(value)) || placement.width <= 0 || placement.height <= 0 || placement.x < 0 || placement.y < 0 || placement.x + placement.width > 1 + 1e-9 || placement.y + placement.height > 1 + 1e-9) {
          errors.push({ code: 'placement_out_of_bounds', ...placementLocation, field: 'placements', message: '配图必须完整位于图片区内' })
        } else {
          const figure = (draft.figures || []).find((item) => item.id === figureId)
          if (figure?.width > 0 && figure?.height > 0 && Number.isFinite(block.height_ratio)) {
            const displayedRatio = placement.width / (placement.height * block.height_ratio)
            const sourceRatio = figure.width / figure.height
            if (Math.abs(displayedRatio - sourceRatio) > Math.max(0.02, sourceRatio * 0.02)) errors.push({ code: 'aspect_ratio_mismatch', ...placementLocation, field: 'placements', message: '配图摆放必须保持原图比例' })
          }
        }
        block.placements.slice(placementIndex + 1).forEach((other) => {
          if (other && typeof other === 'object' && !Array.isArray(other) && placementOverlap(placement, other)) errors.push({ code: 'placement_overlap', ...placementLocation, field: 'placements', message: '同一图片区中的配图不能重叠' })
        })
      })
    })
  }

  const stemHasContent = (sectionBlocks(draft, 'stem') || []).some((block) => block.kind === 'text' ? String(block.markdown || '').trim() : block.kind === 'image_area' && block.placements?.length)
  if (!stemHasContent) errors.push({ code: 'empty_stem', section: 'stem', message: '题干必须包含非空文字或配图' })

  const declarations = new Set()
  if (!Array.isArray(draft?.figures)) errors.push({ code: 'invalid_figures', field: 'figures', message: '配图清单无效' })
  else {
    if (draft.figures.length > MAX_FIGURES_PER_QUESTION) errors.push({ code: 'too_many_figures', field: 'figures', message: `每题最多 ${MAX_FIGURES_PER_QUESTION} 张配图` })
    draft.figures.forEach((figure, figureIndex) => {
      const id = String(figure?.id || '')
      if (!UUID_PATTERN.test(id)) errors.push({ code: 'invalid_figure_id', figure_id: id, figure_index: figureIndex, message: '配图 ID 必须是 UUID' })
      if (declarations.has(id)) errors.push({ code: 'duplicate_figure_declaration', figure_id: id, figure_index: figureIndex, message: '配图声明不能重复' })
      declarations.add(id)
      if (figure.kind === 'crop') {
        const bbox = figure.crop_bbox
        if (!Array.isArray(bbox) || bbox.length !== 4 || bbox.some((value) => !Number.isFinite(value)) || bbox[0] < 0 || bbox[1] < 0 || bbox[2] <= 0 || bbox[3] <= 0 || bbox[0] + bbox[2] > 1 + 1e-9 || bbox[1] + bbox[3] > 1 + 1e-9) errors.push({ code: 'invalid_crop_bbox', figure_id: id, figure_index: figureIndex, field: 'crop_bbox', message: '裁剪框必须完整位于题目区域图内' })
        else if (bbox[2] * bbox[3] < DOCUMENT_MIN_CROP_AREA) errors.push({ code: 'crop_too_small', figure_id: id, figure_index: figureIndex, field: 'crop_bbox', message: '裁剪框面积不能小于题目区域图的 1%' })
      } else if (figure.kind !== 'existing') errors.push({ code: 'invalid_figure_kind', figure_id: id, figure_index: figureIndex, message: '配图来源无效' })
    })
  }
  for (const id of referencedFigures) if (!declarations.has(id)) errors.push({ code: 'figure_not_declared', figure_id: id, message: '内容中引用的配图未声明' })
  for (const id of declarations) if (!referencedFigures.has(id)) errors.push({ code: 'unreferenced_figure', figure_id: id, message: '配图声明未被内容引用' })

  const metadata = draft?.metadata
  if (!metadata || !Array.isArray(metadata.knowledge_tags)) errors.push({ code: 'invalid_metadata', message: '题目元数据无效' })
  else {
    if (metadata.knowledge_tags.some((tag) => !tag || typeof tag.label !== 'string' || !tag.label.trim() || !Number.isFinite(tag.score))) errors.push({ code: 'invalid_tag', message: '知识点标签必须包含非空名称和有效分数' })
    if (metadata.question_type !== null && typeof metadata.question_type !== 'string') errors.push({ code: 'invalid_question_type', message: '题型必须是字符串或空值' })
    if (metadata.difficulty_level !== null && (!Number.isInteger(metadata.difficulty_level) || metadata.difficulty_level < 1 || metadata.difficulty_level > 5)) errors.push({ code: 'invalid_difficulty', message: '难度必须是 1 到 5 的整数或空值' })
  }
  return { valid: errors.length === 0, errors }
}

export const buildQuestionDocumentPayload = (draft, expectedRevisionNo) => ({
  schema_version: 2,
  expected_revision_no: expectedRevisionNo,
  sections: cloneQuestionDocument(draft.sections),
  figures: draft.figures.map((figure) => figure.kind === 'crop'
    ? { id: figure.id, kind: 'crop', crop_bbox: [...figure.crop_bbox] }
    : { id: figure.id, kind: 'existing' }),
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

const findImageArea = (draft, areaId) => {
  for (const section of SECTION_NAMES) {
    const index = (sectionBlocks(draft, section) || []).findIndex((block) => block.id === areaId && block.kind === 'image_area')
    if (index >= 0) return { section, index, block: sectionBlocks(draft, section)[index] }
  }
  return null
}

const figureById = (draft, figureId) => draft.figures.find((figure) => figure.id === figureId)
const naturalSize = (figure) => ({ width: Number(figure?.width || 0), height: Number(figure?.height || 0) })
const areaHeightPx = (area, canvasWidth) => Math.max(1, area.height_ratio * canvasWidth)
const placementPixels = (placement, area, canvasWidth) => {
  const canvasHeight = areaHeightPx(area, canvasWidth)
  return {
    left: placement.x * canvasWidth,
    top: placement.y * canvasHeight,
    width: placement.width * canvasWidth,
    height: placement.height * canvasHeight
  }
}
const pixelsPlacement = (figureId, rect, canvasWidth, canvasHeight) => ({
  figure_id: figureId,
  x: rect.left / canvasWidth,
  y: rect.top / canvasHeight,
  width: rect.width / canvasWidth,
  height: rect.height / canvasHeight
})
const pixelRectsOverlap = (a, b, epsilon = 0.5) => (
  Math.min(a.left + a.width, b.left + b.width) - Math.max(a.left, b.left) > epsilon
  && Math.min(a.top + a.height, b.top + b.height) - Math.max(a.top, b.top) > epsilon
)

export const cropNaturalSize = (bbox, sourceWidth, sourceHeight) => {
  if (!Array.isArray(bbox) || bbox.length !== 4 || sourceWidth <= 0 || sourceHeight <= 0) return { width: 0, height: 0 }
  const [x, y, width, height] = bbox
  const left = Math.min(Math.max(Math.round(x * sourceWidth), 0), sourceWidth - 1)
  const top = Math.min(Math.max(Math.round(y * sourceHeight), 0), sourceHeight - 1)
  const right = Math.min(Math.max(Math.round((x + width) * sourceWidth), left + 1), sourceWidth)
  const bottom = Math.min(Math.max(Math.round((y + height) * sourceHeight), top + 1), sourceHeight)
  return { width: right - left, height: bottom - top }
}

export const addImageArea = (draft, section, { index, createId = defaultId } = {}) => {
  const blocks = sectionBlocks(draft, section)
  if (!blocks) return operationResult(draft, '目标区段不存在')
  if (blocks.length >= MAX_BLOCKS_PER_SECTION) return operationResult(draft, `每个区段最多 ${MAX_BLOCKS_PER_SECTION} 个内容块`)
  const insertionIndex = index === undefined ? blocks.length : Math.max(0, Math.min(index, blocks.length))
  return operationResult(mutate(draft, (next) => sectionBlocks(next, section).splice(insertionIndex, 0, {
    id: createId(), kind: 'image_area', height_ratio: 0.2, placements: []
  })))
}

export const deleteImageArea = (draft, areaId) => {
  const found = findImageArea(draft, areaId)
  if (!found) return operationResult(draft, '图片区不存在')
  const figureIds = new Set(found.block.placements.map((placement) => placement.figure_id))
  const next = mutate(draft, (document) => {
    sectionBlocks(document, found.section).splice(found.index, 1)
    document.figures = document.figures.filter((figure) => !figureIds.has(figure.id))
  })
  const stemError = validateQuestionDocumentDraft(next).errors.find((error) => error.code === 'empty_stem')
  return stemError ? operationResult(draft, stemError.message) : operationResult(next)
}

export const addCropsToImageArea = (
  draft,
  areaId,
  bboxes,
  { canvasWidth, sourceWidth, sourceHeight, createId = defaultId, gap = IMAGE_AREA_GAP_PX } = {}
) => {
  const found = findImageArea(draft, areaId)
  if (!found) return operationResult(draft, '图片区不存在')
  if (!canvasWidth || !sourceWidth || !sourceHeight) return operationResult(draft, '题目区域图尺寸尚未就绪')
  if (!Array.isArray(bboxes) || !bboxes.length) return operationResult(draft, '请至少绘制一个裁剪框')
  if (found.block.placements.length + bboxes.length > MAX_FIGURES_PER_IMAGE_AREA || draft.figures.length + bboxes.length > MAX_FIGURES_PER_QUESTION) return operationResult(draft, '配图数量超过上限')
  const invalid = bboxes.find((bbox) => !Array.isArray(bbox) || bbox.length !== 4 || bbox.some((value) => !Number.isFinite(value)) || bbox[2] * bbox[3] < DOCUMENT_MIN_CROP_AREA)
  if (invalid) return operationResult(draft, '裁剪框面积不能小于题目区域图的 1%')
  for (let index = 0; index < bboxes.length; index += 1) {
    if (bboxes.slice(index + 1).some((other) => placementOverlap(
      { x: bboxes[index][0], y: bboxes[index][1], width: bboxes[index][2], height: bboxes[index][3] },
      { x: other[0], y: other[1], width: other[2], height: other[3] }
    ))) return operationResult(draft, '同一裁图会话中的裁剪框不能重叠')
  }
  const existingRects = found.block.placements.map((placement) => placementPixels(placement, found.block, canvasWidth))
  let top = existingRects.length ? Math.max(...existingRects.map((rect) => rect.top + rect.height)) + gap : 0
  let left = 0
  let rowHeight = 0
  const additions = bboxes.map((bbox) => {
    const id = createId()
    const size = cropNaturalSize(bbox, sourceWidth, sourceHeight)
    const scale = Math.min(1, canvasWidth / size.width)
    const width = size.width * scale
    const height = size.height * scale
    if (left > 0 && left + width > canvasWidth) { top += rowHeight + gap; left = 0; rowHeight = 0 }
    const rect = { left, top, width, height }
    left += width + gap; rowHeight = Math.max(rowHeight, height)
    return { figure: { id, kind: 'crop', crop_bbox: [...bbox], width: size.width, height: size.height }, rect }
  })
  const requiredHeight = Math.max(gap, ...existingRects.map((rect) => rect.top + rect.height + gap), ...additions.map((item) => item.rect.top + item.rect.height + gap))
  return operationResult(mutate(draft, (next) => {
    const area = findImageArea(next, areaId).block
    const oldHeight = areaHeightPx(area, canvasWidth)
    area.height_ratio = requiredHeight / canvasWidth
    area.placements = area.placements.map((placement) => pixelsPlacement(placement.figure_id, placementPixels(placement, { ...area, height_ratio: oldHeight / canvasWidth }, canvasWidth), canvasWidth, requiredHeight))
    additions.forEach(({ figure, rect }) => { next.figures.push(figure); area.placements.push(pixelsPlacement(figure.id, rect, canvasWidth, requiredHeight)) })
  }))
}

export const removeFigurePlacement = (draft, areaId, figureId) => {
  const found = findImageArea(draft, areaId)
  if (!found || !found.block.placements.some((item) => item.figure_id === figureId)) return operationResult(draft, '配图不存在')
  return operationResult(mutate(draft, (next) => {
    const area = findImageArea(next, areaId).block
    area.placements = area.placements.filter((item) => item.figure_id !== figureId)
    next.figures = next.figures.filter((item) => item.id !== figureId)
  }))
}

export const updatePlacement = (draft, areaId, figureId, rect, { canvasWidth } = {}) => {
  const found = findImageArea(draft, areaId)
  if (!found || !canvasWidth) return operationResult(draft, '图片区不存在或尺寸无效')
  if (!found.block.placements.some((item) => item.figure_id === figureId)) return operationResult(draft, '配图不存在')
  const canvasHeight = areaHeightPx(found.block, canvasWidth)
  if (![rect.left, rect.top, rect.width, rect.height].every(Number.isFinite) || rect.left < 0 || rect.top < 0 || rect.width <= 0 || rect.height <= 0 || rect.width > canvasWidth || rect.height > canvasHeight || rect.left + rect.width > canvasWidth + 0.5 || rect.top + rect.height > canvasHeight + 0.5) return operationResult(draft, '配图必须完整位于图片区内')
  const boundedRect = {
    ...rect,
    left: Math.min(rect.left, canvasWidth - rect.width),
    top: Math.min(rect.top, canvasHeight - rect.height)
  }
  const others = found.block.placements.filter((item) => item.figure_id !== figureId).map((item) => placementPixels(item, found.block, canvasWidth))
  if (others.some((other) => pixelRectsOverlap(boundedRect, other))) return operationResult(draft, '配图不能与其他配图重叠')
  return operationResult(mutate(draft, (next) => {
    const placement = findImageArea(next, areaId).block.placements.find((item) => item.figure_id === figureId)
    Object.assign(placement, pixelsPlacement(figureId, boundedRect, canvasWidth, canvasHeight))
  }))
}

export const restorePlacementNaturalSize = (draft, areaId, figureId, { canvasWidth } = {}) => {
  const found = findImageArea(draft, areaId); const figure = figureById(draft, figureId)
  if (!found || !figure || !canvasWidth) return operationResult(draft, '配图不存在或尺寸无效')
  const placement = found.block.placements.find((item) => item.figure_id === figureId)
  if (!placement) return operationResult(draft, '配图在当前图片区中不存在')
  const size = naturalSize(figure)
  if (![size.width, size.height].every(Number.isFinite) || size.width <= 0 || size.height <= 0) return operationResult(draft, '配图自然尺寸无效')
  const current = placementPixels(placement, found.block, canvasWidth)
  const scale = Math.min(1, canvasWidth / size.width)
  return updatePlacement(draft, areaId, figureId, { ...current, width: size.width * scale, height: size.height * scale }, { canvasWidth })
}

export const setImageAreaHeight = (draft, areaId, heightRatio, { canvasWidth, gap = IMAGE_AREA_GAP_PX } = {}) => {
  const found = findImageArea(draft, areaId)
  if (!found || !canvasWidth || !Number.isFinite(heightRatio) || heightRatio <= 0) return operationResult(draft, '图片区高度无效')
  const rects = found.block.placements.map((item) => ({ figureId: item.figure_id, rect: placementPixels(item, found.block, canvasWidth) }))
  const required = Math.max(gap, ...rects.map(({ rect }) => rect.top + rect.height + gap))
  const newHeight = heightRatio * canvasWidth
  if (newHeight + 0.5 < required) return operationResult(draft, '图片区高度不能小于现有配图所需高度')
  return operationResult(mutate(draft, (next) => {
    const area = findImageArea(next, areaId).block
    area.height_ratio = heightRatio
    area.placements = rects.map(({ figureId, rect }) => pixelsPlacement(figureId, rect, canvasWidth, newHeight))
  }))
}

export const createEditorSession = (source) => {
  const state = source?.baseline && source?.draft
    ? source
    : source?.metadata && source?.sections
      ? { baseline: cloneQuestionDocument(source), draft: cloneQuestionDocument(source) }
      : createQuestionDocumentEditorState(source)
  return { baseline: cloneQuestionDocument(state.baseline), past: [], present: cloneQuestionDocument(state.draft), future: [] }
}
export const executeEditorCommand = (session, command, { historyLimit = HISTORY_LIMIT } = {}) => {
  const result = typeof command === 'function' ? command(session.present) : command
  if (!result || result.error || result.document === session.present || JSON.stringify(result.document) === JSON.stringify(session.present)) return { session, error: result?.error || null, changed: false }
  return { session: { baseline: session.baseline, past: [...session.past, cloneQuestionDocument(session.present)].slice(-historyLimit), present: cloneQuestionDocument(result.document), future: [] }, error: null, changed: true }
}
export const undoEditorSession = (session) => session.past.length ? { ...session, past: session.past.slice(0, -1), present: cloneQuestionDocument(session.past.at(-1)), future: [cloneQuestionDocument(session.present), ...session.future] } : session
export const redoEditorSession = (session) => session.future.length ? { ...session, past: [...session.past, cloneQuestionDocument(session.present)].slice(-HISTORY_LIMIT), present: cloneQuestionDocument(session.future[0]), future: session.future.slice(1) } : session
export const resetEditorSession = (source) => createEditorSession(source)
export const reachableFigureIds = (session) => new Set([...(session?.past || []), session?.present, ...(session?.future || [])].filter(Boolean).flatMap((document) => document.figures || []).map((figure) => figure.id))
