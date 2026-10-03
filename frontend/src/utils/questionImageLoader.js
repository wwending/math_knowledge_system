import { reactive } from 'vue'
import axios from 'axios'
import { buildQuestionImageUrl } from '../config/api.js'
import { createQuestionImageLoaderCore } from './questionImageLoaderCore.mjs'
import { acceptsImageGeneration } from './questionImageLoaderHelpers.mjs'
export { acceptsImageGeneration }

export function createQuestionImageLoader({ http = axios, urlApi = URL } = {}) {
  const state = reactive({ urls: {}, errors: {}, loading: {} })
  const core = createQuestionImageLoaderCore({ http, urlApi, buildImageUrl: buildQuestionImageUrl, state })
  const hasImageField = (item) => Boolean(item && (item.image_url || item.origin_image))
  return { hasImageField, ...core }
}
