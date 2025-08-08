### AI Newsletter Generator

Full-stack app with Next.js (UI) and FastAPI on Vercel Python serverless functions.

Features
- Aggregates recent AI news from up to 5 RSS feeds
- Weekly summary generation via OpenAI
- Generates 3 distinct Tweets
- Auto-formats a Mailchimp-style newsletter with links
- In-place editors powered by LLM chat with session memory
- Downloadable HTML newsletter

Requirements
- Node 18+
- Python 3.11
- Vercel CLI (optional for deploy)

Setup
1) Copy env: `cp .env.example .env.local` and set `OPENAI_API_KEY`.
2) Install JS deps: `npm i`.
3) (Optional) Use uv locally (recommended):
   - Install uv: see `https://docs.astral.sh/uv/`
   - Manage Python deps via `pyproject.toml`.
   - Export for Vercel before build: `npm run gen:req` (or `uv export --no-dev --format requirements-txt > requirements.txt`).
   - Without uv, you can install Python deps for local testing using `pip install -r requirements.txt`.
4) Run dev: `npm run dev` and visit http://localhost:3000

Vercel Deploy
- Ensure `vercel.json` is present. Push to GitHub and import in Vercel.
- Set environment variable `OPENAI_API_KEY` in Vercel Project Settings.

Notes
- The Python function lives at `api/index.py` and is exposed under `/api/index/*`.
- Memory is ephemeral in serverless. The UI mirrors history in `localStorage` and sends it with requests.
- We keep `requirements.txt` checked in for Vercel. If you change deps in `pyproject.toml`, regenerate via `npm run gen:req`.


