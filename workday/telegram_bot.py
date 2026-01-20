"""Telegram notification handler for Workday CLI."""

import asyncio
import logging
from typing import Optional

from .config import TelegramConfig
from .models import BreakType

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Handles sending notifications to Telegram."""

    def __init__(self, config: TelegramConfig):
        """Initialize notifier with config.

        Args:
            config: Telegram configuration
        """
        self.config = config
        self._bot = None

    @property
    def enabled(self) -> bool:
        """Check if Telegram notifications are enabled and configured."""
        return (
            self.config.enabled
            and bool(self.config.bot_token)
            and bool(self.config.chat_id)
        )

    async def _get_bot(self):
        """Get or create bot instance."""
        if self._bot is None:
            try:
                from telegram import Bot
                self._bot = Bot(token=self.config.bot_token)
            except ImportError:
                logger.warning("python-telegram-bot not installed")
                return None
            except Exception as e:
                logger.error(f"Failed to create bot: {e}")
                return None
        return self._bot

    async def send_message(self, text: str) -> bool:
        """Send a message to the configured chat.

        Args:
            text: Message text to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            bot = await self._get_bot()
            if bot is None:
                return False

            await bot.send_message(
                chat_id=self.config.chat_id,
                text=text,
                parse_mode="HTML",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    def send_sync(self, text: str) -> bool:
        """Synchronous wrapper for send_message.

        Args:
            text: Message text to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            return asyncio.run(self.send_message(text))
        except Exception as e:
            logger.error(f"Failed to send message synchronously: {e}")
            return False

    # Predefined notification messages

    def notify_focus_start(self, pomodoro_num: int, task_name: Optional[str] = None) -> bool:
        """Send notification for focus session start.

        Args:
            pomodoro_num: Current pomodoro number
            task_name: Optional task being worked on

        Returns:
            True if sent successfully
        """
        task_text = f"\nTask: {task_name}" if task_name else ""
        message = f"🍅 <b>Focus Time</b>\n\nPomodoro #{pomodoro_num} started.{task_text}\n\n25 minutes of focused work."
        return self.send_sync(message)

    def notify_focus_complete(self, pomodoro_num: int) -> bool:
        """Send notification for focus session completion.

        Args:
            pomodoro_num: Completed pomodoro number

        Returns:
            True if sent successfully
        """
        message = f"✅ <b>Pomodoro #{pomodoro_num} Complete!</b>\n\nGreat work! Time for a break."
        return self.send_sync(message)

    def notify_break_start(self, break_type: BreakType, duration_minutes: int) -> bool:
        """Send notification for break start.

        Args:
            break_type: Type of break
            duration_minutes: Break duration

        Returns:
            True if sent successfully
        """
        if break_type == BreakType.EMAIL:
            emoji = "📧"
            title = "Email Break"
            suggestion = "Check your inbox, respond to messages."
        elif break_type == BreakType.LONG:
            emoji = "☕"
            title = "Long Break"
            suggestion = "Stretch, grab a coffee, take a walk."
        else:
            emoji = "🧘"
            title = "Rest Break"
            suggestion = "Step away from the screen. Stretch. Breathe."

        message = f"{emoji} <b>{title}</b>\n\n{duration_minutes} minutes.\n{suggestion}"
        return self.send_sync(message)

    def notify_break_end(self) -> bool:
        """Send notification for break ending.

        Returns:
            True if sent successfully
        """
        message = "⏰ <b>Break Over</b>\n\nReady for the next pomodoro?"
        return self.send_sync(message)

    def notify_day_start(self, planned_pomodoros: int, tasks: list[str]) -> bool:
        """Send notification for day start.

        Args:
            planned_pomodoros: Number of planned pomodoros
            tasks: List of task descriptions

        Returns:
            True if sent successfully
        """
        task_list = "\n".join(f"• {t}" for t in tasks) if tasks else "No tasks set"
        message = (
            f"🌅 <b>Workday Started</b>\n\n"
            f"Plan: {planned_pomodoros} pomodoros\n\n"
            f"<b>Tasks:</b>\n{task_list}"
        )
        return self.send_sync(message)

    def notify_day_complete(
        self,
        completed_pomodoros: int,
        planned_pomodoros: int,
        completed_tasks: int,
        total_tasks: int,
    ) -> bool:
        """Send notification for day completion.

        Args:
            completed_pomodoros: Number of completed pomodoros
            planned_pomodoros: Number of planned pomodoros
            completed_tasks: Number of completed tasks
            total_tasks: Total number of tasks

        Returns:
            True if sent successfully
        """
        goal_met = completed_pomodoros >= planned_pomodoros
        emoji = "🎉" if goal_met else "📊"

        message = (
            f"{emoji} <b>Day Complete</b>\n\n"
            f"Pomodoros: {completed_pomodoros}/{planned_pomodoros}\n"
            f"Tasks: {completed_tasks}/{total_tasks}\n"
        )

        if goal_met:
            message += "\nGoal achieved! Great work! 🏆"
        elif completed_pomodoros > 0:
            message += f"\n{planned_pomodoros - completed_pomodoros} short of goal."

        return self.send_sync(message)

    def notify_timer_paused(self) -> bool:
        """Send notification for timer pause.

        Returns:
            True if sent successfully
        """
        message = "⏸️ <b>Timer Paused</b>\n\nResume when ready."
        return self.send_sync(message)

    def notify_timer_resumed(self, time_remaining: str) -> bool:
        """Send notification for timer resume.

        Args:
            time_remaining: Formatted time remaining

        Returns:
            True if sent successfully
        """
        message = f"▶️ <b>Timer Resumed</b>\n\n{time_remaining} remaining."
        return self.send_sync(message)


async def test_telegram_connection(config: TelegramConfig) -> tuple[bool, str]:
    """Test Telegram bot connection and send test message.

    Args:
        config: Telegram configuration to test

    Returns:
        Tuple of (success, message)
    """
    if not config.bot_token:
        return False, "Bot token not configured"

    if not config.chat_id:
        return False, "Chat ID not configured"

    try:
        from telegram import Bot
        bot = Bot(token=config.bot_token)

        # Verify bot is valid
        me = await bot.get_me()

        # Send test message
        await bot.send_message(
            chat_id=config.chat_id,
            text="🔔 <b>Workday CLI</b>\n\nConnection test successful!",
            parse_mode="HTML",
        )

        return True, f"Connected as @{me.username}"

    except ImportError:
        return False, "python-telegram-bot package not installed"
    except Exception as e:
        return False, f"Connection failed: {e}"


def test_connection_sync(config: TelegramConfig) -> tuple[bool, str]:
    """Synchronous wrapper for test_telegram_connection.

    Args:
        config: Telegram configuration to test

    Returns:
        Tuple of (success, message)
    """
    return asyncio.run(test_telegram_connection(config))
