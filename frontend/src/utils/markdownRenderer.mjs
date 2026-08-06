import MarkdownIt from 'markdown-it'
import markdownItMathjax3 from 'markdown-it-mathjax3'

export const createMarkdownRenderer = () => {
  const md = new MarkdownIt({
    html: false,
    breaks: true,
    linkify: false
  })
  const validateMarkdownItLink = md.validateLink.bind(md)

  // The question bank has no data-URL use case, including inline data images.
  md.validateLink = (url) => !/^\s*data:/i.test(url) && validateMarkdownItLink(url)

  return md.use(markdownItMathjax3)
}

export const normalizeLatexDelimiters = (text) => {
  if (!text) {
    return ''
  }

  return text
    .replace(/\\\[((?:.|\n)*?)\\\]/g, (_, content) => `$$${content}$$`)
    .replace(/\\\(((?:.|\n)*?)\\\)/g, (_, content) => `$${content}$`)
}
