"""Display formatting for Workday CLI - ASCII art, progress bars, and UI."""

import click
from datetime import datetime
from typing import Optional

from .models import Day, Task, TimerState, TimerStatus, BreakType, Streak


# ANSI color codes for terminals
class Colors:
    """Terminal color constants."""
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


TOMATO_ASCII = """
    .-~~-.
   /      \\
  |  .--.  |
  | |    | |
   \\  `--' /
    `----'
"""

TOMATO_SMALL = "🍅"


def format_time(seconds: int) -> str:
    """Format seconds as MM:SS.

    Args:
        seconds: Number of seconds

    Returns:
        Formatted time string
    """
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def progress_bar(current: int, total: int, width: int = 20, filled: str = "█", empty: str = "░") -> str:
    """Create an ASCII progress bar.

    Args:
        current: Current value
        total: Total value
        width: Width of the bar in characters
        filled: Character for filled portion
        empty: Character for empty portion

    Returns:
        Progress bar string
    """
    if total == 0:
        return empty * width

    ratio = min(current / total, 1.0)
    filled_width = int(width * ratio)
    empty_width = width - filled_width
    return filled * filled_width + empty * empty_width


def pomodoro_icons(completed: int, planned: int) -> str:
    """Create pomodoro progress icons.

    Args:
        completed: Number of completed pomodoros
        planned: Number of planned pomodoros

    Returns:
        String of tomato icons
    """
    filled = "●" * completed
    empty = "○" * max(0, planned - completed)
    extra = "●" * max(0, completed - planned)
    return filled + empty + extra


def print_header(text: str) -> None:
    """Print a styled header.

    Args:
        text: Header text
    """
    width = 50
    click.echo()
    click.echo("═" * width)
    click.echo(f" {text}")
    click.echo("═" * width)


def print_subheader(text: str) -> None:
    """Print a styled subheader.

    Args:
        text: Subheader text
    """
    click.echo()
    click.echo(f"── {text} ──")


def print_timer_status(state: TimerState, config_timer: Optional[object] = None) -> None:
    """Print current timer status.

    Args:
        state: Current timer state
        config_timer: Timer configuration for total time calculation
    """
    time_str = format_time(state.time_remaining_seconds)

    if state.status == TimerStatus.STOPPED:
        click.echo("\nTimer is stopped.")
        return

    if state.status == TimerStatus.PAUSED:
        status_text = "PAUSED"
        click.secho(f"\n⏸  {status_text}", fg="yellow", bold=True)
    elif state.status == TimerStatus.FOCUS:
        status_text = "FOCUS TIME"
        click.secho(f"\n🍅 {status_text}", fg="red", bold=True)
    elif state.status == TimerStatus.BREAK:
        if state.break_type == BreakType.EMAIL:
            status_text = "EMAIL BREAK"
            icon = "📧"
        elif state.break_type == BreakType.LONG:
            status_text = "LONG BREAK"
            icon = "☕"
        else:
            status_text = "REST BREAK"
            icon = "🧘"
        click.secho(f"\n{icon} {status_text}", fg="green", bold=True)

    # Time display
    click.echo(f"\n   {time_str}")

    # Progress bar
    if config_timer:
        # Determine total time based on current or paused state
        if state.status == TimerStatus.FOCUS or (state.status == TimerStatus.PAUSED and state.break_type is None):
            total_seconds = config_timer.focus_minutes * 60
        elif state.break_type == BreakType.LONG:
            total_seconds = config_timer.long_break_minutes * 60
        else:
            total_seconds = config_timer.short_break_minutes * 60
        elapsed = total_seconds - state.time_remaining_seconds
        bar = progress_bar(elapsed, total_seconds, width=30)
        click.echo(f"   [{bar}]")

    click.echo(f"\n   Pomodoro #{state.current_pomodoro}")


def print_day_plan(day: Day) -> None:
    """Print the day's plan summary.

    Args:
        day: Day record to display
    """
    print_header(f"Workday Plan - {day.date}")

    click.echo(f"\nPlanned: {day.planned_pomodoros} pomodoros")

    # Calculate estimated end time
    total_minutes = day.planned_pomodoros * 30  # 25 min focus + 5 min break
    from datetime import timedelta
    now = datetime.now()
    end_time = now + timedelta(minutes=total_minutes)
    click.echo(f"Estimated completion: {end_time.strftime('%H:%M')}")

    print_subheader("Tasks")
    if day.tasks:
        for i, task in enumerate(day.tasks, 1):
            status = "✓" if task.completed else "○"
            click.echo(f"  {status} {i}. {task.description}")
    else:
        click.echo("  No tasks planned")


def print_tasks(tasks: list[Task]) -> None:
    """Print task list.

    Args:
        tasks: List of tasks to display
    """
    if not tasks:
        click.echo("No tasks for today.")
        return

    click.echo("\nTasks:")
    for task in tasks:
        status = click.style("✓", fg="green") if task.completed else click.style("○", fg="yellow")
        desc = click.style(task.description, dim=task.completed)
        click.echo(f"  {status} {task.position}. {desc}")


def print_progress(day: Day) -> None:
    """Print day progress summary.

    Args:
        day: Day record with current progress
    """
    completed = day.actual_pomodoros
    planned = day.planned_pomodoros

    print_header(f"Progress - {day.date}")

    # Pomodoro progress
    click.echo(f"\nPomodoros: {completed}/{planned}")
    icons = pomodoro_icons(completed, planned)
    click.echo(f"  {icons}")

    # Progress bar
    bar = progress_bar(completed, planned, width=30)
    pct = (completed / planned * 100) if planned > 0 else 0
    click.echo(f"  [{bar}] {pct:.0f}%")

    # Breaks
    click.echo(f"\nBreaks: {day.email_breaks} email, {day.rest_breaks} rest")

    # Tasks
    if day.tasks:
        completed_tasks = sum(1 for t in day.tasks if t.completed)
        click.echo(f"\nTasks: {completed_tasks}/{len(day.tasks)} completed")
        print_tasks(day.tasks)


def print_day_summary(day: Day, streak: Streak) -> None:
    """Print end of day summary.

    Args:
        day: Day record to summarize
        streak: Current streak data
    """
    print_header(f"Day Complete - {day.date}")

    # Duration
    duration = day.duration_formatted()
    if duration:
        click.echo(f"\nWorkday duration: {duration}")
        if day.started_at and day.ended_at:
            click.echo(f"  {day.started_at.strftime('%H:%M')} - {day.ended_at.strftime('%H:%M')}")

    # Pomodoros
    completed = day.actual_pomodoros
    planned = day.planned_pomodoros
    click.echo(f"\nPomodoros: {completed}/{planned} completed")
    icons = pomodoro_icons(completed, planned)
    click.echo(f"  {icons}")

    if completed >= planned:
        click.secho("  ✨ Goal achieved!", fg="green", bold=True)
    elif completed > 0:
        click.echo(f"  {planned - completed} short of goal")

    # Task summary
    if day.tasks:
        completed_tasks = sum(1 for t in day.tasks if t.completed)
        click.echo(f"\nTasks: {completed_tasks}/{len(day.tasks)} completed")
        for task in day.tasks:
            status = click.style("✓", fg="green") if task.completed else click.style("✗", fg="red")
            click.echo(f"  {status} {task.description}")

    # Breaks
    click.echo(f"\nBreaks taken:")
    click.echo(f"  📧 Email: {day.email_breaks}")
    click.echo(f"  🧘 Rest: {day.rest_breaks}")

    # Streak
    click.echo(f"\nStreak: {streak.current_streak} day{'s' if streak.current_streak != 1 else ''}")
    if streak.current_streak == streak.longest_streak and streak.current_streak > 1:
        click.secho("  🏆 Personal best!", fg="yellow", bold=True)

    # Satisfaction
    if day.satisfaction:
        stars = "★" * day.satisfaction + "☆" * (4 - day.satisfaction)
        click.echo(f"\nSatisfaction: {stars}")


def print_setup_complete() -> None:
    """Print setup completion message."""
    click.echo()
    click.secho("✓ Setup complete!", fg="green", bold=True)
    click.echo()
    click.echo("Get started:")
    click.echo("  workday start  - Plan your day")
    click.echo("  workday timer  - Start a pomodoro")
    click.echo("  workday status - Check progress")
    click.echo("  workday --help - See all commands")


def print_notification_preview(message_type: str, message: str) -> None:
    """Print a preview of what notification will be sent.

    Args:
        message_type: Type of notification
        message: Message content
    """
    click.echo(f"\n📱 Telegram ({message_type}):")
    click.echo(f"   {message}")


def print_timeline(planned_pomodoros: int, start_time: Optional[datetime] = None) -> None:
    """Print estimated timeline for the day.

    Args:
        planned_pomodoros: Number of planned pomodoros
        start_time: Starting time (defaults to now)
    """
    from datetime import timedelta

    if start_time is None:
        start_time = datetime.now()

    click.echo("\nTimeline:")

    current_time = start_time
    for i in range(1, planned_pomodoros + 1):
        # Focus block
        focus_end = current_time + timedelta(minutes=25)
        click.echo(f"  {current_time.strftime('%H:%M')}-{focus_end.strftime('%H:%M')} 🍅 Pomodoro #{i}")

        # Break
        current_time = focus_end
        if i < planned_pomodoros:
            break_type = "📧" if i % 2 == 1 else "🧘"
            break_end = current_time + timedelta(minutes=5)
            click.echo(f"  {current_time.strftime('%H:%M')}-{break_end.strftime('%H:%M')} {break_type} Break")
            current_time = break_end

    click.echo(f"\nEstimated finish: {current_time.strftime('%H:%M')}")
