import { boundedGet, IMAGE_TIMEOUT_MS } from './boundedRequest.mjs'

export function createQuestionImageLoaderCore({ http, urlApi, buildImageUrl, state = {}, timeout = IMAGE_TIMEOUT_MS }) {
  const urls = state.urls || (state.urls = {})
  const errors = state.errors || (state.errors = {})
  const loading = state.loading || (state.loading = {})
  const controllers = new Map()
  const pending = new Set()
  const known = new Set()
  const generations = new Map()
  const signatures = new Map()
  let epoch = 0

  const hasImage = (item) => Boolean(item?.image_url || item?.origin_image)
  const remove = (id) => {
    if (!id) return
    controllers.get(id)?.abort()
    controllers.delete(id)
    generations.set(id, (generations.get(id) || 0) + 1)
    if (urls[id]) urlApi.revokeObjectURL(urls[id])
    delete urls[id]
    delete errors[id]
    delete loading[id]
    pending.delete(id)
    signatures.delete(id)
  }
  const ensure = (item) => {
    const id = item?.id
    if (!id || pending.has(id) || urls[id]) return
    if (!hasImage(item)) return
    known.add(id)
    pending.add(id)
    errors[id] = ''
    loading[id] = true
    const controller = new AbortController()
    controllers.set(id, controller)
    const generation = (generations.get(id) || 0) + 1
    const requestEpoch = epoch
    generations.set(id, generation)
    boundedGet(http, buildImageUrl(id), { responseType: 'blob', timeout, signal: controller.signal }).then(({ data }) => {
      if (epoch !== requestEpoch || generations.get(id) !== generation) {
        const stale = urlApi.createObjectURL(data)
        urlApi.revokeObjectURL(stale)
        return
      }
      urls[id] = urlApi.createObjectURL(data)
    }).catch((error) => {
      if (epoch === requestEpoch && generations.get(id) === generation) {
        delete urls[id]
        errors[id] = error.code === 'ECONNABORTED' ? '图片加载超时，请重试' : '图片加载失败，请重试'
      }
    }).finally(() => {
      if (epoch === requestEpoch && generations.get(id) === generation) {
        pending.delete(id)
        loading[id] = false
        controllers.delete(id)
      }
    })
  }
  const syncItems = (items) => {
    const ids = new Set((items || []).map((item) => item?.id).filter(Boolean))
    ;[...known].forEach((id) => {
      if (!ids.has(id) && !ids.has(String(id))) remove(id)
    })
    ;(items || []).forEach((item) => {
      const id = item?.id
      if (!id) return
      known.add(id)
      const signature = hasImage(item) ? `image:${item.current_revision_no || ''}:${item.image_url || item.origin_image}` : 'none'
      if (signatures.has(id) && signatures.get(id) !== signature) remove(id)
      known.add(id)
      signatures.set(id, signature)
      ensure(item)
    })
  }
  const dispose = () => {
    epoch += 1
    controllers.forEach((controller) => controller.abort())
    controllers.clear()
    Object.values(urls).forEach((url) => {
      if (url) urlApi.revokeObjectURL(url)
    })
    Object.keys(urls).forEach((id) => delete urls[id])
    Object.keys(errors).forEach((id) => delete errors[id])
    Object.keys(loading).forEach((id) => delete loading[id])
    pending.clear()
    known.clear()
    signatures.clear()
    generations.clear()
  }
  const retry = (item) => { remove(item?.id); ensure(item) }
  const markFailed = (item) => { remove(item?.id); if (item?.id) errors[item.id] = '图片无法显示，请重试' }
  return { ensure, syncItems, retry, markFailed, errorFor: (item) => errors[item?.id] || '', loadingFor: (item) => Boolean(loading[item?.id]), imageUrlFor: (item) => item?.id ? urls[item.id] || '' : '', remove, dispose }
}
