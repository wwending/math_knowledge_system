export const QUESTION_BBOX_MIN_AREA = 0.0025
export const QUESTION_RECOGNITION_CONCURRENCY = 2
export const QUESTION_RECOGNITION_TIMEOUT_MS = 120_000

export const clampUnit = (value) => Math.min(1, Math.max(0, Number(value) || 0))

export const normalizeQuestionBbox = (bbox, minArea = QUESTION_BBOX_MIN_AREA) => {
  if (!Array.isArray(bbox) || bbox.length !== 4 || !bbox.every((value) => Number.isFinite(Number(value)))) {
    return null
  }
  let [x, y, width, height] = bbox.map(Number)
  x = clampUnit(x)
  y = clampUnit(y)
  width = Math.min(clampUnit(width), 1 - x)
  height = Math.min(clampUnit(height), 1 - y)
  if (width <= 0 || height <= 0 || width * height < minArea) {
    return null
  }
  return [x, y, width, height]
}

export const pointerRangeToQuestionBbox = (start, end) => normalizeQuestionBbox([
  Math.min(start.x, end.x),
  Math.min(start.y, end.y),
  Math.abs(end.x - start.x),
  Math.abs(end.y - start.y),
])

export const sortQuestionBoxes = (boxes) => [...boxes].sort((left, right) => {
  const vertical = left.bbox[1] - right.bbox[1]
  return Math.abs(vertical) > 0.015 ? vertical : left.bbox[0] - right.bbox[0]
})

// The editor owns manual order. Sorting is an explicit user action, never an implicit submit side effect.
// When a box is unchanged from a previous run, its Draft id and content are reused so re-confirming
// after "返回框选" does not create duplicate Drafts for already-saved questions; already-saved questions
// keep their saved state and are skipped on the next run.
export const createQuestionJobs = (boxes, previousJobs = []) => {
  const previousById = new Map((previousJobs || []).map((job) => [job.id, job]))
  return boxes.map((box, index) => {
    const previous = previousById.get(box.id)
    const unchanged = previous && previous.bbox && previous.bbox.length === 4
      && previous.bbox.every((value, i) => value === box.bbox[i])
    const preservedSaved = unchanged && previous.status === 'saved_to_bank'
    return {
      id: box.id,
      number: index + 1,
      bbox: [...box.bbox],
      status: preservedSaved ? 'saved_to_bank' : 'queued',
      draftId: unchanged && previous.draftId ? previous.draftId : null,
      content: unchanged ? previous.content || '' : '',
      editContent: unchanged ? previous.content || '' : '',
      error: '',
      warning: '',
      qualityWarnings: unchanged ? previous.qualityWarnings || [] : [],
      recognitionDebug: unchanged ? previous.recognitionDebug : null,
      detectedFigures: unchanged ? previous.detectedFigures || [] : [],
      confirmedFigureBbox: unchanged ? previous.confirmedFigureBbox : null,
      saving: false,
      editing: false,
      saveResult: preservedSaved ? previous.saveResult || null : null,
    }
  })
}

export const isRecognizeTimeout = (error) =>
  error?.code === 'ECONNABORTED' || /timeout/i.test(String(error?.message || ''))

export const reconcileDraftStatus = (payload) => {
  const status = payload?.status || ''
  if (status === 'draft_ready' || status === 'saved_to_bank') {
    return { terminal: true, succeeded: true, status }
  }
  if (status === 'failed') {
    return { terminal: true, succeeded: false, status }
  }
  return { terminal: false, succeeded: false, status: status || 'recognizing' }
}

export const createConcurrencyGate = (limit = QUESTION_RECOGNITION_CONCURRENCY) => {
  const maximum = Math.max(1, Number(limit) || 1)
  let active = 0
  const waiting = []
  const release = () => {
    active -= 1
    waiting.shift()?.()
  }
  return async (task) => {
    if (active >= maximum) await new Promise((resolve) => waiting.push(resolve))
    active += 1
    try { return await task() } finally { release() }
  }
}

export const runWithConcurrency = async (items, worker, limit = QUESTION_RECOGNITION_CONCURRENCY) => {
  const concurrency = Math.max(1, Math.min(Number(limit) || 1, items.length || 1))
  let cursor = 0
  const runners = Array.from({ length: concurrency }, async () => {
    while (cursor < items.length) {
      const index = cursor
      cursor += 1
      await worker(items[index], index)
    }
  })
  await Promise.all(runners)
}
