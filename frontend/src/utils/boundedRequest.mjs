// Lists are small JSON responses; image generation/download gets a longer budget.
export const LIST_TIMEOUT_MS = 15000
export const IMAGE_TIMEOUT_MS = 30000

export function boundedGet(http, url, { timeout = LIST_TIMEOUT_MS, signal, ...options } = {}) {
  const controller = new AbortController()
  return new Promise((resolve, reject) => {
    let settled = false
    const finish = (callback, value) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      signal?.removeEventListener('abort', cancel)
      callback(value)
    }
    const cancel = () => {
      controller.abort()
      finish(reject, Object.assign(new Error('请求已取消'), { code: 'ERR_CANCELED' }))
    }
    const timer = setTimeout(() => {
      controller.abort()
      finish(reject, Object.assign(new Error('请求超时，请重试'), { code: 'ECONNABORTED' }))
    }, timeout)
    signal?.addEventListener('abort', cancel, { once: true })
    if (signal?.aborted) return cancel()
    try {
      Promise.resolve(http.get(url, { ...options, timeout, signal: controller.signal }))
        .then(value => finish(resolve, value), error => finish(reject, error))
    } catch (error) {
      finish(reject, error)
    }
  })
}
