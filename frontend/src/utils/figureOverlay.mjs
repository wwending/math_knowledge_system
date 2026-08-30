// Pure coordinate math for the detected-figure confirmation editor.
// Bboxes are [x, y, w, h] normalized to [0, 1], mirroring the backend.

export const FIGURE_BBOX_MIN_AREA = 0.01
export const FIGURE_READING_ROW_TOLERANCE = 0.015
export const MAX_CONFIRMED_FIGURES = 10

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

const bboxFrom = (item) => Array.isArray(item) ? item : item?.bbox

export const sortFigureBboxesReadingOrder = (items) => (Array.isArray(items) ? items : [])
  .map((item, index) => ({ bbox: bboxFrom(item), index }))
  .filter(({ bbox }) => isValidFigureBbox(bbox))
  .sort((left, right) => {
    const vertical = left.bbox[1] - right.bbox[1]
    if (Math.abs(vertical) > FIGURE_READING_ROW_TOLERANCE) {
      return vertical
    }
    return left.bbox[0] - right.bbox[0] || left.index - right.index
  })
  .map(({ bbox }) => bbox.map(Number))

export const figureBboxesOverlap = (left, right, epsilon = 1e-9) => {
  if (!isValidFigureBbox(left) || !isValidFigureBbox(right)) {
    return false
  }
  const [lx, ly, lw, lh] = left.map(Number)
  const [rx, ry, rw, rh] = right.map(Number)
  return Math.min(lx + lw, rx + rw) - Math.max(lx, rx) > epsilon
    && Math.min(ly + lh, ry + rh) - Math.max(ly, ry) > epsilon
}

export const findOverlappingFigureBboxes = (bboxes) => {
  const values = Array.isArray(bboxes) ? bboxes : []
  const conflicts = []
  for (let left = 0; left < values.length; left += 1) {
    for (let right = left + 1; right < values.length; right += 1) {
      if (figureBboxesOverlap(values[left], values[right])) {
        conflicts.push([left, right])
      }
    }
  }
  return conflicts
}
