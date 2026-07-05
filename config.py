"""
config.py — Settings Loader
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT THIS FILE DOES:
    Loads ALL settings the bot needs from two places:
      1. `.env` file     → secret keys (API keys, email credentials)
      2. `config.yaml`   → non-secret settings (which feeds to read, how many
                           stories per category, who to email, etc.)

    It validates the config using Pydantic, which means if a required key is
    missing, you get a clear error message — not a mysterious crash later.

WHY SEPARATE SECRETS FROM CONFIG?
    Your `.env` file is in `.gitignore` — it's never accidentally uploaded to
    GitHub. `config.yaml` is safe to share publicly.

DATA FLOW:
    .env file ──────────────────────────────────────────────┐
                                                            ▼
    config.yaml ──→ AppConfig ──→ Settings ──→ rest of the bot
                    (yaml data)   (complete config object)
"""

import os       # For reading environment variables (os.getenv)
import yaml     # For parsing the config.yaml file (PyYAML library)
from pydantic import BaseModel      # For data validation with clean error messages
from dotenv import load_dotenv      # For loading .env file into os.environ
from typing import List, Optional   # Type hints to document what data looks like

# Load the .env file into the environment so os.getenv() can find our secrets.
# This must happen BEFORE any os.getenv() calls below!
load_dotenv()


# ─── DATA MODELS ──────────────────────────────────────────────────────────────
# These Pydantic classes describe the "shape" of our config data.
# Pydantic automatically validates types and gives helpful errors if data is wrong.

class DomainConfig(BaseModel):
    """
    Represents one news category/domain in config.yaml.

    Example YAML that maps to this class:
        - name: "Tech & AI"
          emoji: "💻"
          target_stories: 3
          feeds:
            - "https://techcrunch.com/feed/"
            - "https://www.theverge.com/rss/index.xml"
    """
    name: str              # Category name, e.g. "India", "Sports", "Tech & AI"
    emoji: str             # The emoji shown in the email, e.g. "🇮🇳", "🏅"
    target_stories: int    # How many stories to include from this category per email
    feeds: List[str]       # List of RSS feed URLs to pull news from


class AppConfig(BaseModel):
    """
    The top-level structure of config.yaml.

    This holds WHO gets the email, and the list of all news categories.
    """
    recipient_email: str          # Email address to send the morning briefing to
    domains: List[DomainConfig]   # All the news categories (India, Sports, Tech, etc.)


class Settings(BaseModel):
    """
    The complete settings object that the rest of the bot uses.

    This combines:
    - API keys from .env  (openrouter, gmail, sports APIs)
    - App config from config.yaml  (recipient email, domains/feeds)

    Optional fields (Optional[str]) default to None if not set.
    The sports API keys are optional — the bot still works without them,
    it just won't have live scores.
    """
    openrouter_api_key: Optional[str] = None       # Key for OpenRouter (accesses multiple LLMs)
    gmail_address: str            # Your Gmail address (the "From" address)
    gmail_app_password: str       # Gmail App Password (NOT your regular password!)
    app_config: AppConfig         # The full app configuration from config.yaml
    cricapi_key: Optional[str] = None      # Optional: Cricket live scores
    football_api_key: Optional[str] = None # Optional: Football live scores
    
    # Custom validator to handle cases when we don't have OpenRouter or Ollama (we'll check later)
    # but keeping it simple for Pydantic.


# ─── LOADER FUNCTION ──────────────────────────────────────────────────────────

def load_config(config_path: str = "config.yaml") -> Settings:
    """
    Main function: reads .env + config.yaml, validates everything, returns Settings.

    Called once at startup in main.py:
        config = load_config()

    Args:
        config_path: Path to the YAML file. Default is "config.yaml"
                     in the current directory.

    Returns:
        A fully validated Settings object.

    Raises:
        ValueError: If a required environment variable is missing.
        FileNotFoundError: If config.yaml doesn't exist.

    Step-by-step walkthrough:
        1. Read secret keys from environment (loaded from .env by load_dotenv() above)
        2. Validate that required keys exist
        3. Read and parse config.yaml
        4. Build and return a Settings object that bundles everything together
    """

    # ── Step 1: Read secrets from environment variables ──────────────────────
    # os.getenv() returns None if the variable isn't set (won't crash).
    openrouter_key   = os.getenv("OPENROUTER_API_KEY")
    gmail_address    = os.getenv("GMAIL_ADDRESS")
    gmail_app_pwd    = os.getenv("GMAIL_APP_PASSWORD")
    cricapi_key      = os.getenv("CRICAPI_KEY")       # Optional — can be None
    football_api_key = os.getenv("FOOTBALL_API_KEY")  # Optional — can be None

    # ── Step 2: Validate required keys are present ───────────────────────────
    # If a required key is missing, raise an error with a clear message.
    # `not openrouter_key` is True when the value is None or an empty string "".
    if not gmail_address or not gmail_app_pwd:
        raise ValueError("GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set in environment or .env file.")

    # ── Step 3: Read and parse config.yaml ───────────────────────────────────
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file {config_path} not found.")

    # `with open(...) as f` safely opens and automatically closes the file.
    # encoding="utf-8" ensures emoji characters in the YAML file are read correctly.
    with open(config_path, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)  # Parses YAML into a Python dict
    
    # `**yaml_data` "unpacks" the dict as keyword arguments to AppConfig().
    # Pydantic validates the data — e.g., if target_stories is missing or not an int,
    # it raises a clear validation error here.
    app_config = AppConfig(**yaml_data)

    # ── Step 4: Bundle everything into a Settings object and return ───────────
    return Settings(
        openrouter_api_key=openrouter_key,
        gmail_address=gmail_address,
        gmail_app_password=gmail_app_pwd,
        app_config=app_config,
        cricapi_key=cricapi_key,
        football_api_key=football_api_key,
    )
