export const QUESTION_SEARCH_FIELDS = [
  { key: 'stem', source: 'content', label: '题干' },
  { key: 'answer', source: 'answer', label: '答案' },
  { key: 'analysis', source: 'analysis', label: '解析' },
  { key: 'knowledge', source: 'knowledge_tags', label: '知识点' }
]

const normalize = (value) => String(value ?? '').trim().toLocaleLowerCase()

export const normalizeQuestionTags = (item) => {
  const raw = item?.knowledge_tags || item?.knowledge || []
  return Array.isArray(raw) ? raw.map((tag) => {
    if (typeof tag === 'string') return { label: tag, score: 1 }
    if (tag && typeof tag === 'object') return { label: tag.label || String(tag), score: tag.score ?? 1 }
    return { label: String(tag), score: 1 }
  }) : []
}

export const getQuestionSearchMatch = (item, keyword) => {
  const query = normalize(keyword)
  if (!query) return { matched: true, locations: [], primarySection: 'stem' }
  const locations = []
  if (normalize(item?.content).includes(query)) locations.push('stem')
  if (normalize(item?.answer).includes(query)) locations.push('answer')
  if (normalize(item?.analysis).includes(query)) locations.push('analysis')
  if (normalizeQuestionTags(item).some((tag) => normalize(tag.label).includes(query))) locations.push('knowledge')
  return {
    matched: locations.length > 0,
    locations,
    primarySection: locations.find((location) => location !== 'knowledge') || 'stem'
  }
}

export const questionSearchLocationLabel = (location) =>
  QUESTION_SEARCH_FIELDS.find((field) => field.key === location)?.label || location

export const getQuestionPreviewSource = (item, keyword) => {
  const match = getQuestionSearchMatch(item, keyword)
  const source = match.primarySection === 'answer' ? item?.answer : match.primarySection === 'analysis' ? item?.analysis : item?.content
  return source || item?.content || ''
}

export const sectionFigureIds = (section) => new Set(
  (section?.blocks || [])
    .filter((block) => block?.kind === 'image_area')
    .flatMap((block) => (block.placements || []).map((placement) => placement?.figure_id).filter(Boolean))
)

export const flatQuestionSections = (item) => ({
  stem: { blocks: item?.content ? [{ id: `trash-${item.id}-stem`, kind: 'text', markdown: item.content }] : [] },
  answer: { blocks: item?.answer ? [{ id: `trash-${item.id}-answer`, kind: 'text', markdown: item.answer }] : [] },
  analysis: { blocks: item?.analysis ? [{ id: `trash-${item.id}-analysis`, kind: 'text', markdown: item.analysis }] : [] }
})
