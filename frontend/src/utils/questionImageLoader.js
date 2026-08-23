import { reactive } from 'vue'
import axios from 'axios'

import { buildQuestionImageUrl } from '../config/api'

// Loads question images through the authenticated endpoint (#44). <el-image> cannot
// attach an Authorization header, so images are prefetched as blobs (reusing the
// global axios interceptors, including the 401 refresh retry) and rendered via
// object URLs. Callers must invoke dispose() on unmount to release the blobs.
export function createQuestionImageLoader() {
  const blobUrlByQuestionId = reactive({})
  const pendingIds = new Set()

  const hasImageField = (item) => Boolean(item && (item.image_url || item.origin_image))

  const ensureLoaded = (item) => {
    const questionId = item?.id
    if (!questionId || pendingIds.has(questionId)) {
      return
    }
    if (blobUrlByQuestionId[questionId] !== undefined) {
      return
    }
    if (!hasImageField(item)) {
      blobUrlByQuestionId[questionId] = ''
      return
    }

    pendingIds.add(questionId)
    axios
      .get(buildQuestionImageUrl(questionId), { responseType: 'blob' })
      .then((response) => {
        blobUrlByQuestionId[questionId] = URL.createObjectURL(response.data)
      })
      .catch((error) => {
        console.error(`Failed to load image for question ${questionId}`, error)
        blobUrlByQuestionId[questionId] = ''
      })
      .finally(() => {
        pendingIds.delete(questionId)
      })
  }

  const syncItems = (items) => {
    for (const item of items || []) {
      ensureLoaded(item)
    }
  }

  const imageUrlFor = (item) => {
    if (!item?.id) {
      return ''
    }
    return blobUrlByQuestionId[item.id] || ''
  }

  const dispose = () => {
    for (const url of Object.values(blobUrlByQuestionId)) {
      if (url) {
        URL.revokeObjectURL(url)
      }
    }
    Object.keys(blobUrlByQuestionId).forEach((key) => {
      delete blobUrlByQuestionId[key]
    })
    pendingIds.clear()
  }

  return { hasImageField, syncItems, imageUrlFor, dispose }
}
