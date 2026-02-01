"""
Database models for storing scheduled Instagram story uploads.
Uses SQLite for persistence across restarts.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, asdict
from config import Config


@dataclass
class ScheduledStory:
    """Represents a scheduled Instagram story upload."""
    id: Optional[int]
    user_id: int  # Telegram user who scheduled this
    image_path: str  # Path to the image file
    link_url: str  # URL for the link sticker
    link_text: str  # Text to display (e.g., "קנה כאן 🛒")
    scheduled_time: datetime  # When to upload
    recurrence: Optional[str]  # 'daily', 'weekly', 'none'
    recurrence_day: Optional[int]  # 0=Monday, 6=Sunday (for weekly)
    status: str  # 'pending', 'uploaded', 'failed'
    created_at: datetime
    error_message: Optional[str] = None
    
    def to_dict(self):
        d = asdict(self)
        d['scheduled_time'] = self.scheduled_time.isoformat()
        d['created_at'] = self.created_at.isoformat()
        return d
    
    @classmethod
    def from_row(cls, row: tuple) -> 'ScheduledStory':
        return cls(
            id=row[0],
            user_id=row[1],
            image_path=row[2],
            link_url=row[3],
            link_text=row[4],
            scheduled_time=datetime.fromisoformat(row[5]),
            recurrence=row[6],
            recurrence_day=row[7],
            status=row[8],
            created_at=datetime.fromisoformat(row[9]),
            error_message=row[10]
        )


class Database:
    """SQLite database manager for scheduled stories."""
    
    def __init__(self):
        Config.ensure_dirs()
        self.db_path = Config.DATABASE_PATH
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
    
    def _init_db(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_stories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    image_path TEXT NOT NULL,
                    link_url TEXT NOT NULL,
                    link_text TEXT NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    recurrence TEXT,
                    recurrence_day INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    error_message TEXT
                )
            ''')
            conn.commit()
    
    def add_story(self, story: ScheduledStory) -> int:
        """Add a new scheduled story and return its ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO scheduled_stories 
                (user_id, image_path, link_url, link_text, scheduled_time, 
                 recurrence, recurrence_day, status, created_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                story.user_id,
                story.image_path,
                story.link_url,
                story.link_text,
                story.scheduled_time.isoformat(),
                story.recurrence,
                story.recurrence_day,
                story.status,
                story.created_at.isoformat(),
                story.error_message
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_pending_stories(self, before_time: Optional[datetime] = None) -> List[ScheduledStory]:
        """Get all pending stories, optionally filtered by time."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if before_time:
                cursor.execute('''
                    SELECT * FROM scheduled_stories 
                    WHERE status = 'pending' AND scheduled_time <= ?
                    ORDER BY scheduled_time
                ''', (before_time.isoformat(),))
            else:
                cursor.execute('''
                    SELECT * FROM scheduled_stories 
                    WHERE status = 'pending'
                    ORDER BY scheduled_time
                ''')
            return [ScheduledStory.from_row(row) for row in cursor.fetchall()]
    
    def get_user_stories(self, user_id: int, status: Optional[str] = None) -> List[ScheduledStory]:
        """Get all stories for a specific user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute('''
                    SELECT * FROM scheduled_stories 
                    WHERE user_id = ? AND status = ?
                    ORDER BY scheduled_time
                ''', (user_id, status))
            else:
                cursor.execute('''
                    SELECT * FROM scheduled_stories 
                    WHERE user_id = ?
                    ORDER BY scheduled_time
                ''', (user_id,))
            return [ScheduledStory.from_row(row) for row in cursor.fetchall()]
    
    def update_status(self, story_id: int, status: str, error_message: Optional[str] = None):
        """Update the status of a story."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scheduled_stories 
                SET status = ?, error_message = ?
                WHERE id = ?
            ''', (status, error_message, story_id))
            conn.commit()
    
    def delete_story(self, story_id: int):
        """Delete a scheduled story."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM scheduled_stories WHERE id = ?', (story_id,))
            conn.commit()
    
    def get_story_by_id(self, story_id: int) -> Optional[ScheduledStory]:
        """Get a specific story by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM scheduled_stories WHERE id = ?', (story_id,))
            row = cursor.fetchone()
            return ScheduledStory.from_row(row) if row else None
