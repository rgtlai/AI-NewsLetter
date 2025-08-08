import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AI Newsletter Generator',
  description: 'Weekly AI highlights from top sources with tweet and newsletter generation',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gradient-to-b from-indigo-50 to-purple-50 text-gray-900">
        <div className="mx-auto max-w-5xl px-4 py-6">
          <header className="mb-6">
            <div className="flex items-center gap-3">
              <img src="/logo.svg" alt="AI Newsletter" className="h-10 w-10" />
              <div>
                <h1 className="text-xl font-semibold bg-gradient-to-r from-indigo-500 to-purple-500 bg-clip-text text-transparent">AI Newsletter Generator</h1>
                <p className="text-xs text-gray-500">Curate, summarize, and publish—fast.</p>
              </div>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  )
}


