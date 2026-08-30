import assert from 'node:assert/strict'
import { createQuestionFigurePreviewRegistryCore } from '../src/utils/questionFigurePreviewRegistry.mjs'

const flush = async () => {
  await Promise.resolve()
  await Promise.resolve()
}
const created = []
const revoked = []
const requests = []
const pending = new Map()
const urlApi = {
  createObjectURL: (blob) => {
    const url = `blob:${blob.name}`
    created.push(url)
    return url
  },
  revokeObjectURL: (url) => revoked.push(url)
}
const registry = createQuestionFigurePreviewRegistryCore({
  http: {
    get: (url) => {
      requests.push(url)
      return new Promise((resolve, reject) => pending.set(url, { resolve, reject }))
    }
  },
  urlApi,
  buildFigureUrl: (questionId, id) => `/${questionId}/${id}`,
  createCropBlob: async (_, bbox) => ({ name: `crop-${bbox.join('-')}` })
})

registry.reconcile({ questionId: 7, figures: [{ id: 'hidden' }], reachableIds: new Set() })
assert.deepEqual(requests, [], 'empty sections must not request figure blobs')

const existing = { id: 'a' }
const crop = { id: 'b', kind: 'crop', crop_bbox: [0, 0, 0.2, 0.2] }
registry.reconcile({
  questionId: 7,
  figures: [existing, crop],
  reachableIds: new Set(['a', 'b']),
  source: { url: 'blob:source', generation: 1 }
})
await flush()
assert.deepEqual(requests, ['/7/a'], 'persisted figures without kind load through the authenticated endpoint')
assert.equal(registry.urlFor('b'), 'blob:crop-0-0-0.2-0.2')

registry.reconcile({ questionId: 7, figures: [existing], reachableIds: new Set(['a']) })
assert.ok(revoked.includes('blob:crop-0-0-0.2-0.2'), 'switching sections revokes unreachable previews')

registry.reconcile({ questionId: 8, figures: [], reachableIds: new Set() })
pending.get('/7/a').resolve({ data: { name: 'late' } })
await flush()
assert.ok(revoked.includes('blob:late'), 'stale blob responses are revoked immediately')

registry.reconcile({ questionId: 9, figures: [{ id: 'failed' }], reachableIds: new Set(['failed']) })
pending.get('/9/failed').reject(new Error('failed'))
await new Promise((resolve) => setImmediate(resolve))
assert.equal(registry.errorFor('failed'), '配图预览加载失败')
registry.reconcile({ questionId: 9, figures: [{ id: 'failed' }], reachableIds: new Set(['failed']) })
pending.get('/9/failed').resolve({ data: { name: 'retry-success' } })
await flush()
assert.equal(registry.urlFor('failed'), 'blob:retry-success', 'a later reconcile must retry a transient figure failure')
registry.reconcile({ questionId: 9, figures: [], reachableIds: new Set() })
assert.equal(registry.errorFor('failed'), '')

registry.reconcile({ questionId: 10, figures: [{ id: 'same' }], reachableIds: new Set(['same']) })
const beforeDispose = pending.get('/10/same')
registry.dispose()
registry.reconcile({ questionId: 10, figures: [{ id: 'same' }], reachableIds: new Set(['same']) })
const afterReopen = pending.get('/10/same')
afterReopen.resolve({ data: { name: 'new-same' } })
await flush()
beforeDispose.resolve({ data: { name: 'old-same' } })
await flush()
assert.equal(registry.urlFor('same'), 'blob:new-same', 'a pre-dispose response must not overwrite the reopened request')
assert.ok(revoked.includes('blob:old-same'))

registry.dispose()
console.log('Question figure preview registry passed.')
