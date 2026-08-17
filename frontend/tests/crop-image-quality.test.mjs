import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import {
  CROPPER_MAX_EDGE,
  CROPPER_MAX_PIXELS,
  CROP_OUTPUT_TYPE,
  calculateCropperMaxImageSize,
  createImageUploadFile
} from '../src/utils/imageProcessing.mjs'

const applyVueCropperMaxSize = (width, height, maxImgSize) => {
  let scaledWidth = width
  let scaledHeight = height
  if (scaledWidth > maxImgSize) {
    scaledHeight = (scaledHeight / scaledWidth) * maxImgSize
    scaledWidth = maxImgSize
  }
  if (scaledHeight > maxImgSize) {
    scaledWidth = (scaledWidth / scaledHeight) * maxImgSize
    scaledHeight = maxImgSize
  }
  return { width: Math.round(scaledWidth), height: Math.round(scaledHeight) }
}

const a4Scan = { width: 4961, height: 7016 }
const a4MaxSize = calculateCropperMaxImageSize(a4Scan.width, a4Scan.height)
assert.equal(a4MaxSize, 7016, 'a 600 DPI A4 scan must retain its source pixels')
assert.deepEqual(
  applyVueCropperMaxSize(a4Scan.width, a4Scan.height, a4MaxSize),
  a4Scan,
  'vue-cropper input must not fall back to its 2000px default for a normal high-resolution scan'
)

const oversized = { width: 6000, height: 8000 }
const oversizedMaxSize = calculateCropperMaxImageSize(oversized.width, oversized.height)
const bounded = applyVueCropperMaxSize(oversized.width, oversized.height, oversizedMaxSize)
assert.ok(Math.max(bounded.width, bounded.height) <= CROPPER_MAX_EDGE)
assert.ok(bounded.width * bounded.height <= CROPPER_MAX_PIXELS)
assert.ok(Math.abs(bounded.width / bounded.height - oversized.width / oversized.height) < 0.001)
assert.equal(calculateCropperMaxImageSize(20_000, 1000), CROPPER_MAX_EDGE)
assert.equal(calculateCropperMaxImageSize(0, Number.NaN), CROPPER_MAX_EDGE)

const pngBlob = new Blob(['lossless crop'], { type: 'image/png' })
const uploadFile = createImageUploadFile(pngBlob, 'crop_question')
assert.equal(uploadFile.name, 'crop_question.png')
assert.equal(uploadFile.type, 'image/png')
assert.equal(CROP_OUTPUT_TYPE, 'png')

const dashboardSource = readFileSync(resolve(process.cwd(), 'src/views/Dashboard.vue'), 'utf8')
assert.match(dashboardSource, /:max-img-size="cropperMaxImgSize"/)
assert.match(dashboardSource, /:output-type="CROP_OUTPUT_TYPE"/)
assert.match(dashboardSource, /:full="true"/)
assert.doesNotMatch(dashboardSource, /crop_question\.jpg/)
assert.doesNotMatch(dashboardSource, /new File\(\[blob\], 'crop_question[^']*', \{ type: 'image\/jpeg' \}\)/)

console.log('Crop image quality tests passed.')
