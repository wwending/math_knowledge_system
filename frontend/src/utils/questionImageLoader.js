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
  const generations = new Map()

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
    const generation = (generations.get(questionId) || 0) + 1
    generations.set(questionId, generation)
    axios
      .get(buildQuestionImageUrl(questionId), { responseType: 'blob' })
      .then((response) => {
        if (generations.get(questionId) !== generation) return
        blobUrlByQuestionId[questionId] = URL.createObjectURL(response.data)
      })
      .catch((error) => {
        console.error(`Failed to load image for question ${questionId}`, error)
        if (generations.get(questionId) === generation) blobUrlByQuestionId[questionId] = ''
      })
      .finally(() => {
        if (generations.get(questionId) === generation) pendingIds.delete(questionId)
      })
  }

  const remove = (questionId) => {
    if (!questionId) return
    generations.set(questionId, (generations.get(questionId) || 0) + 1)
    const url = blobUrlByQuestionId[questionId]
    if (url) URL.revokeObjectURL(url)
    delete blobUrlByQuestionId[questionId]
    pendingIds.delete(questionId)
  }

  const syncItems = (items) => {
    const ids = new Set((items || []).map((item) => item?.id).filter(Boolean))
    Object.keys(blobUrlByQuestionId).forEach((id) => {
      if (!ids.has(Number(id)) && !ids.has(id)) remove(id)
    })
    for (const item of items || []) ensureLoaded(item)
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
    generations.clear()
  }

  return { hasImageField, syncItems, imageUrlFor, remove, dispose }
}
