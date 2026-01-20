"""Configuration management for Workday CLI."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import toml


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = False


@dataclass
class TimerConfig:
    """Timer duration settings."""
    focus_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    long_break_after: int = 4  # pomodoros before long break


@dataclass
class Config:
    """Main application configuration."""
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    timer: TimerConfig = field(default_factory=TimerConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create Config from dictionary."""
        telegram_data = data.get("telegram", {})
        timer_data = data.get("timer", {})

        return cls(
            telegram=TelegramConfig(
                bot_token=telegram_data.get("bot_token", ""),
                chat_id=telegram_data.get("chat_id", ""),
                enabled=telegram_data.get("enabled", False),
            ),
            timer=TimerConfig(
                focus_minutes=timer_data.get("focus_minutes", 25),
                short_break_minutes=timer_data.get("short_break_minutes", 5),
                long_break_minutes=timer_data.get("long_break_minutes", 15),
                long_break_after=timer_data.get("long_break_after", 4),
            ),
        )

    def to_dict(self) -> dict:
        """Convert Config to dictionary."""
        return {
            "telegram": {
                "bot_token": self.telegram.bot_token,
                "chat_id": self.telegram.chat_id,
                "enabled": self.telegram.enabled,
            },
            "timer": {
                "focus_minutes": self.timer.focus_minutes,
                "short_break_minutes": self.timer.short_break_minutes,
                "long_break_minutes": self.timer.long_break_minutes,
                "long_break_after": self.timer.long_break_after,
            },
        }


class ConfigManager:
    """Manages configuration file operations."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize config manager.

        Args:
            config_dir: Override config directory (for testing)
        """
        if config_dir is None:
            self.config_dir = Path.home() / ".workday"
        else:
            self.config_dir = config_dir

        self.config_file = self.config_dir / "config.toml"
        self.db_file = self.config_dir / "workday.db"
        self.state_file = self.config_dir / "timer.state"
        self.pid_file = self.config_dir / "timer.pid"

    def ensure_dirs(self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Config:
        """Load configuration from file.

        Returns:
            Config object with loaded or default values
        """
        if not self.config_file.exists():
            return Config()

        try:
            data = toml.load(self.config_file)
            return Config.from_dict(data)
        except Exception:
            return Config()

    def save(self, config: Config) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save
        """
        self.ensure_dirs()
        with open(self.config_file, "w") as f:
            toml.dump(config.to_dict(), f)

    def is_configured(self) -> bool:
        """Check if initial setup has been completed."""
        return self.config_file.exists()

    def get_pid(self) -> Optional[int]:
        """Get the PID of the running timer daemon.

        Returns:
            PID if timer is running, None otherwise
        """
        if not self.pid_file.exists():
            return None

        try:
            pid = int(self.pid_file.read_text().strip())
            # Check if process is actually running
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, PermissionError):
            # Process doesn't exist or PID file is invalid
            self.pid_file.unlink(missing_ok=True)
            return None

    def set_pid(self, pid: int) -> None:
        """Save timer daemon PID.

        Args:
            pid: Process ID to save
        """
        self.ensure_dirs()
        self.pid_file.write_text(str(pid))

    def clear_pid(self) -> None:
        """Remove PID file."""
        self.pid_file.unlink(missing_ok=True)


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
