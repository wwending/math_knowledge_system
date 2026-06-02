import MarkdownIt from 'markdown-it'
import markdownItMathjax3 from 'markdown-it-mathjax3'

const md = new MarkdownIt({
  html: true,
  breaks: true,
  linkify: true
}).use(markdownItMathjax3)

export const normalizeLatexDelimiters = (text: string): string => {
  if (!text) {
    return ''
  }

  return text
    .replace(/\\\[((?:.|\n)*?)\\\]/g, (_, content: string) => `$$${content}$$`)
    .replace(/\\\(((?:.|\n)*?)\\\)/g, (_, content: string) => `$${content}$`)
}

export const renderMarkdown = (content: string): string => md.render(normalizeLatexDelimiters(content))
