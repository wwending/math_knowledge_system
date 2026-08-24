import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve(process.cwd(), 'src/components/PaperPanel.vue'), 'utf8')
const failures = []

const requiredText = [
  '编辑试卷',
  '试卷标题',
  '试卷描述',
  '分值',
  '题干',
  '答案',
  '解析',
  '↑ 上移',
  '↓ 下移',
  '删除',
  '从题库添加题目',
  '保存修改',
  '取消修改'
]

for (const text of requiredText) {
  if (!source.includes(text)) failures.push(`PaperPanel is missing paper editing control: ${text}`)
}

const contracts = [
  ['editDraft', 'PaperPanel does not keep a local edit draft'],
  ['JSON.parse(JSON.stringify', 'PaperPanel does not deep-copy paper detail into edit state'],
  ['ElMessageBox.confirm', 'PaperPanel does not confirm destructive/discard actions'],
  ['axios.patch', 'PaperPanel does not call the PATCH paper endpoint'],
  ['currentPaper.value = response.data', 'PaperPanel does not refresh currentPaper from the save response'],
  ['papers.value = papers.value.map', 'PaperPanel does not refresh the paper list summary after save'],
  ['paperRenderModel.value = null', 'PaperPanel does not invalidate the old render model'],
  ['/questions?limit=100', 'PaperPanel does not reuse the question list API'],
  ['draftQuestionIds', 'PaperPanel does not disable questions already in the paper'],
  ['renderMarkdown', 'PaperPanel does not reuse the shared safe Markdown renderer'],
  [':disabled="index === 0"', 'PaperPanel does not disable moving the first item up'],
  [':disabled="index === editDraft.items.length - 1"', 'PaperPanel does not disable moving the last item down'],
  ['saveLoading', 'PaperPanel does not prevent duplicate saves']
]

for (const [needle, message] of contracts) {
  if (!source.includes(needle)) failures.push(message)
}

if (source.includes('markdown-it') || source.includes('MarkdownIt')) {
  failures.push('PaperPanel initializes a Markdown renderer directly')
}

// Question picker rows must not wrap el-checkbox (which renders its own
// <label class="el-checkbox">) in a native label — nested labels are invalid HTML.
if (!/<div[^>]*class="question-picker-item"[^>]*@click=/.test(source)) {
  failures.push('PaperPanel question-picker row must be a clickable div wrapper')
}
if (/<label[^>]*class="question-picker-item"/.test(source)) {
  failures.push('PaperPanel question-picker row must not use a native <label> around el-checkbox')
}
if (!source.includes("closest('.el-checkbox')")) {
  failures.push('PaperPanel question-picker row click must ignore clicks inside the checkbox to avoid double toggle')
}

if (failures.length > 0) {
  console.error('Paper editing frontend contract failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log('Paper editing frontend contract passed.')
