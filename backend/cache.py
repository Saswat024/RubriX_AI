"""
AI Response Cache Module
Caches Gemini API responses in SQLite to avoid redundant token usage.
Same input content → same cached result (until TTL expires).
"""

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from database import get_db_connection
from dotenv import load_dotenv

load_dotenv(override=True)

# Cache TTL in hours (default 24h, configurable via .env)
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))


def normalize_code(code: str) -> str:
    """
    Normalize code/pseudocode to produce the same hash for trivially different inputs.
    Strips semicolons, extra whitespace, comments, and other syntactic noise
    so that 'return true;' and 'return true' produce the same cache key.
    """
    # Remove single-line comments (// ... and # ...)
    text = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
    text = re.sub(r'#.*$', '', text, flags=re.MULTILINE)

    # Remove multi-line comments (/* ... */)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    # Remove semicolons
    text = text.replace(';', '')

    # Normalize all whitespace: tabs, multiple spaces, \r\n → single space
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Lowercase for case-insensitive matching
    text = text.lower()

    return text


def generate_cache_key(call_type: str, *content_parts: str) -> str:
    """
    Generate a deterministic SHA-256 hash from call type + content.
    Multiple content parts are joined with a separator to avoid collisions.
    """
    combined = call_type + "||" + "||".join(str(p) for p in content_parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def get_cached_response(call_type: str, content_hash: str) -> dict | None:
    """
    Look up a cached response. Returns the parsed JSON result or None.
    Also increments hit_count on cache hit.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, response FROM ai_cache 
                   WHERE call_type = ? AND content_hash = ? AND expires_at > ?""",
                (call_type, content_hash, datetime.now().isoformat()),
            )
            row = cursor.fetchone()

            if row:
                # Increment hit count
                cursor.execute(
                    "UPDATE ai_cache SET hit_count = hit_count + 1 WHERE id = ?",
                    (row[0],),
                )
                conn.commit()
                print(f"[CACHE HIT] {call_type} (hash: {content_hash[:12]}...)")
                return json.loads(row[1])

        return None
    except Exception as e:
        print(f"[CACHE ERROR] get_cached_response: {e}")
        return None


def set_cached_response(call_type: str, content_hash: str, response: dict) -> None:
    """
    Store a Gemini API response in the cache with TTL.
    Uses INSERT OR REPLACE to handle duplicate keys gracefully.
    """
    try:
        expires_at = datetime.now() + timedelta(hours=CACHE_TTL_HOURS)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO ai_cache 
                   (call_type, content_hash, response, created_at, expires_at, hit_count)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (
                    call_type,
                    content_hash,
                    json.dumps(response),
                    datetime.now().isoformat(),
                    expires_at.isoformat(),
                ),
            )
            conn.commit()
            print(f"[CACHE STORE] {call_type} (hash: {content_hash[:12]}..., TTL: {CACHE_TTL_HOURS}h)")
    except Exception as e:
        print(f"[CACHE ERROR] set_cached_response: {e}")


def get_cache_stats() -> dict:
    """Get cache statistics for the admin endpoint."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Total entries
            cursor.execute("SELECT COUNT(*) FROM ai_cache")
            total_entries = cursor.fetchone()[0]

            # Active (non-expired) entries
            cursor.execute(
                "SELECT COUNT(*) FROM ai_cache WHERE expires_at > ?",
                (datetime.now().isoformat(),),
            )
            active_entries = cursor.fetchone()[0]

            # Total hits
            cursor.execute("SELECT COALESCE(SUM(hit_count), 0) FROM ai_cache")
            total_hits = cursor.fetchone()[0]

            # Hits by call type
            cursor.execute(
                """SELECT call_type, COUNT(*) as entries, COALESCE(SUM(hit_count), 0) as hits
                   FROM ai_cache WHERE expires_at > ?
                   GROUP BY call_type ORDER BY hits DESC""",
                (datetime.now().isoformat(),),
            )
            by_type = [
                {"call_type": r[0], "entries": r[1], "hits": r[2]}
                for r in cursor.fetchall()
            ]

            return {
                "total_entries": total_entries,
                "active_entries": active_entries,
                "expired_entries": total_entries - active_entries,
                "total_cache_hits": total_hits,
                "ttl_hours": CACHE_TTL_HOURS,
                "by_call_type": by_type,
            }
    except Exception as e:
        print(f"[CACHE ERROR] get_cache_stats: {e}")
        return {"error": str(e)}


def cleanup_expired_cache() -> int:
    """Remove expired cache entries. Returns number of entries removed."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM ai_cache WHERE expires_at <= ?",
                (datetime.now().isoformat(),),
            )
            removed = cursor.rowcount
            conn.commit()
            if removed > 0:
                print(f"[CACHE CLEANUP] Removed {removed} expired entries")
            return removed
    except Exception as e:
        print(f"[CACHE ERROR] cleanup_expired_cache: {e}")
        return 0
