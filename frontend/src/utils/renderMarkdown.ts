import {
  normalizeLatexDelimiters as normalizeSharedLatexDelimiters,
  renderMarkdown as renderSharedMarkdown
} from './markdownRenderer.mjs'

export const normalizeLatexDelimiters = (text: string): string => {
  return normalizeSharedLatexDelimiters(text)
}

export const renderMarkdown = (content: string): string => renderSharedMarkdown(content)
