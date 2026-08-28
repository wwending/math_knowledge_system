import assert from 'node:assert/strict'
import { acceptsImageGeneration } from '../src/utils/questionImageLoaderHelpers.mjs'

assert.equal(acceptsImageGeneration(3, 3), true)
assert.equal(acceptsImageGeneration(3, 2), false)
assert.equal(acceptsImageGeneration(undefined, 1), false)
console.log('Question bank lifecycle behavior helpers passed.')
