import {
  createMarkdownRenderer,
  normalizeLatexDelimiters as normalizeSharedLatexDelimiters
} from './markdownRenderer.mjs'

const md = createMarkdownRenderer()

export const normalizeLatexDelimiters = (text: string): string => {
  return normalizeSharedLatexDelimiters(text)
}

export const renderMarkdown = (content: string): string => md.render(normalizeLatexDelimiters(content))
