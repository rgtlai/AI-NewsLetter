"use client"

import { useMemo, useState } from 'react'
import FeedPicker from '../components/FeedPicker'
import EditorModal from '../components/EditorModal'
import TweetCards from '../components/TweetCards'

type Article = { title: string, link: string, summary?: string, published?: string, source?: string }

export default function Page() {
  const [sessionId] = useState(() => Math.random().toString(36).slice(2))
  const [apiBase] = useState('/api/index')
  const [sources, setSources] = useState<string[]>([])
  const [articles, setArticles] = useState<Article[]>([])
  const [summary, setSummary] = useState('')
  const [tweets, setTweets] = useState<string[]>([])
  const [newsletterHtml, setNewsletterHtml] = useState('')
  const [loading, setLoading] = useState(false)
  const [editorOpen, setEditorOpen] = useState(false)
  const [editorTitle, setEditorTitle] = useState('Editor')
  const [editorText, setEditorText] = useState('')
  const [editTarget, setEditTarget] = useState<'summary' | `tweet-${number}` | 'newsletter'>('summary')

  async function aggregate() {
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/aggregate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sources }) })
      const data = await res.json()
      setArticles(data.articles)
    } finally { setLoading(false) }
  }

  async function makeSummary() {
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/summarize`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, articles }) })
      const data = await res.json()
      setSummary(data.summary_markdown)
    } finally { setLoading(false) }
  }

  async function makeTweets() {
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/tweets`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, summary_markdown: summary }) })
      const data = await res.json()
      setTweets(data.tweets)
    } finally { setLoading(false) }
  }

  async function makeNewsletter() {
    setLoading(true)
    try {
      const res = await fetch(`${apiBase}/newsletter`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, summary_markdown: summary, articles }) })
      const data = await res.json()
      setNewsletterHtml(data.html)
    } finally { setLoading(false) }
  }

  function openEditor(target: 'summary' | `tweet-${number}` | 'newsletter') {
    setEditTarget(target)
    if (target === 'summary') {
      setEditorTitle('Edit Summary')
      setEditorText(summary)
    } else if (target.startsWith('tweet-')) {
      const idx = Number(target.split('-')[1])
      setEditorTitle(`Edit Tweet ${idx + 1}`)
      setEditorText(tweets[idx])
    } else {
      setEditorTitle('Edit Newsletter (HTML)')
      setEditorText(newsletterHtml)
    }
    setEditorOpen(true)
  }

  function onEditorDone(newText: string) {
    if (editTarget === 'summary') setSummary(newText)
    else if (editTarget.startsWith('tweet-')) {
      const idx = Number(editTarget.split('-')[1])
      const next = tweets.slice()
      next[idx] = newText
      setTweets(next)
    } else setNewsletterHtml(newText)
  }

  async function download() {
    const res = await fetch(`${apiBase}/download_html`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, html: newsletterHtml }) })
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'ai_weekly.html'
    document.body.appendChild(a)
    a.click()
    URL.revokeObjectURL(url)
    a.remove()
  }

  return (
    <main className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="md:col-span-1">
          <FeedPicker selected={sources} setSelected={setSources} />
        </div>
        <div className="md:col-span-2 space-y-3">
          <div className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Weekly Highlights</h3>
              <div className="flex gap-2">
                <button className="btn" onClick={aggregate} disabled={loading}>Fetch</button>
                <button className="btn" onClick={makeSummary} disabled={loading || articles.length === 0}>Summarize</button>
                <button className="btn" onClick={() => openEditor('summary')} disabled={!summary}>Edit with AI</button>
              </div>
            </div>
            <pre className="whitespace-pre-wrap text-sm text-gray-900">{summary || 'No summary yet.'}</pre>
          </div>
          <div className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Tweets</h3>
              <div className="flex gap-2">
                <button className="btn" onClick={makeTweets} disabled={!summary || loading}>Generate Tweets</button>
              </div>
            </div>
            {tweets.length > 0 ? <TweetCards tweets={tweets} onEdit={(i) => openEditor(`tweet-${i}`)} /> : <div className="text-sm text-gray-500">No tweets yet.</div>}
          </div>
          <div className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Newsletter</h3>
              <div className="flex gap-2">
                <button className="btn" onClick={makeNewsletter} disabled={!summary || loading}>Generate</button>
                <button className="btn" onClick={() => openEditor('newsletter')} disabled={!newsletterHtml}>Edit with AI</button>
                <button className="btn" onClick={download} disabled={!newsletterHtml}>Download</button>
              </div>
            </div>
            <div className="overflow-hidden rounded-lg border">
              {newsletterHtml ? <iframe srcDoc={newsletterHtml} className="h-[500px] w-full" /> : <div className="p-4 text-sm text-gray-500">No newsletter yet.</div>}
            </div>
          </div>
        </div>
      </div>

      <EditorModal
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        onDone={onEditorDone}
        initialText={editorText}
        title={editorTitle}
        sessionId={sessionId}
        apiBase={apiBase}
      />
    </main>
  )
}


