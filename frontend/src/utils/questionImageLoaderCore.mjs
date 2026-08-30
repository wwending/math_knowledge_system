export function createQuestionImageLoaderCore({ http, urlApi, buildImageUrl, state = {} }) {
  const urls = state.urls || (state.urls = {})
  const pending = new Set()
  const known = new Set()
  const generations = new Map()
  const signatures = new Map()
  let epoch = 0

  const hasImage = (item) => Boolean(item?.image_url || item?.origin_image)
  const remove = (id) => {
    if (!id) return
    generations.set(id, (generations.get(id) || 0) + 1)
    if (urls[id]) urlApi.revokeObjectURL(urls[id])
    delete urls[id]
    pending.delete(id)
    signatures.delete(id)
  }
  const ensure = (item) => {
    const id = item?.id
    if (!id || pending.has(id) || urls[id]) return
    if (!hasImage(item)) return
    known.add(id)
    pending.add(id)
    const generation = (generations.get(id) || 0) + 1
    const requestEpoch = epoch
    generations.set(id, generation)
    http.get(buildImageUrl(id), { responseType: 'blob' }).then(({ data }) => {
      if (epoch !== requestEpoch || generations.get(id) !== generation) {
        const stale = urlApi.createObjectURL(data)
        urlApi.revokeObjectURL(stale)
        return
      }
      urls[id] = urlApi.createObjectURL(data)
    }).catch(() => {
      if (epoch === requestEpoch && generations.get(id) === generation) delete urls[id]
    }).finally(() => {
      if (epoch === requestEpoch && generations.get(id) === generation) pending.delete(id)
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
      const signature = hasImage(item) ? 'image' : 'none'
      if (signatures.has(id) && signatures.get(id) !== signature) remove(id)
      known.add(id)
      signatures.set(id, signature)
      ensure(item)
    })
  }
  const dispose = () => {
    epoch += 1
    Object.values(urls).forEach((url) => {
      if (url) urlApi.revokeObjectURL(url)
    })
    Object.keys(urls).forEach((id) => delete urls[id])
    pending.clear()
    known.clear()
    signatures.clear()
  }
  return { ensure, syncItems, imageUrlFor: (item) => item?.id ? urls[item.id] || '' : '', remove, dispose }
}
