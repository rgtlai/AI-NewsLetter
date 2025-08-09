/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // In dev, proxy Python FastAPI (uvicorn) on 8001
    if (process.env.NODE_ENV !== 'production') {
      return [
        {
          source: '/api/:path*',
          destination: 'http://127.0.0.1:8001/:path*',
        },
      ]
    }
    // Production: proxy to Railway API
    return [
      {
        source: '/api/:path*',
        destination: 'https://ai-newsletter-production-42e7.up.railway.app/:path*',
      },
    ]
  },
}

module.exports = nextConfig