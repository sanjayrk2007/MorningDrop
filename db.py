"""
db.py — News Memory Database
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT THIS FILE DOES:
    Gives the bot a "memory" — it remembers every article it has already
    sent, so it never sends the same story twice in future runs.

HOW IT WORKS:
    Uses SQLite (a simple file-based database that lives right here in
    the project folder as `news.db`). No external database server needed!

    The database has ONE table called `processed_stories`:
    ┌──────────────────┬────────────┬────────────────────────────┐
    │ url (primary key)│ domain     │ processed_date             │
    ├──────────────────┼────────────┼────────────────────────────┤
    │ https://bbc...   │ India      │ 2025-06-19 07:00:00        │
    │ https://nyt...   │ Tech & AI  │ 2025-06-19 07:00:00        │
    └──────────────────┴────────────┴────────────────────────────┘

    Each time an article is sent in an email, its URL is saved here.
    Next morning, before fetching new articles, we check this table —
    if an article's URL is already in the table, we skip it.

    Old records (>30 days) are deleted automatically to keep the DB tidy.
"""

import sqlite3       # Python's built-in library for working with SQLite databases
import datetime      # For calculating "how old is this record?"


class NewsDatabase:
    """
    A simple helper class that wraps all database operations.

    Think of this like a "black box" — you tell it:
      - "Did we already send this article?" → is_processed()
      - "We just sent this article, remember it." → mark_processed()
      - "Delete anything older than 30 days." → prune_old_records()
    """

    def __init__(self, db_path: str = "news.db"):
        """
        Called automatically when you create a NewsDatabase object.

        Args:
            db_path: Where to store the SQLite database file.
                     Default is "news.db" in the current directory.

        Example:
            db = NewsDatabase()  # creates/opens news.db
        """
        self.db_path = db_path
        self._init_db()  # Make sure the table exists when we start

    def _init_db(self):
        """
        Creates the database table if it doesn't already exist.

        The `IF NOT EXISTS` clause means this is safe to call every time
        the bot starts — it won't crash or erase data if the table already
        exists from a previous run.

        (The leading underscore _ is a Python convention meaning "this method
        is internal — only used inside this class, not by outside code.")
        """
        # `with sqlite3.connect(...) as conn` is a "context manager" —
        # it automatically closes the database connection when done,
        # even if an error occurs. Always use `with` for database connections!
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()  # A cursor is the object you use to send SQL commands

            # CREATE TABLE IF NOT EXISTS = "only create if it doesn't exist yet"
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_stories (
                    url TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()  # Save the changes to disk

    def is_processed(self, url: str) -> bool:
        """
        Checks if an article URL has already been sent before.

        Args:
            url: The full URL of the article, e.g. "https://bbc.com/news/..."

        Returns:
            True  → we've seen this article before, SKIP IT
            False → this is a brand new article, keep it

        How it works:
            We run: SELECT 1 FROM processed_stories WHERE url = ?
            If this finds a row, fetchone() returns something (truthy).
            If no row found, fetchone() returns None (falsy).
            `is not None` converts this to a proper True/False.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # The `?` placeholder is IMPORTANT — never put variables
            # directly in SQL strings (that's a "SQL injection" vulnerability).
            # SQLite safely substitutes the `?` with the url value.
            cursor.execute("SELECT 1 FROM processed_stories WHERE url = ?", (url,))
            return cursor.fetchone() is not None  # True if row exists, False if not

    def mark_processed(self, url: str, domain: str):
        """
        Saves an article URL to the database after it's been sent.

        Args:
            url:    The article's full URL
            domain: Which news category it belongs to (e.g. "India", "Tech & AI")

        INSERT OR IGNORE means:
            If the URL is already in the database (unlikely but possible),
            just silently do nothing instead of crashing with a "duplicate key" error.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO processed_stories (url, domain) VALUES (?, ?)",
                (url, domain)   # Always use ? placeholders for safety!
            )
            conn.commit()

    def prune_old_records(self, days: int = 30):
        """
        Deletes old records to keep the database from growing forever.

        Why 30 days? Because it's very unlikely the same article will appear
        in an RSS feed more than a month later. After 30 days, it's safe to
        "forget" about it.

        Args:
            days: Delete records older than this many days. Default is 30.

        Example:
            db.prune_old_records(days=30)
            # Deletes everything processed more than 30 days ago
        """
        # Calculate the cutoff point: "anything before this date gets deleted"
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM processed_stories WHERE processed_date < ?",
                (cutoff_date,)
            )
            conn.commit()
