// #75：面板筛选/选中状态 ↔ URL query 的双向同步工具。
// 约定：
// - 一律 router.replace，前进/后退不产生中间态历史；
// - 空值写入等价于从 URL 移除该键；
// - query 键必须带面板前缀（bank_ / user_ / paper_），避免各面板互相覆盖；
//   `tab` 键保留给 Dashboard 页签深链（#73），任何面板不得占用。
export const readStringQuery = (route, key) => {
  const value = route.query[key]
  return typeof value === 'string' ? value : ''
}

export const replaceQueryValues = (router, route, values) => {
  const query = { ...route.query }
  for (const [key, value] of Object.entries(values)) {
    if (value === '' || value === null || value === undefined) {
      delete query[key]
    } else {
      query[key] = String(value)
    }
  }
  return router.replace({ query })
}
