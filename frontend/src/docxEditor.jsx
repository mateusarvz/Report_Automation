import { useEffect, useMemo, useRef, useState } from 'react'
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from 'docx'
import { apiPost } from './api'

function htmlToDocxParagraphs(html) {
  const parser = new DOMParser()
  const doc = parser.parseFromString(html || '', 'text/html')
  const blocks = Array.from(doc.body.children)

  const walkInline = (node, inherited = {}) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent || ''
      return text ? [new TextRun({ text, ...inherited })] : []
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
      return []
    }

    const tag = node.tagName.toLowerCase()
    const next = { ...inherited }
    if (tag === 'strong' || tag === 'b') next.bold = true
    if (tag === 'em' || tag === 'i') next.italics = true
    if (tag === 'u') next.underline = {}

    if (tag === 'br') return [new TextRun({ break: 1 })]
    return Array.from(node.childNodes).flatMap((child) => walkInline(child, next))
  }

  const paragraphs = []
  for (const block of blocks) {
    const tag = block.tagName.toLowerCase()
    if (tag === 'div' || tag === 'p' || tag === 'h1' || tag === 'h2' || tag === 'h3' || tag === 'h4') {
      paragraphs.push(
        new Paragraph({
          heading: tag === 'h1' ? HeadingLevel.HEADING_1 : tag === 'h2' ? HeadingLevel.HEADING_2 : undefined,
          children: walkInline(block),
        })
      )
      continue
    }

    if (tag === 'ul' || tag === 'ol') {
      Array.from(block.children).forEach((li) => {
        paragraphs.push(
          new Paragraph({
            bullet: tag === 'ul' ? { level: 0 } : undefined,
            children: walkInline(li),
          })
        )
      })
      continue
    }

    paragraphs.push(new Paragraph({ children: walkInline(block) }))
  }

  return paragraphs.length ? paragraphs : [new Paragraph('')]
}

export function DocxEditorPage({ user }) {
  const editorRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [sourceHtml, setSourceHtml] = useState('')
  const [fileName, setFileName] = useState('relatorio-editavel.docx')

  const payload = useMemo(() => {
    try {
      const raw = localStorage.getItem('docx-editor-payload')
      if (!raw) return null
      const parsed = JSON.parse(raw)
      localStorage.removeItem('docx-editor-payload')
      return parsed
    } catch {
      return null
    }
  }, [])

  useEffect(() => {
    if (!user) return
    const load = async () => {
      if (!payload) {
        setLoading(false)
        return
      }
      try {
        const data = await apiPost('/api/reports/editor-html', payload)
        setSourceHtml(data.html || '')
        setFileName(`relatorio-${Date.now()}.docx`)
      } catch (err) {
        setMessage(err.message || 'Erro ao carregar editor')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [payload, user])

  useEffect(() => {
    if (editorRef.current && sourceHtml) {
      editorRef.current.innerHTML = sourceHtml
    }
  }, [sourceHtml])

  const exec = (command) => {
    document.execCommand(command, false, null)
    editorRef.current?.focus()
  }

  const handleInput = () => {
    setMessage('')
  }

  const handleDownload = async () => {
    const html = editorRef.current?.innerHTML || ''
    const doc = new Document({
      sections: [{ properties: {}, children: htmlToDocxParagraphs(html) }],
    })
    const blob = await Packer.toBlob(doc)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    link.click()
    URL.revokeObjectURL(url)
  }

  if (!user) {
    return null
  }

  return (
    <div className="docx-editor-page">
      <div className="docx-editor-shell">
        <div className="docx-editor-toolbar">
          <button type="button" onClick={() => exec('bold')}>B</button>
          <button type="button" onClick={() => exec('italic')}>I</button>
          <button type="button" onClick={() => exec('underline')}>U</button>
          <button type="button" onClick={() => exec('insertUnorderedList')}>• Lista</button>
          <button type="button" onClick={() => exec('insertOrderedList')}>1. Lista</button>
          <button type="button" onClick={() => exec('undo')}>Desfazer</button>
          <button type="button" onClick={() => exec('redo')}>Refazer</button>
          <button type="button" onClick={handleDownload}>Baixar DOCX</button>
        </div>
        <div className="docx-editor-canvas">
          {loading ? (
            <div className="docx-editor-loading">Carregando editor...</div>
          ) : (
            <div
              ref={editorRef}
              className="docx-editor"
              contentEditable
              suppressContentEditableWarning
              onInput={handleInput}
            />
          )}
        </div>
        {message && <div className="docx-editor-message">{message}</div>}
      </div>
    </div>
  )
}
