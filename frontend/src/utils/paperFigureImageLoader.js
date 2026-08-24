import { reactive } from 'vue'
import axios from 'axios'

import { buildPaperItemImageUrl } from '../config/api'

// Loads the figures frozen in paper items through the authenticated papers
// endpoint (#59). Plain <img> cannot attach an Authorization header, so figures
// are prefetched as blobs over the global axios instance (reusing its
// interceptors, including the 401 refresh retry) and rendered via object URLs.
// Keyed by paper_item_id; items that disappear from the render model have their
// object URLs revoked immediately, and responses landing after removal are
// dropped instead of leaking a blob. Callers must invoke dispose() on unmount.
export function createPaperFigureImageLoader() {
  const blobUrlByItemId = reactive({})
  const pendingIds = new Set()
  let wantedIds = new Set()

  const revoke = (paperItemId) => {
    const existing = blobUrlByItemId[paperItemId]
    if (existing) {
      URL.revokeObjectURL(existing)
    }
    delete blobUrlByItemId[paperItemId]
  }

  const storeBlob = (paperItemId, blob) => {
    // The item may have been removed from the render model while the request
    // was in flight; storing then would leak an object URL nothing revokes.
    if (!wantedIds.has(paperItemId)) {
      return
    }
    blobUrlByItemId[paperItemId] = URL.createObjectURL(blob)
  }

  const ensureLoaded = (paperId, paperItemId) => {
    if (blobUrlByItemId[paperItemId] !== undefined || pendingIds.has(paperItemId)) {
      return
    }
    pendingIds.add(paperItemId)
    axios
      .get(buildPaperItemImageUrl(paperId, paperItemId), { responseType: 'blob' })
      .then((response) => {
        storeBlob(paperItemId, response.data)
      })
      .catch((error) => {
        console.error(`Failed to load figure for paper item ${paperItemId}`, error)
        if (wantedIds.has(paperItemId)) {
          blobUrlByItemId[paperItemId] = ''
        }
      })
      .finally(() => {
        pendingIds.delete(paperItemId)
      })
  }

  const syncRenderModel = (renderModel) => {
    const wantedItems = new Map()
    for (const section of renderModel?.sections || []) {
      for (const item of section.items || []) {
        // figure_image_url only marks that this item has a frozen figure; the
        // request URL itself is built here through the central builder.
        if (item?.paper_item_id && item?.figure_image_url) {
          wantedItems.set(item.paper_item_id, true)
        }
      }
    }

    for (const rawId of Object.keys(blobUrlByItemId)) {
      const paperItemId = Number(rawId)
      if (!wantedItems.has(paperItemId)) {
        revoke(paperItemId)
      }
    }

    wantedIds = new Set(wantedItems.keys())
    const paperId = renderModel?.paper?.id
    if (!paperId) {
      return
    }
    for (const paperItemId of wantedItems.keys()) {
      ensureLoaded(paperId, paperItemId)
    }
  }

  const figureUrlFor = (item) => {
    if (!item?.paper_item_id) {
      return ''
    }
    return blobUrlByItemId[item.paper_item_id] || ''
  }

  const dispose = () => {
    wantedIds = new Set()
    for (const rawId of Object.keys(blobUrlByItemId)) {
      revoke(Number(rawId))
    }
    pendingIds.clear()
  }

  return { syncRenderModel, figureUrlFor, dispose }
}
