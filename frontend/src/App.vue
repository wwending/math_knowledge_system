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

/* #77: 触屏统一禁用双击缩放，保留滚动与捏合缩放。touch-action 不继承，需全量覆盖。 */
* {
  touch-action: manipulation;
}

/* #77: 弹层滚动到边界时不带动底层页面一起滚动。 */
.el-overlay-dialog,
.el-dialog__body {
  overscroll-behavior: contain;
}
</style>