import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dashboardPath = resolve(process.cwd(), 'src/views/Dashboard.vue')
const bankPanelPath = resolve(process.cwd(), 'src/components/BankPanel.vue')
const paperPanelPath = resolve(process.cwd(), 'src/components/PaperPanel.vue')
const paperPreviewPath = resolve(process.cwd(), 'src/components/PaperPreview.vue')

const dashboardSource = readFileSync(dashboardPath, 'utf8')
const bankPanelSource = readFileSync(bankPanelPath, 'utf8')
const failures = []

if (!dashboardSource.includes("index=\"papers\"")) {
  failures.push('dashboard is missing the paper navigation entry')
}

if (!dashboardSource.includes('<paper-panel')) {
  failures.push('dashboard does not render PaperPanel')
}

if (!bankPanelSource.includes('selectedQuestionIds')) {
  failures.push('bank panel does not track selected questions')
}

if (!bankPanelSource.includes('/papers')) {
  failures.push('bank panel does not call the papers API to create a paper')
}

if (!bankPanelSource.includes('question_id')) {
  failures.push('bank panel does not map selected questions to question_id items')
}

if (!bankPanelSource.includes('formatQuestionType')) {
  failures.push('bank panel does not format question_type for display')
}

if (!bankPanelSource.includes('formatDifficultyStars')) {
  failures.push('bank panel does not format difficulty_level as stars')
}

if (!bankPanelSource.includes('difficulty_level')) {
  failures.push('bank panel does not read difficulty_level')
}

if (!bankPanelSource.includes('metadata_status')) {
  failures.push('bank panel does not read metadata_status')
}

for (const expectedText of ['元数据评估中', '难度评估失败', '未评估']) {
  if (!bankPanelSource.includes(expectedText)) {
    failures.push(`bank panel does not display metadata state text: ${expectedText}`)
  }
}

if (!existsSync(paperPanelPath)) {
  failures.push('PaperPanel.vue is missing')
} else {
  const paperPanelSource = readFileSync(paperPanelPath, 'utf8')

  if (!paperPanelSource.includes('/papers')) {
    failures.push('PaperPanel does not call the papers API')
  }

  if (!paperPanelSource.includes('/render-model')) {
    failures.push('PaperPanel does not call the paper render-model API')
  }

  if (!paperPanelSource.includes('answer_area_mode')) {
    failures.push('PaperPanel does not expose answer_area_mode configuration')
  }

  if (!paperPanelSource.includes('PaperPreview')) {
    failures.push('PaperPanel does not render PaperPreview')
  }

  if (!paperPanelSource.includes('renderMarkdown')) {
    failures.push('PaperPanel does not reuse the shared Markdown renderer')
  }

  if (!paperPanelSource.includes('content_snapshot')) {
    failures.push('PaperPanel does not display paper item content snapshots')
  }

  if (!paperPanelSource.includes('answer_snapshot')) {
    failures.push('PaperPanel does not handle answer snapshots')
  }

  if (!paperPanelSource.includes('analysis_snapshot')) {
    failures.push('PaperPanel does not handle analysis snapshots')
  }
}

if (!existsSync(paperPreviewPath)) {
  failures.push('PaperPreview.vue is missing')
} else {
  const paperPreviewSource = readFileSync(paperPreviewPath, 'utf8')

  if (!paperPreviewSource.includes('renderMarkdown')) {
    failures.push('PaperPreview does not reuse the shared Markdown renderer')
  }

  if (paperPreviewSource.includes('markdown-it') || paperPreviewSource.includes('MarkdownIt')) {
    failures.push('PaperPreview initializes markdown-it directly')
  }

  if (paperPreviewSource.includes('answer_snapshot') || paperPreviewSource.includes('analysis_snapshot')) {
    failures.push('PaperPreview renders answer or analysis snapshot fields')
  }
}

if (failures.length > 0) {
  console.error('Paper MVP frontend contract failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Paper MVP frontend contract passed.')
