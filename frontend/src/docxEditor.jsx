import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
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
    if (node.nodeType !== Node.ELEMENT_NODE) return []
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
  const location = useLocation()
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [sourceHtml, setSourceHtml] = useState('')
  const [fileName, setFileName] = useState('relatorio-editavel.docx')
  const [templateBlob, setTemplateBlob] = useState(null)
  const [templateReady, setTemplateReady] = useState(false)

  const payload = useMemo(() => {
    try {
      const params = new URLSearchParams(location.search)
      const encoded = params.get('payload')
      if (encoded) {
        const decoded = decodeURIComponent(escape(atob(encoded)))
        return JSON.parse(decoded)
      }
      const raw = localStorage.getItem('docx-editor-payload')
      if (!raw) return null
      const parsed = JSON.parse(raw)
      localStorage.removeItem('docx-editor-payload')
      return parsed
    } catch {
      return null
    }
  }, [location.search])

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
        setFileName(data.file_name || `relatorio-${Date.now()}.docx`)
        if (data.docx_base64) {
          const bin = atob(data.docx_base64)
          const bytes = new Uint8Array(bin.length)
          for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i)
          setTemplateBlob(new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }))
          setTemplateReady(true)
        }
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
    setTemplateReady(false)
  }

  const handleDownloadDocx = async () => {
    if (templateReady && templateBlob) {
      const url = URL.createObjectURL(templateBlob)
      const link = document.createElement('a')
      link.href = url
      link.download = fileName
      link.click()
      URL.revokeObjectURL(url)
      return
    }

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

  const handleDownloadPdf = async () => {
    const html = editorRef.current?.innerHTML || sourceHtml || ''
    if (!html.trim()) {
      setMessage('Nada para exportar.')
      return
    }

    try {
      const response = await fetch('/api/reports/editor-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ html }),
      })
      if (!response.ok) {
        throw new Error(await response.text())
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = fileName.replace(/\.docx$/i, '.pdf')
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setMessage(err?.message || 'Erro ao gerar PDF')
    }
  }

  if (!user) return null

  return (
    <div className="docx-editor-page">
      <div className="docx-editor-shell">
        <div className="docx-editor-header">
          <div>
            <h1>Editor do relatório</h1>
            <p>Visual A4 para ficar mais perto do PDF final.</p>
          </div>
        </div>
        <div className="docx-editor-toolbar">
          <button type="button" onClick={() => exec('bold')}>B</button>
          <button type="button" onClick={() => exec('italic')}>I</button>
          <button type="button" onClick={() => exec('underline')}>U</button>
          <button type="button" onClick={() => exec('undo')}>Desfazer</button>
          <button type="button" onClick={() => exec('redo')}>Refazer</button>
          <button type="button" onClick={handleDownloadDocx}>Baixar DOCX</button>
          <button type="button" onClick={handleDownloadPdf}>Baixar PDF</button>
        </div>
        <div className="docx-editor-canvas">
          {loading ? (
            <div className="docx-editor-loading">Carregando editor...</div>
          ) : (
            <div className="docx-editor-stage">
              <div className="docx-editor-page-sheet">
                <div
                  ref={editorRef}
                  className="docx-editor"
                  contentEditable
                  suppressContentEditableWarning
                  onInput={handleInput}
                />
              </div>
            </div>
          )}
        </div>
        {message && <div className="docx-editor-message">{message}</div>}
      </div>
    </div>
  )
}
