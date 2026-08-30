<template><section v-if="errors.length" class="error-nav"><el-alert :title="`发现 ${errors.length} 个结构化错误`" type="error" :closable="false" show-icon/><div class="error-list"><button v-for="(error,index) in errors" :key="`${error.code}-${index}`" type="button" @click="$emit('navigate',error)"><el-tag size="small" type="danger">{{label(error.section)}}</el-tag><span>{{error.message}}</span></button></div></section></template>
<script setup>
defineProps({errors:{type:Array,default:()=>[]}});defineEmits(['navigate']);const label=(section)=>({stem:'题干',answer:'答案',analysis:'解析'}[section]||'整题')
</script>
<style scoped>.error-nav{display:grid;gap:8px}.error-list{display:grid;gap:4px}.error-list button{display:flex;gap:8px;align-items:center;text-align:left;border:1px solid #fab6b6;background:#fef0f0;padding:8px;border-radius:6px;cursor:pointer}</style>
