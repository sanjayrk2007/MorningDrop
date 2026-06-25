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

import os            # To read DATABASE_URL environment variable
import sqlite3       # Python's built-in library for working with SQLite databases
import datetime      # For calculating "how old is this record?"


class NewsDatabase:
    """
    A simple helper class that wraps all database operations.

    Supports PostgreSQL in production (if DATABASE_URL is set)
    and SQLite locally.
    """

    def __init__(self, db_path: str = "news.db"):
        """
        Called automatically when you create a NewsDatabase object.
        """
        self.db_path = db_path
        self.db_url = os.environ.get("DATABASE_URL")
        self.is_postgres = bool(self.db_url)
        self.placeholder = "%s" if self.is_postgres else "?"
        self._init_db()  # Make sure the table exists when we start

    def _get_connection(self):
        if self.is_postgres:
            # Import psycopg2 lazily so it's only required in production
            import psycopg2
            return psycopg2.connect(self.db_url)
        else:
            return sqlite3.connect(self.db_path)

    def _init_db(self):
        """
        Creates the database table if it doesn't already exist.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.is_postgres:
                # PostgreSQL syntax
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS processed_stories (
                        url TEXT PRIMARY KEY,
                        domain VARCHAR(255) NOT NULL,
                        processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            else:
                # SQLite syntax
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS processed_stories (
                        url TEXT PRIMARY KEY,
                        domain TEXT NOT NULL,
                        processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            conn.commit()
        finally:
            conn.close()

    def is_processed(self, url: str) -> bool:
        """
        Checks if an article URL has already been sent before.

        Args:
            url: The full URL of the article, e.g. "https://bbc.com/news/..."

        Returns:
            True  → we've seen this article before, SKIP IT
            False → this is a brand new article, keep it
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = f"SELECT 1 FROM processed_stories WHERE url = {self.placeholder}"
            cursor.execute(query, (url,))
            return cursor.fetchone() is not None  # True if row exists, False if not
        finally:
            conn.close()

    def mark_processed(self, url: str, domain: str):
        """
        Saves an article URL to the database after it's been sent.

        Args:
            url:    The article's full URL
            domain: Which news category it belongs to (e.g. "India", "Tech & AI")
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.is_postgres:
                # PostgreSQL uses ON CONFLICT DO NOTHING for IGNORE
                query = "INSERT INTO processed_stories (url, domain) VALUES (%s, %s) ON CONFLICT (url) DO NOTHING"
            else:
                query = "INSERT OR IGNORE INTO processed_stories (url, domain) VALUES (?, ?)"
            cursor.execute(query, (url, domain))
            conn.commit()
        finally:
            conn.close()

    def prune_old_records(self, days: int = 30):
        """
        Deletes old records to keep the database from growing forever.

        Args:
            days: Delete records older than this many days. Default is 30.
        """
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = f"DELETE FROM processed_stories WHERE processed_date < {self.placeholder}"
            cursor.execute(query, (cutoff_date,))
            conn.commit()
        finally:
            conn.close()
