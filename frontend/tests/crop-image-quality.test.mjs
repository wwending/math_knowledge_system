import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import {
  CROP_JPEG_QUALITIES,
  CROP_MAX_DOWNSAMPLE_SCALE,
  CROP_MAX_ENCODING_ATTEMPTS,
  CROP_MIN_DOWNSAMPLE_SCALE,
  CROPPER_MAX_EDGE,
  CROPPER_MAX_PIXELS,
  CROP_OUTPUT_TYPE,
  CROP_UPLOAD_SOFT_LIMIT_BYTES,
  CropImageTooLargeError,
  calculateCropDownsampleScale,
  calculateCropperMaxImageSize,
  createCropUploadFile,
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
assert.throws(() => createImageUploadFile(new Blob(['unknown']), 'crop_question'), /Unsupported image MIME type/)
assert.throws(() => createImageUploadFile(new Blob(['webp'], { type: 'image/webp' }), 'crop_question'), /Unsupported image MIME type/)
assert.equal(CROP_UPLOAD_SOFT_LIMIT_BYTES, 16 * 1024 * 1024)
assert.deepEqual(CROP_JPEG_QUALITIES, [0.95, 0.9, 0.85])
assert.equal(Object.isFrozen(CROP_JPEG_QUALITIES), true)
assert.equal(CROP_MAX_ENCODING_ATTEMPTS, 4)

const TEST_SOFT_LIMIT = 1000
const sizedBlob = (size, type) => new Blob([new Uint8Array(size)], { type })
const makeEncoder = (sizes) => {
  const calls = []
  const encode = async (_source, options) => {
    calls.push(options)
    const size = sizes[calls.length - 1]
    return sizedBlob(size, options.mimeType)
  }
  return { calls, encode }
}

const smallPngEncoder = makeEncoder([])
const smallPng = await createCropUploadFile(sizedBlob(999, 'image/png'), 'crop_question', {
  softLimitBytes: TEST_SOFT_LIMIT,
  encode: smallPngEncoder.encode
})
assert.equal(smallPng.file.name, 'crop_question.png')
assert.equal(smallPng.file.type, 'image/png')
assert.equal(smallPng.file.size, 999)
assert.equal(smallPng.encodingAttempts, 0)
assert.equal(smallPngEncoder.calls.length, 0, 'small PNG must not be re-encoded')

const jpegFallbackEncoder = makeEncoder([1200, 900])
const jpegFallback = await createCropUploadFile(sizedBlob(1001, 'image/png'), 'crop_question', {
  softLimitBytes: TEST_SOFT_LIMIT,
  encode: jpegFallbackEncoder.encode
})
assert.equal(jpegFallback.file.name, 'crop_question.jpg')
assert.equal(jpegFallback.file.type, 'image/jpeg')
assert.equal(jpegFallback.file.size, 900)
assert.equal(jpegFallback.quality, 0.9)
assert.equal(jpegFallback.scale, 1, 'JPEG quality fallback must preserve pixel dimensions')
assert.equal(jpegFallback.encodingAttempts, 2)
assert.deepEqual(jpegFallbackEncoder.calls.map(({ quality }) => quality), [0.95, 0.9])

const resizedEncoder = makeEncoder([1400, 1300, 1200, 850])
const resized = await createCropUploadFile(sizedBlob(1001, 'image/png'), 'crop_question', {
  softLimitBytes: TEST_SOFT_LIMIT,
  encode: resizedEncoder.encode
})
assert.equal(resized.file.type, 'image/jpeg')
assert.equal(resized.file.name, 'crop_question.jpg')
assert.equal(resized.file.size, 850)
assert.equal(resized.quality, 0.85)
assert.equal(resized.encodingAttempts, CROP_MAX_ENCODING_ATTEMPTS)
assert.ok(resized.scale >= CROP_MIN_DOWNSAMPLE_SCALE)
assert.ok(resized.scale <= CROP_MAX_DOWNSAMPLE_SCALE)
assert.equal(resizedEncoder.calls.length, CROP_MAX_ENCODING_ATTEMPTS)
assert.deepEqual(resizedEncoder.calls.slice(0, 3).map(({ scale }) => scale), [1, 1, 1])
assert.equal(resizedEncoder.calls.at(-1).scale, resized.scale)

const failedEncoder = makeEncoder([1400, 1300, 1200, 1001])
await assert.rejects(
  createCropUploadFile(sizedBlob(1001, 'image/png'), 'crop_question', {
    softLimitBytes: TEST_SOFT_LIMIT,
    encode: failedEncoder.encode
  }),
  CropImageTooLargeError
)
assert.equal(failedEncoder.calls.length, CROP_MAX_ENCODING_ATTEMPTS, 'fallback attempts must be bounded')
assert.equal(calculateCropDownsampleScale(10_000, TEST_SOFT_LIMIT), CROP_MIN_DOWNSAMPLE_SCALE)
assert.equal(calculateCropDownsampleScale(1001, TEST_SOFT_LIMIT), CROP_MAX_DOWNSAMPLE_SCALE)

const dashboardSource = readFileSync(resolve(process.cwd(), 'src/views/Dashboard.vue'), 'utf8')
assert.match(dashboardSource, /:max-img-size="cropperMaxImgSize"/)
assert.match(dashboardSource, /:output-type="CROP_OUTPUT_TYPE"/)
assert.match(dashboardSource, /:full="true"/)
assert.match(dashboardSource, /mode="cover"/)
assert.match(dashboardSource, /:can-move="true"/)
assert.match(dashboardSource, /:can-move-box="true"/)
assert.match(dashboardSource, /:can-scale="true"/)
assert.match(dashboardSource, /:info-true="true"/)
assert.match(dashboardSource, /changeCropperScale\(-10\)/)
assert.match(dashboardSource, /changeCropperScale\(10\)/)
assert.match(dashboardSource, /拖动图片定位题目，可使用滚轮或 \+\/- 缩放/)
assert.doesNotMatch(dashboardSource, /mode="contain"/)
assert.match(dashboardSource, /await createCropUploadFile\(blob\)/)
assert.match(dashboardSource, /裁剪图片过大，请缩小裁剪范围后重试/)
assert.match(dashboardSource, /setCurrentImageSource\(''\)/)
assert.match(dashboardSource, /source\.startsWith\('blob:'\)/)
assert.match(dashboardSource, /cropEncodingGeneration \+= 1/)
assert.match(dashboardSource, /onBeforeUnmount\(\(\) => \{[\s\S]*revokeImageObjectUrl/)
assert.doesNotMatch(dashboardSource, /crop_question\.jpg/)
assert.doesNotMatch(dashboardSource, /new File\(\[blob\], 'crop_question[^']*', \{ type: 'image\/jpeg' \}\)/)

assert.match(dashboardSource, /一页多题请逐题框选录入/, 'cropper toolbar must guide per-question framing')
// #31: the toolbar sits above the viewport in normal flow — an absolutely
// positioned bar used to cover questions near the top of the page.
assert.match(
  dashboardSource,
  /class="cropper-toolbar"[\s\S]*?<vue-cropper/,
  'cropper toolbar must be rendered above the crop viewport, not after it'
)
assert.doesNotMatch(
  dashboardSource,
  /\.cropper-toolbar \{[^}]*position:\s*absolute/,
  'cropper toolbar must not overlay the viewport via absolute positioning'
)
assert.match(dashboardSource, /const cropPreviewUrl = ref\(''\)/, 'Dashboard must track the actual crop product for preview')
assert.match(
  dashboardSource,
  /setCropPreviewSource\(URL\.createObjectURL\(blob\)\)/,
  'crop upload must snapshot the encoded crop blob as the confirmation preview'
)
assert.match(dashboardSource, /setCropPreviewSource\(''\)/, 'upload reset must revoke the crop preview')
assert.match(
  dashboardSource,
  /processMode\.value === 'crop' \? cropPreviewUrl\.value : currentImageUrl\.value/,
  'confirmation preview must show the framed selection in crop mode and the full page otherwise'
)
// #22 integration: the confirmation preview owns the pre-result phase; once
// the recognition result renders, the split-layout reference panel takes over.
assert.match(
  dashboardSource,
  /v-if="resultImageUrl && !ocrResult"/,
  'confirmation preview must render before the result arrives and yield to the reference panel after'
)

console.log('Crop image quality tests passed.')
