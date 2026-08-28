export const cloneQuestionDraft = (value) => JSON.parse(JSON.stringify(value))

export const normalizeQuestionDraft = (question = {}) => ({
  content: question.content || '',
  answer: question.answer || '',
  analysis: question.analysis || '',
  knowledge_tags: (question.knowledge_tags || [])
    .map((tag) => (typeof tag === 'string' ? tag : tag.label))
    .filter(Boolean),
  question_type: question.question_type || 'unknown',
  difficulty_level: Number(question.difficulty_level) || 0
})

export const applyDraftToQuestion = (question, draft) => ({
  ...question,
  ...draft
})

export const isQuestionDraftDirty = (draft, baseline) => (
  JSON.stringify(draft) !== JSON.stringify(baseline)
)

export const mergeSavedQuestionResponse = (currentQuestion, savedResponse) => {
  const question = savedResponse?.question || savedResponse
  if (!question || typeof question !== 'object') return currentQuestion
  const revision = savedResponse?.current_revision_no ?? question.current_revision_no
  return {
    ...currentQuestion,
    ...question,
    current_revision_no: revision ?? currentQuestion?.current_revision_no
  }
}
