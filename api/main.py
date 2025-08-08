import os
import io
import json
from datetime import datetime, timedelta, timezone
import re
from html import unescape
import httpx
from typing import List, Optional, Dict, Any

import feedparser
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, AnyHttpUrl
from dateutil import parser as dateparser
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


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
    # Working RSS feeds verified as of 2025
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "The Gradient": "https://thegradient.pub/rss/",
    "MIT Technology Review AI": "https://www.technologyreview.com/tag/artificial-intelligence/feed/",
    "VentureBeat AI": "https://venturebeat.com/ai/feed/",
    "AI News": "https://artificialintelligence-news.com/feed/",
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


# ----- Per-Article Summaries (Highlights) -----
class HighlightItem(BaseModel):
    title: str
    link: AnyHttpUrl
    source: Optional[str] = None
    summary: str


class TweetsRequest(BaseModel):
    session_id: str
    summaries: List[HighlightItem]  # Changed to use individual summaries
    prior_history: Optional[List[ConversationTurn]] = None


class Tweet(BaseModel):
    id: str
    content: str
    summary_title: str
    summary_link: str
    summary_source: str


class TweetsResponse(BaseModel):
    tweets: List[Tweet]


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


class SummariesSelectedRequest(BaseModel):
    articles: List[Article]


class EditResponse(BaseModel):
    edited_text: str
    history: List[ConversationTurn]


class TweetEditRequest(BaseModel):
    session_id: str
    tweet_id: str
    current_tweet: str
    original_summary: str
    user_message: str
    conversation_history: Optional[List[ConversationTurn]] = None


class TweetEditResponse(BaseModel):
    new_tweet: str
    ai_response: str
    conversation_history: List[ConversationTurn]


# Initialize OpenAI client with error handling
try:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("WARNING: OPENAI_API_KEY not found in environment variables")
        openai_client = None
    else:
        openai_client = OpenAI(api_key=api_key)
    MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
except Exception as e:
    print(f"ERROR initializing OpenAI client: {e}")
    openai_client = None


def _parse_date(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return dateparser.parse(dt_str)
    except Exception:
        return None


@app.get("/")
def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "AI Newsletter API is running"}


@app.get("/defaults", response_model=Dict[str, str])
def get_defaults() -> Dict[str, str]:
    """Get default RSS feed sources"""
    try:
        return DEFAULT_FEEDS
    except Exception as e:
        print(f"Error in get_defaults: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.post("/aggregate", response_model=AggregateResponse)
def aggregate(req: AggregateRequest) -> AggregateResponse:
    # Only retrieve from explicitly selected sources. If none provided, return empty.
    sources = req.sources or []
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


# ----- Simple Web Scraper (no external heavy deps) -----
class ScrapeRequest(BaseModel):
    url: AnyHttpUrl


class ScrapeResponse(BaseModel):
    content_text: str


def _extract_main_text(html: str) -> str:
    # Try to focus on <article> or <main> blocks first
    try:
        article_match = re.search(r"<article[\s\S]*?</article>", html, flags=re.IGNORECASE)
        main_match = re.search(r"<main[\s\S]*?</main>", html, flags=re.IGNORECASE)
        snippet = None
        if article_match:
            snippet = article_match.group(0)
        elif main_match:
            snippet = main_match.group(0)
        else:
            snippet = html
        # Remove scripts/styles
        snippet = re.sub(r"<script[\s\S]*?</script>", " ", snippet, flags=re.IGNORECASE)
        snippet = re.sub(r"<style[\s\S]*?</style>", " ", snippet, flags=re.IGNORECASE)
        # Strip tags
        text = re.sub(r"<[^>]+>", " ", snippet)
        text = unescape(text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception:
        return ""


@app.post("/scrape", response_model=ScrapeResponse)
def scrape(req: ScrapeRequest) -> ScrapeResponse:
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Newsletter/1.0)"}) as client:
            resp = client.get(str(req.url))
            resp.raise_for_status()
            text = _extract_main_text(resp.text)
            # Limit to a safe size for LLM context
            if len(text) > 8000:
                text = text[:8000]
            return ScrapeResponse(content_text=text)
    except Exception:
        return ScrapeResponse(content_text="")


class HighlightsRequest(BaseModel):
    sources: List[AnyHttpUrl]
    since_days: int = Field(default=7, ge=1, le=31)
    max_articles: int = Field(default=8, ge=1, le=20)


class HighlightsResponse(BaseModel):
    items: List[HighlightItem]


@app.post("/summaries", response_model=HighlightsResponse)
def summaries(req: HighlightsRequest) -> HighlightsResponse:
    # Enforce selection: if no sources, return empty list
    if not req.sources:
        return HighlightsResponse(items=[])

    articles_resp = aggregate(AggregateRequest(sources=req.sources, since_days=req.since_days))
    items: List[HighlightItem] = []

    # Use configurable limit (default 8, max 20)
    limited_articles = articles_resp.articles[:req.max_articles]

    for a in limited_articles:
        # Scrape content with shorter timeout
        content_text = ""
        try:
            with httpx.Client(timeout=5.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Newsletter/1.0)"}) as client:
                resp = client.get(str(a.link))
                resp.raise_for_status()
                raw_html = resp.text
                content_text = _extract_main_text(raw_html)
        except Exception:
            # Fallback to RSS summary if scraping fails
            content_text = a.summary or ""

        if len(content_text) > 4000:  # Reduced from 8000 for faster processing
            content_text = content_text[:4000]

        # If no content available, use title and RSS summary
        if not content_text.strip():
            content_text = f"Title: {a.title}\nRSS Summary: {a.summary or 'No summary available'}"

        # Summarize the single article's content
        system = (
            "You are an expert AI news editor. Summarize the article content for a busy technical audience. "
            "Be concise (3-5 bullet points), capture key findings. If content is limited, work with what's available."
        )
        user = (
            f"Title: {a.title}\nSource: {a.source or ''}\nURL: {a.link}\n\n"
            f"Content:\n{content_text}\n\n"
            "Write a clear, concise summary."
        )
        
        try:
            summary_text = _chat([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ], temperature=0.3)
        except Exception:
            # Fallback if OpenAI fails
            summary_text = a.summary or f"Unable to generate summary for: {a.title}"

        items.append(HighlightItem(title=a.title, link=a.link, source=a.source, summary=summary_text.strip()))

    return HighlightsResponse(items=items)


@app.post("/summaries_selected", response_model=HighlightsResponse)
def summaries_selected(req: SummariesSelectedRequest) -> HighlightsResponse:
    """Process summaries for only selected articles (no RSS aggregation needed)"""
    items: List[HighlightItem] = []

    for a in req.articles[:5]:  # Limit to 5 articles max for performance
        # Scrape content with shorter timeout
        content_text = ""
        try:
            with httpx.Client(timeout=5.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Newsletter/1.0)"}) as client:
                resp = client.get(str(a.link))
                resp.raise_for_status()
                raw_html = resp.text
                content_text = _extract_main_text(raw_html)
        except Exception:
            # Fallback to RSS summary if scraping fails
            content_text = a.summary or ""

        if len(content_text) > 4000:  # Reduced for faster processing
            content_text = content_text[:4000]

        # If no content available, use title and RSS summary
        if not content_text.strip():
            content_text = f"Title: {a.title}\nRSS Summary: {a.summary or 'No summary available'}"

        # Summarize the single article's content
        system = (
            "You are an expert AI news editor. Summarize the article content for a busy technical audience. "
            "Be concise (3-5 bullet points), capture key findings. If content is limited, work with what's available."
        )
        user = (
            f"Title: {a.title}\nSource: {a.source or ''}\nURL: {a.link}\n\n"
            f"Content:\n{content_text}\n\n"
            "Write a clear, concise summary."
        )
        
        try:
            summary_text = _chat([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ], temperature=0.3)
        except Exception:
            # Fallback if OpenAI fails
            summary_text = a.summary or f"Unable to generate summary for: {a.title}"

        items.append(HighlightItem(title=a.title, link=a.link, source=a.source, summary=summary_text.strip()))

    return HighlightsResponse(items=items)


def _chat(messages: List[Dict[str, str]], temperature: float = 0.4) -> str:
    completion = openai_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
    )
    return completion.choices[0].message.content or ""


@app.post("/highlights", response_model=SummarizeResponse)
def highlights_endpoint(req: SummarizeRequest) -> SummarizeResponse:
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

    # Anchor summary to the current week to avoid stale dates from the model
    now_local = datetime.now()
    week_start = now_local - timedelta(days=now_local.weekday())  # Monday
    week_of = week_start.strftime("%b %d, %Y")

    system = (
        "You are an expert AI news editor. Create a crisp weekly summary for a technical audience. "
        "Use clear section headings, bullet points, and callouts. Include hyperlinks when relevant. "
        f"Always label the summary with a top heading 'Week of {week_of}'."
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
    # Ensure the summary includes the correct 'Week of' label without duplication
    content_clean = content.strip()
    if not content_clean.lower().startswith(("week of", "# week of", "## week of")):
        content = f"## Week of {week_of}\n\n" + content_clean
    else:
        content = content_clean
    memory.last_summary = content
    memory.history.append(ConversationTurn(role="user", content=user))
    memory.history.append(ConversationTurn(role="assistant", content=content))
    return SummarizeResponse(summary_markdown=content)


@app.post("/tweets", response_model=TweetsResponse)
def generate_tweets(req: TweetsRequest) -> TweetsResponse:
    memory = get_memory(req.session_id)
    if req.prior_history:
        memory.history.extend(req.prior_history[-8:])
    
    tweets: List[Tweet] = []
    
    for i, summary in enumerate(req.summaries):
        system = (
            "You write engaging, factual, and concise Twitter posts (X). "
            "Create ONE tweet about this specific AI news article."
        )
        user = (
            f"Create a single engaging tweet about this AI news article:\n\n"
            f"Title: {summary.title}\n"
            f"Source: {summary.source}\n"
            f"Summary: {summary.summary}\n\n"
            "Include 1-2 relevant emojis and 1-2 hashtags. Keep under 280 characters. "
            "Return only the tweet text, no JSON formatting."
        )
        
        messages = (
            [{"role": "system", "content": system}]
            + [{"role": t.role, "content": t.content} for t in memory.history[-4:]]
            + [{"role": "user", "content": user}]
        )
        
        try:
            tweet_content = _chat(messages, temperature=0.7)
            # Clean up the response
            tweet_content = tweet_content.strip().strip('"').strip("'")
            
            tweet = Tweet(
                id=f"tweet_{i}_{summary.title[:20].replace(' ', '_')}",
                content=tweet_content,
                summary_title=summary.title,
                summary_link=str(summary.link),
                summary_source=summary.source or "Unknown"
            )
            tweets.append(tweet)
            
        except Exception:
            # Fallback tweet if AI generation fails
            fallback_content = f"🤖 {summary.title[:200]}... #AI #Tech"
            tweet = Tweet(
                id=f"tweet_{i}_{summary.title[:20].replace(' ', '_')}",
                content=fallback_content,
                summary_title=summary.title,
                summary_link=str(summary.link),
                summary_source=summary.source or "Unknown"
            )
            tweets.append(tweet)
    
    # Store conversation context
    turn_user = ConversationTurn(role="user", content=f"Generated {len(tweets)} tweets from summaries")
    turn_assistant = ConversationTurn(role="assistant", content="Tweets generated successfully")
    memory.history.append(turn_user)
    memory.history.append(turn_assistant)
    
    memory.last_tweets = [t.content for t in tweets]  # Store for backward compatibility
    return TweetsResponse(tweets=tweets)


def _build_newsletter_html(summary_md: str, articles: List[Article]) -> str:
    # Select featured article (first article with good content)
    featured_article = None
    remaining_articles = []
    
    for article in articles[:8]:  # Use first 8 articles
        if not featured_article and article.summary and len(article.summary) > 100:
            featured_article = article
        else:
            remaining_articles.append(article)
    
    # If no good featured article found, use the first one
    if not featured_article and articles:
        featured_article = articles[0]
        remaining_articles = articles[1:8]
    
    # Build news grid items (max 6 items, 2x3 grid)
    news_items = ""
    for i, article in enumerate(remaining_articles[:6]):
        news_items += f"""
                    <div class="news-item">
                        <h4>{article.title}</h4>
                        <p>{(article.summary or 'Click to read more about this story.')[:150]}{'...' if len(article.summary or '') > 150 else ''}</p>
                        <a href="{article.link}" class="read-more">Read more →</a>
                    </div>
        """
    
    now = datetime.now().strftime("%B %d, %Y")
    
    # Format featured article
    featured_title = featured_article.title if featured_article else "AI Weekly Highlights"
    featured_summary = (featured_article.summary or "This week brings exciting developments in AI and technology.")[:200] + "..." if featured_article and len(featured_article.summary or "") > 200 else (featured_article.summary if featured_article else "This week brings exciting developments in AI and technology.")
    featured_link = featured_article.link if featured_article else "#"
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Weekly - Newsletter</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            background-color: #f4f4f4;
            color: #333;
        }}
        
        .container {{
            max-width: 600px;
            margin: 20px auto;
            background-color: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
        }}
        
        .logo {{
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .tagline {{
            font-size: 14px;
            opacity: 0.9;
        }}
        
        .content {{
            padding: 30px 20px;
        }}
        
        .section {{
            margin-bottom: 30px;
            border-bottom: 1px solid #eee;
            padding-bottom: 30px;
        }}
        
        .section:last-child {{
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }}
        
        .section h2 {{
            color: #667eea;
            font-size: 22px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
            padding-left: 15px;
        }}
        
        .featured-article {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        
        .featured-article h3 {{
            font-size: 20px;
            margin-bottom: 10px;
        }}
        
        .featured-article p {{
            margin-bottom: 15px;
            opacity: 0.95;
        }}
        
        .btn {{
            display: inline-block;
            background-color: white;
            color: #f5576c;
            padding: 12px 25px;
            text-decoration: none;
            border-radius: 25px;
            font-weight: bold;
            transition: transform 0.3s ease;
        }}
        
        .btn:hover {{
            transform: translateY(-2px);
        }}
        
        .news-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }}
        
        .news-item {{
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 20px;
            transition: box-shadow 0.3s ease;
        }}
        
        .news-item:hover {{
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .news-item h4 {{
            color: #333;
            margin-bottom: 10px;
            font-size: 16px;
        }}
        
        .news-item p {{
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }}
        
        .read-more {{
            color: #667eea;
            text-decoration: none;
            font-size: 14px;
            font-weight: bold;
        }}
        
        .cta-section {{
            background-color: #f8f9fa;
            padding: 30px;
            text-align: center;
            border-radius: 10px;
        }}
        
        .cta-section h3 {{
            color: #333;
            margin-bottom: 15px;
        }}
        
        .cta-btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 30px;
            text-decoration: none;
            border-radius: 30px;
            font-weight: bold;
            display: inline-block;
            margin-top: 10px;
        }}
        
        .social-links {{
            text-align: center;
            margin-top: 30px;
        }}
        
        .social-links a {{
            display: inline-block;
            margin: 0 10px;
            width: 40px;
            height: 40px;
            background-color: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 50%;
            line-height: 40px;
            transition: background-color 0.3s ease;
        }}
        
        .social-links a:hover {{
            background-color: #764ba2;
        }}
        
        .footer {{
            background-color: #333;
            color: white;
            padding: 30px 20px;
            text-align: center;
        }}
        
        .footer p {{
            margin-bottom: 10px;
            font-size: 14px;
        }}
        
        .footer a {{
            color: #667eea;
            text-decoration: none;
        }}
        
        @media (max-width: 600px) {{
            .news-grid {{
                grid-template-columns: 1fr;
            }}
            
            .container {{
                margin: 10px;
            }}
            
            .content {{
                padding: 20px 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="logo" style="display:flex; align-items:center; justify-content:center; gap:10px;">
                <img src="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjQiIGhlaWdodD0iNjQiIHZpZXdCb3g9IjAgMCA2NCA2NCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8ZGVmcz4KICAgIDxsaW5lYXJHcmFkaWVudCBpZD0ibG9nb0dyYWQiIHgxPSIwJSIgeTE9IjAlIiB4Mj0iMTAwJSIgeTI9IjEwMCUiPgogICAgICA8c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjNjY3ZWVhIi8+CiAgICAgIDxzdG9wIG9mZnNldD0iNTAlIiBzdG9wLWNvbG9yPSIjNzY0YmEyIi8+CiAgICAgIDxzdG9wIG9mZnNldD0iMTAwJSIgc3RvcC1jb2xvcj0iI2YwOTNmYiIvPgogICAgPC9saW5lYXJHcmFkaWVudD4KICA8L2RlZnM+CiAgCiAgPCEtLSBNYWluIGNvbnRhaW5lciBjaXJjbGUgLS0+CiAgPGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iMjgiIGZpbGw9InVybCgjbG9nb0dyYWQpIi8+CiAgCiAgPCEtLSBOZXVyYWwgbmV0d29yayBub2RlcyAtLT4KICA8ZyBmaWxsPSIjZmZmZmZmIiBvcGFjaXR5PSIwLjkiPgogICAgPCEtLSBJbnB1dCBsYXllciAtLT4KICAgIDxjaXJjbGUgY3g9IjE4IiBjeT0iMjQiIHI9IjIuNSIvPgogICAgPGNpcmNsZSBjeD0iMTgiIGN5PSIzMiIgcj0iMi41Ii8+CiAgICA8Y2lyY2xlIGN4PSIxOCIgY3k9IjQwIiByPSIyLjUiLz4KICAgIAogICAgPCEtLSBIaWRkZW4gbGF5ZXIgLS0+CiAgICA8Y2lyY2xlIGN4PSIzMiIgY3k9IjIwIiByPSIyIi8+CiAgICA8Y2lyY2xlIGN4PSIzMiIgY3k9IjI4IiByPSIyIi8+CiAgICA8Y2lyY2xlIGN4PSIzMiIgY3k9IjM2IiByPSIyIi8+CiAgICA8Y2lyY2xlIGN4PSIzMiIgY3k9IjQ0IiByPSIyIi8+CiAgICAKICAgIDwhLS0gT3V0cHV0IGxheWVyIC0tPgogICAgPGNpcmNsZSBjeD0iNDYiIGN5PSIyOCIgcj0iMi41Ii8+CiAgICA8Y2lyY2xlIGN4PSI0NiIgY3k9IjM2IiByPSIyLjUiLz4KICA8L2c+CiAgCiAgPCEtLSBOZXVyYWwgbmV0d29yayBjb25uZWN0aW9ucyAtLT4KICA8ZyBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iMSIgb3BhY2l0eT0iMC42IiBmaWxsPSJub25lIj4KICAgIDwhLS0gSW5wdXQgdG8gaGlkZGVuIGNvbm5lY3Rpb25zIC0tPgogICAgPGxpbmUgeDE9IjIwLjUiIHkxPSIyNCIgeDI9IjMwIiB5Mj0iMjAiLz4KICAgIDxsaW5lIHgxPSIyMC41IiB5MT0iMjQiIHgyPSIzMCIgeTI9IjI4Ii8+CiAgICA8bGluZSB4MT0iMjAuNSIgeTE9IjMyIiB4Mj0iMzAiIHkyPSIyOCIvPgogICAgPGxpbmUgeDE9IjIwLjUiIHkxPSIzMiIgeDI9IjMwIiB5Mj0iMzYiLz4KICAgIDxsaW5lIHgxPSIyMC41IiB5MT0iNDAiIHgyPSIzMCIgeTI9IjM2Ii8+CiAgICA8bGluZSB4MT0iMjAuNSIgeTE9IjQwIiB4Mj0iMzAiIHkyPSI0NCIvPgogICAgCiAgICA8IS0tIEhpZGRlbiB0byBvdXRwdXQgY29ubmVjdGlvbnMgLS0+CiAgICA8bGluZSB4MT0iMzQiIHkxPSIyMCIgeDI9IjQzLjUiIHkyPSIyOCIvPgogICAgPGxpbmUgeDE9IjM0IiB5MT0iMjgiIHgyPSI0My41IiB5Mj0iMjgiLz4KICAgIDxsaW5lIHgxPSIzNCIgeTE9IjM2IiB4Mj0iNDMuNSIgeTI9IjM2Ii8+CiAgICA8bGluZSB4MT0iMzQiIHkxPSI0NCIgeDI9IjQzLjUiIHkyPSIzNiIvPgogIDwvZz4KICAKICA8IS0tIEFJIHN5bWJvbCBpbiBjZW50ZXIgLS0+CiAgPGcgZmlsbD0iI2ZmZmZmZiIgb3BhY2l0eT0iMC44Ij4KICAgIDx0ZXh0IHg9IjMyIiB5PSIxNiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1mYW1pbHk9IkFyaWFsLCBzYW5zLXNlcmlmIiBmb250LXNpemU9IjgiIGZvbnQtd2VpZ2h0PSJib2xkIj5BSTwvdGV4dD4KICA8L2c+CiAgCiAgPCEtLSBOZXdzbGV0dGVyL2RvY3VtZW50IGljb24gLS0+CiAgPGcgZmlsbD0iI2ZmZmZmZiIgb3BhY2l0eT0iMC43Ij4KICAgIDxyZWN0IHg9IjI2IiB5PSI0OCIgd2lkdGg9IjEyIiBoZWlnaHQ9IjgiIHJ4PSIxIi8+CiAgICA8bGluZSB4MT0iMjgiIHkxPSI1MCIgeDI9IjM2IiB5Mj0iNTAiIHN0cm9rZT0iIzY2N2VlYSIgc3Ryb2tlLXdpZHRoPSIwLjgiLz4KICAgIDxsaW5lIHgxPSIyOCIgeTE9IjUyIiB4Mj0iMzQiIHkyPSI1MiIgc3Ryb2tlPSIjNjY3ZWVhIiBzdHJva2Utd2lkdGg9IjAuOCIvPgogICAgPGxpbmUgeDE9IjI4IiB5MT0iNTQiIHgyPSIzNiIgeTI9IjU0IiBzdHJva2U9IiM2NjdlZWEiIHN0cm9rZS13aWR0aD0iMC44Ii8+CiAgPC9nPgo8L3N2Zz4K" alt="AI Weekly" width="28" height="28" style="display:inline-block; vertical-align:middle;" />
                <span>AI Weekly</span>
            </div>
            <div class="tagline">Your weekly dose of AI insights • {now}</div>
        </div>
        
        <!-- Main Content -->
        <div class="content">
            <!-- Welcome Section -->
            <div class="section">
                <h2>📧 This Week's Highlights</h2>
                <p>Hello AI Tech Enthusiasts! Welcome to another edition of AI Weekly. This week, we're diving deep into the latest AI developments, breakthrough innovations, and emerging technologies that are shaping our digital future.</p>
            </div>
            
            <!-- Featured Article -->
            <div class="section">
                <h2>🌟 Featured Story</h2>
                <div class="featured-article">
                    <h3>{featured_title}</h3>
                    <p>{featured_summary}</p>
                    <a href="{featured_link}" class="btn">Read Full Article</a>
                </div>
            </div>
            
            <!-- News Section -->
            <div class="section">
                <h2>📰 Latest AI News</h2>
                <div class="news-grid">
                    {news_items}
                </div>
            </div>
            
            <!-- CTA Section -->
            <div class="section">
                <div class="cta-section">
                    <h3>🤖 Stay Connected</h3>
                    <p>Join thousands of AI enthusiasts getting the latest insights delivered weekly.</p>
                    <a href="#" class="cta-btn">Subscribe for Updates</a>
                </div>
            </div>
            
            <!-- Social Links -->
            <div class="social-links">
                <a href="#">🐦</a>
                <a href="#">📘</a>
                <a href="#">💼</a>
                <a href="#">📧</a>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p><strong>AI Weekly</strong></p>
            <p>Curated with ❤️ by AI Newsletter</p>
            <p>© 2025 AI Weekly. All rights reserved.</p>
            <p style="margin-top: 20px;">
                <a href="#">Unsubscribe</a> | 
                <a href="#">Update Preferences</a> | 
                <a href="#">Privacy Policy</a>
            </p>
        </div>
    </div>
</body>
</html>"""


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


@app.post("/edit_tweet", response_model=TweetEditResponse)
def edit_tweet(req: TweetEditRequest) -> TweetEditResponse:
    # Get or create conversation history for this specific tweet
    conversation_key = f"{req.session_id}_tweet_{req.tweet_id}"
    if conversation_key not in memory_store:
        memory_store[conversation_key] = SessionMemory(session_id=conversation_key)
    
    tweet_memory = memory_store[conversation_key]
    
    # Add any provided conversation history
    if req.conversation_history:
        tweet_memory.history.extend(req.conversation_history)
    
    system = (
        "You are an AI assistant helping to edit and improve Twitter/X posts. "
        "You have context about the original article summary and the current tweet. "
        "Help the user modify the tweet based on their requests while keeping it STRICTLY under 280 characters. "
        "CRITICAL: Count characters carefully - if adding hashtags would exceed 280 chars, shorten the main text to make room. "
        "IMPORTANT: Always structure your response as follows:\n"
        "1. A brief conversational response to the user\n"
        "2. Then on a new line, write 'UPDATED TWEET:' followed by the new tweet content\n"
        "Example format:\n"
        "Sure! I'll add more hashtags and shorten the text to fit.\n\n"
        "UPDATED TWEET: Your concise tweet content with #hashtags #AI #Tech"
    )
    
    context = (
        f"Original Article Summary: {req.original_summary}\n"
        f"Current Tweet: {req.current_tweet}\n"
        f"User Request: {req.user_message}"
    )
    
    messages = (
        [{"role": "system", "content": system}]
        + [{"role": t.role, "content": t.content} for t in tweet_memory.history[-6:]]
        + [{"role": "user", "content": context}]
    )
    
    ai_response = _chat(messages, temperature=0.7)
    
    # Extract the new tweet and AI message using the structured format
    new_tweet = req.current_tweet  # Fallback to current tweet
    ai_message = ai_response
    
    # Look for "UPDATED TWEET:" pattern
    if "UPDATED TWEET:" in ai_response:
        parts = ai_response.split("UPDATED TWEET:", 1)
        if len(parts) == 2:
            ai_message = parts[0].strip()
            new_tweet = parts[1].strip()
            
            # Clean up the new tweet (remove any quotes or extra formatting)
            new_tweet = new_tweet.strip('"').strip("'").strip()
            
            # Validate tweet length and truncate smartly
            if len(new_tweet) > 280:
                # Try to truncate at word boundaries to avoid cutting hashtags
                words = new_tweet.split(' ')
                truncated = ""
                for word in words:
                    if len(truncated + " " + word) <= 280:
                        if truncated:
                            truncated += " " + word
                        else:
                            truncated = word
                    else:
                        break
                new_tweet = truncated if truncated else new_tweet[:280]
            
            if not ai_message:
                ai_message = "I've updated your tweet based on your request!"
    else:
        # Fallback: if the structured format wasn't followed, try to extract tweet-like content
        lines = ai_response.split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 20 and len(line) <= 280 and ('#' in line or '@' in line or any(emoji in line for emoji in ['🔥', '🚀', '💡', '🤖', '⚡'])):
                new_tweet = line
                ai_message = ai_response.replace(new_tweet, "").strip()
                if not ai_message:
                    ai_message = "I've updated your tweet based on your request!"
                break
    
    # Store conversation
    turn_user = ConversationTurn(role="user", content=req.user_message)
    turn_assistant = ConversationTurn(role="assistant", content=ai_response)
    tweet_memory.history.append(turn_user)
    tweet_memory.history.append(turn_assistant)
    
    return TweetEditResponse(
        new_tweet=new_tweet,
        ai_response=ai_message,
        conversation_history=tweet_memory.history[-10:]
    )


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


# Export for Vercel - app is automatically detected
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
