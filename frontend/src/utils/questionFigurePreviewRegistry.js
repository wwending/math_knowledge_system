import { reactive } from 'vue'
import axios from 'axios'
import { buildQuestionFigureImageUrl } from '../config/api'
import { createQuestionFigurePreviewRegistryCore, cropBlobFromImage } from './questionFigurePreviewRegistry.mjs'

export function createQuestionFigurePreviewRegistry() {
  const state = reactive({ urls: {}, errors: {} })
  return createQuestionFigurePreviewRegistryCore({
    http: axios,
    urlApi: URL,
    buildFigureUrl: buildQuestionFigureImageUrl,
    createCropBlob: cropBlobFromImage,
    state
  })
}
