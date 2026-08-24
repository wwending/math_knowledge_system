// Pure coordinate math for the #58 figure-region overlay editor.
// Bboxes are [x, y, w, h] normalized to [0, 1], mirroring the backend
// FigureDetection schema. Kept dependency-free so Node can import it directly.

export const FIGURE_BBOX_MIN_AREA = 0.005

export const clamp01 = (value) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return 0
  }
  return Math.min(1, Math.max(0, numeric))
}

export const isValidFigureBbox = (bbox, minArea = FIGURE_BBOX_MIN_AREA) => {
  if (!Array.isArray(bbox) || bbox.length !== 4) {
    return false
  }
  if (!bbox.every((value) => Number.isFinite(Number(value)))) {
    return false
  }
  const [x, y, w, h] = bbox.map(Number)
  if (x < 0 || y < 0 || x > 1 || y > 1 || w <= 0 || h <= 0 || x + w > 1 || y + h > 1) {
    return false
  }
  return w * h >= minArea
}

// Convert a drag rectangle captured in display pixels into a normalized bbox.
export const pointerRectToBbox = (startX, startY, endX, endY, displayWidth, displayHeight) => {
  if (!Number.isFinite(displayWidth) || !Number.isFinite(displayHeight) || displayWidth <= 0 || displayHeight <= 0) {
    return null
  }
  const left = Math.min(startX, endX)
  const top = Math.min(startY, endY)
  const width = Math.abs(endX - startX)
  const height = Math.abs(endY - startY)
  const bbox = [
    clamp01(left / displayWidth),
    clamp01(top / displayHeight),
    clamp01(width / displayWidth),
    clamp01(height / displayHeight),
  ]
  return isValidFigureBbox(bbox) ? bbox : null
}

// Convert a normalized bbox to absolute px offsets for overlay positioning.
export const bboxToStylePx = (bbox, displayWidth, displayHeight) => {
  if (!isValidFigureBbox(bbox) || displayWidth <= 0 || displayHeight <= 0) {
    return null
  }
  const [x, y, w, h] = bbox.map(Number)
  return {
    left: `${(x * displayWidth).toFixed(2)}px`,
    top: `${(y * displayHeight).toFixed(2)}px`,
    width: `${(w * displayWidth).toFixed(2)}px`,
    height: `${(h * displayHeight).toFixed(2)}px`,
  }
}

// Pick the primary figure from backend detections: highest score wins,
// ties broken by reading order (top-to-bottom, left-to-right).
export const pickPrimaryBox = (detections) => {
  if (!Array.isArray(detections) || detections.length === 0) {
    return null
  }
  const valid = detections.filter((item) => isValidFigureBbox(item?.bbox))
  if (valid.length === 0) {
    return null
  }
  return valid.reduce((best, current) => {
    const bestScore = Number(best.score ?? 0)
    const currentScore = Number(current.score ?? 0)
    if (currentScore !== bestScore) {
      return currentScore > bestScore ? current : best
    }
    const [bx, by] = best.bbox
    const [cx, cy] = current.bbox
    return cy < by || (cy === by && cx < bx) ? current : best
  })
}
