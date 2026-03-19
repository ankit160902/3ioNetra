"""
QueryLogger — Async SQLite-based query analytics pipeline.

Logs every RAG search with metadata for offline analysis:
- query text, intent, life_domain, emotion
- result count, top score, latency
- expanded queries, Sanskrit terms detected

Uses aiosqlite for non-blocking writes. Fire-and-forget from pipeline.py.
"""

import asyncio
import logging
import os
import time
from typing import Optional, List

logger = logging.getLogger(__name__)


class QueryLogger:
    """Async SQLite query logger for RAG analytics."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db = None
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    async def initialize(self) -> None:
        """Create the SQLite database and queries table."""
        try:
            import aiosqlite
        except ImportError:
            logger.warning("QueryLogger: aiosqlite not installed — query logging disabled")
            return

        try:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            self._db = await aiosqlite.connect(self._db_path)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    query TEXT NOT NULL,
                    intent TEXT,
                    life_domain TEXT,
                    emotion TEXT,
                    num_results INTEGER,
                    top_score REAL,
                    latency_ms INTEGER,
                    expanded_queries TEXT,
                    session_id TEXT,
                    sanskrit_terms TEXT
                )
            """)
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_queries_timestamp ON queries(timestamp)
            """)
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_queries_intent ON queries(intent)
            """)
            await self._db.commit()
            self._available = True
            logger.info(f"QueryLogger: initialized at {self._db_path}")
        except Exception as e:
            logger.error(f"QueryLogger: initialization failed — {e}")
            self._available = False

    async def log(
        self,
        query: str,
        intent: Optional[str] = None,
        life_domain: Optional[str] = None,
        emotion: Optional[str] = None,
        num_results: int = 0,
        top_score: float = 0.0,
        latency_ms: int = 0,
        expanded_queries: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        sanskrit_terms: Optional[List[str]] = None,
    ) -> None:
        """Insert a query log entry. Non-blocking, errors are swallowed."""
        if not self._available or self._db is None:
            return

        try:
            from datetime import datetime, timezone
            await self._db.execute(
                """INSERT INTO queries
                   (timestamp, query, intent, life_domain, emotion,
                    num_results, top_score, latency_ms,
                    expanded_queries, session_id, sanskrit_terms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    query[:500],
                    intent,
                    life_domain,
                    emotion,
                    num_results,
                    round(top_score, 4),
                    latency_ms,
                    ",".join(expanded_queries) if expanded_queries else None,
                    session_id,
                    ",".join(sanskrit_terms) if sanskrit_terms else None,
                ),
            )
            await self._db.commit()
        except Exception as e:
            logger.debug(f"QueryLogger: log write failed — {e}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            try:
                await self._db.close()
            except Exception:
                pass
            self._db = None
            self._available = False


# Singleton
_query_logger: Optional[QueryLogger] = None


def get_query_logger() -> QueryLogger:
    global _query_logger
    if _query_logger is None:
        from config import settings
        _query_logger = QueryLogger(settings.QUERY_LOG_PATH)
    return _query_logger
