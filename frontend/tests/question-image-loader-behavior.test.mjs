import assert from 'node:assert/strict'
import { createQuestionImageLoaderCore } from '../src/utils/questionImageLoaderCore.mjs'
const deferred = []
const http = { get: () => new Promise((resolve) => deferred.push(resolve)) }
const created = []; const revoked = []
const urlApi = { createObjectURL: (blob) => { const u = `blob:${blob.id}:${created.length}`; created.push(u); return u }, revokeObjectURL: (u) => revoked.push(u) }
const loader = createQuestionImageLoaderCore({ http, urlApi, buildImageUrl: (id) => `/image/${id}` })
loader.syncItems([{ id: 1, image_url: true }]); loader.syncItems([]); deferred.shift()({ data: { id: 1 } }); await Promise.resolve(); assert.equal(loader.imageUrlFor({ id: 1 }), ''); assert.equal(revoked.length, 1)
loader.syncItems([{ id: 2, image_url: true }]); loader.remove(2); deferred.shift()({ data: { id: 2 } }); await Promise.resolve(); assert.equal(loader.imageUrlFor({ id: 2 }), '')
loader.syncItems([{ id: 3, image_url: true }]); const old = deferred.shift(); loader.remove(3); loader.syncItems([{ id: 3, image_url: true }]); const newer = deferred.shift(); old({ data: { id: 'old' } }); newer({ data: { id: 'new' } }); await Promise.resolve(); assert.equal(loader.imageUrlFor({ id: 3 }), 'blob:new:3')
loader.dispose(); assert.ok(revoked.includes('blob:new:3'))
console.log('Question image loader behavior passed.')
