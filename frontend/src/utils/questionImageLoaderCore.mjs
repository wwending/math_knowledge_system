export function createQuestionImageLoaderCore({ http, urlApi, buildImageUrl, state = {} }) {
  const urls = state.urls || (state.urls = {})
  const pending = new Set()
  const known = new Set()
  const generations = new Map()
  const remove = (id) => { if (!id) return; generations.set(id, (generations.get(id) || 0) + 1); if (urls[id]) urlApi.revokeObjectURL(urls[id]); delete urls[id]; pending.delete(id) }
  const ensure = (item) => {
    const id = item?.id
    if (!id || pending.has(id) || urls[id] !== undefined) return
    if (!item.image_url && !item.origin_image) { urls[id] = ''; return }
    known.add(id); pending.add(id); const generation = (generations.get(id) || 0) + 1; generations.set(id, generation)
    http.get(buildImageUrl(id), { responseType: 'blob' }).then(({ data }) => {
      if (generations.get(id) !== generation) { const stale = urlApi.createObjectURL(data); urlApi.revokeObjectURL(stale); return }
      urls[id] = urlApi.createObjectURL(data)
    }).catch(() => { if (generations.get(id) === generation) urls[id] = '' }).finally(() => { if (generations.get(id) === generation) pending.delete(id) })
  }
  const syncItems = (items) => { const ids = new Set((items || []).map((x) => x?.id).filter(Boolean)); [...known].forEach((id) => { if (!ids.has(id) && !ids.has(String(id))) remove(id) }); (items || []).forEach((item) => { known.add(item?.id); ensure(item) }) }
  const dispose = () => { Object.values(urls).forEach((url) => { if (url) urlApi.revokeObjectURL(url) }); Object.keys(urls).forEach((id) => delete urls[id]); pending.clear(); known.clear(); generations.clear() }
  return { syncItems, imageUrlFor: (item) => item?.id ? urls[item.id] || '' : '', remove, dispose }
}
