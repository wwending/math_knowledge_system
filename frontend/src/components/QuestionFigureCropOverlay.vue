<template>
  <div class="crop-editor">
    <div ref="stage" class="crop-stage" @pointerdown="startDraw">
      <img :src="src" alt="题目区域图" draggable="false" @load="emitNaturalSize" />
      <button v-for="(box,index) in boxes" :key="index" type="button" class="crop-box" :class="{selected:index===selected,overlap:conflicts.has(index)}" :style="boxStyle(box)" @pointerdown.stop="startMove($event,index)" @click.stop="selected=index">
        <span>{{ index+1 }}</span><i class="resize" @pointerdown.stop="startResize($event,index)"></i>
      </button>
      <div v-if="drawing" class="crop-box drawing" :style="boxStyle(drawing)"></div>
    </div>
    <div class="crop-actions"><el-button size="small" :disabled="selected<0" @click="removeSelected">删除选中框</el-button><el-button size="small" :disabled="!boxes.length" @click="clear">清空</el-button><span>已绘制 {{ boxes.length }} 个；单框面积至少 1%，边缘接触允许。</span></div>
    <el-alert v-if="conflicts.size" title="裁剪框不能实质重叠" type="error" :closable="false" show-icon />
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
const props=defineProps({src:{type:String,required:true},modelValue:{type:Array,default:()=>[]}});const emit=defineEmits(['update:modelValue','natural-size'])
const stage=ref(),selected=ref(-1),drawing=ref(null);let operation=null
const boxes=computed({get:()=>props.modelValue,set:(value)=>emit('update:modelValue',value)})
const overlap=(a,b)=>Math.min(a[0]+a[2],b[0]+b[2])-Math.max(a[0],b[0])>1e-6&&Math.min(a[1]+a[3],b[1]+b[3])-Math.max(a[1],b[1])>1e-6
const conflicts=computed(()=>{const result=new Set();boxes.value.forEach((box,index)=>boxes.value.slice(index+1).forEach((other,offset)=>{if(overlap(box,other)){result.add(index);result.add(index+offset+1)}}));return result})
const point=(event)=>{const rect=stage.value.getBoundingClientRect();return{x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))}}
const boxStyle=(box)=>({left:`${box[0]*100}%`,top:`${box[1]*100}%`,width:`${box[2]*100}%`,height:`${box[3]*100}%`})
const bind=()=>{window.addEventListener('pointermove',move);window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',cancel)};const unbind=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',finish);window.removeEventListener('pointercancel',cancel)}
const startDraw=(event)=>{if(event.button!==0)return;const p=point(event);operation={type:'draw',start:p};drawing.value=[p.x,p.y,0,0];bind()}
const startMove=(event,index)=>{const p=point(event);operation={type:'move',index,start:p,original:[...boxes.value[index]]};selected.value=index;bind()}
const startResize=(event,index)=>{const p=point(event);operation={type:'resize',index,start:p,original:[...boxes.value[index]]};selected.value=index;bind()}
const move=(event)=>{if(!operation)return;const p=point(event);if(operation.type==='draw'){drawing.value=[Math.min(operation.start.x,p.x),Math.min(operation.start.y,p.y),Math.abs(p.x-operation.start.x),Math.abs(p.y-operation.start.y)];return}const next=boxes.value.map((box)=>[...box]);const [x,y,w,h]=operation.original;if(operation.type==='move'){next[operation.index]=[Math.max(0,Math.min(1-w,x+p.x-operation.start.x)),Math.max(0,Math.min(1-h,y+p.y-operation.start.y)),w,h]}else next[operation.index]=[x,y,Math.max(0.001,Math.min(1-x,w+p.x-operation.start.x)),Math.max(0.001,Math.min(1-y,h+p.y-operation.start.y))];boxes.value=next}
const finish=()=>{if(operation?.type==='draw'&&drawing.value?.[2]*drawing.value?.[3]>=0.01){boxes.value=[...boxes.value,drawing.value];selected.value=boxes.value.length-1}drawing.value=null;operation=null;unbind()};const cancel=()=>{if(operation?.type!=='draw'&&operation){const next=boxes.value.map((box)=>[...box]);next[operation.index]=operation.original;boxes.value=next}drawing.value=null;operation=null;unbind()}
const removeSelected=()=>{if(selected.value<0)return;boxes.value=boxes.value.filter((_,index)=>index!==selected.value);selected.value=-1};const clear=()=>{boxes.value=[];selected.value=-1};const emitNaturalSize=(event)=>emit('natural-size',{width:event.target.naturalWidth,height:event.target.naturalHeight})
onBeforeUnmount(unbind)
defineExpose({valid:computed(()=>boxes.value.length>0&&!conflicts.value.size),conflicts})
</script>
<style scoped>
.crop-stage{position:relative;line-height:0;user-select:none;touch-action:none;background:#111;overflow:hidden}.crop-stage>img{display:block;width:100%;height:auto}.crop-box{position:absolute;border:2px solid #409eff;background:rgba(64,158,255,.12);color:#fff;line-height:1;cursor:move}.crop-box.selected{border-color:#e6a23c}.crop-box.overlap{border-color:#f56c6c;background:rgba(245,108,108,.2)}.crop-box.drawing{pointer-events:none}.crop-box span{position:absolute;left:2px;top:2px;background:#409eff;padding:2px}.resize{position:absolute;right:-5px;bottom:-5px;width:12px;height:12px;background:#fff;border:2px solid currentColor;cursor:nwse-resize}.crop-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px;line-height:1.5}
</style>
