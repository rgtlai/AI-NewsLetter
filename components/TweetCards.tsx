"use client"

import { useState } from 'react'

type Tweet = {
  id: string
  content: string
  summary_title: string
  summary_link: string
  summary_source: string
}

type Highlight = {
  title: string
  link: string
  source?: string
  summary: string
}

export default function TweetCards({ 
  tweets, 
  onEdit,
  currentEditingTweetId,
  tweetConversations,
  pendingTweetUpdate,
  highlights,
  onSendMessage,
  onAcceptUpdate,
  onRejectUpdate,
  onCloseEditor
}: { 
  tweets: Tweet[], 
  onEdit: (tweet: Tweet) => void,
  currentEditingTweetId: string | null,
  tweetConversations: Record<string, Array<{role: string, content: string}>>,
  pendingTweetUpdate: string | null,
  highlights: Highlight[],
  onSendMessage: (message: string) => Promise<string | undefined>,
  onAcceptUpdate: () => void,
  onRejectUpdate: () => void,
  onCloseEditor: () => void
}) {
  const XLogo = () => (
    <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden="true">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>
  )

  return (
    <div className="space-y-4">
      {tweets.map((tweet) => (
        <div key={tweet.id} className="bg-white border border-gray-200 rounded-xl p-4 hover:bg-gray-50 transition-colors">
          {/* Header */}
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-black rounded-full flex items-center justify-center">
                <XLogo />
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center space-x-2">
                <div className="text-sm font-bold text-gray-900">AI Newsletter</div>
                <div className="text-sm text-gray-500">@AI_Newsletter</div>
                <div className="text-sm text-gray-500">·</div>
                <div className="text-sm text-gray-500">now</div>
              </div>
              
              {/* Tweet Content */}
              <div className="mt-2">
                <div className="text-gray-900 whitespace-pre-wrap break-words">
                  {tweet.content}
                </div>
              </div>
              
              {/* Source Link */}
              <div className="mt-3 p-3 border border-gray-200 rounded-lg bg-gray-50">
                <div className="text-xs text-gray-500 mb-1">{tweet.summary_source}</div>
                <a 
                  href={tweet.summary_link} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-blue-600 hover:text-blue-800 line-clamp-2"
                >
                  {tweet.summary_title}
                </a>
              </div>
              
              {/* Actions */}
              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center space-x-6 text-gray-500">
                  <button className="flex items-center space-x-2 hover:text-blue-500 transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    <span className="text-sm">0</span>
                  </button>
                  <button className="flex items-center space-x-2 hover:text-green-500 transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                    </svg>
                    <span className="text-sm">0</span>
                  </button>
                  <button className="flex items-center space-x-2 hover:text-red-500 transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                    </svg>
                    <span className="text-sm">0</span>
                  </button>
                  <button className="flex items-center space-x-2 hover:text-blue-500 transition-colors">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z" />
                    </svg>
                    <span className="text-sm">0</span>
                  </button>
                </div>
                {currentEditingTweetId !== tweet.id && (
                  <button 
                    onClick={() => onEdit(tweet)}
                    className="px-3 py-1 text-sm bg-blue-500 text-white rounded-full hover:bg-blue-600 transition-colors"
                  >
                    Edit with AI
                  </button>
                )}
              </div>
            </div>
          </div>
          
          {/* Inline Chatbot - Show only for the currently editing tweet */}
          {currentEditingTweetId === tweet.id && (
            <div className="mt-4 border-t border-gray-200 pt-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-medium text-gray-700">Edit Tweet with AI</h4>
                  <button 
                    onClick={onCloseEditor}
                    className="text-gray-500 hover:text-gray-700"
                  >
                    ✕
                  </button>
                </div>
                
                {/* Current Tweet Preview */}
                <div className="mb-4 p-3 bg-white rounded border">
                  <div className="text-xs font-medium text-gray-600 mb-1">Current Tweet:</div>
                  <div className="text-sm text-gray-900">{tweet.content}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    About: {tweet.summary_title}
                  </div>
                </div>
                
                {/* Conversation History */}
                <div className="max-h-64 overflow-y-auto mb-4">
                  <div className="space-y-2">
                    {(tweetConversations[tweet.id] || []).map((msg, i) => {
                      const isLastMessage = i === (tweetConversations[tweet.id] || []).length - 1
                      const isAIMessage = msg.role === 'assistant'
                      const hasUpdateInMessage = pendingTweetUpdate && isLastMessage && isAIMessage
                      
                      return (
                        <div key={i}>
                          <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[80%] p-2 rounded text-sm ${
                              msg.role === 'user' 
                                ? 'bg-blue-500 text-white' 
                                : 'bg-white border text-gray-900'
                            }`}>
                              {msg.content}
                            </div>
                          </div>
                          
                          {/* Show accept/reject buttons after the last AI message with an update */}
                          {hasUpdateInMessage && (
                            <div className="mt-2 ml-auto max-w-[80%]">
                              <div className="p-3 bg-blue-50 border border-blue-200 rounded">
                                <div className="flex items-center justify-between mb-1">
                                  <div className="text-xs font-medium text-blue-700">Suggested Tweet:</div>
                                  <div className={`text-xs font-mono ${
                                    pendingTweetUpdate.length > 280 ? 'text-red-600' : 
                                    pendingTweetUpdate.length > 260 ? 'text-yellow-600' : 'text-green-600'
                                  }`}>
                                    {pendingTweetUpdate.length}/280
                                  </div>
                                </div>
                                <div className="text-sm text-gray-900 mb-2 p-2 bg-white rounded border">
                                  {pendingTweetUpdate}
                                </div>
                                <div className="flex gap-2">
                                  <button
                                    onClick={onAcceptUpdate}
                                    className="px-2 py-1 bg-green-500 text-white text-xs rounded hover:bg-green-600 transition-colors"
                                    disabled={pendingTweetUpdate.length > 280}
                                  >
                                    ✓ Accept
                                  </button>
                                  <button
                                    onClick={onRejectUpdate}
                                    className="px-2 py-1 bg-red-500 text-white text-xs rounded hover:bg-red-600 transition-colors"
                                  >
                                    ✗ Reject
                                  </button>
                                </div>
                                {pendingTweetUpdate.length > 280 && (
                                  <div className="mt-1 text-xs text-red-600">
                                    Tweet is too long! Ask the AI to shorten it.
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
                
                {/* Message Input */}
                <form onSubmit={async (e) => {
                  e.preventDefault()
                  const formData = new FormData(e.target as HTMLFormElement)
                  const message = formData.get('message') as string
                  if (!message.trim()) return
                  
                  // Add user message to conversation immediately
                  const newConversation = [
                    ...(tweetConversations[tweet.id] || []),
                    { role: 'user', content: message }
                  ]
                  
                  // Clear input
                  const form = e.target as HTMLFormElement
                  form.reset()
                  
                  // Send message and get AI response
                  await onSendMessage(message)
                }}>
                  <div className="flex gap-2">
                    <input
                      name="message"
                      type="text"
                      placeholder="Tell me how to improve this tweet..."
                      className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      type="submit"
                      className="px-3 py-2 bg-blue-500 text-white text-sm rounded hover:bg-blue-600 transition-colors"
                    >
                      Send
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}


