"use client"

import { useEffect, useState } from 'react'

export default function FeedPicker({
  selected,
  setSelected,
  apiBase = '/api/index',
}: {
  selected: string[]
  setSelected: (s: string[]) => void
  apiBase?: string
}) {
  const [defaults, setDefaults] = useState<Record<string, string>>({})
  const [custom, setCustom] = useState('')

  useEffect(() => {
    fetch(`${apiBase}/defaults`).then(r => r.json()).then(setDefaults).catch(console.error)
  }, [apiBase])

  function toggle(url: string) {
    setSelected(selected.includes(url) ? selected.filter(u => u !== url) : [...selected, url])
  }

  function addCustom() {
    try {
      const url = new URL(custom).toString()
      if (!selected.includes(url)) setSelected([...selected, url])
      setCustom('')
    } catch { /* ignore invalid */ }
  }

  return (
    <div className="card p-4">
      <h3 className="mb-3 text-sm font-semibold">Sources</h3>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {Object.entries(defaults).map(([name, url]) => (
          <label key={url} className="flex items-center gap-2">
            <input type="checkbox" checked={selected.includes(url)} onChange={() => toggle(url)} />
            <span className="text-sm">{name}</span>
          </label>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <input className="input w-full" placeholder="Add custom RSS URL" value={custom} onChange={e => setCustom(e.target.value)} />
        <button className="btn" onClick={addCustom}>Add</button>
      </div>
    </div>
  )
}


