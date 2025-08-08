"use client"

export default function TweetCards({ tweets, onEdit }: { tweets: string[], onEdit: (idx: number) => void }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {tweets.map((t, i) => (
        <div key={i} className="card p-3">
          <div className="mb-2 text-sm text-gray-500">Tweet {i + 1}</div>
          <div className="whitespace-pre-wrap text-sm">{t}</div>
          <div className="mt-3 flex justify-end">
            <button className="btn" onClick={() => onEdit(i)}>Edit with AI</button>
          </div>
        </div>
      ))}
    </div>
  )
}


