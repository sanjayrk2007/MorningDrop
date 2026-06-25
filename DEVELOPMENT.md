# 🛠️ Developer & Learning Guide

This guide breaks down the technical architecture, file responsibilities, and key design patterns of **The Morning Drop** to show how LangChain, LangGraph, and Python utilities are combined to build a production-ready agentic curation workflow.

---

## 🧬 Tech Stack & Key Concepts

* **LangGraph**: Orchestrates the multi-step news processing pipeline. It models our workflow as a **StateGraph** (a state machine) where every node updates a shared dictionary state.
* **LangChain Core & langchain-openrouter**: Provides a clean interface to query multiple LLM models (DeepSeek, Llama, Gemini, Mistral) through OpenRouter.
* **Pydantic**: Used in `config.py` to validate environmental settings and feed schemas at startup.
* **SQLite (`news.db`)**: Acts as the local short-term memory to keep track of processed URLs and prevent duplicate deliveries.

---

## 📂 File-by-File Breakdown

```
morning-bot/
├── config.yaml          # Defines user settings: email address, feeds, story targets
├── config.py            # Loads, parses, and validates config.yaml + .env secrets
├── db.py                # SQLite wrapper that tracks previously sent article URLs
├── sports_api.py        # Integrates CricAPI and API-Football to get live scoreboard data
├── email_sender.py      # Generates a responsive HTML email design and sends via SMTP
├── graph.py             # Defines the LangGraph workflow, state, nodes, and LLM prompts
└── main.py              # CLI entry point orchestrating Phase 1 (Draft), Phase 2 (Approve), and Auto
```

---

## 🧱 Deep Dive: LangGraph Architecture

### 1. The Shared State (`GraphState`)
In `graph.py`, the `GraphState` is a `TypedDict` that flows through every node in the graph:
```python
class GraphState(TypedDict):
    config: Any                    # Settings loaded from config.py
    raw_articles: List[Dict]       # Parsed RSS feed list
    filtered_articles: List[Dict]  # Articles after history DB check
    curated_articles: List[Dict]   # Articles after LLM/fuzzy curation
    domain_briefings: Dict[str, str]# Written content mapped to each domain
    final_briefing: str            # Unified newsletter string
    sports_scores: str             # Real-time scores injected into prompt
```

### 2. Node Operations

| Node Name | Function | Purpose |
| :--- | :--- | :--- |
| `fetch` | `fetch_rss_node` | Crawls up to 15 recent articles per feed. |
| `deduplicate` | `deduplicate_node` | Filters out URLs already marked as `processed` in `news.db`. |
| `curation` | `curation_node` | Asks an LLM to choose the top $N$ most interesting articles per category. |
| `cross_dedup` | `cross_dedup_node` | Uses fuzzy text comparison (85% similarity threshold) to remove near-duplicate titles across categories. |
| `sports_scores` | `fetch_sports_scores_node` | Pulls live scores from external APIs to inject into LLM prompts. |
| `analyze` | `analyze_and_narrate_node` | Triggers LLM rewriting using domain-specific tone guidelines. |
| `format` | `format_briefing_node` | Combines all written sections in the order defined by the config. |

---

## 🔄 LLM Fallback & Curation Strategy

To maximize uptime and cost-efficiency, the curation and narration nodes use a **fallback model list** in `graph.py`:

```python
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
```

If the primary LLM provider fails (due to rate limits, API key balance, or network issues), the code catches the exception, prints a fallback message, and automatically retries with the next model in the list.

---

## 💾 News Memory (Deduplication)

We prevent emailing identical stories using two levels of deduplication:

1. **Exact URL Check (`db.py`)**: Before curation, article URLs are checked against `news.db` using SQLite:
   ```sql
   SELECT 1 FROM processed_stories WHERE url = ?
   ```
2. **Semantic Crossover Check (`graph.py`)**: After curation, we perform cross-category deduplication. If a technology article and a finance article cover the same announcement, the titles are compared fuzzy:
   ```python
   similarity = difflib.SequenceMatcher(None, norm_title_1, norm_title_2).ratio()
   if similarity >= 0.85:
       # Discard near-duplicate
   ```

---

## ⚡ Running & Automating

1. **Local Setup**: Create a `.env` file containing your `OPENROUTER_API_KEY`, `GMAIL_ADDRESS`, and `GMAIL_APP_PASSWORD`.
2. **Execute Draft / Approval (HITL)**:
   ```bash
   python main.py --draft
   # [Edit draft.json if needed]
   python main.py --approve
   ```
3. **Run Automatically**:
   ```bash
   python main.py --auto
   ```
   *In `--auto` mode, the bot runs all nodes in succession, updates the SQLite memory database to record the sent links, and dispatches the HTML email.*
