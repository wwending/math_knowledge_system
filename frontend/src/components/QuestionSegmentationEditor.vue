<template>
  <section class="segmentation-editor" aria-labelledby="segmentation-title">
    <div class="segmentation-toolbar">
      <div>
        <h3 id="segmentation-title">逐题框选</h3>
        <p>拖动空白处新增题框；选中题框后可移动、调整大小或按 Delete 删除。题目按右侧顺序处理。</p>
      </div>
      <div class="segmentation-actions">
        <el-button :disabled="boxes.length < 2" @click="sortReadingOrder">按阅读顺序排列</el-button>
        <el-button :disabled="boxes.length === 0" @click="clearBoxes">清空全部</el-button>
        <el-button type="primary" :disabled="boxes.length === 0" @click="emitConfirm">确认 {{ boxes.length }} 道题</el-button>
      </div>
    </div>

    <div class="segmentation-layout">
      <div
        ref="stageRef"
        class="segmentation-stage"
        tabindex="0"
        aria-label="题目框选画布。拖动创建题目框；选中框后可拖动移动，拖动右下角调整大小，按 Delete 删除。"
        @pointerdown.prevent="startDrawing"
        @keydown="handleStageKeydown"
      >
        <img :src="imageUrl" alt="待分题的页面" draggable="false" />
        <div
          v-for="(box, index) in boxes"
          :key="box.id"
          class="question-box"
          :class="{ 'is-selected': box.id === selectedId }"
          :style="bboxStyle(box.bbox)"
          @pointerdown.stop.prevent="startMoving($event, box)"
        >
          <span>第 {{ index + 1 }} 题</span>
          <button type="button" :aria-label="`删除第 ${index + 1} 题框`" @pointerdown.stop @click.stop="removeBox(box.id)">×</button>
          <span
            v-if="box.id === selectedId"
            class="resize-handle"
            role="button"
            tabindex="0"
            :aria-label="`调整第 ${index + 1} 题框大小`"
            @pointerdown.stop.prevent="startResizing($event, box)"
          ></span>
        </div>
        <div v-if="draftBbox" class="question-box is-draft" :style="bboxStyle(draftBbox)" aria-hidden="true"></div>
      </div>

      <ol class="segmentation-list" aria-label="题目处理顺序">
        <li v-for="(box, index) in boxes" :key="box.id" :class="{ 'is-selected': box.id === selectedId }">
          <button type="button" class="select-box" @click="selectBox(box.id)">第 {{ index + 1 }} 题</button>
          <div class="order-actions">
            <el-button size="small" :disabled="index === 0" :aria-label="`第 ${index + 1} 题上移`" @click="moveBox(index, -1)">上移</el-button>
            <el-button size="small" :disabled="index === boxes.length - 1" :aria-label="`第 ${index + 1} 题下移`" @click="moveBox(index, 1)">下移</el-button>
            <el-button size="small" type="danger" plain :aria-label="`删除第 ${index + 1} 题框`" @click="removeBox(box.id)">删除</el-button>
          </div>
        </li>
        <li v-if="boxes.length === 0" class="empty-boxes">尚未框选题目</li>
      </ol>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { normalizeQuestionBbox, pointerRangeToQuestionBbox, sortQuestionBoxes } from '../utils/questionSegmentation.mjs'

const props = defineProps({ imageUrl: { type: String, required: true }, initialBoxes: { type: Array, default: () => [] } })
const emit = defineEmits(['confirm'])
let nextId = 1
const stageRef = ref(null)
const boxes = ref([])
const selectedId = ref(null)
const dragState = ref(null)
const draftEnd = ref(null)

const draftBbox = computed(() => dragState.value?.mode === 'draw' && draftEnd.value
  ? pointerRangeToQuestionBbox(dragState.value.start, draftEnd.value, 0)
  : null)
const pointFromEvent = (event) => {
  const rect = stageRef.value.getBoundingClientRect()
  return { x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)), y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)) }
}
const bboxStyle = (bbox) => ({ left: `${bbox[0] * 100}%`, top: `${bbox[1] * 100}%`, width: `${bbox[2] * 100}%`, height: `${bbox[3] * 100}%` })
const selectBox = (id) => { selectedId.value = id; stageRef.value?.focus({ preventScroll: true }) }
const stopPointerOperation = () => { window.removeEventListener('pointermove', handlePointerMove); window.removeEventListener('pointerup', finishPointerOperation) }
const beginPointerOperation = (state) => { dragState.value = state; window.addEventListener('pointermove', handlePointerMove); window.addEventListener('pointerup', finishPointerOperation) }
const startDrawing = (event) => { if (!stageRef.value || event.button !== 0) return; selectedId.value = null; const start = pointFromEvent(event); draftEnd.value = start; beginPointerOperation({ mode: 'draw', start }) }
const startMoving = (event, box) => { selectBox(box.id); beginPointerOperation({ mode: 'move', id: box.id, start: pointFromEvent(event), bbox: [...box.bbox] }) }
const startResizing = (event, box) => { selectBox(box.id); beginPointerOperation({ mode: 'resize', id: box.id, start: pointFromEvent(event), bbox: [...box.bbox] }) }
const handlePointerMove = (event) => {
  if (!dragState.value || !stageRef.value) return
  const point = pointFromEvent(event)
  if (dragState.value.mode === 'draw') { draftEnd.value = point; return }
  const box = boxes.value.find((item) => item.id === dragState.value.id)
  if (!box) return
  const [x, y, width, height] = dragState.value.bbox
  const dx = point.x - dragState.value.start.x
  const dy = point.y - dragState.value.start.y
  if (dragState.value.mode === 'move') box.bbox = [Math.min(Math.max(0, x + dx), 1 - width), Math.min(Math.max(0, y + dy), 1 - height), width, height]
  if (dragState.value.mode === 'resize') box.bbox = normalizeQuestionBbox([x, y, Math.max(0.02, width + dx), Math.max(0.02, height + dy)], 0) || box.bbox
}
const finishPointerOperation = () => {
  if (dragState.value?.mode === 'draw' && draftEnd.value) {
    const bbox = pointerRangeToQuestionBbox(dragState.value.start, draftEnd.value)
    if (bbox) { const id = nextId++; boxes.value.push({ id, bbox }); selectedId.value = id }
  }
  dragState.value = null; draftEnd.value = null; stopPointerOperation()
}
const removeBox = (id) => { boxes.value = boxes.value.filter((box) => box.id !== id); if (selectedId.value === id) selectedId.value = null }
const clearBoxes = () => { boxes.value = []; selectedId.value = null }
const moveBox = (index, offset) => { const target = index + offset; if (target < 0 || target >= boxes.value.length) return; const next = [...boxes.value]; [next[index], next[target]] = [next[target], next[index]]; boxes.value = next }
const sortReadingOrder = () => { boxes.value = sortQuestionBoxes(boxes.value) }
const handleStageKeydown = (event) => {
  if (!['Delete', 'Backspace'].includes(event.key) || !selectedId.value) return
  const target = event.target
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target?.isContentEditable) return
  event.preventDefault(); removeBox(selectedId.value)
}
const emitConfirm = () => emit('confirm', boxes.value.map((box) => ({ id: box.id, bbox: [...box.bbox] })))
watch(() => props.initialBoxes, (value) => {
  boxes.value = (value || []).map((box) => ({ id: box.id ?? nextId++, bbox: [...box.bbox] }))
  nextId = Math.max(nextId, ...boxes.value.map((box) => Number(box.id) + 1).filter(Number.isFinite), 1)
  if (!boxes.value.some((box) => box.id === selectedId.value)) selectedId.value = null
}, { immediate: true })
onBeforeUnmount(stopPointerOperation)
defineExpose({ clearBoxes, sortReadingOrder })
</script>

<style scoped>
.segmentation-editor { display: flex; flex-direction: column; gap: 16px; }
.segmentation-toolbar, .segmentation-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
h3, p { margin: 0; } p { margin-top: 6px; color: var(--el-text-color-secondary); }
.segmentation-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(260px, 340px); gap: 16px; align-items: start; }
.segmentation-stage { position: relative; overflow: hidden; border: 1px solid var(--el-border-color); border-radius: 12px; background: #263b45; cursor: crosshair; touch-action: none; user-select: none; }
.segmentation-stage:focus-visible { outline: 3px solid var(--el-color-primary-light-5); outline-offset: 3px; }
.segmentation-stage img { display: block; width: 100%; height: auto; pointer-events: none; }
.question-box { position: absolute; box-sizing: border-box; border: 3px solid var(--el-color-primary); background: rgba(64, 158, 255, 0.14); cursor: move; }
.question-box.is-selected { border-color: var(--el-color-success); background: rgba(103, 194, 58, 0.16); }
.question-box > span:first-child { position: absolute; top: 0; left: 0; padding: 2px 7px; color: #fff; background: var(--el-color-primary); font-size: 12px; }
.question-box > button { position: absolute; top: 0; right: 0; width: 28px; height: 28px; border: 0; color: #fff; background: var(--el-color-danger); cursor: pointer; font-size: 20px; }
.resize-handle { position: absolute; right: -7px; bottom: -7px; width: 16px; height: 16px; border: 2px solid #fff; border-radius: 50%; background: var(--el-color-success); cursor: se-resize; }
.question-box.is-draft { border-style: dashed; pointer-events: none; }
.segmentation-list { margin: 0; padding: 8px; list-style: none; border: 1px solid var(--el-border-color); border-radius: 10px; background: var(--el-fill-color-blank); }
.segmentation-list li { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px; border-radius: 7px; }
.segmentation-list li.is-selected { background: var(--el-color-primary-light-9); }
.select-box { flex: none; border: 0; padding: 6px; color: var(--el-color-primary); background: transparent; font: inherit; font-weight: 600; cursor: pointer; }
.order-actions { display: flex; gap: 4px; flex-wrap: wrap; justify-content: flex-end; }
.empty-boxes { color: var(--el-text-color-secondary); }
@media (max-width: 820px) { .segmentation-layout { grid-template-columns: 1fr; } }
</style>
