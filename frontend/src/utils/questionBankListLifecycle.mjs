export const beginQuestionListRequest = (generation) => ({
  generation: generation + 1,
  items: []
})

export const acceptsQuestionListResponse = (requestGeneration, currentGeneration) =>
  requestGeneration === currentGeneration
