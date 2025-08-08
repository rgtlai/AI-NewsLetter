import os
import io
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

import feedparser
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, AnyHttpUrl
from dateutil import parser as dateparser
from openai import OpenAI


# ASGI app for Vercel Python function: export `app`
app = FastAPI(title="AI Newsletter Generator API", version="1.0.0")

# CORS (same-origin on Vercel, but allow localhost for dev)
allowed_origins = [
    os.getenv("ALLOWED_ORIGIN", "*"),
    "http://localhost:3000",
    "https://localhost:3000",
    "http://localhost:3001",
    "https://localhost:3001",
    "http://localhost:3010",
    "https://localhost:3010",
    "http://localhost:3002",
    "https://localhost:3002",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"]
    ,
    allow_headers=["*"]
)


# ----- Memory Store (ephemeral in serverless) -----
class ConversationTurn(BaseModel):
    role: str
    content: str


class SessionMemory(BaseModel):
    session_id: str
    history: List[ConversationTurn] = Field(default_factory=list)
    last_newsletter_html: Optional[str] = None
    last_summary: Optional[str] = None
    last_tweets: Optional[List[str]] = None


memory_store: Dict[str, SessionMemory] = {}


def get_memory(session_id: str) -> SessionMemory:
    if session_id not in memory_store:
        memory_store[session_id] = SessionMemory(session_id=session_id)
    return memory_store[session_id]


# ----- Default RSS Feeds (AI-focused) -----
DEFAULT_FEEDS: Dict[str, str] = {
    # Verified commonly available feeds; users can also provide custom RSS URLs
    "Google AI Blog": "https://ai.googleblog.com/atom.xml",
    "DeepMind": "https://deepmind.google/discover/blog/feed.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "Stability AI": "https://stability.ai/blog/rss.xml",
    "The Gradient": "https://thegradient.pub/rss/",
}


# ----- Models -----
class AggregateRequest(BaseModel):
    sources: Optional[List[AnyHttpUrl]] = None
    since_days: int = Field(default=7, ge=1, le=31)


class Article(BaseModel):
    title: str
    link: AnyHttpUrl
    summary: Optional[str] = None
    published: Optional[str] = None
    source: Optional[str] = None


class AggregateResponse(BaseModel):
    articles: List[Article]


class SummarizeRequest(BaseModel):
    session_id: str
    articles: List[Article]
    instructions: Optional[str] = Field(
        default=(
            "Summarize the week's most important AI developments for a technical but busy audience. "
            "Be concise, structured with headings and bullet points, and include source attributions."
        )
    )
    prior_history: Optional[List[ConversationTurn]] = None


class SummarizeResponse(BaseModel):
    summary_markdown: str


class TweetsRequest(BaseModel):
    session_id: str
    summary_markdown: str
    prior_history: Optional[List[ConversationTurn]] = None


class TweetsResponse(BaseModel):
    tweets: List[str]


class NewsletterRequest(BaseModel):
    session_id: str
    summary_markdown: str
    articles: List[Article]
    prior_history: Optional[List[ConversationTurn]] = None


class NewsletterResponse(BaseModel):
    html: str


class EditRequest(BaseModel):
    session_id: str
    text: str
    instruction: str
    prior_history: Optional[List[ConversationTurn]] = None


class EditResponse(BaseModel):
    edited_text: str
    history: List[ConversationTurn]


openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _parse_date(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return dateparser.parse(dt_str)
    except Exception:
        return None


@app.get("/defaults", response_model=Dict[str, str])
def get_defaults() -> Dict[str, str]:
    return DEFAULT_FEEDS


@app.post("/aggregate", response_model=AggregateResponse)
def aggregate(req: AggregateRequest) -> AggregateResponse:
    sources = req.sources or list(DEFAULT_FEEDS.values())
    cutoff = datetime.now(timezone.utc) - timedelta(days=req.since_days)

    collected: List[Article] = []
    for src in sources:
        feed = feedparser.parse(str(src))
        source_title = getattr(feed.feed, "title", None) or "Unknown Source"
        for entry in feed.entries[:50]:
            published = None
            published_dt: Optional[datetime] = None
            if hasattr(entry, "published"):
                published = entry.published
                published_dt = _parse_date(published)
            elif hasattr(entry, "updated"):
                published = entry.updated
                published_dt = _parse_date(published)

            # Filter by recency if date available
            if published_dt and published_dt.tzinfo is None:
                published_dt = published_dt.replace(tzinfo=timezone.utc)
            if published_dt and published_dt < cutoff:
                continue

            summary = getattr(entry, "summary", None)
            link = getattr(entry, "link", None)
            title = getattr(entry, "title", None)
            if not (title and link):
                continue

            collected.append(
                Article(
                    title=title,
                    link=link,
                    summary=summary,
                    published=published,
                    source=source_title,
                )
            )

    return AggregateResponse(articles=collected)


def _chat(messages: List[Dict[str, str]], temperature: float = 0.4) -> str:
    completion = openai_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
    )
    return completion.choices[0].message.content or ""


@app.post("/summarize", response_model=SummarizeResponse)
def summarize(req: SummarizeRequest) -> SummarizeResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    memory = get_memory(req.session_id)
    if req.prior_history:
        memory.history.extend(req.prior_history[-8:])
    # Build context from articles
    articles_text = "\n".join(
        [
            f"- {a.title} ({a.source}) — {a.link}\n{a.summary or ''}"
            for a in req.articles[:20]
        ]
    )

    system = (
        "You are an expert AI news editor. Create a crisp weekly summary for a technical audience. "
        "Use clear section headings, bullet points, and callouts. Include hyperlinks when relevant."
    )
    user = (
        f"Write a weekly highlights summary based on these items:\n\n{articles_text}\n\n"
        f"Instructions: {req.instructions}"
    )

    messages: List[Dict[str, str]] = (
        [
            {"role": "system", "content": system},
        ]
        + [{"role": t.role, "content": t.content} for t in memory.history[-6:]]
        + [
            {"role": "user", "content": user},
        ]
    )

    content = _chat(messages, temperature=0.3)
    memory.last_summary = content
    memory.history.append(ConversationTurn(role="user", content=user))
    memory.history.append(ConversationTurn(role="assistant", content=content))
    return SummarizeResponse(summary_markdown=content)


@app.post("/tweets", response_model=TweetsResponse)
def generate_tweets(req: TweetsRequest) -> TweetsResponse:
    memory = get_memory(req.session_id)
    if req.prior_history:
        memory.history.extend(req.prior_history[-8:])
    system = (
        "You write engaging, factual, and concise Twitter posts (X)."
    )
    user = (
        "Create 3 distinct tweets derived from the weekly AI summary below. "
        "Vary tone and angle. Include 1-2 relevant emojis and 1-2 hashtags per tweet. "
        "Keep each under 280 characters. Do not number them; return as a JSON array of strings.\n\n"
        f"Summary:\n{req.summary_markdown}"
    )
    messages = (
        [
            {"role": "system", "content": system},
        ]
        + [{"role": t.role, "content": t.content} for t in memory.history[-6:]]
        + [
            {"role": "user", "content": user},
        ]
    )
    content = _chat(messages, temperature=0.7)
    tweets: List[str]
    try:
        tweets = json.loads(content)
        if not isinstance(tweets, list):
            raise ValueError
        tweets = [str(t) for t in tweets][:3]
    except Exception:
        # Fallback: split by newlines
        tweets = [t.strip("- ") for t in content.split("\n") if t.strip()][:3]

    memory.last_tweets = tweets
    return TweetsResponse(tweets=tweets)


def _build_newsletter_html(summary_md: str, articles: List[Article]) -> str:
    # Minimal Mailchimp-like layout with inline CSS for broad compatibility
    # For production, consider a templating system and inlining CSS
    article_items = "".join(
        [
            f"""
            <tr>
              <td style=\"padding:12px 0; border-bottom:1px solid #eee;\">
                <a href=\"{a.link}\" style=\"font-size:16px; color:#2563eb; text-decoration:none;\">{a.title}</a>
                <div style=\"color:#6b7280; font-size:12px; margin-top:4px;\">{(a.source or '')}{' • ' + (a.published or '') if a.published else ''}</div>
                {f'<div style=\\"margin-top:6px; color:#111827;\\">{a.summary}</div>' if a.summary else ''}
              </td>
            </tr>
            """
            for a in articles[:12]
        ]
    )
    # Very simple markdown to HTML conversions (headings and bullets)
    def md_to_html(md: str) -> str:
        lines = []
        for line in md.splitlines():
            if line.startswith("### "):
                lines.append(f"<h3 style=\"margin:16px 0 8px;\">{line[4:]}</h3>")
            elif line.startswith("## "):
                lines.append(f"<h2 style=\"margin:20px 0 10px;\">{line[3:]}</h2>")
            elif line.startswith("- "):
                lines.append(f"<li>{line[2:]}</li>")
            else:
                if line.strip():
                    lines.append(f"<p style=\"margin:8px 0;\">{line}</p>")
        # Wrap list items in a <ul>
        html = []
        in_list = False
        for l in lines:
            if l.startswith("<li>") and not in_list:
                in_list = True
                html.append("<ul style=\"margin:8px 0 8px 20px;\">")
            if not l.startswith("<li>") and in_list:
                in_list = False
                html.append("</ul>")
            html.append(l)
        if in_list:
            html.append("</ul>")
        return "".join(html)

    summary_html = md_to_html(summary_md)
    now = datetime.now().strftime("%b %d, %Y")
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>AI Weekly — {now}</title>
    </head>
    <body style=\"margin:0; padding:0; background:#f3f4f6;\">
      <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\" style=\"background:#f3f4f6;\">
        <tr>
          <td align=\"center\">
            <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" width=\"640\" style=\"max-width:640px; background:#ffffff; margin:24px; padding:24px; font-family:ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial; color:#111827;\">
              <tr>
                <td style=\"text-align:center; padding-bottom:16px;\">
                  <img src=\"https://assets.vercel.com/image/upload/v1662130559/nextjs/Icon_dark_background.png\" alt=\"AI Weekly\" width=\"48\" height=\"48\" style=\"display:inline-block; border-radius:8px;\" />
                  <h1 style=\"margin:12px 0 0; font-size:24px;\">AI Weekly</h1>
                  <div style=\"color:#6b7280;\">{now}</div>
                </td>
              </tr>
              <tr>
                <td>
                  {summary_html}
                </td>
              </tr>
              <tr>
                <td>
                  <h2 style=\"margin:24px 0 12px;\">Top Reads</h2>
                  <table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\">{article_items}</table>
                </td>
              </tr>
              <tr>
                <td style=\"padding-top:24px; color:#6b7280; font-size:12px;\">
                  You are receiving this because you subscribed to AI Weekly. Unsubscribe at any time.
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


@app.post("/newsletter", response_model=NewsletterResponse)
def newsletter(req: NewsletterRequest) -> NewsletterResponse:
    memory = get_memory(req.session_id)
    if req.prior_history:
        memory.history.extend(req.prior_history[-8:])
    html = _build_newsletter_html(req.summary_markdown, req.articles)
    memory.last_newsletter_html = html
    return NewsletterResponse(html=html)


@app.post("/edit", response_model=EditResponse)
def edit(req: EditRequest) -> EditResponse:
    memory = get_memory(req.session_id)
    if req.prior_history:
        # Allow client to supply recent context from local storage when serverless memory resets
        memory.history.extend(req.prior_history[-8:])

    system = (
        "You are a helpful writing assistant. Edit the provided text according to the instruction, "
        "preserving facts and links. Return only the edited text."
    )
    user = f"Instruction: {req.instruction}\n\nText to edit:\n{req.text}"
    messages = (
        [{"role": "system", "content": system}]
        + [{"role": t.role, "content": t.content} for t in memory.history[-8:]]
        + [{"role": "user", "content": user}]
    )
    content = _chat(messages, temperature=0.4)
    turn_user = ConversationTurn(role="user", content=user)
    turn_assistant = ConversationTurn(role="assistant", content=content)
    memory.history.append(turn_user)
    memory.history.append(turn_assistant)
    return EditResponse(edited_text=content, history=memory.history[-10:])


# Provide a synchronous alternative endpoint with explicit model
class DownloadRequest(BaseModel):
    session_id: Optional[str] = None
    html: Optional[str] = None


@app.post("/download_html")
def download_html(req: DownloadRequest):
    html = req.html
    if not html and req.session_id:
        mem = get_memory(req.session_id)
        html = mem.last_newsletter_html
    if not html:
        raise HTTPException(status_code=400, detail="No HTML provided or found for session")
    buffer = io.BytesIO(html.encode("utf-8"))
    headers = {
        "Content-Disposition": "attachment; filename=ai_weekly.html"
    }
    return Response(content=buffer.getvalue(), headers=headers, media_type="text/html")


