"use client"

import { useMemo, useState } from 'react'
import FeedPicker from '../components/FeedPicker'
import EditorModal from '../components/EditorModal'
import TweetCards from '../components/TweetCards'

type Article = { title: string, link: string, summary?: string, published?: string, source?: string }

// Simple spinner component
function Spinner() {
  return (
    <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" role="status">
      <span className="!absolute !-m-px !h-px !w-px !overflow-hidden !whitespace-nowrap !border-0 !p-0 ![clip:rect(0,0,0,0)]">Loading...</span>
    </div>
  )
}

export default function Page() {
  const [sessionId] = useState(() => Math.random().toString(36).slice(2))
  const [apiBase] = useState('')
  const [sources, setSources] = useState<string[]>([])
  const [articles, setArticles] = useState<Article[]>([])
  const [summary, setSummary] = useState('')
  const [tweets, setTweets] = useState<Array<{id: string, content: string, summary_title: string, summary_link: string, summary_source: string}>>([])
  const [newsletterHtml, setNewsletterHtml] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingHighlights, setLoadingHighlights] = useState(false)
  const [loadingSummaries, setLoadingSummaries] = useState(false)
  const [loadingTweets, setLoadingTweets] = useState(false)
  const [loadingNewsletter, setLoadingNewsletter] = useState(false)
  const [summariesMode, setSummariesMode] = useState(false)
  const [pageIndex, setPageIndex] = useState(0)
  const pageSize = 5
  const [highlights, setHighlights] = useState<Array<{ title: string, link: string, source?: string, summary: string }>>([])
  const [selectedArticles, setSelectedArticles] = useState<string[]>([]) // Array of article URLs
  const [isPaginated, setIsPaginated] = useState(true) // Default to paginated view
  const [currentEditingTweetId, setCurrentEditingTweetId] = useState<string | null>(null)
  const [tweetConversations, setTweetConversations] = useState<Record<string, Array<{role: string, content: string}>>>({})
  const [pendingTweetUpdate, setPendingTweetUpdate] = useState<string | null>(null)
  const hasHighlights = useMemo(() => !!summary, [summary])

  const [editorOpen, setEditorOpen] = useState(false)
  const [editorTitle, setEditorTitle] = useState('Editor')
  const [editorText, setEditorText] = useState('')
  const [editTarget, setEditTarget] = useState<'summary' | `tweet-${number}` | 'newsletter'>('summary')

  async function fetchAndSummarize() {
    setLoadingHighlights(true)
    try {
      // 1) Aggregate articles (uses selected sources or backend defaults)
      const resAgg = await fetch(`${apiBase}/aggregate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sources })
      })
      const dataAgg = await resAgg.json()
      
      // Auto-select all articles by default
      const articleUrls = dataAgg.articles.map((a: any) => a.link)

      // 2) Summarize using the freshly fetched articles (do not rely on async state)
      const resSum = await fetch(`${apiBase}/highlights`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, articles: dataAgg.articles })
      })
      const dataSum = await resSum.json()
      
      // Batch all state updates after loading is complete
      setLoadingHighlights(false)
      setArticles(dataAgg.articles)
      setSelectedArticles(articleUrls)
      
      // Set appropriate message based on whether articles were found
      if (dataAgg.articles && dataAgg.articles.length > 0) {
        setSummary(dataSum.summary_markdown)
      } else {
        setSummary('No articles found for the selected sources in the past 7 days.')
      }
      setSummariesMode(false)
    } catch (error) {
      setLoadingHighlights(false)
      throw error
    }
  }

  async function getHighlights() {
    // Validate selection limit before making API call
    if (selectedArticles.length > 5) {
      alert('Please select 5 or fewer articles for summarization. You currently have ' + selectedArticles.length + ' articles selected.')
      return
    }
    
    setLoadingSummaries(true)
    try {
      // Only scrape selected articles
      const selectedArticleData = articles.filter(a => selectedArticles.includes(a.link))
      
      const res = await fetch(`${apiBase}/summaries_selected`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ articles: selectedArticleData })
      })
      const data = await res.json()
      const items: { title: string, link: string, source?: string, summary: string }[] = data.items || []
      
      // Batch all state updates after loading is complete
      setLoadingSummaries(false)
      setHighlights(items)
      setSummariesMode(true)
      setPageIndex(0)
    } catch (error) {
      setLoadingSummaries(false)
      throw error
    }
  }

  function resetSummaries() {
    setSummariesMode(false)
    setSummary('')
    setArticles([])
    setTweets([])
    setNewsletterHtml('')
    setPageIndex(0)
    setHighlights([])
    setSelectedArticles([])
    setIsPaginated(true) // Reset to default paginated view
  }

  function toggleArticleSelection(articleUrl: string) {
    setSelectedArticles(prev => 
      prev.includes(articleUrl) 
        ? prev.filter(url => url !== articleUrl)
        : [...prev, articleUrl]
    )
  }

  function selectAllArticles() {
    setSelectedArticles(articles.map(a => a.link))
  }

  function deselectAllArticles() {
    setSelectedArticles([])
  }

  async function makeTweets() {
    setLoadingTweets(true)
    try {
      const res = await fetch(`${apiBase}/tweets`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ 
          session_id: sessionId, 
          summaries: highlights  // Send highlights instead of summary_markdown
        }) 
      })
      const data = await res.json()
      
      // Batch state updates after loading is complete
      setLoadingTweets(false)
      setTweets(data.tweets)
    } catch (error) {
      setLoadingTweets(false)
      throw error
    }
  }

  async function makeNewsletter() {
    setLoadingNewsletter(true)
    try {
      const res = await fetch(`${apiBase}/newsletter`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, summary_markdown: summary, articles }) })
      const data = await res.json()
      
      // Batch state updates after loading is complete
      setLoadingNewsletter(false)
      setNewsletterHtml(data.html)
    } catch (error) {
      setLoadingNewsletter(false)
      throw error
    }
  }

  function openEditor(target: 'summary' | `tweet-${number}` | 'newsletter') {
    setEditTarget(target)
    if (target === 'summary') {
      setEditorTitle('Edit Summary')
      setEditorText(summary)
    } else if (target.startsWith('tweet-')) {
      const idx = Number(target.split('-')[1])
      setEditorTitle(`Edit Tweet ${idx + 1}`)
      setEditorText(tweets[idx]?.content || '')
    } else {
      setEditorTitle('Edit Newsletter (HTML)')
      setEditorText(newsletterHtml)
    }
    setEditorOpen(true)
  }

  function openTweetEditor(tweet: {id: string, content: string, summary_title: string, summary_link: string, summary_source: string}) {
    // Close any existing editor first, then open the new one
    if (currentEditingTweetId === tweet.id) {
      setCurrentEditingTweetId(null)
      setPendingTweetUpdate(null)
    } else {
      setCurrentEditingTweetId(tweet.id)
      setPendingTweetUpdate(null)
    }
  }

  async function sendTweetMessage(message: string) {
    if (!currentEditingTweetId) return

    const currentTweet = tweets.find(t => t.id === currentEditingTweetId)
    if (!currentTweet) return

    try {
      const res = await fetch(`${apiBase}/edit_tweet`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          tweet_id: currentTweet.id,
          current_tweet: currentTweet.content,
          original_summary: highlights.find(h => h.link === currentTweet.summary_link)?.summary || '',
          user_message: message,
          conversation_history: tweetConversations[currentTweet.id] || []
        })
      })
      
      const data = await res.json()
      
      // Store pending update instead of immediately applying it
      setPendingTweetUpdate(data.new_tweet)
      
      // Update conversation history
      setTweetConversations(prev => ({
        ...prev,
        [currentTweet.id]: data.conversation_history
      }))
      
      return data.ai_response
    } catch (error) {
      console.error('Error editing tweet:', error)
      return 'Sorry, I encountered an error while processing your request.'
    }
  }

  function acceptTweetUpdate() {
    if (!currentEditingTweetId || !pendingTweetUpdate) return
    
    // Update tweet content in main list
    const updatedTweets = tweets.map(tweet => 
      tweet.id === currentEditingTweetId 
        ? { ...tweet, content: pendingTweetUpdate }
        : tweet
    )
    setTweets(updatedTweets)
    setPendingTweetUpdate(null)
  }

  function rejectTweetUpdate() {
    setPendingTweetUpdate(null)
  }

  function onEditorDone(newText: string) {
    if (editTarget === 'summary') setSummary(newText)
    else if (editTarget.startsWith('tweet-')) {
      const idx = Number(editTarget.split('-')[1])
      const next = tweets.slice()
      if (next[idx]) {
        next[idx] = { ...next[idx], content: newText }
      setTweets(next)
      }
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
              <div className="flex flex-wrap items-center gap-2">
                {!hasHighlights && !summariesMode && (
                  <button className="btn flex items-center gap-2" onClick={fetchAndSummarize} disabled={loadingHighlights}>
                    {loadingHighlights && <Spinner />}
                    Get Highlights
                  </button>
                )}
                {hasHighlights && !summariesMode && (
                  <>
                    <button className="btn" onClick={resetSummaries}>Reset</button>
                                         <button 
                       className="btn flex items-center gap-2" 
                       onClick={async () => { await getHighlights(); /* switches to summariesMode */ }} 
                       disabled={loadingSummaries || selectedArticles.length === 0}
                       title={selectedArticles.length === 0 ? "Please select at least one article" : `Process ${selectedArticles.length} selected articles`}
                     >
                       {loadingSummaries && <Spinner />}
                       Get Summaries ({selectedArticles.length})
                     </button>
                  </>
                )}
                {summariesMode && (
                  <>
                    <button className="btn" onClick={resetSummaries}>Reset</button>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={isPaginated}
                        onChange={(e) => {
                          setIsPaginated(e.target.checked)
                          setPageIndex(0) // Reset to first page when toggling
                        }}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                      />
                      Paginated View
                    </label>
                  </>
                )}
              </div>
            </div>
            {!summariesMode ? (
              <>
                {!hasHighlights && (
                  summary ? (
                    <div className="max-h-96 overflow-y-auto">
                      <pre className="whitespace-pre-wrap text-sm text-gray-900">{summary}</pre>
                    </div>
                  ) : (
                    <div className="text-sm text-gray-500">No highlights yet.</div>
                  )
                )}
                
                {hasHighlights && articles.length === 0 && (
                  <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                    <div className="text-sm text-yellow-800">
                      No articles found for the selected sources in the past 7 days.
                    </div>
                  </div>
                )}
                
                {articles.length > 0 && (
                  <div className="mt-4 border-t pt-4">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm font-medium text-gray-700">
                        Articles Found ({articles.length})
                      </h4>
                      <div className="flex gap-2">
                        <button 
                          className="text-xs text-blue-600 hover:text-blue-800" 
                          onClick={selectAllArticles}
                        >
                          Select All
                        </button>
                        <button 
                          className="text-xs text-gray-600 hover:text-gray-800" 
                          onClick={deselectAllArticles}
                        >
                          Deselect All
                        </button>
                      </div>
                    </div>
                    <div className="max-h-64 overflow-y-auto space-y-2">
                      {articles.map((article, i) => (
                        <div key={`${article.link}-${i}`} className="flex items-start gap-3 p-3 border rounded-lg hover:bg-gray-50">
                          <input
                            type="checkbox"
                            checked={selectedArticles.includes(article.link)}
                            onChange={() => toggleArticleSelection(article.link)}
                            className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                          />
                          <div className="flex-1 min-w-0">
                            <a 
                              href={article.link} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="text-sm font-medium text-blue-600 hover:text-blue-800 block truncate"
                            >
                              {article.title}
                            </a>
                            <div className="text-xs text-gray-500 mt-1">
                              {article.source} {article.published && `• ${article.published}`}
                            </div>
                            {article.summary && (
                              <div className="text-xs text-gray-600 mt-1 line-clamp-2">
                                {article.summary}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 text-xs text-gray-600">
                      {selectedArticles.length} of {articles.length} articles selected
                    </div>
                  </div>
                )}
              </>
            ) : (
              <>
                {isPaginated ? (
                  // Paginated view - one summary per page
                  <div className="space-y-4">
                    {highlights.length > 0 && (
                      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                        <div className="flex items-start justify-between mb-2">
                          <a 
                            href={highlights[pageIndex]?.link} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-lg font-semibold text-blue-600 hover:text-blue-800 leading-tight"
                          >
                            {highlights[pageIndex]?.title}
                          </a>
                        </div>
                        <div className="text-sm text-gray-500 mb-3">
                          {highlights[pageIndex]?.source}
                        </div>
                        <div className="prose prose-sm max-w-none">
                          <div className="text-gray-700 whitespace-pre-wrap">{highlights[pageIndex]?.summary}</div>
                        </div>
                      </div>
                    )}
                    
                    {/* Pagination controls */}
                    {highlights.length > 1 && (
                      <div className="flex items-center justify-center gap-4 mt-4">
                        <button
                          className="btn-outline text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                          onClick={() => setPageIndex(Math.max(0, pageIndex - 1))}
                          disabled={pageIndex === 0}
                        >
                          ← Previous
                        </button>
                        <span className="text-sm text-gray-600">
                          {pageIndex + 1} of {highlights.length}
                        </span>
                        <button
                          className="btn-outline text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                          onClick={() => setPageIndex(Math.min(highlights.length - 1, pageIndex + 1))}
                          disabled={pageIndex === highlights.length - 1}
                        >
                          Next →
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  // List view - all summaries at once (original behavior)
                  <div className="max-h-96 overflow-y-auto space-y-4">
                    {highlights.map((it, i) => (
                      <div key={`${it.link}-${i}`} className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                        <div className="flex items-start justify-between mb-2">
                          <a 
                            href={it.link} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-lg font-semibold text-blue-600 hover:text-blue-800 leading-tight"
                          >
                            {it.title}
                          </a>
                        </div>
                        <div className="text-sm text-gray-500 mb-3">
                          {it.source}
                        </div>
                        <div className="prose prose-sm max-w-none">
                          <div className="text-gray-700 whitespace-pre-wrap">{it.summary}</div>
                        </div>
                      </div>
                    ))}
                    <div className="text-center text-sm text-gray-600 pt-2">
                      {highlights.length} summaries generated
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
          <div className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold">X/Tweets</h3>
              <div className="flex gap-2">
                <button className="btn flex items-center gap-2" onClick={makeTweets} disabled={highlights.length === 0 || loadingTweets}>
                  {loadingTweets && <Spinner />}
                  Generate X/Tweets
                </button>
              </div>
            </div>
            {tweets.length > 0 ? (
              <TweetCards 
                tweets={tweets} 
                onEdit={(tweet) => openTweetEditor(tweet)}
                currentEditingTweetId={currentEditingTweetId}
                tweetConversations={tweetConversations}
                pendingTweetUpdate={pendingTweetUpdate}
                highlights={highlights}
                onSendMessage={sendTweetMessage}
                onAcceptUpdate={acceptTweetUpdate}
                onRejectUpdate={rejectTweetUpdate}
                onCloseEditor={() => {
                  setCurrentEditingTweetId(null)
                  setPendingTweetUpdate(null)
                }}
              />
            ) : (
              <div className="text-sm text-gray-500">No tweets yet.</div>
            )}
          </div>
          <div className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Newsletter</h3>
              <div className="flex gap-2">
                <button 
                  className="btn flex items-center gap-2" 
                  onClick={makeNewsletter} 
                  disabled={highlights.length === 0 || loadingNewsletter}
                  title={highlights.length === 0 ? "Please create summaries first by clicking 'Get Summaries'" : "Generate newsletter from summaries"}
                >
                  {loadingNewsletter && <Spinner />}
                  Generate
                </button>
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


