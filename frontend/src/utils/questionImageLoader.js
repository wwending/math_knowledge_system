import { reactive } from 'vue'
import axios from 'axios'
import { buildQuestionImageUrl } from '../config/api.js'
import { createQuestionImageLoaderCore } from './questionImageLoaderCore.mjs'
import { acceptsImageGeneration } from './questionImageLoaderHelpers.mjs'
export { acceptsImageGeneration }

export function createQuestionImageLoader({ http = axios, urlApi = URL } = {}) {
  const blobUrlByQuestionId = reactive({})
  const core = createQuestionImageLoaderCore({ http, urlApi, buildImageUrl: buildQuestionImageUrl, state: { urls: blobUrlByQuestionId } })
  const hasImageField = (item) => Boolean(item && (item.image_url || item.origin_image))
  return { hasImageField, ...core }
}
