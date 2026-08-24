<template>
  <div class="figure-overlay-editor">
    <div class="figure-editor-toolbar">
      <span class="figure-editor-hint">拖框调整大小，点「设为主图」选择入库图形</span>
      <div class="figure-editor-actions">
        <el-button size="small" :disabled="!canReset" @click="resetBoxes">重置</el-button>
        <el-button size="small" type="danger" plain :disabled="boxes.length === 0" @click="markNoFigure">
          标记无图
        </el-button>
        <el-button size="small" @click="viewerVisible = true">放大核对</el-button>
      </div>
    </div>
    <div
      ref="stageRef"
      class="figure-stage"
      @pointerdown.prevent="onStagePointerDown"
    >
      <img :src="imageUrl" class="figure-stage-image" draggable="false" alt="题目原图" />
      <div
        v-for="box in boxes"
        :key="box.id"
        class="figure-box"
        :class="{ 'is-primary': box.id === primaryId }"
        :style="boxStyle(box.bbox)"
        @pointerdown.stop="onBoxPointerDown($event, box)"
      >
        <span v-if="box.id === primaryId" class="figure-box-badge">主图</span>
        <button
          v-else
          type="button"
          class="figure-box-btn figure-box-set"
          title="设为主图"
          @pointerdown.stop
          @click.stop="setPrimary(box.id)"
        >
          设为主图
        </button>
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
      <div v-if="draftRect" class="figure-draft" :style="draftStyle"></div>
    </div>
    <p class="figure-editor-status">{{ statusText }}</p>
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

import { clamp01, isValidFigureBbox, pickPrimaryBox } from '../utils/figureOverlay.mjs'

const props = defineProps({
  imageUrl: { type: String, required: true },
  initialBoxes: { type: Array, default: () => [] },
  modelValue: { type: Array, default: null },
})

const emit = defineEmits(['update:modelValue'])

let nextBoxId = 1
const stageRef = ref(null)
const boxes = ref([])
const primaryId = ref(null)
const viewerVisible = ref(false)
const draftRect = ref(null)
const dragState = ref(null)

const initialDetections = computed(() => props.initialBoxes || [])

const selectedBbox = computed(() => {
  const primary = boxes.value.find((box) => box.id === primaryId.value)
  return primary ? [...primary.bbox] : null
})

const canReset = computed(() => {
  if (boxes.value.length !== initialDetections.value.length) {
    return true
  }
  if (primaryId.value === null && initialDetections.value.length > 0) {
    return true
  }
  return false
})

const statusText = computed(() => {
  if (selectedBbox.value) {
    return '已确认图形区域，保存时将按主图裁剪。'
  }
  return '未确认任何图形：将按“无图”入库。'
})

const emitSelection = () => {
  emit('update:modelValue', selectedBbox.value ? [...selectedBbox.value] : null)
}

const initFromDetections = (detections) => {
  boxes.value = detections.map((item) => ({
    id: nextBoxId++,
    bbox: [...item.bbox],
  }))
  const preferred = pickPrimaryBox(detections)
  primaryId.value = null
  if (preferred) {
    const match = boxes.value.find(
      (box, index) => detections[index] === preferred || box.bbox.every((v, i) => v === preferred.bbox[i])
    )
    primaryId.value = match ? match.id : boxes.value[0].id
  }
  emitSelection()
}

watch(initialDetections, (detections) => initFromDetections(detections), { immediate: true })

const pointToNormalized = (event) => {
  const rect = stageRef.value.getBoundingClientRect()
  return {
    x: clamp01(((event.clientX - rect.left) / rect.width)),
    y: clamp01(((event.clientY - rect.top) / rect.height)),
  }
}

const boxStyle = (bbox) => ({
  left: `${bbox[0] * 100}%`,
  top: `${bbox[1] * 100}%`,
  width: `${bbox[2] * 100}%`,
  height: `${bbox[3] * 100}%`,
})

const draftStyle = computed(() => {
  if (!draftRect.value) {
    return {}
  }
  const { startX, startY, endX, endY } = draftRect.value
  return boxStyle([
    Math.min(startX, endX),
    Math.min(startY, endY),
    Math.abs(endX - startX),
    Math.abs(endY - startY),
  ])
})

const setPrimary = (id) => {
  primaryId.value = id
  emitSelection()
}

const removeBox = (id) => {
  boxes.value = boxes.value.filter((box) => box.id !== id)
  if (primaryId.value === id) {
    primaryId.value = boxes.value.length > 0 ? boxes.value[0].id : null
  }
  emitSelection()
}

const markNoFigure = () => {
  boxes.value = []
  primaryId.value = null
  emitSelection()
}

const resetBoxes = () => initFromDetections(initialDetections.value)

// -- pointer interactions ---------------------------------------------------

const stopDragListeners = () => {
  window.removeEventListener('pointermove', onWindowPointerMove)
  window.removeEventListener('pointerup', onWindowPointerUp)
}

const startDrag = (state) => {
  dragState.value = state
  window.addEventListener('pointermove', onWindowPointerMove)
  window.addEventListener('pointerup', onWindowPointerUp)
}

const onStagePointerDown = (event) => {
  if (!stageRef.value) {
    return
  }
  const point = pointToNormalized(event)
  draftRect.value = { startX: point.x, startY: point.y, endX: point.x, endY: point.y }
  startDrag({ mode: 'draw' })
}

const onBoxPointerDown = (event, box) => {
  const point = pointToNormalized(event)
  setPrimary(box.id)
  startDrag({ mode: 'move', id: box.id, originX: point.x, originY: point.y, bbox: [...box.bbox] })
}

const onHandlePointerDown = (event, box) => {
  const point = pointToNormalized(event)
  setPrimary(box.id)
  startDrag({ mode: 'resize', id: box.id, originX: point.x, originY: point.y, bbox: [...box.bbox] })
}

const applyDrag = (point) => {
  const state = dragState.value
  if (!state) {
    return
  }
  const target = boxes.value.find((box) => box.id === state.id)
  const dx = point.x - state.originX
  const dy = point.y - state.originY
  const [x, y, w, h] = state.bbox
  if (state.mode === 'move') {
    const nextX = Math.min(Math.max(0, x + dx), 1 - w)
    const nextY = Math.min(Math.max(0, y + dy), 1 - h)
    if (target) {
      target.bbox = [nextX, nextY, w, h]
    }
    return
  }
  if (state.mode === 'resize') {
    const nextW = Math.min(Math.max(0.02, w + dx), 1 - x)
    const nextH = Math.min(Math.max(0.02, h + dy), 1 - y)
    if (target) {
      target.bbox = [x, y, nextW, nextH]
    }
  }
}

const onWindowPointerMove = (event) => {
  if (!stageRef.value) {
    return
  }
  const point = pointToNormalized(event)
  if (dragState.value?.mode === 'draw' && draftRect.value) {
    draftRect.value.endX = point.x
    draftRect.value.endY = point.y
    return
  }
  applyDrag(point)
}

const onWindowPointerUp = () => {
  if (dragState.value?.mode === 'draw' && draftRect.value) {
    const { startX, startY, endX, endY } = draftRect.value
    const candidate = [
      Math.min(startX, endX),
      Math.min(startY, endY),
      Math.abs(endX - startX),
      Math.abs(endY - startY),
    ]
    if (isValidFigureBbox(candidate)) {
      const newId = nextBoxId++
      boxes.value.push({ id: newId, bbox: candidate })
      primaryId.value = newId
      emitSelection()
    }
    draftRect.value = null
  } else if (dragState.value?.mode === 'move' || dragState.value?.mode === 'resize') {
    emitSelection()
  }
  dragState.value = null
  stopDragListeners()
}

onBeforeUnmount(stopDragListeners)

defineExpose({ markNoFigure, resetBoxes })
</script>

<style scoped>
.figure-overlay-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.figure-editor-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.figure-editor-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.figure-editor-actions {
  display: flex;
  gap: 4px;
}

.figure-stage {
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  border: 1px solid var(--el-border-color);
  background: #f5f7fa;
  touch-action: none;
  cursor: crosshair;
  user-select: none;
}

.figure-stage-image {
  display: block;
  width: 100%;
  height: auto;
  pointer-events: none;
}

.figure-box {
  position: absolute;
  border: 2px solid var(--el-color-primary);
  border-radius: 2px;
  background: rgba(64, 158, 255, 0.12);
  cursor: move;
}

.figure-box.is-primary {
  border-color: var(--el-color-success);
  background: rgba(103, 194, 58, 0.14);
}

.figure-box-badge {
  position: absolute;
  top: -22px;
  left: -2px;
  padding: 0 6px;
  font-size: 12px;
  line-height: 20px;
  color: #fff;
  background: var(--el-color-success);
  border-radius: 3px 3px 0 0;
}

.figure-box-btn {
  position: absolute;
  top: -24px;
  padding: 0 6px;
  font-size: 12px;
  line-height: 18px;
  border: none;
  border-radius: 3px 3px 0 0;
  cursor: pointer;
}

.figure-box-set {
  right: -2px;
  color: #fff;
  background: var(--el-color-primary);
}

.figure-box-remove {
  right: auto;
  left: -2px;
  color: #fff;
  background: var(--el-color-danger);
}

.figure-box-handle {
  position: absolute;
  right: -5px;
  bottom: -5px;
  width: 10px;
  height: 10px;
  background: var(--el-color-success);
  border: 2px solid #fff;
  border-radius: 50%;
  cursor: se-resize;
}

.figure-draft {
  position: absolute;
  border: 2px dashed var(--el-color-primary);
  background: rgba(64, 158, 255, 0.1);
  pointer-events: none;
}

.figure-editor-status {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
