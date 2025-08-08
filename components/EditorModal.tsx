"use client"

import { useEffect, useMemo, useState } from 'react'

type ConversationTurn = { role: 'user' | 'assistant', content: string }

export default function EditorModal({
  open,
  onClose,
  onDone,
  initialText,
  sessionId,
  title,
  apiBase = '/api',
}: {
  open: boolean
  onClose: () => void
  onDone: (text: string) => void
  initialText: string
  sessionId: string
  title: string
  apiBase?: string
}) {
  const [text, setText] = useState(initialText)
  const [instruction, setInstruction] = useState('Improve clarity, keep links.')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState<ConversationTurn[]>([])

  useEffect(() => {
    if (open) {
      setText(initialText)
    }
  }, [open, initialText])

  useEffect(() => {
    const key = `mem_${sessionId}`
    const saved = localStorage.getItem(key)
    if (saved) {
      try { setHistory(JSON.parse(saved)) } catch {}
    }
  }, [sessionId])

  useEffect(() => {
    const key = `mem_${sessionId}`
    localStorage.setItem(key, JSON.stringify(history))
  }, [history, sessionId])

  async function applyEdit() {
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, text, instruction, prior_history: history }),
      })
      if (!res.ok) throw new Error('Failed to edit')
      const data = await res.json()
      setText(data.edited_text)
      setHistory(data.history)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="card w-full max-w-3xl p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <div className="flex gap-2">
            <button className="text-sm text-gray-600 hover:text-black" onClick={onClose}>Close</button>
            <button className="btn" onClick={() => { onDone(text); onClose(); }}>Use result</button>
          </div>
        </div>
        <div className="mb-3 flex gap-2">
          <input className="input w-full" value={instruction} onChange={e => setInstruction(e.target.value)} placeholder="Instruction for the editor" />
          <button className="btn" onClick={applyEdit} disabled={loading}>{loading ? 'Editing…' : 'Apply'}</button>
        </div>
        <textarea className="input h-80 w-full whitespace-pre-wrap" value={text} onChange={e => setText(e.target.value)} />
      </div>
    </div>
  )
}


