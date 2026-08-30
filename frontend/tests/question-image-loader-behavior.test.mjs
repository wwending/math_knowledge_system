import assert from 'node:assert/strict'
import { createQuestionImageLoaderCore } from '../src/utils/questionImageLoaderCore.mjs'

const deferred = []
const http = { get: () => new Promise((resolve, reject) => deferred.push({ resolve, reject })) }
const created = []
const revoked = []
const urlApi = {
  createObjectURL: (blob) => { const url = `blob:${blob.id}:${created.length}`; created.push(url); return url },
  revokeObjectURL: (url) => revoked.push(url)
}
const loader = createQuestionImageLoaderCore({ http, urlApi, buildImageUrl: (id) => `/image/${id}` })

loader.syncItems([{ id: 1, image_url: true }])
loader.syncItems([])
deferred.shift().resolve({ data: { id: 1 } })
await Promise.resolve()
assert.equal(loader.imageUrlFor({ id: 1 }), '')
assert.equal(revoked.length, 1)

loader.syncItems([{ id: 2, image_url: true }])
loader.remove(2)
deferred.shift().resolve({ data: { id: 2 } })
await Promise.resolve()
assert.equal(loader.imageUrlFor({ id: 2 }), '')

loader.syncItems([{ id: 3, image_url: true }])
const old = deferred.shift()
loader.remove(3)
loader.syncItems([{ id: 3, image_url: true }])
const newer = deferred.shift()
old.resolve({ data: { id: 'old' } })
newer.resolve({ data: { id: 'new' } })
await Promise.resolve()
assert.equal(loader.imageUrlFor({ id: 3 }), 'blob:new:3')

loader.syncItems([{ id: 4 }])
assert.equal(deferred.length, 0)
loader.syncItems([{ id: 4, image_url: true }])
assert.equal(deferred.length, 1, 'an item changing from no image to image must load')
deferred.shift().resolve({ data: { id: 4 } })
await Promise.resolve()
assert.ok(loader.imageUrlFor({ id: 4 }))

loader.syncItems([{ id: 5, image_url: true }])
deferred.shift().reject(new Error('temporary failure'))
await new Promise((resolve) => setImmediate(resolve))
loader.syncItems([{ id: 5, image_url: true }])
assert.equal(deferred.length, 1, 'failed image loads must be retryable')
deferred.shift().resolve({ data: { id: 5 } })
await Promise.resolve()
assert.ok(loader.imageUrlFor({ id: 5 }))

loader.dispose()
assert.ok(revoked.includes('blob:new:3'))

loader.syncItems([{ id: 6, image_url: true }])
const beforeDispose = deferred.shift()
loader.dispose()
loader.syncItems([{ id: 6, image_url: true }])
const afterReopen = deferred.shift()
afterReopen.reject(new Error('new request failed'))
beforeDispose.resolve({ data: { id: 'old-after-dispose' } })
await new Promise((resolve) => setImmediate(resolve))
assert.equal(loader.imageUrlFor({ id: 6 }), '', 'a pre-dispose response must not populate the reopened loader')
assert.ok(revoked.some((url) => url.startsWith('blob:old-after-dispose:')), 'the stale pre-dispose blob must be revoked')

loader.dispose()

loader.ensure({ id: 7, image_url: true })
deferred.shift().reject(new Error('thumbnail failed'))
await new Promise((resolve) => setImmediate(resolve))
loader.ensure({ id: 7, image_url: true })
assert.equal(deferred.length, 1, 'opening a detail retries a failed thumbnail without syncing it into the list')
deferred.shift().resolve({ data: { id: 'detail-image' } })
await new Promise((resolve) => setImmediate(resolve))
assert.ok(loader.imageUrlFor({ id: 7 }), 'a list-external detail item can load its region image directly')

loader.dispose()
console.log('Question image loader behavior passed.')
