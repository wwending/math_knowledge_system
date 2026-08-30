import assert from 'node:assert/strict'
import { acceptsImageGeneration } from '../src/utils/questionImageLoaderHelpers.mjs'
import { acceptsQuestionListResponse, beginQuestionListRequest } from '../src/utils/questionBankListLifecycle.mjs'

assert.equal(acceptsImageGeneration(3, 3), true)
assert.equal(acceptsImageGeneration(3, 2), false)
assert.equal(acceptsImageGeneration(undefined, 1), false)

let generation = 4
let items = [{ id: 1, lifecycle: 'active' }]
let request = beginQuestionListRequest(generation)
generation = request.generation
items = request.items
assert.deepEqual(items, [], 'active to trash clears active rows before the trash request settles')
assert.equal(acceptsQuestionListResponse(generation, generation), true)
// The trash request fails: no assignment occurs and the list stays empty.
assert.deepEqual(items, [])

items = [{ id: 2, lifecycle: 'trash' }]
request = beginQuestionListRequest(generation)
generation = request.generation
items = request.items
assert.deepEqual(items, [], 'trash to active clears trash rows before the active request settles')
const staleGeneration = generation
request = beginQuestionListRequest(generation)
generation = request.generation
assert.equal(acceptsQuestionListResponse(staleGeneration, generation), false, 'late responses cannot restore a prior lifecycle list')

console.log('Question bank lifecycle behavior helpers passed.')
