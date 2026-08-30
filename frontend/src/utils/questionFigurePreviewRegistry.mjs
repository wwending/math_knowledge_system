export function createQuestionFigurePreviewRegistryCore({ http, urlApi, buildFigureUrl, createCropBlob, state = {} }) {
  const urls = state.urls || (state.urls = {})
  const errors = state.errors || (state.errors = {})
  const generations = new Map()
  const fingerprints = new Map()
  const pending = new Set()
  let epoch = 0
  let wanted = new Set()

  const revoke = (id) => {
    generations.set(id, (generations.get(id) || 0) + 1)
    if (urls[id]) urlApi.revokeObjectURL(urls[id])
    delete urls[id]; delete errors[id]; fingerprints.delete(id)
  }
  const store = (id, requestEpoch, generation, fingerprint, blob) => {
    if (epoch !== requestEpoch || !wanted.has(id) || generations.get(id) !== generation || fingerprints.get(id) !== fingerprint) {
      const stale = urlApi.createObjectURL(blob); urlApi.revokeObjectURL(stale); return
    }
    if (urls[id]) urlApi.revokeObjectURL(urls[id])
    urls[id] = urlApi.createObjectURL(blob); errors[id] = ''
  }
  const load = (questionId, figure, source) => {
    const id = figure.id
    const fingerprint = figure.kind === 'crop' ? `crop:${figure.crop_bbox.join(',')}:${source?.generation || 0}` : `existing:${questionId}`
    if (fingerprints.get(id) === fingerprint && (urls[id] !== undefined || pending.has(id))) return
    revoke(id); fingerprints.set(id, fingerprint)
    pending.add(id)
    const generation = (generations.get(id) || 0) + 1
    const requestEpoch = epoch
    generations.set(id, generation)
    const task = figure.kind === 'crop'
      ? createCropBlob(source, figure.crop_bbox)
      : http.get(buildFigureUrl(questionId, id), { responseType: 'blob' }).then((response) => response.data)
    Promise.resolve(task).then((blob) => store(id, requestEpoch, generation, fingerprint, blob)).catch(() => {
      if (epoch === requestEpoch && wanted.has(id) && generations.get(id) === generation) errors[id] = '配图预览加载失败'
    }).finally(() => {
      if (epoch === requestEpoch && generations.get(id) === generation) pending.delete(id)
    })
  }
  const reconcile = ({ questionId, figures = [], reachableIds, source }) => {
    wanted = new Set(reachableIds || figures.map((figure) => figure.id))
    Object.keys(urls).forEach((id) => { if (!wanted.has(id)) revoke(id) })
    Object.keys(errors).forEach((id) => { if (!wanted.has(id)) revoke(id) })
    figures.filter((figure) => wanted.has(figure.id)).forEach((figure) => load(questionId, figure, source))
  }
  const dispose = () => {
    epoch += 1
    wanted = new Set()
    ;[...new Set([...Object.keys(urls), ...fingerprints.keys()])].forEach(revoke)
    pending.clear()
  }
  return { urls, errors, reconcile, urlFor: (id) => urls[id] || '', errorFor: (id) => errors[id] || '', revoke, dispose }
}

export const cropBlobFromImage = async (source, bbox) => {
  if (!source?.url) throw new Error('source image is unavailable')
  const image = new Image()
  image.src = source.url
  if (image.decode) await image.decode()
  else await new Promise((resolve, reject) => { image.onload = resolve; image.onerror = reject })
  const [x, y, width, height] = bbox
  const left = Math.min(Math.max(Math.round(x * image.naturalWidth), 0), image.naturalWidth - 1)
  const top = Math.min(Math.max(Math.round(y * image.naturalHeight), 0), image.naturalHeight - 1)
  const right = Math.min(Math.max(Math.round((x + width) * image.naturalWidth), left + 1), image.naturalWidth)
  const bottom = Math.min(Math.max(Math.round((y + height) * image.naturalHeight), top + 1), image.naturalHeight)
  const canvas = document.createElement('canvas'); canvas.width = right - left; canvas.height = bottom - top
  canvas.getContext('2d').drawImage(image, left, top, canvas.width, canvas.height, 0, 0, canvas.width, canvas.height)
  return await new Promise((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('crop preview failed')), 'image/png'))
}
