import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AI Newsletter Generator',
  description: 'Weekly AI highlights from top sources with tweet and newsletter generation',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <div className="mx-auto max-w-5xl px-4 py-6">
          <header className="mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-lg bg-black" />
              <div>
                <h1 className="text-xl font-semibold">AI Newsletter Generator</h1>
                <p className="text-xs text-gray-500">Curate, summarize, and publish—fast.</p>
              </div>
            </div>
            <a className="btn" href="https://vercel.com" target="_blank" rel="noreferrer">Deploy</a>
          </header>
          {children}
        </div>
      </body>
    </html>
  )
}


