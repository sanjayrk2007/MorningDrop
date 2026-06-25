"""
sports_api.py — Live Sports Score Fetcher
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT THIS FILE DOES:
    Fetches real, live match scores from two sports APIs:
      1. CricAPI      → Cricket: IPL, ICC World Cup, T20Is, ODIs, Tests
      2. API-Football → Football: FIFA World Cup, Champions League, Premier League, etc.

    The results are formatted as plain text (not JSON) so they can be
    directly injected into an LLM prompt like:
        "Here are today's live scores — use these to write the Sports section."

    Both APIs are OPTIONAL. If a key is missing or the API fails, the bot
    gracefully skips that sport and continues — no crash, no fuss.

THE OUTPUT FORMAT:
    The functions return strings like this:

    🏏 CRICKET LIVE SCORES & RECENT RESULTS
    ========================================
    📍 India vs Australia — 3rd Test Match
       🏟️  Sydney Cricket Ground
       India 1st innings: 256/10 (87.4 ov)
       Australia 1st innings: 312/8 (95.0 ov)
       📊 Result/Status: Australia leads by 56 runs

    ⚽ FOOTBALL LIVE SCORES & RECENT RESULTS
    ========================================
    ⚽ [UEFA Champions League — Final]
       Real Madrid  1 - 0  Manchester City
       Status: Match Finished

API DOCS:
    CricAPI:      https://cricapi.com/docs
    API-Football: https://www.api-football.com/documentation-v3
"""

import requests                                    # For making HTTP requests to the APIs
from datetime import datetime, timedelta           # For calculating yesterday's date
from typing import Optional                        # Type hint: value that can be None


# ─── API BASE URLS ────────────────────────────────────────────────────────────
# These are the root endpoints — we append paths like /currentMatches to them.
CRICAPI_BASE      = "https://api.cricapi.com/v1"
FOOTBALL_API_BASE = "https://v3.football.api-sports.io"


# ─── FOOTBALL LEAGUE FILTER ───────────────────────────────────────────────────
# API-Football has hundreds of leagues worldwide. We only care about major ones.
# This dict maps league ID (used by the API) → human-readable name.
# Lower IDs = higher priority (FIFA World Cup = 1 is the most important).
MAJOR_FOOTBALL_LEAGUES = {
    1:   "FIFA World Cup",
    2:   "UEFA Champions League",
    3:   "UEFA Europa League",
    4:   "UEFA Euro Championship",
    9:   "Copa America",
    6:   "Africa Cup of Nations",
    39:  "Premier League",       # English top division
    140: "La Liga",              # Spanish top division
    135: "Serie A",              # Italian top division
    78:  "Bundesliga",           # German top division
    61:  "Ligue 1",              # French top division
}


# ─── CRICKET PRIORITY KEYWORDS ────────────────────────────────────────────────
# CricAPI may return dozens of matches (state leagues, domestic cups, etc.)
# We score each match based on how many of these keywords appear in its name/series.
# Matches with more keywords get prioritized (they're more important/interesting).
CRICKET_PRIORITY_KEYWORDS = [
    "world cup", "ipl", "icc", "t20i", "odi", "test match",
    "champions trophy", "asia cup", "india", "england", "australia",
    "south africa", "pakistan", "new zealand", "west indies"
]


# ─── CRICKET SCORE FETCHER ────────────────────────────────────────────────────

def fetch_cricket_scores(api_key: str) -> str:
    """
    Fetches current/recent cricket matches from CricAPI.

    Args:
        api_key: Your CricAPI key from cricapi.com

    Returns:
        A formatted multi-line string of match scores, OR
        An empty string "" if the API is unavailable or key is missing.

    LEARNER NOTE — How the prioritization works:
        1. Get all current matches from the API (could be 20+ matches)
        2. Score each match: count how many priority keywords appear in its name
        3. Sort by that score (highest first = most important matches first)
        4. Take only the top 5 matches
    """
    # Guard clause: exit early if no API key is provided
    # api_key.startswith("your_") catches placeholder values like "your_api_key_here"
    if not api_key or api_key.startswith("your_"):
        return ""

    try:
        # Make the HTTP GET request to CricAPI
        # timeout=10 means: if no response in 10 seconds, give up (don't hang forever)
        resp = requests.get(
            f"{CRICAPI_BASE}/currentMatches",
            params={"apikey": api_key, "offset": 0},  # Query string: ?apikey=...&offset=0
            timeout=10
        )
        resp.raise_for_status()  # Raises an exception if HTTP status is 4xx or 5xx

        data = resp.json()  # Parse the JSON response into a Python dict

        # CricAPI uses a "status" field to indicate if the request succeeded
        if data.get("status") != "success":
            print(f"   [CricAPI] Unexpected response status: {data.get('status')}")
            return ""

        matches = data.get("data", [])  # The list of matches (empty list if no matches)
        if not matches:
            return ""

        # ── Priority Sorting ──────────────────────────────────────────────────
        # This is a "key function" used by .sort() to score each match.
        # Python's sort is stable — matches with equal scores keep their original order.
        def priority_score(match):
            """Returns a score (0–15) based on how many keywords match this match."""
            name_lower   = match.get("name", "").lower()    # e.g. "india vs australia"
            series_lower = match.get("series", "").lower()  # e.g. "icc cricket world cup 2025"
            combined     = name_lower + " " + series_lower
            # Count how many keywords from our list appear in the match info
            return sum(1 for keyword in CRICKET_PRIORITY_KEYWORDS if keyword in combined)

        matches.sort(key=priority_score, reverse=True)  # Highest score first
        top_matches = matches[:5]  # Take only the top 5 most important matches

        # ── Format Output ─────────────────────────────────────────────────────
        # We build the output as a list of strings, then join them at the end.
        # This is more efficient than repeatedly concatenating strings with +=.
        lines = ["🏏 CRICKET LIVE SCORES & RECENT RESULTS"]
        lines.append("=" * 40)

        for match in top_matches:
            name     = match.get("name", "Unknown Match")
            status   = match.get("status", "")    # e.g. "Match in progress" or "India won"
            venue    = match.get("venue", "")     # Stadium name
            scores   = match.get("score", [])     # List of innings scores
            date_str = match.get("dateTimeGMT", "")

            lines.append(f"\n📍 {name}")
            if venue:
                lines.append(f"   🏟️  {venue}")

            # Scores is a list because there can be multiple innings
            # e.g. [{inning: "India 1st innings", r: 256, w: 10, o: 87.4}, ...]
            if scores:
                for innings_score in scores:
                    innings = innings_score.get("inning", "")
                    runs    = innings_score.get("r", "")  # Runs scored
                    wickets = innings_score.get("w", "")  # Wickets fallen
                    overs   = innings_score.get("o", "")  # Overs bowled
                    if runs != "":  # Only show if there are actual runs
                        lines.append(f"   {innings}: {runs}/{wickets} ({overs} ov)")
            else:
                lines.append("   (Scores not yet available)")

            if status:
                lines.append(f"   📊 Result/Status: {status}")

        return "\n".join(lines)  # Combine all lines into one big string

    except requests.exceptions.RequestException as e:
        # Network errors (no internet, API down, timeout)
        print(f"   [CricAPI] Network error: {e}")
        return ""
    except Exception as e:
        # Any other unexpected error (bad JSON, etc.)
        print(f"   [CricAPI] Unexpected error: {e}")
        return ""


# ─── FOOTBALL SCORE FETCHER ───────────────────────────────────────────────────

def fetch_football_scores(api_key: str) -> str:
    """
    Fetches today's and yesterday's football fixtures from API-Football.
    Filters to only show major tournaments from MAJOR_FOOTBALL_LEAGUES.

    Args:
        api_key: Your API-Football key from dashboard.api-football.com

    Returns:
        A formatted multi-line string of match results, OR
        An empty string "" if the API is unavailable or key is missing.

    WHY YESTERDAY TOO?
        A Champions League final might have ended at 11pm last night.
        If the bot runs at 7am, "today" has no matches yet.
        Fetching yesterday ensures we capture last night's big results.
    """
    if not api_key or api_key.startswith("your_"):
        return ""

    # API-Football requires the key in an HTTP header (not as a query parameter)
    headers = {"x-apisports-key": api_key}

    # Calculate date strings in YYYY-MM-DD format (required by the API)
    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    all_fixtures = []  # We'll collect fixtures from both days here

    try:
        # Fetch fixtures for BOTH today and yesterday in one loop
        for date in [today, yesterday]:
            resp = requests.get(
                f"{FOOTBALL_API_BASE}/fixtures",
                headers=headers,
                params={"date": date},  # Query string: ?date=2025-06-19
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()

            # Filter: only keep fixtures from major leagues we care about
            for fixture in data.get("response", []):
                league_id = fixture.get("league", {}).get("id", 0)
                if league_id in MAJOR_FOOTBALL_LEAGUES:  # Is this a major league?
                    all_fixtures.append(fixture)

        if not all_fixtures:
            return ""  # No major matches found for today or yesterday

        # ── Priority Sorting ──────────────────────────────────────────────────
        # Sort so that:
        #   1. Finished matches come first (we know the result)
        #   2. Among matches with same finish status, lower league ID = higher priority
        #      (FIFA World Cup has id=1, Premier League has id=39)
        def fixture_priority(fixture):
            """Returns a tuple used for sorting. Python compares tuples element by element."""
            league_id    = fixture.get("league", {}).get("id", 9999)
            status_short = fixture.get("fixture", {}).get("status", {}).get("short", "")
            # FT=Full Time, AET=After Extra Time, PEN=Penalty Shootout
            is_finished  = 1 if status_short in ("FT", "AET", "PEN") else 0
            return (is_finished, -league_id)  # -league_id: lower ID = larger negative = sorts first

        all_fixtures.sort(key=fixture_priority, reverse=True)
        top_fixtures = all_fixtures[:6]  # Show at most 6 matches

        # ── Format Output ─────────────────────────────────────────────────────
        lines = ["⚽ FOOTBALL LIVE SCORES & RECENT RESULTS"]
        lines.append("=" * 40)

        for fixture in top_fixtures:
            # Navigate the nested dict structure of the API response
            league_name  = fixture.get("league", {}).get("name", "")
            league_round = fixture.get("league", {}).get("round", "")
            home         = fixture.get("teams", {}).get("home", {}).get("name", "?")
            away         = fixture.get("teams", {}).get("away", {}).get("name", "?")
            goals_home   = fixture.get("goals", {}).get("home")   # Can be None if not started
            goals_away   = fixture.get("goals", {}).get("away")
            status_long  = fixture.get("fixture", {}).get("status", {}).get("long", "")

            # Show "1 - 0" if goals exist, or "vs" if match hasn't started
            score_str = f"{goals_home} - {goals_away}" if goals_home is not None else "vs"

            lines.append(f"\n⚽ [{league_name} — {league_round}]")
            lines.append(f"   {home}  {score_str}  {away}")
            lines.append(f"   Status: {status_long}")

        return "\n".join(lines)

    except requests.exceptions.RequestException as e:
        print(f"   [API-Football] Network error: {e}")
        return ""
    except Exception as e:
        print(f"   [API-Football] Unexpected error: {e}")
        return ""


# ─── MASTER FUNCTION ──────────────────────────────────────────────────────────

def fetch_all_sports_scores(cricapi_key: str, football_api_key: str) -> str:
    """
    Fetches both cricket AND football scores and returns them combined.

    This is the only function called from graph.py — it's the "public API"
    of this module. The two helper functions above are called internally.

    Args:
        cricapi_key:      CricAPI key (can be empty string "" to skip cricket)
        football_api_key: API-Football key (can be empty string "" to skip football)

    Returns:
        A combined string with both sports sections, separated by a blank line.
        Returns "" if both APIs are unavailable.

    Example output when both APIs work:
        🏏 CRICKET LIVE SCORES & RECENT RESULTS
        ========================================
        ...cricket data...

        ⚽ FOOTBALL LIVE SCORES & RECENT RESULTS
        ========================================
        ...football data...
    """
    print("   -> Fetching live cricket scores (CricAPI)...")
    cricket  = fetch_cricket_scores(cricapi_key)

    print("   -> Fetching live football scores (API-Football)...")
    football = fetch_football_scores(football_api_key)

    # Build the combined output, only including sections that have data
    parts = []
    if cricket:
        parts.append(cricket)
    if football:
        parts.append(football)

    if not parts:
        print("   [Sports API] No live score data available (APIs skipped or no data).")

    return "\n\n".join(parts)  # Separate cricket and football with a blank line
