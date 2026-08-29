<template>
  <div class="figure-overlay-editor">
    <div class="figure-editor-toolbar">
      <span class="figure-editor-hint">确认自动检测结果：可移动、调整大小或删除，漏检配图请入库后补充。</span>
      <div class="figure-editor-actions">
        <el-button size="small" :disabled="!canReset" @click="resetBoxes">重置</el-button>
        <el-button size="small" type="danger" plain :disabled="boxes.length === 0" @click="markNoFigure">
          标记无图
        </el-button>
        <el-button size="small" @click="viewerVisible = true">放大核对</el-button>
      </div>
    </div>
    <div ref="stageRef" class="figure-stage">
      <img :src="imageUrl" class="figure-stage-image" draggable="false" alt="题目原图" />
      <div
        v-for="(box, index) in boxes"
        :key="box.id"
        class="figure-box"
        :class="{ 'is-conflicting': conflictingIndexes.has(index) }"
        :style="boxStyle(box.bbox)"
        @pointerdown.stop="onBoxPointerDown($event, box)"
      >
        <span class="figure-box-badge">{{ index + 1 }}</span>
        <button
          type="button"
          class="figure-box-btn figure-box-remove"
          title="删除此框"
          @pointerdown.stop
          @click.stop="removeBox(box.id)"
        >
          ×
        </button>
        <span class="figure-box-handle" @pointerdown.stop="onHandlePointerDown($event, box)"></span>
      </div>
    </div>
    <p class="figure-editor-status" :class="{ 'is-error': overlapPairs.length > 0 }">{{ statusText }}</p>
    <el-image-viewer
      v-if="viewerVisible"
      :url-list="[imageUrl]"
      teleported
      @close="viewerVisible = false"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import {
  FIGURE_BBOX_MIN_AREA,
  clamp01,
  findOverlappingFigureBboxes,
  isValidFigureBbox,
  sortFigureBboxesReadingOrder,
} from '../utils/figureOverlay.mjs'

const props = defineProps({
  imageUrl: { type: String, required: true },
  initialBoxes: { type: Array, default: () => [] },
  modelValue: { type: Array, default: null },
})

const emit = defineEmits(['update:modelValue'])

let nextBoxId = 1
const stageRef = ref(null)
const boxes = ref([])
const viewerVisible = ref(false)
const dragState = ref(null)

const initialBboxes = computed(() => sortFigureBboxesReadingOrder(props.initialBoxes))
const currentBboxes = computed(() => boxes.value.map((box) => [...box.bbox]))
const overlapPairs = computed(() => findOverlappingFigureBboxes(currentBboxes.value))
const conflictingIndexes = computed(() => new Set(overlapPairs.value.flat()))

const canReset = computed(() => {
  if (boxes.value.length !== initialBboxes.value.length) return true
  return boxes.value.some((box, index) => box.bbox.some((value, part) => value !== initialBboxes.value[index]?.[part]))
})

const statusText = computed(() => {
  if (overlapPairs.value.length > 0) {
    return '配图框存在重叠，请调整或删除高亮冲突框后再保存。'
  }
  if (boxes.value.length === 0) {
    return '已标记为无图，保存时不会创建配图。'
  }
  return `已确认 ${boxes.value.length} 个配图区域，保存时将全部裁剪入库。`
})

const emitBoxes = () => {
  emit('update:modelValue', sortFigureBboxesReadingOrder(currentBboxes.value))
}

const replaceBoxes = (bboxes, shouldEmit = true) => {
  boxes.value = sortFigureBboxesReadingOrder(bboxes).map((bbox) => ({
    id: nextBoxId++,
    bbox,
  }))
  if (shouldEmit) emitBoxes()
}

watch(
  () => props.initialBoxes,
  () => replaceBoxes(Array.isArray(props.modelValue) ? props.modelValue : initialBboxes.value),
  { immediate: true }
)

const pointToNormalized = (event) => {
  const rect = stageRef.value.getBoundingClientRect()
  return {
    x: clamp01((event.clientX - rect.left) / rect.width),
    y: clamp01((event.clientY - rect.top) / rect.height),
  }
}

const boxStyle = (bbox) => ({
  left: `${bbox[0] * 100}%`,
  top: `${bbox[1] * 100}%`,
  width: `${bbox[2] * 100}%`,
  height: `${bbox[3] * 100}%`,
})

const removeBox = (id) => {
  boxes.value = boxes.value.filter((box) => box.id !== id)
  emitBoxes()
}

const markNoFigure = () => {
  boxes.value = []
  emitBoxes()
}

const resetBoxes = () => replaceBoxes(initialBboxes.value)

const stopDragListeners = () => {
  window.removeEventListener('pointermove', onWindowPointerMove)
  window.removeEventListener('pointerup', onWindowPointerUp)
}

const startDrag = (state) => {
  dragState.value = state
  window.addEventListener('pointermove', onWindowPointerMove)
  window.addEventListener('pointerup', onWindowPointerUp)
}

const onBoxPointerDown = (event, box) => {
  const point = pointToNormalized(event)
  startDrag({ mode: 'move', id: box.id, originX: point.x, originY: point.y, bbox: [...box.bbox] })
}

const onHandlePointerDown = (event, box) => {
  const point = pointToNormalized(event)
  startDrag({ mode: 'resize', id: box.id, originX: point.x, originY: point.y, bbox: [...box.bbox] })
}

const applyDrag = (point) => {
  const state = dragState.value
  if (!state) return
  const target = boxes.value.find((box) => box.id === state.id)
  if (!target) return
  const dx = point.x - state.originX
  const dy = point.y - state.originY
  const [x, y, width, height] = state.bbox
  if (state.mode === 'move') {
    target.bbox = [
      Math.min(Math.max(0, x + dx), 1 - width),
      Math.min(Math.max(0, y + dy), 1 - height),
      width,
      height,
    ]
    return
  }
  const nextWidth = Math.min(Math.max(0.02, width + dx), 1 - x)
  const nextHeight = Math.min(Math.max(0.02, height + dy), 1 - y)
  const candidate = [x, y, nextWidth, nextHeight]
  if (nextWidth * nextHeight >= FIGURE_BBOX_MIN_AREA && isValidFigureBbox(candidate)) {
    target.bbox = candidate
  }
}

const onWindowPointerMove = (event) => {
  if (!stageRef.value) return
  applyDrag(pointToNormalized(event))
}

const onWindowPointerUp = () => {
  if (dragState.value) emitBoxes()
  dragState.value = null
  stopDragListeners()
}

onBeforeUnmount(stopDragListeners)

defineExpose({ markNoFigure, resetBoxes })
</script>

<style scoped>
.figure-overlay-editor { display: flex; flex-direction: column; gap: 8px; }
.figure-editor-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
.figure-editor-hint { font-size: 12px; color: var(--el-text-color-secondary); }
.figure-editor-actions { display: flex; gap: 4px; }
.figure-stage { position: relative; overflow: hidden; border-radius: 6px; border: 1px solid var(--el-border-color); background: #f5f7fa; touch-action: none; user-select: none; }
.figure-stage-image { display: block; width: 100%; height: auto; pointer-events: none; }
.figure-box { position: absolute; border: 2px solid var(--el-color-primary); border-radius: 2px; background: rgba(64, 158, 255, 0.12); cursor: move; }
.figure-box.is-conflicting { border-color: var(--el-color-danger); background: rgba(245, 108, 108, 0.2); }
.figure-box-badge { position: absolute; top: -22px; left: -2px; min-width: 20px; padding: 0 5px; font-size: 12px; line-height: 20px; text-align: center; color: #fff; background: var(--el-color-primary); border-radius: 3px 3px 0 0; }
.figure-box.is-conflicting .figure-box-badge { background: var(--el-color-danger); }
.figure-box-btn { position: absolute; top: -24px; padding: 0 6px; font-size: 12px; line-height: 18px; border: none; border-radius: 3px 3px 0 0; cursor: pointer; }
.figure-box-remove { right: -2px; color: #fff; background: var(--el-color-danger); }
.figure-box-handle { position: absolute; right: -5px; bottom: -5px; width: 10px; height: 10px; background: var(--el-color-success); border: 2px solid #fff; border-radius: 50%; cursor: se-resize; }
.figure-editor-status { margin: 0; font-size: 12px; color: var(--el-text-color-secondary); }
.figure-editor-status.is-error { color: var(--el-color-danger); }
</style>
