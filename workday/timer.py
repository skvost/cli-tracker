"""Timer daemon for Workday CLI - handles background pomodoro timing."""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import ConfigManager, Config
from .models import TimerState, TimerStatus, BreakType, Pomodoro
from .storage import Storage
from .telegram_bot import TelegramNotifier

logger = logging.getLogger(__name__)


class TimerDaemon:
    """Background timer daemon process."""

    def __init__(self, config_manager: ConfigManager):
        """Initialize timer daemon.

        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.config = config_manager.load()
        self.storage = Storage(config_manager.db_file)
        self.notifier = TelegramNotifier(self.config.telegram)

        self.state = TimerState()
        self._running = False
        self._break_counter = 0  # Tracks alternating breaks

    def _save_state(self) -> None:
        """Save current state to file."""
        self.config_manager.ensure_dirs()
        with open(self.config_manager.state_file, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)

    def _load_state(self) -> Optional[TimerState]:
        """Load state from file.

        Returns:
            TimerState if file exists and is valid, None otherwise
        """
        if not self.config_manager.state_file.exists():
            return None

        try:
            with open(self.config_manager.state_file) as f:
                data = json.load(f)
                return TimerState.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return None

    def _clear_state(self) -> None:
        """Remove state file."""
        self.config_manager.state_file.unlink(missing_ok=True)

    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}, stopping timer")
        self._running = False

    def _pause_signal_handler(self, signum, frame):
        """Handle pause signal (SIGUSR1)."""
        if self.state.status != TimerStatus.PAUSED:
            self.state.status = TimerStatus.PAUSED
            self._save_state()

    def _resume_signal_handler(self, signum, frame):
        """Handle resume signal (SIGUSR2)."""
        if self.state.status == TimerStatus.PAUSED:
            self.state.status = TimerStatus.FOCUS if self.state.break_type is None else TimerStatus.BREAK
            self._save_state()

    def _daemonize(self) -> None:
        """Fork process to background."""
        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent exits
                sys.exit(0)
        except OSError as e:
            logger.error(f"First fork failed: {e}")
            sys.exit(1)

        # Decouple from parent
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            logger.error(f"Second fork failed: {e}")
            sys.exit(1)

        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()

        # Redirect to /dev/null
        with open("/dev/null", "r") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        with open("/dev/null", "w") as devnull:
            os.dup2(devnull.fileno(), sys.stdout.fileno())
            os.dup2(devnull.fileno(), sys.stderr.fileno())

        # Save PID
        self.config_manager.set_pid(os.getpid())

    def start(
        self,
        day_id: int,
        task_id: Optional[int] = None,
        starting_pomodoro: int = 1,
        daemonize: bool = True,
    ) -> None:
        """Start the timer daemon.

        Args:
            day_id: Day ID to track pomodoros for
            task_id: Optional task ID to associate with pomodoros
            starting_pomodoro: Which pomodoro number to start with
            daemonize: Whether to fork to background
        """
        # Check if already running
        existing_pid = self.config_manager.get_pid()
        if existing_pid:
            raise RuntimeError(f"Timer already running (PID {existing_pid})")

        if daemonize:
            self._daemonize()

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGUSR1, self._pause_signal_handler)
        signal.signal(signal.SIGUSR2, self._resume_signal_handler)

        # Initialize state
        self.state = TimerState(
            status=TimerStatus.FOCUS,
            current_pomodoro=starting_pomodoro,
            time_remaining_seconds=self.config.timer.focus_minutes * 60,
            started_at=datetime.now(),
            current_task_id=task_id,
            day_id=day_id,
        )
        self._break_counter = 0
        self._running = True

        # Get task name for notifications
        task_name = None
        if task_id:
            task = self.storage.get_task(task_id)
            if task:
                task_name = task.description

        # Notify focus start
        self.notifier.notify_focus_start(self.state.current_pomodoro, task_name)

        # Create pomodoro record
        pomodoro = Pomodoro(
            day_id=day_id,
            task_id=task_id,
            started_at=datetime.now(),
            duration_minutes=self.config.timer.focus_minutes,
        )
        pomodoro = self.storage.create_pomodoro(pomodoro)
        current_pomodoro_id = pomodoro.id

        self._save_state()

        # Main timer loop
        try:
            self._run_loop(day_id, task_id, current_pomodoro_id)
        finally:
            self._cleanup()

    def _run_loop(
        self,
        day_id: int,
        task_id: Optional[int],
        current_pomodoro_id: int,
    ) -> None:
        """Main timer loop.

        Args:
            day_id: Day ID
            task_id: Task ID
            current_pomodoro_id: Current pomodoro record ID
        """
        while self._running:
            # Check for external skip command via state file
            external_state = self._load_state()
            if external_state and external_state.time_remaining_seconds == 0 and self.state.time_remaining_seconds > 0:
                self.state.time_remaining_seconds = 0

            # Skip time if paused (pause/resume handled via signals)
            if self.state.status == TimerStatus.PAUSED:
                time.sleep(1)
                self._save_state()
                continue

            # Count down
            if self.state.time_remaining_seconds > 0:
                time.sleep(1)
                self.state.time_remaining_seconds -= 1
                self._save_state()
                continue

            # Timer completed - handle transition
            if self.state.status == TimerStatus.FOCUS:
                # Focus session complete
                self.storage.complete_pomodoro(current_pomodoro_id)

                # Update day's actual pomodoro count
                day = self.storage.get_day(day_id)
                if day:
                    day.actual_pomodoros += 1
                    self.storage.update_day(day)

                self.notifier.notify_focus_complete(self.state.current_pomodoro)

                # Determine break type
                self._break_counter += 1

                # Long break every N pomodoros
                if self._break_counter >= self.config.timer.long_break_after:
                    break_type = BreakType.LONG
                    break_minutes = self.config.timer.long_break_minutes
                    self._break_counter = 0
                else:
                    # Alternate between email and rest breaks
                    if self._break_counter % 2 == 1:
                        break_type = BreakType.EMAIL
                        if day:
                            day.email_breaks += 1
                            self.storage.update_day(day)
                    else:
                        break_type = BreakType.REST
                        if day:
                            day.rest_breaks += 1
                            self.storage.update_day(day)
                    break_minutes = self.config.timer.short_break_minutes

                # Start break
                self.state.status = TimerStatus.BREAK
                self.state.break_type = break_type
                self.state.time_remaining_seconds = break_minutes * 60
                self._save_state()

                self.notifier.notify_break_start(break_type, break_minutes)

            elif self.state.status == TimerStatus.BREAK:
                # Break complete
                self.notifier.notify_break_end()

                # Start next pomodoro
                self.state.current_pomodoro += 1
                self.state.status = TimerStatus.FOCUS
                self.state.break_type = None
                self.state.time_remaining_seconds = self.config.timer.focus_minutes * 60
                self.state.started_at = datetime.now()
                self._save_state()

                # Get task name
                task_name = None
                if task_id:
                    task = self.storage.get_task(task_id)
                    if task:
                        task_name = task.description

                self.notifier.notify_focus_start(self.state.current_pomodoro, task_name)

                # Create new pomodoro record
                pomodoro = Pomodoro(
                    day_id=day_id,
                    task_id=task_id,
                    started_at=datetime.now(),
                    duration_minutes=self.config.timer.focus_minutes,
                )
                pomodoro = self.storage.create_pomodoro(pomodoro)
                current_pomodoro_id = pomodoro.id

    def _cleanup(self) -> None:
        """Clean up on exit."""
        self.state.status = TimerStatus.STOPPED
        self._save_state()
        self.config_manager.clear_pid()

    def stop(self) -> bool:
        """Stop the running timer.

        Returns:
            True if timer was stopped, False if not running
        """
        pid = self.config_manager.get_pid()
        if not pid:
            return False

        try:
            os.kill(pid, signal.SIGTERM)
            # Wait for process to exit
            for _ in range(10):
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
            self.config_manager.clear_pid()
            return True
        except ProcessLookupError:
            self.config_manager.clear_pid()
            return False
        except Exception as e:
            logger.error(f"Failed to stop timer: {e}")
            return False

    def pause(self) -> bool:
        """Pause the running timer.

        Returns:
            True if paused, False if not running or already paused
        """
        pid = self.config_manager.get_pid()
        if not pid:
            return False

        state = self._load_state()
        if not state or state.status == TimerStatus.STOPPED:
            return False

        if state.status == TimerStatus.PAUSED:
            return False

        try:
            os.kill(pid, signal.SIGUSR1)
            self.notifier.notify_timer_paused()
            return True
        except ProcessLookupError:
            return False

    def resume(self) -> bool:
        """Resume a paused timer.

        Returns:
            True if resumed, False if not paused
        """
        pid = self.config_manager.get_pid()
        if not pid:
            return False

        state = self._load_state()
        if not state or state.status != TimerStatus.PAUSED:
            return False

        try:
            os.kill(pid, signal.SIGUSR2)
            # Wait a moment for state to update
            time.sleep(0.1)
            state = self._load_state()
            from .display import format_time
            time_str = format_time(state.time_remaining_seconds) if state else "unknown"
            self.notifier.notify_timer_resumed(time_str)
            return True
        except ProcessLookupError:
            return False

    def skip(self) -> bool:
        """Skip current focus/break period.

        Returns:
            True if skipped, False if not running
        """
        state = self._load_state()
        if not state or state.status == TimerStatus.STOPPED:
            return False

        # Set remaining time to 0 to trigger transition
        state.time_remaining_seconds = 0
        with open(self.config_manager.state_file, "w") as f:
            json.dump(state.to_dict(), f, indent=2)

        return True

    def get_status(self) -> Optional[TimerState]:
        """Get current timer status.

        Returns:
            Current TimerState or None if not running
        """
        # Check if daemon is actually running
        pid = self.config_manager.get_pid()
        if not pid:
            # Clear stale state file if no daemon
            self._clear_state()
            return None

        return self._load_state()


def get_timer_status(config_manager: Optional[ConfigManager] = None) -> Optional[TimerState]:
    """Convenience function to get timer status.

    Args:
        config_manager: Optional config manager, creates default if not provided

    Returns:
        Current TimerState or None if not running
    """
    if config_manager is None:
        config_manager = ConfigManager()

    daemon = TimerDaemon(config_manager)
    return daemon.get_status()
