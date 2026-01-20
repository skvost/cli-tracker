"""SQLite database operations for Workday CLI."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Iterator

from .models import Day, Task, Pomodoro, Streak


SCHEMA = """
-- Daily plans
CREATE TABLE IF NOT EXISTS days (
    id INTEGER PRIMARY KEY,
    date TEXT UNIQUE NOT NULL,
    planned_pomodoros INTEGER DEFAULT 0,
    actual_pomodoros INTEGER DEFAULT 0,
    email_breaks INTEGER DEFAULT 0,
    rest_breaks INTEGER DEFAULT 0,
    satisfaction INTEGER,
    notes TEXT,
    created_at TEXT,
    started_at TEXT,
    ended_at TEXT
);

-- Tasks for each day
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    day_id INTEGER REFERENCES days(id),
    description TEXT NOT NULL,
    completed INTEGER DEFAULT 0,
    position INTEGER,
    created_at TEXT
);

-- Individual pomodoro records
CREATE TABLE IF NOT EXISTS pomodoros (
    id INTEGER PRIMARY KEY,
    day_id INTEGER REFERENCES days(id),
    task_id INTEGER REFERENCES tasks(id),
    started_at TEXT,
    completed_at TEXT,
    duration_minutes INTEGER DEFAULT 25
);

-- Streak tracking
CREATE TABLE IF NOT EXISTS streaks (
    id INTEGER PRIMARY KEY,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_active_date TEXT
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tasks_day_id ON tasks(day_id);
CREATE INDEX IF NOT EXISTS idx_pomodoros_day_id ON pomodoros(day_id);
CREATE INDEX IF NOT EXISTS idx_days_date ON days(date);
"""


class Storage:
    """SQLite database operations."""

    def __init__(self, db_path: Path):
        """Initialize storage with database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.executescript(SCHEMA)
            # Initialize streak record if not exists
            cursor = conn.execute("SELECT COUNT(*) FROM streaks")
            if cursor.fetchone()[0] == 0:
                conn.execute(
                    "INSERT INTO streaks (current_streak, longest_streak, last_active_date) "
                    "VALUES (0, 0, '')"
                )
            # Migration: add started_at and ended_at columns if missing
            cursor = conn.execute("PRAGMA table_info(days)")
            columns = [row[1] for row in cursor.fetchall()]
            if "started_at" not in columns:
                conn.execute("ALTER TABLE days ADD COLUMN started_at TEXT")
            if "ended_at" not in columns:
                conn.execute("ALTER TABLE days ADD COLUMN ended_at TEXT")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # Day operations

    def create_day(self, day: Day) -> Day:
        """Create a new day record.

        Args:
            day: Day to create

        Returns:
            Day with assigned ID
        """
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO days (date, planned_pomodoros, actual_pomodoros,
                                  email_breaks, rest_breaks, satisfaction, notes, created_at,
                                  started_at, ended_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    day.date,
                    day.planned_pomodoros,
                    day.actual_pomodoros,
                    day.email_breaks,
                    day.rest_breaks,
                    day.satisfaction,
                    day.notes,
                    day.created_at.isoformat(),
                    day.started_at.isoformat() if day.started_at else None,
                    day.ended_at.isoformat() if day.ended_at else None,
                ),
            )
            day.id = cursor.lastrowid
            return day

    def get_day(self, day_id: int) -> Optional[Day]:
        """Get day by ID.

        Args:
            day_id: Day ID

        Returns:
            Day if found, None otherwise
        """
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM days WHERE id = ?", (day_id,))
            row = cursor.fetchone()
            if row:
                day = Day.from_row(tuple(row))
                day.tasks = self.get_tasks_for_day(day_id)
                day.pomodoros = self.get_pomodoros_for_day(day_id)
                return day
            return None

    def get_day_by_date(self, date_str: str) -> Optional[Day]:
        """Get day by date string.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            Day if found, None otherwise
        """
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM days WHERE date = ?", (date_str,))
            row = cursor.fetchone()
            if row:
                day = Day.from_row(tuple(row))
                day.tasks = self.get_tasks_for_day(day.id)
                day.pomodoros = self.get_pomodoros_for_day(day.id)
                return day
            return None

    def get_today(self) -> Optional[Day]:
        """Get today's day record."""
        return self.get_day_by_date(date.today().isoformat())

    def get_or_create_today(self) -> Day:
        """Get today's record, creating if needed."""
        today = self.get_today()
        if today:
            return today
        return self.create_day(Day(date=date.today().isoformat()))

    def update_day(self, day: Day) -> None:
        """Update day record.

        Args:
            day: Day to update
        """
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE days SET
                    planned_pomodoros = ?,
                    actual_pomodoros = ?,
                    email_breaks = ?,
                    rest_breaks = ?,
                    satisfaction = ?,
                    notes = ?,
                    started_at = ?,
                    ended_at = ?
                WHERE id = ?
                """,
                (
                    day.planned_pomodoros,
                    day.actual_pomodoros,
                    day.email_breaks,
                    day.rest_breaks,
                    day.satisfaction,
                    day.notes,
                    day.started_at.isoformat() if day.started_at else None,
                    day.ended_at.isoformat() if day.ended_at else None,
                    day.id,
                ),
            )

    def get_recent_days(self, limit: int = 7) -> list[Day]:
        """Get recent days.

        Args:
            limit: Maximum number of days to return

        Returns:
            List of days, most recent first
        """
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM days ORDER BY date DESC LIMIT ?", (limit,)
            )
            days = []
            for row in cursor.fetchall():
                day = Day.from_row(tuple(row))
                day.tasks = self.get_tasks_for_day(day.id)
                day.pomodoros = self.get_pomodoros_for_day(day.id)
                days.append(day)
            return days

    # Task operations

    def create_task(self, task: Task) -> Task:
        """Create a new task.

        Args:
            task: Task to create

        Returns:
            Task with assigned ID
        """
        with self._connection() as conn:
            # Get next position
            cursor = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM tasks WHERE day_id = ?",
                (task.day_id,),
            )
            position = cursor.fetchone()[0]
            task.position = position

            cursor = conn.execute(
                """
                INSERT INTO tasks (day_id, description, completed, position, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task.day_id,
                    task.description,
                    int(task.completed),
                    task.position,
                    task.created_at.isoformat(),
                ),
            )
            task.id = cursor.lastrowid
            return task

    def get_task(self, task_id: int) -> Optional[Task]:
        """Get task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task if found, None otherwise
        """
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                return Task.from_row(tuple(row))
            return None

    def get_tasks_for_day(self, day_id: int) -> list[Task]:
        """Get all tasks for a day.

        Args:
            day_id: Day ID

        Returns:
            List of tasks ordered by position
        """
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE day_id = ? ORDER BY position", (day_id,)
            )
            return [Task.from_row(tuple(row)) for row in cursor.fetchall()]

    def update_task(self, task: Task) -> None:
        """Update task record.

        Args:
            task: Task to update
        """
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE tasks SET
                    description = ?,
                    completed = ?,
                    position = ?
                WHERE id = ?
                """,
                (task.description, int(task.completed), task.position, task.id),
            )

    def complete_task(self, task_id: int) -> None:
        """Mark task as completed.

        Args:
            task_id: Task ID
        """
        with self._connection() as conn:
            conn.execute("UPDATE tasks SET completed = 1 WHERE id = ?", (task_id,))

    # Pomodoro operations

    def create_pomodoro(self, pomodoro: Pomodoro) -> Pomodoro:
        """Create a new pomodoro record.

        Args:
            pomodoro: Pomodoro to create

        Returns:
            Pomodoro with assigned ID
        """
        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pomodoros (day_id, task_id, started_at, completed_at, duration_minutes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    pomodoro.day_id,
                    pomodoro.task_id,
                    pomodoro.started_at.isoformat() if pomodoro.started_at else None,
                    pomodoro.completed_at.isoformat() if pomodoro.completed_at else None,
                    pomodoro.duration_minutes,
                ),
            )
            pomodoro.id = cursor.lastrowid
            return pomodoro

    def complete_pomodoro(self, pomodoro_id: int) -> None:
        """Mark pomodoro as completed.

        Args:
            pomodoro_id: Pomodoro ID
        """
        with self._connection() as conn:
            conn.execute(
                "UPDATE pomodoros SET completed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), pomodoro_id),
            )

    def get_pomodoros_for_day(self, day_id: int) -> list[Pomodoro]:
        """Get all pomodoros for a day.

        Args:
            day_id: Day ID

        Returns:
            List of pomodoros
        """
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM pomodoros WHERE day_id = ? ORDER BY started_at", (day_id,)
            )
            return [Pomodoro.from_row(tuple(row)) for row in cursor.fetchall()]

    def get_completed_pomodoro_count(self, day_id: int) -> int:
        """Get count of completed pomodoros for a day.

        Args:
            day_id: Day ID

        Returns:
            Number of completed pomodoros
        """
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM pomodoros WHERE day_id = ? AND completed_at IS NOT NULL",
                (day_id,),
            )
            return cursor.fetchone()[0]

    # Streak operations

    def get_streak(self) -> Streak:
        """Get current streak data.

        Returns:
            Streak record
        """
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM streaks LIMIT 1")
            row = cursor.fetchone()
            if row:
                return Streak.from_row(tuple(row))
            return Streak()

    def update_streak(self, today_str: str) -> Streak:
        """Update streak based on activity.

        Args:
            today_str: Today's date in YYYY-MM-DD format

        Returns:
            Updated streak
        """
        streak = self.get_streak()

        # Check if today already counted
        if streak.last_active_date == today_str:
            return streak

        # Calculate yesterday
        today = date.fromisoformat(today_str)
        yesterday = (today - __import__("datetime").timedelta(days=1)).isoformat()

        if streak.last_active_date == yesterday:
            # Continue streak
            streak.current_streak += 1
        elif streak.last_active_date == "":
            # First activity
            streak.current_streak = 1
        else:
            # Streak broken, start fresh
            streak.current_streak = 1

        # Update longest if needed
        if streak.current_streak > streak.longest_streak:
            streak.longest_streak = streak.current_streak

        streak.last_active_date = today_str

        # Save to database
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE streaks SET
                    current_streak = ?,
                    longest_streak = ?,
                    last_active_date = ?
                WHERE id = ?
                """,
                (
                    streak.current_streak,
                    streak.longest_streak,
                    streak.last_active_date,
                    streak.id,
                ),
            )

        return streak

    # Statistics

    def get_total_pomodoros(self) -> int:
        """Get total completed pomodoros across all days."""
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM pomodoros WHERE completed_at IS NOT NULL"
            )
            return cursor.fetchone()[0]

    def get_total_days(self) -> int:
        """Get total days with at least one completed pomodoro."""
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT day_id) FROM pomodoros
                WHERE completed_at IS NOT NULL
                """
            )
            return cursor.fetchone()[0]
