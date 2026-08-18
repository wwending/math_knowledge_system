export const CROPPER_MAX_EDGE = 8192
export const CROPPER_MAX_PIXELS = 36_000_000
export const CROP_OUTPUT_TYPE = 'png'
export const CROP_UPLOAD_SOFT_LIMIT_BYTES = 16 * 1024 * 1024
export const CROP_JPEG_QUALITIES = Object.freeze([0.95, 0.9, 0.85])
export const CROP_MIN_DOWNSAMPLE_SCALE = 0.75
export const CROP_MAX_DOWNSAMPLE_SCALE = 0.9
export const CROP_MAX_ENCODING_ATTEMPTS = CROP_JPEG_QUALITIES.length + 1

const normalizeDimension = (value) => {
  const dimension = Number(value)
  return Number.isFinite(dimension) && dimension > 0 ? dimension : null
}

export const calculateCropperMaxImageSize = (width, height) => {
  const normalizedWidth = normalizeDimension(width)
  const normalizedHeight = normalizeDimension(height)
  if (!normalizedWidth || !normalizedHeight) {
    return CROPPER_MAX_EDGE
  }

  const longSide = Math.max(normalizedWidth, normalizedHeight)
  const shortSide = Math.min(normalizedWidth, normalizedHeight)
  const pixelLimitedLongSide = Math.floor(
    Math.sqrt(CROPPER_MAX_PIXELS * (longSide / shortSide))
  )

  return Math.max(1, Math.floor(Math.min(longSide, CROPPER_MAX_EDGE, pixelLimitedLongSide)))
}

export const imageExtensionForMime = (mimeType) => {
  if (mimeType === 'image/png') {
    return 'png'
  }
  if (mimeType === 'image/jpeg') {
    return 'jpg'
  }
  throw new Error(`Unsupported image MIME type: ${mimeType || '(empty)'}`)
}

export const createImageUploadFile = (blob, basename) => {
  const mimeType = blob.type
  const extension = imageExtensionForMime(mimeType)
  return new File([blob], `${basename}.${extension}`, { type: mimeType })
}

export class CropImageTooLargeError extends Error {
  constructor() {
    super('Crop image exceeds the frontend upload limit after bounded encoding fallbacks')
    this.name = 'CropImageTooLargeError'
  }
}

export const calculateCropDownsampleScale = (
  encodedBytes,
  softLimitBytes = CROP_UPLOAD_SOFT_LIMIT_BYTES
) => {
  if (!Number.isFinite(encodedBytes) || encodedBytes <= 0 || !Number.isFinite(softLimitBytes) || softLimitBytes <= 0) {
    return CROP_MIN_DOWNSAMPLE_SCALE
  }

  const estimatedScale = Math.sqrt(softLimitBytes / encodedBytes) * 0.95
  return Math.max(
    CROP_MIN_DOWNSAMPLE_SCALE,
    Math.min(CROP_MAX_DOWNSAMPLE_SCALE, estimatedScale)
  )
}

const canvasToBlob = (canvas, mimeType, quality) => new Promise((resolve, reject) => {
  canvas.toBlob((blob) => {
    if (blob) {
      resolve(blob)
      return
    }
    reject(new Error(`Unable to encode crop as ${mimeType}`))
  }, mimeType, quality)
})

const loadBlobImage = async (blob) => {
  if (typeof createImageBitmap === 'function') {
    const bitmap = await createImageBitmap(blob)
    return {
      image: bitmap,
      width: bitmap.width,
      height: bitmap.height,
      release: () => bitmap.close()
    }
  }

  const objectUrl = URL.createObjectURL(blob)
  try {
    const image = new Image()
    image.src = objectUrl
    await image.decode()
    return {
      image,
      width: image.naturalWidth,
      height: image.naturalHeight,
      release: () => URL.revokeObjectURL(objectUrl)
    }
  } catch (error) {
    URL.revokeObjectURL(objectUrl)
    throw error
  }
}

export const reencodeImageBlob = async (
  sourceBlob,
  { mimeType = 'image/jpeg', quality = 0.85, scale = 1 } = {}
) => {
  const decoded = await loadBlobImage(sourceBlob)
  try {
    const width = Math.max(1, Math.floor(decoded.width * scale))
    const height = Math.max(1, Math.floor(decoded.height * scale))
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (!context) {
      throw new Error('Unable to create crop encoding canvas')
    }
    if (mimeType === 'image/jpeg') {
      context.fillStyle = '#fff'
      context.fillRect(0, 0, width, height)
    }
    context.drawImage(decoded.image, 0, 0, width, height)
    return await canvasToBlob(canvas, mimeType, quality)
  } finally {
    decoded.release()
  }
}

export const createCropUploadFile = async (
  sourcePngBlob,
  basename = 'crop_question',
  {
    softLimitBytes = CROP_UPLOAD_SOFT_LIMIT_BYTES,
    encode = reencodeImageBlob
  } = {}
) => {
  if (sourcePngBlob.size <= softLimitBytes) {
    return {
      file: createImageUploadFile(sourcePngBlob, basename),
      quality: null,
      scale: 1,
      encodingAttempts: 0
    }
  }

  let lastJpeg = null
  for (const quality of CROP_JPEG_QUALITIES) {
    lastJpeg = await encode(sourcePngBlob, { mimeType: 'image/jpeg', quality, scale: 1 })
    if (lastJpeg.type !== 'image/jpeg') {
      throw new Error('Browser did not produce the requested JPEG crop')
    }
    if (lastJpeg.size <= softLimitBytes) {
      return {
        file: createImageUploadFile(lastJpeg, basename),
        quality,
        scale: 1,
        encodingAttempts: CROP_JPEG_QUALITIES.indexOf(quality) + 1
      }
    }
  }

  const scale = calculateCropDownsampleScale(lastJpeg?.size, softLimitBytes)
  const resizedJpeg = await encode(sourcePngBlob, {
    mimeType: 'image/jpeg',
    quality: CROP_JPEG_QUALITIES.at(-1),
    scale
  })
  if (resizedJpeg.type !== 'image/jpeg') {
    throw new Error('Browser did not produce the requested resized JPEG crop')
  }
  if (resizedJpeg.size <= softLimitBytes) {
    return {
      file: createImageUploadFile(resizedJpeg, basename),
      quality: CROP_JPEG_QUALITIES.at(-1),
      scale,
      encodingAttempts: CROP_MAX_ENCODING_ATTEMPTS
    }
  }

  throw new CropImageTooLargeError()
}
