import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const panel = readFileSync(resolve(process.cwd(), 'src/components/PaperPanel.vue'), 'utf8')
const preview = readFileSync(resolve(process.cwd(), 'src/components/PaperPreview.vue'), 'utf8')
const failures = []

for (const needle of ['response_line_count', ':min="0"', ':max="24"', '不留作答区', '全部设为', 'batchResponseLineCount', 'draftRenderModel', 'height_mm: item.response_line_count * 8', '当前显示答案或解析，作答区暂不显示；行数设置将在关闭后生效']) {
  if (!panel.includes(needle)) failures.push(`PaperPanel is missing response-line contract: ${needle}`)
}
for (const needle of ['hasUnsavedChanges', '请先保存修改后再导出 PDF', 'item.answer_area.height_mm']) {
  if (!preview.includes(needle)) failures.push(`PaperPreview is missing response-line/export contract: ${needle}`)
}
if (!preview.includes('margin-top: 4mm') || !preview.includes('break-inside: avoid')) failures.push('PaperPreview does not keep the 4mm gap and indivisible response area')
if (preview.includes('height: 50mm') || preview.includes('answer-line')) failures.push('PaperPreview retains a legacy fixed height or drawn response line')

if (failures.length) {
  console.error('Paper response-line frontend contract failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}
console.log('Paper response-line frontend contract passed.')
