"""Data models for Workday CLI."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TimerStatus(Enum):
    """Timer state enumeration."""
    FOCUS = "focus"
    BREAK = "break"
    PAUSED = "paused"
    STOPPED = "stopped"


class BreakType(Enum):
    """Type of break."""
    EMAIL = "email"
    REST = "rest"
    LONG = "long"


@dataclass
class Task:
    """A task for the day."""
    id: Optional[int] = None
    day_id: Optional[int] = None
    description: str = ""
    completed: bool = False
    position: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_row(cls, row: tuple) -> "Task":
        """Create Task from database row."""
        return cls(
            id=row[0],
            day_id=row[1],
            description=row[2],
            completed=bool(row[3]),
            position=row[4],
            created_at=datetime.fromisoformat(row[5]) if row[5] else datetime.now(),
        )


@dataclass
class Pomodoro:
    """A single pomodoro session."""
    id: Optional[int] = None
    day_id: Optional[int] = None
    task_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_minutes: int = 25

    @classmethod
    def from_row(cls, row: tuple) -> "Pomodoro":
        """Create Pomodoro from database row."""
        return cls(
            id=row[0],
            day_id=row[1],
            task_id=row[2],
            started_at=datetime.fromisoformat(row[3]) if row[3] else None,
            completed_at=datetime.fromisoformat(row[4]) if row[4] else None,
            duration_minutes=row[5],
        )


@dataclass
class Day:
    """A workday record."""
    id: Optional[int] = None
    date: str = ""  # YYYY-MM-DD format
    planned_pomodoros: int = 0
    actual_pomodoros: int = 0
    email_breaks: int = 0
    rest_breaks: int = 0
    satisfaction: Optional[int] = None  # 1-4 rating
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    tasks: list[Task] = field(default_factory=list)
    pomodoros: list[Pomodoro] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: tuple) -> "Day":
        """Create Day from database row."""
        return cls(
            id=row[0],
            date=row[1],
            planned_pomodoros=row[2],
            actual_pomodoros=row[3],
            email_breaks=row[4],
            rest_breaks=row[5],
            satisfaction=row[6],
            notes=row[7] or "",
            created_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now(),
        )


@dataclass
class Streak:
    """Streak tracking data."""
    id: Optional[int] = None
    current_streak: int = 0
    longest_streak: int = 0
    last_active_date: str = ""  # YYYY-MM-DD format

    @classmethod
    def from_row(cls, row: tuple) -> "Streak":
        """Create Streak from database row."""
        return cls(
            id=row[0],
            current_streak=row[1],
            longest_streak=row[2],
            last_active_date=row[3] or "",
        )


@dataclass
class TimerState:
    """Current state of the timer daemon."""
    status: TimerStatus = TimerStatus.STOPPED
    break_type: Optional[BreakType] = None
    current_pomodoro: int = 0
    time_remaining_seconds: int = 0
    started_at: Optional[datetime] = None
    current_task_id: Optional[int] = None
    day_id: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "break_type": self.break_type.value if self.break_type else None,
            "current_pomodoro": self.current_pomodoro,
            "time_remaining_seconds": self.time_remaining_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "current_task_id": self.current_task_id,
            "day_id": self.day_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TimerState":
        """Create TimerState from dictionary."""
        break_type = None
        if data.get("break_type"):
            break_type = BreakType(data["break_type"])

        started_at = None
        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])

        return cls(
            status=TimerStatus(data.get("status", "stopped")),
            break_type=break_type,
            current_pomodoro=data.get("current_pomodoro", 0),
            time_remaining_seconds=data.get("time_remaining_seconds", 0),
            started_at=started_at,
            current_task_id=data.get("current_task_id"),
            day_id=data.get("day_id"),
        )
