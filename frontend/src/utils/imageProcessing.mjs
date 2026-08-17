export const CROPPER_MAX_EDGE = 8192
export const CROPPER_MAX_PIXELS = 36_000_000
export const CROP_OUTPUT_TYPE = 'png'

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
  if (mimeType === 'image/webp') {
    return 'webp'
  }
  return 'jpg'
}

export const createImageUploadFile = (blob, basename) => {
  const mimeType = blob.type || 'image/jpeg'
  const extension = imageExtensionForMime(mimeType)
  return new File([blob], `${basename}.${extension}`, { type: mimeType })
}
