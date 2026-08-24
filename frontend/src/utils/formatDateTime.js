// 统一的时间展示工具（#76）：此前各面板散落着 toLocaleString()，
// 默认 locale 随浏览器漂移，与 UserManagementPanel 的 zh-CN + 24 小时制不一致。
// 固定 zh-CN + 24 小时制，全站时间列展示同一格式；模块级单例避免重复构造。
const formatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false
})

// value 为空或调用方需要特定占位文案（如「从未登录」）时返回 fallback。
export const formatDateTime = (value, fallback = '-') => {
  if (!value) {
    return fallback
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return String(value)
  }
  return formatter.format(date)
}
