# 🌅 The Morning Drop

> **Elevating daily news from a chore to a conversation.** An AI-driven, agentic newsletter curation engine designed specifically for Gen-Z & young professionals in India who skip traditional news but love social media doomscrolling.

---

## 🎯 The Business Case

| The Problem 😴 | The Vibe-Check Solution ⚡ |
| :--- | :--- |
| **Information Overload**: 100+ RSS feeds, newsletters, and articles are published daily. Nobody has time to read them. | **Curation Layer**: An agentic pipeline automatically parses, filters, and selects only the absolute best stories. |
| **Stiff & Boring Tone**: Traditional news is dry, full of corporate jargon, and distant from youth culture. | **Persona-Driven Writing**: Converts complex topics into conversational, witty, and meme-friendly summaries. |
| **Duplicate Fatigue**: The same story is repeated across multiple domains (e.g. tech/finance crossover). | **Intelligent Cross-Dedup**: An 85%+ semantic comparison filter ensures a clean, repeat-free reading experience. |
| **Static News**: Sports sections are written hours before publication, missing late-night live results. | **Live scoreboard Integrations**: Cricket and football live API data injected dynamically into LLM prompts. |

---

## 🚀 MVP (Minimum Viable Product) Features

```
┌────────────────────────────────────────────────────────────────────────┐
│                              CORE ENGINES                              │
├───────────────────┬───────────────────┬────────────────────────────────┤
│ 📰 Curation Engine│ ⚡ Personality     │ 🛠️ Enterprise Operations        │
│ • RSS Parser      │ • Multi-persona   │ • SQLite memory database       │
│ • LLM selector    │ • Gen-Z Indian    │ • Scheduled runner (7 AM)      │
│ • Fuzzy dedup     │   localization    │ • Automated HTML styling       │
│ • Sports API      │ • Smart analogies │ • Human-In-The-Loop review     │
└───────────────────┴───────────────────┴────────────────────────────────┘
```

---

## 🧠 Agentic Workflow (LangGraph)

Our curation pipeline is powered by a structured state machine graph using **LangGraph**. Below is the diagrammatic representation of the workflow showing how raw data flows to final email delivery:

```mermaid
graph TD
    A["📡 RSS Feeds<br/>Parse multiple sources"]
    B["⬇️ Fetch Node<br/>Gathers recent stories"]
    C["🗑️ History Filter<br/>Removes already-sent URLs"]
    D["🧠 LLM Selector Node<br/>Multi-model curation"]
    E["🔁 Cross-Dedup Node<br/>Fuzzy title similarity"]
    F{"🔀 Interactive Mode?"}
    G["✋ Draft Approval<br/>Human reviews draft.json"]
    H["🏏 Sports Node<br/>Inject CricAPI & Football data"]
    I["✍️ Narration Node<br/>Category-specific LLM rewrite"]
    J["🎨 Formatting Node<br/>Stitches final layout"]
    K["📧 SMTP Delivery<br/>Premium HTML email sent"]

    A --> B --> C --> D --> E --> F
    F -- "Phase 1: Manual" --> G
    G -- "Phase 2: approve" --> H
    F -- "Auto Mode: auto" --> H
    H --> I --> J --> K

    classDef fetchStyle fill:#F3E5F5,stroke:#8E24AA,color:#4A148C,stroke-width:2px;
    classDef curateStyle fill:#E0F2F1,stroke:#00897B,color:#004D40,stroke-width:2px;
    classDef humanStyle fill:#FFEBEE,stroke:#E53935,color:#B71C1C,stroke-width:2px;
    classDef deliverStyle fill:#E8F5E9,stroke:#43A047,color:#1B5E20,stroke-width:2px;

    class A,B,C fetchStyle;
    class D,E curateStyle;
    class F,G humanStyle;
    class H,I,J,K deliverStyle;
```

### 🤖 Dual LLM Engines & Fallback Architecture

To ensure high curation quality, 100% uptime, and cost-free execution, the pipeline utilizes a dual-engine LLM orchestration system that falls back automatically:

#### 1. Cloud Engine (OpenRouter)
Queries models in this preferred order:
* **DeepSeek-V3** (`deepseek/deepseek-chat`) — Primary high-performance curator
* **Llama 3.3 70B & Llama 3 8B** (`meta-llama/llama-3.3-70b-instruct:free`, `meta-llama/llama-3-8b-instruct:free`) — Extremely conversational and robust
* **GPT-OSS-120B** (`openai/gpt-oss-120b:free`) — High-reasoning open-weights model
* **Google Gemma 4 31B** (`google/gemma-4-31b-it:free`) — State-of-the-art reasoning model
* **Fallback Cluster** — `gemini-flash-1.5`, `gemini-pro-1.5`, and `mistral-7b-instruct:free`

#### 2. Local Backup Engine (Ollama)
If OpenRouter hits rate limits (429 errors), lacks credit, or if `OPENROUTER_API_KEY` is not provided in `.env`, the system automatically shifts execution to local Ollama models:
* **Qwen 2.5 3B** (`ollama/qwen2.5:3b`) — Lightweight, extremely fast local fallback
* **Llama 3.1 & Llama 3** (`ollama/llama3.1`, `ollama/llama3`) — High-quality local narration and structure
* **Gemma 2** (`ollama/gemma2`) — Local backup model

---

## 🎭 The Vibe Engine (Category Personas)

The newsletter is split into distinct categories, each styled with unique accent colors and targeted LLM personas:

```
  🇮🇳 India & Tamil Nadu (Terracotta & Jade)
  └─ Conversational, friendly context on domestic events.
  
  🌍 World in 60 Seconds (Dusk Blue)
  └─ Global headlines, boiled down to the absolute essentials.
  
  💸 Money & Jobs (Golden Sand)
  └─ Layman stock & company insights. Translates "SIPs" and "IPOs" into real wallet impacts.
  
  💻 Tech & AI (Lavender)
  └─ Futurist focus. Explains how tech breakthroughs affect the reader's life in 1-3 years.
  
  🏅 Sports (Coral Blush)
  └─ Live Scorecards + "Tournament Radar" (Cricket & Football) tracking key plays & drama.
  
  🍿 Entertainment & WTF (Deep Teal & Aqua)
  └─ Pop-culture catchups and bizarre, internet-breaking events.
```

---

## 📈 Scalability & Monetization Potential

1. **Hyper-Personalized Feeds**: Let users pick their own domain configurations inside `config.yaml`.
2. **Sponsor Slots**: Dynamically inject custom visual sponsor blocks between categories using LangGraph nodes.
3. **Analytics Integration**: Track email open-rates and interaction to feed back into the LLM curator.

---

## 🛠️ Quick Launch Guide

### 1. Project Environment Setup
Set up your Python virtual environment and install dependencies:
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies (includes langchain-ollama)
pip install -r requirements.txt
```

### 2. Configure Environment Secrets
Create a `.env` file in the root directory:
```env
# Optional: OpenRouter API Key (Ollama will be used directly if left empty)
OPENROUTER_API_KEY=your_key_here

# Required: Gmail Credentials for SMTP delivery
GMAIL_ADDRESS=your_gmail@gmail.com
GMAIL_APP_PASSWORD=your_app_specific_password
```

### 3. Local Ollama Pre-requisites (Optional)
If you plan to run offline or use Ollama for free fallback, make sure Ollama is running and download your backup model:
```bash
# Pull the qwen or llama models
ollama pull qwen2.5:3b
ollama pull llama3.1
```

### 4. Running the Curation Pipeline
* **Manual Mode (Human-in-the-Loop review)**:
  ```bash
  # Phase 1: Fetch and save curated stories to draft.json
  python main.py --draft

  # [Review and edit draft.json to remove unwanted stories]

  # Phase 2: Generate narration and deliver the email
  python main.py --approve
  ```
* **Auto Mode**:
  ```bash
  python main.py --auto
  ```

### 5. Register Automation (7:00 AM Daily)
To run the automated script every morning at 7 AM:
Open **PowerShell as Administrator** and execute:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; & ".\setup_scheduler.ps1"
```
