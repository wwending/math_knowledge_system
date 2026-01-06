<template>
  <div class="bank-container">
    <h2>📚 智能题库</h2>
    <el-alert title="功能开发中" type="info" description="这里将展示所有用户的公开题目，支持按知识点搜索。" show-icon />
    
    <div style="margin-top: 40px; text-align: center;">
      <el-empty description="题库正在建设中..." />
    </div>
  </div>
</template>

<script setup>
// 目前不需要逻辑，留空即可
</script>

<style scoped>
.bank-container {
  padding: 20px;
}
</style>