"""SQLite database for storing user analytics history."""

import aiosqlite
import json
import time
from config import DB_PATH


async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                first_seen INTEGER,
                last_seen INTEGER,
                analysis_count INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp INTEGER,
                followers_count INTEGER,
                following_count INTEGER,
                mutual_count INTEGER,
                not_following_back_count INTEGER,
                not_followed_back_count INTEGER,
                followers_snapshot TEXT,
                following_snapshot TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()


async def upsert_user(user_id: int, username: str | None, first_name: str | None):
    """Insert or update user record."""
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name, first_seen, last_seen, analysis_count)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_seen = excluded.last_seen
        """, (user_id, username, first_name, now, now))
        await db.commit()


async def save_analysis(user_id: int, stats: dict, followers: list[str], following: list[str]):
    """Save analysis results."""
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO analyses (user_id, timestamp, followers_count, following_count,
                mutual_count, not_following_back_count, not_followed_back_count,
                followers_snapshot, following_snapshot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, now,
            stats["followers"], stats["following"], stats["mutual"],
            stats["not_following_back"], stats["not_followed_back"],
            json.dumps(followers), json.dumps(following)
        ))
        await db.execute("""
            UPDATE users SET analysis_count = analysis_count + 1, last_seen = ? WHERE user_id = ?
        """, (now, user_id))
        await db.commit()


async def get_previous_analysis(user_id: int):
    """Get the most recent previous analysis for comparison."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM analyses WHERE user_id = ?
            ORDER BY timestamp DESC LIMIT 1 OFFSET 1
        """, (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_last_analysis(user_id: int):
    """Get the latest analysis."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM analyses WHERE user_id = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_admin_stats():
    """Get overall bot statistics for admin."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM analyses")
        total_analyses = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE last_seen > ?",
            (int(time.time()) - 86400 * 7,)
        )
        active_week = (await cursor.fetchone())[0]

        return {
            "total_users": total_users,
            "total_analyses": total_analyses,
            "active_last_7_days": active_week,
        }
