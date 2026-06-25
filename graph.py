import feedparser
import time
import json
import difflib
import re
from datetime import datetime, timedelta
from typing import Dict, List, TypedDict, Any
from langgraph.graph import StateGraph, END
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, HumanMessage
from db import NewsDatabase
from sports_api import fetch_all_sports_scores

class GraphState(TypedDict):
    config: Any  # Settings from config.py
    raw_articles: List[Dict[str, str]]
    filtered_articles: List[Dict[str, str]]
    curated_articles: List[Dict[str, str]]
    domain_briefings: Dict[str, str]
    final_briefing: str
    sports_scores: str  # Live score data injected into Sports LLM prompt

def is_recent(entry) -> bool:
    """Checks if the parsed RSS entry is within the last 48 hours."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
        return datetime.now() - dt < timedelta(hours=48)
    return True  # If no date provided, assume recent to be safe

def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation for fair comparison."""
    return re.sub(r'[^\w\s]', '', title.lower()).strip()

def fetch_rss_node(state: GraphState) -> Dict[str, Any]:
    print("-> Fetching RSS feeds...")
    config = state["config"]
    raw_articles = []

    for domain in config.app_config.domains:
        for feed_url in domain.feeds:
            parsed_feed = feedparser.parse(feed_url)
            for entry in parsed_feed.entries[:15]:  # Fetch more to allow for filtering
                if is_recent(entry):
                    raw_articles.append({
                        "domain": domain.name,
                        "emoji": domain.emoji,
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", "")[:500]
                    })

    return {"raw_articles": raw_articles}

def deduplicate_node(state: GraphState) -> Dict[str, Any]:
    """Removes articles already seen in the database (URL-based)."""
    print("-> Deduplicating articles against history DB...")
    db = NewsDatabase()
    filtered_articles = []
    raw_articles = state["raw_articles"]

    for article in raw_articles:
        if not db.is_processed(article["link"]):
            filtered_articles.append(article)

    return {"filtered_articles": filtered_articles}

def curation_node(state: GraphState) -> Dict[str, Any]:
    print("-> Curating most interesting and relatable stories specially for you")
    filtered_articles = state["filtered_articles"]
    config = state["config"]
    curated_articles = []

    models_to_try = [
        "deepseek/deepseek-chat",
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3-8b-instruct:free",
        "meta-llama/llama-3-8b-instruct",
        "openai/gpt-oss-120b:free",
        "openai/gpt-oss-120b",
        "google/gemma-4-31b-it:free",
        "google/gemma-4-31b-it",
        "nvidia/llama-3.1-nemotron-70b-instruct",
        "google/gemini-flash-1.5",
        "google/gemini-pro-1.5",
        "mistralai/mistral-7b-instruct:free"
    ]

    for domain in config.app_config.domains:
        domain_articles = [a for a in filtered_articles if a["domain"] == domain.name]

        if len(domain_articles) <= domain.target_stories:
            curated_articles.extend(domain_articles)
            continue

        system_prompt = (
            f"You are a viral news curator for a Gen-Z Indian audience. Your job is to find the most "
            f"interesting, buzzworthy, and relatable stories from a raw RSS feed.\n\n"
            f"Select exactly {domain.target_stories} stories from the list below that have the highest "
            f"potential to be viral, highly shareable, and useful. The chosen stories must be simple and "
            f"interesting enough that even a person with zero background knowledge can understand, care about, "
            f"and immediately share with their friends.\n"
            f"Output your selection ONLY as a JSON list of integers representing the IDs of the chosen stories. "
            f"Do not include any other text. Example output: [1, 4]"
        )

        articles_text = ""
        for idx, a in enumerate(domain_articles):
            articles_text += f"ID: {idx}\nTitle: {a['title']}\nSummary: {a['summary']}\n\n"

        selected_indices = None

        for model_name in models_to_try:
            try:
                print(f"   Curating {domain.name} using {model_name}...")
                llm = ChatOpenRouter(
                    model_name=model_name,
                    openrouter_api_key=config.openrouter_api_key,
                    max_retries=1
                )
                response = llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=articles_text)
                ])

                content = response.content.strip()
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()

                indices = json.loads(content)
                if isinstance(indices, list):
                    valid_indices = []
                    for i in indices:
                        try:
                            idx = int(i)
                            if 0 <= idx < len(domain_articles) and idx not in valid_indices:
                                valid_indices.append(idx)
                        except:
                            pass

                    if len(valid_indices) > 0:
                        selected_indices = valid_indices[:domain.target_stories]
                        break
            except Exception as e:
                print(f"   [!] Curation error with {model_name}: {e}. Falling back...")

        # Fallback if all models fail or return bad JSON
        if not selected_indices:
            selected_indices = list(range(min(domain.target_stories, len(domain_articles))))

        # Pad if LLM returned fewer than requested
        if len(selected_indices) < domain.target_stories:
            for idx in range(len(domain_articles)):
                if idx not in selected_indices:
                    selected_indices.append(idx)
                if len(selected_indices) == domain.target_stories:
                    break

        for idx in selected_indices:
            curated_articles.append(domain_articles[idx])

    return {"curated_articles": curated_articles}

def fetch_sports_scores_node(state: GraphState) -> Dict[str, Any]:
    """
    Calls CricAPI and API-Football to fetch live/recent match scores.
    The result is stored in state['sports_scores'] and injected
    into the Sports section LLM prompt in analyze_and_narrate_node.
    """
    print("-> Fetching live sports scores...")
    config = state["config"]
    scores = fetch_all_sports_scores(
        cricapi_key=config.cricapi_key or "",
        football_api_key=config.football_api_key or "",
    )
    return {"sports_scores": scores}

def cross_dedup_node(state: GraphState) -> Dict[str, Any]:
    """
    Removes articles that are duplicates across different domains/sources.
    Uses URL exact-match first, then fuzzy title similarity (>=85%) as fallback.
    Keeps the first occurrence (by domain order in config).
    """
    print("-> Cross-category deduplication (removing cross-domain duplicates)...")
    curated_articles = state["curated_articles"]

    seen_urls: set = set()
    seen_titles: List[str] = []
    unique_articles: List[Dict[str, str]] = []
    removed = 0

    for article in curated_articles:
        url = article.get("link", "").strip()
        norm_title = _normalize_title(article.get("title", ""))

        # 1. Exact URL match
        if url and url in seen_urls:
            print(f"   [DEDUP] Removed exact URL duplicate: '{article['title']}' (domain: {article['domain']})")
            removed += 1
            continue

        # 2. Fuzzy title similarity
        is_dupe = False
        for seen_title in seen_titles:
            similarity = difflib.SequenceMatcher(None, norm_title, seen_title).ratio()
            if similarity >= 0.85:
                print(f"   [DEDUP] Removed near-duplicate title ({similarity:.0%}): '{article['title']}' (domain: {article['domain']})")
                removed += 1
                is_dupe = True
                break

        if not is_dupe:
            if url:
                seen_urls.add(url)
            if norm_title:
                seen_titles.append(norm_title)
            unique_articles.append(article)

    print(f"   Cross-dedup complete: {removed} duplicate(s) removed, {len(unique_articles)} unique article(s) kept.")
    return {"curated_articles": unique_articles}

def _build_domain_system_prompt(domain: str, emoji: str, sports_scores: str = "") -> str:
    """Returns a domain-specific system prompt for the narration LLM."""

    base = (
        f"You are the writer of 'The Morning Drop', a daily automated news brief designed for young Indians "
        f"(18-25, college students and early-career professionals) who doomscroll social media and skip traditional news. "
        f"You are covering the '{domain}' section today.\n\n"
        f"GLOBAL TONE RULES (apply to every section):\n"
        f"- Sound like a smart, funny, well-informed friend texting you — not a news anchor or a press release.\n"
        f"- Use extremely simple, conversational language. Zero jargon. If a term is unavoidable, explain it in brackets.\n"
        f"- Add light humor where it fits. Never trivialize serious events.\n"
        f"- Every story must feel shareable and relevant to their daily life.\n"
        f"- Never be generic. Make the reader feel like you're talking directly to THEM.\n\n"
    )

    if "Sports" in domain:
        # Build the live scores block to inject
        scores_block = ""
        if sports_scores.strip():
            scores_block = (
                f"\n\nLIVE SCORES DATA (use this as the authoritative source for scores, results, and standings):\n"
                f"{'='*50}\n"
                f"{sports_scores}\n"
                f"{'='*50}\n"
                f"Use the above data to produce the LIVE TOURNAMENT RADAR block. "
                f"Include exact scores, top performers, and any interesting moments mentioned.\n"
            )
        else:
            scores_block = (
                "\n\n(No live score data available from APIs today. "
                "Generate the TOURNAMENT RADAR block only if the articles below contain match result data. "
                "If no match data is found, skip the RADAR block entirely.)\n"
            )

        return base + scores_block + (
            f"SPORTS SECTION — SPECIAL RULES:\n"
            f"- Check the LIVE SCORES DATA above AND the articles below for ongoing tournaments:\n"
            f"  ICC World Cup (Cricket), FIFA World Cup, IPL, Champions League, or similar.\n"
            f"- If tournament data found — produce a HIGHLIGHTS BLOCK at the TOP of the section:\n"
            f"\n"
            f"    🏆 LIVE TOURNAMENT RADAR 🏆\n"
            f"    📍 [Tournament Name & Stage/Round]\n"
            f"    ⚡ Latest Result: [Team A] [Score] vs [Team B] [Score] — [Winner] won!\n"
            f"    ⭐ Top Performer: [Name] — [what they did, stats if available]\n"
            f"    🗣️ Talking Point: [One spicy/interesting moment — a record, controversy, comeback]\n"
            f"    📅 Next Up: [Next match or fixture if known]\n"
            f"\n"
            f"  Keep the RADAR block punchy (max 8 lines). Gen-Z casual — no stiff language.\n"
            f"  If MULTIPLE tournaments are active, produce one RADAR block per tournament.\n"
            f"- After all RADAR blocks, narrate individual sports stories in standard format.\n"
            f"- If NO tournament data anywhere, skip RADAR and go straight to stories.\n\n"
            f"STANDARD STORY FORMAT (for each story):\n"
            f"---\n[{emoji} {domain.upper()}]\n\n[Headline in plain casual English — max 10 words]\n\n"
            f"[5-6 lines: what happened, who's involved, why it's wild/relevant]\n"
            f"[1 line: Why it matters: ...]\n"
            f"Read more: [exact link]\n---\n\n"
            f"Do not output anything other than this format."
        )
    elif "Money" in domain or "Jobs" in domain:
        return base + (
            f"MONEY & JOBS SECTION — SPECIAL RULES:\n"
            f"- Focus on: Big business deals, company acquisitions/mergers, stock market moves, IPOs launching/listing, "
            f"startup funding rounds, layoffs/hiring booms, and economic policy impacts on common people.\n"
            f"- Make every financial concept feel REAL and personal:\n"
            f"  * 'The NSE IPO is like if your school suddenly went public on the stock market — and your principal is now a billionaire.'\n"
            f"  * Connect stock market moves to: what it means for your SIP, your job market, your city's economy.\n"
            f"- Always include a 'So what does this mean for your wallet?' angle.\n"
            f"- Make the reader think like a smart, money-aware young person — not scared of finance, but in control of it.\n\n"
            f"STANDARD STORY FORMAT (for each story):\n"
            f"---\n[{emoji} {domain.upper()}]\n\n[Headline in plain casual English — max 10 words]\n\n"
            f"[5-6 lines: what happened, numbers explained simply, real-world analogy]\n"
            f"[1 line: Why it matters to your wallet: ...]\n"
            f"Read more: [exact link]\n---\n\n"
            f"Do not output anything other than this format."
        )
    elif "Tech" in domain or "AI" in domain:
        return base + (
            f"TECH & AI SECTION — SPECIAL RULES:\n"
            f"- Focus on: Mind-blowing new products, AI/ML breakthroughs, startup acquisitions by tech giants, "
            f"innovative gadgets, software launches, and anything that makes you go 'wait, that's actually insane'.\n"
            f"- Make the reader feel like they're living in the future RIGHT NOW:\n"
            f"  * Connect every story to how it will change their daily life in 1-3 years.\n"
            f"  * Use vivid comparisons: 'This is basically a real-life Jarvis but cheaper.'\n"
            f"- Think futuristic. Think progressive. Make the reader excited about innovation — not scared of it.\n"
            f"- If it's an acquisition: explain WHY the big company bought this startup and what they plan to do with it.\n"
            f"- If it's a product launch: tell them whether they'll actually use/want this thing.\n\n"
            f"STANDARD STORY FORMAT (for each story):\n"
            f"---\n[{emoji} {domain.upper()}]\n\n[Headline in plain casual English — max 10 words]\n\n"
            f"[5-6 lines: what it is, why it's revolutionary, who it affects, future angle]\n"
            f"[1 line: Why it matters to your future: ...]\n"
            f"Read more: [exact link]\n---\n\n"
            f"Do not output anything other than this format."
        )
    else:
        # Default prompt for India, TamilNadu, World, Entertainment, WTF
        return base + (
            f"STANDARD STORY FORMAT (follow strictly for each story):\n"
            f"---\n[{emoji} {domain.upper()}]\n\n[Headline in plain casual English — max 10 words]\n\n"
            f"[5-6 lines explaining what happened in simple language with context]\n"
            f"[1 line: Why it matters: ...]\n"
            f"Read more: [exact link]\n---\n\n"
            f"Do not output anything other than this format."
        )

def analyze_and_narrate_node(state: GraphState) -> Dict[str, Any]:
    print("-> Analyzing and narrating stories using LLM...")
    curated_articles = state.get("curated_articles", [])
    config = state["config"]
    domain_briefings = {}

    models_to_try = [
        "deepseek/deepseek-chat",
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3-8b-instruct:free",
        "meta-llama/llama-3-8b-instruct",
        "openai/gpt-oss-120b:free",
        "openai/gpt-oss-120b",
        "google/gemma-4-31b-it:free",
        "google/gemma-4-31b-it",
        "nvidia/llama-3.1-nemotron-70b-instruct",
        "google/gemini-flash-1.5",
        "google/gemini-pro-1.5",
        "mistralai/mistral-7b-instruct:free"
    ]

    # Group articles by domain
    articles_by_domain = {}
    for article in curated_articles:
        domain = article["domain"]
        if domain not in articles_by_domain:
            articles_by_domain[domain] = {"emoji": article["emoji"], "articles": []}
        articles_by_domain[domain]["articles"].append(article)

    for domain, data in articles_by_domain.items():
        if not data["articles"]:
            continue

        # Pass live scores into the Sports prompt
        sports_scores = state.get("sports_scores", "") if "Sports" in domain else ""
        system_prompt = _build_domain_system_prompt(domain, data["emoji"], sports_scores)
        articles_text = "\n\n".join([
            f"Title: {a['title']}\nLink: {a['link']}\nSummary: {a['summary']}"
            for a in data["articles"]
        ])

        response_content = None
        for model_name in models_to_try:
            try:
                print(f"   Trying model {model_name} for {domain}...")
                llm = ChatOpenRouter(
                    model_name=model_name,
                    openrouter_api_key=config.openrouter_api_key,
                    max_retries=1
                )
                response = llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Here are today's articles for {domain}:\n{articles_text}")
                ])
                response_content = response.content
                break  # Success, break out of fallback loop
            except Exception as e:
                print(f"   [!] Error with {model_name}: {e}. Falling back...")

        if response_content:
            domain_briefings[domain] = response_content
        else:
            domain_briefings[domain] = (
                f"[{data['emoji']} {domain.upper()}]\n\n"
                f"*Failed to generate briefing due to API limits.*"
            )

    return {"domain_briefings": domain_briefings}

def format_briefing_node(state: GraphState) -> Dict[str, Any]:
    print("-> Formatting final briefing...")
    domain_briefings = state["domain_briefings"]
    config = state["config"]

    if not domain_briefings:
        return {"final_briefing": "No new articles found today."}

    final_briefing = ""
    # Ensure strict domain ordering from config
    for domain in config.app_config.domains:
        if domain.name in domain_briefings:
            final_briefing += f"{domain_briefings[domain.name]}\n\n"

    final_briefing += "That's your world for today. See you tomorrow. 🌅\n"

    return {"final_briefing": final_briefing}

def build_workflow() -> StateGraph:
    workflow = StateGraph(GraphState)

    workflow.add_node("fetch", fetch_rss_node)
    workflow.add_node("deduplicate", deduplicate_node)
    workflow.add_node("curation", curation_node)
    workflow.add_node("cross_dedup", cross_dedup_node)
    workflow.add_node("sports_scores", fetch_sports_scores_node)
    workflow.add_node("analyze", analyze_and_narrate_node)
    workflow.add_node("format", format_briefing_node)

    workflow.set_entry_point("fetch")
    workflow.add_edge("fetch", "deduplicate")
    workflow.add_edge("deduplicate", "curation")
    workflow.add_edge("curation", "cross_dedup")
    # Human-in-the-loop happens between cross_dedup and sports_scores via main.py
    workflow.add_edge("cross_dedup", "sports_scores")
    workflow.add_edge("sports_scores", "analyze")
    workflow.add_edge("analyze", "format")
    workflow.add_edge("format", END)

    return workflow.compile()
