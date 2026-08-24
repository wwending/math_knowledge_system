<template>
  <router-view></router-view>
</template>

<style>
/* 全局样式重置 */
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  width: 100%;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
}

/* prefers-reduced-motion（#76）：关闭 Element Plus 骨架屏闪烁动画，
   占位块保持静态展示；各组件自身的 hover 位移在各自样式内处理。 */
@media (prefers-reduced-motion: reduce) {
  .el-skeleton.is-animated .el-skeleton__item {
    animation: none;
  }
}
</style>