"""Main CLI entry point for Workday - pomodoro timer with Telegram notifications."""

import click
from datetime import date, datetime
from typing import Optional

from . import __version__
from .config import ConfigManager, Config, TelegramConfig, get_config_manager
from .display import (
    print_header,
    print_subheader,
    print_day_plan,
    print_tasks,
    print_progress,
    print_day_summary,
    print_setup_complete,
    print_timer_status,
    print_timeline,
    format_time,
)
from .models import Day, Task, TimerStatus
from .storage import Storage
from .telegram_bot import TelegramNotifier, test_connection_sync
from .timer import TimerDaemon, get_timer_status


def get_storage() -> Storage:
    """Get storage instance."""
    cm = get_config_manager()
    cm.ensure_dirs()
    return Storage(cm.db_file)


def require_setup(ctx: click.Context) -> None:
    """Ensure setup has been completed."""
    cm = get_config_manager()
    if not cm.is_configured():
        click.echo("Workday is not configured. Run 'workday setup' first.")
        ctx.exit(1)


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version")
@click.pass_context
def main(ctx: click.Context, version: bool) -> None:
    """Workday - Command-line pomodoro timer with Telegram notifications.

    Use 'workday start' to plan your day and 'workday timer' to begin.
    """
    if version:
        click.echo(f"workday {__version__}")
        return

    if ctx.invoked_subcommand is None:
        # Show status by default
        cm = get_config_manager()
        if not cm.is_configured():
            click.echo("Welcome to Workday!")
            click.echo("Run 'workday setup' to configure.")
            return

        # Show current status
        ctx.invoke(status)


# ============================================================================
# Setup Command
# ============================================================================

@main.command()
@click.option("--telegram-token", prompt=False, help="Telegram bot token")
@click.option("--telegram-chat-id", prompt=False, help="Telegram chat ID")
def setup(telegram_token: Optional[str], telegram_chat_id: Optional[str]) -> None:
    """Configure Workday settings interactively."""
    cm = get_config_manager()
    config = cm.load()

    print_header("Workday Setup")

    # Telegram configuration
    click.echo("\nTelegram notifications (optional)")
    click.echo("To get a bot token, message @BotFather on Telegram")
    click.echo("To get your chat ID, message @userinfobot")

    if telegram_token is None:
        telegram_token = click.prompt(
            "Bot token",
            default=config.telegram.bot_token or "",
            show_default=False,
        )

    if telegram_chat_id is None:
        telegram_chat_id = click.prompt(
            "Chat ID",
            default=config.telegram.chat_id or "",
            show_default=False,
        )

    # Update config
    config.telegram.bot_token = telegram_token.strip()
    config.telegram.chat_id = telegram_chat_id.strip()
    config.telegram.enabled = bool(telegram_token and telegram_chat_id)

    # Test Telegram connection if configured
    if config.telegram.enabled:
        click.echo("\nTesting Telegram connection...")
        success, message = test_connection_sync(config.telegram)
        if success:
            click.secho(f"✓ {message}", fg="green")
        else:
            click.secho(f"✗ {message}", fg="red")
            if click.confirm("Save anyway?", default=True):
                pass
            else:
                config.telegram.enabled = False

    # Timer settings
    print_subheader("Timer Settings")
    click.echo(f"Focus duration: {config.timer.focus_minutes} minutes (default)")
    click.echo(f"Short break: {config.timer.short_break_minutes} minutes (default)")
    click.echo(f"Long break: {config.timer.long_break_minutes} minutes (default)")

    if click.confirm("Customize timer durations?", default=False):
        config.timer.focus_minutes = click.prompt(
            "Focus duration (minutes)", default=config.timer.focus_minutes, type=int
        )
        config.timer.short_break_minutes = click.prompt(
            "Short break (minutes)", default=config.timer.short_break_minutes, type=int
        )
        config.timer.long_break_minutes = click.prompt(
            "Long break (minutes)", default=config.timer.long_break_minutes, type=int
        )

    # Save config
    cm.save(config)
    print_setup_complete()


# ============================================================================
# Day Planning Commands
# ============================================================================

@main.command()
@click.pass_context
def start(ctx: click.Context) -> None:
    """Plan your workday - add tasks and estimate pomodoros."""
    require_setup(ctx)

    storage = get_storage()
    today = storage.get_today()

    if today and today.tasks:
        click.echo(f"You already have a plan for today ({today.date})")
        print_day_plan(today)
        if not click.confirm("Create a new plan?", default=False):
            return
        # Keep existing day, just add more tasks
    else:
        # Create new day
        today = storage.get_or_create_today()

    print_header("Plan Your Workday")

    # Get tasks
    click.echo("\nWhat will you work on today? (Enter blank line when done)")
    tasks = []
    while True:
        task_desc = click.prompt(f"Task {len(tasks) + 1}", default="", show_default=False)
        if not task_desc:
            break
        tasks.append(task_desc)
        if len(tasks) >= 10:
            click.echo("Maximum 10 tasks reached.")
            break

    if not tasks:
        click.echo("No tasks entered. Use 'workday task add' to add tasks later.")
        return

    # Save tasks
    for desc in tasks:
        task = Task(day_id=today.id, description=desc)
        storage.create_task(task)

    # Get pomodoro estimate
    click.echo(f"\nYou have {len(tasks)} tasks.")
    planned = click.prompt(
        "How many pomodoros do you plan to complete?",
        default=len(tasks) * 2,
        type=int,
    )

    today.planned_pomodoros = planned
    storage.update_day(today)

    # Reload day with tasks
    today = storage.get_day(today.id)

    # Show plan
    print_day_plan(today)
    print_timeline(planned)

    # Send Telegram notification
    cm = get_config_manager()
    config = cm.load()
    if config.telegram.enabled:
        notifier = TelegramNotifier(config.telegram)
        notifier.notify_day_start(planned, tasks)
        click.echo("\n📱 Plan sent to Telegram")


# ============================================================================
# Timer Commands
# ============================================================================

@main.command()
@click.option("--task", "-t", type=int, help="Task number to work on")
@click.pass_context
def timer(ctx: click.Context, task: Optional[int]) -> None:
    """Start the pomodoro timer."""
    require_setup(ctx)

    cm = get_config_manager()
    storage = get_storage()

    # Check if timer is already running
    current_state = get_timer_status(cm)
    if current_state and current_state.status != TimerStatus.STOPPED:
        click.echo("Timer is already running.")
        print_timer_status(current_state, cm.load().timer)
        return

    # Get or create today's record
    today = storage.get_or_create_today()

    # Resolve task
    task_id = None
    if task:
        tasks = storage.get_tasks_for_day(today.id)
        if task <= 0 or task > len(tasks):
            click.echo(f"Invalid task number. You have {len(tasks)} tasks.")
            return
        task_id = tasks[task - 1].id
        click.echo(f"Working on: {tasks[task - 1].description}")

    # Determine starting pomodoro number
    starting_pomodoro = storage.get_completed_pomodoro_count(today.id) + 1

    click.echo(f"\nStarting pomodoro #{starting_pomodoro}")
    click.echo("Timer running in background. Use 'workday status' to check progress.")

    # Start daemon
    daemon = TimerDaemon(cm)
    try:
        daemon.start(
            day_id=today.id,
            task_id=task_id,
            starting_pomodoro=starting_pomodoro,
            daemonize=True,
        )
    except RuntimeError as e:
        click.echo(f"Error: {e}")
        ctx.exit(1)


@main.command()
@click.pass_context
def pause(ctx: click.Context) -> None:
    """Pause the running timer."""
    require_setup(ctx)

    cm = get_config_manager()
    daemon = TimerDaemon(cm)

    if daemon.pause():
        click.echo("Timer paused. Use 'workday resume' to continue.")
    else:
        click.echo("Timer is not running or already paused.")


@main.command()
@click.pass_context
def resume(ctx: click.Context) -> None:
    """Resume a paused timer."""
    require_setup(ctx)

    cm = get_config_manager()
    daemon = TimerDaemon(cm)

    if daemon.resume():
        click.echo("Timer resumed.")
    else:
        click.echo("Timer is not paused.")


@main.command()
@click.pass_context
def skip(ctx: click.Context) -> None:
    """Skip current focus or break period."""
    require_setup(ctx)

    cm = get_config_manager()
    daemon = TimerDaemon(cm)

    state = daemon.get_status()
    if not state:
        click.echo("Timer is not running.")
        return

    if state.status == TimerStatus.FOCUS:
        if not click.confirm("Skip current focus session? This won't count the pomodoro."):
            return

    if daemon.skip():
        click.echo("Skipped to next period.")
    else:
        click.echo("Failed to skip.")


@main.command(name="stop")
@click.pass_context
def stop_timer(ctx: click.Context) -> None:
    """Stop the timer completely."""
    require_setup(ctx)

    cm = get_config_manager()
    daemon = TimerDaemon(cm)

    if daemon.stop():
        click.echo("Timer stopped.")
    else:
        click.echo("Timer is not running.")


# ============================================================================
# Status Commands
# ============================================================================

@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current timer status and day progress."""
    require_setup(ctx)

    cm = get_config_manager()
    config = cm.load()
    storage = get_storage()

    # Timer status
    state = get_timer_status(cm)
    if state and state.status != TimerStatus.STOPPED:
        print_timer_status(state, config.timer)

    # Day progress
    today = storage.get_today()
    if today:
        print_progress(today)
    else:
        click.echo("\nNo workday started. Run 'workday start' to plan your day.")


# ============================================================================
# Task Commands
# ============================================================================

@main.group()
def task() -> None:
    """Manage tasks for today."""
    pass


@task.command(name="add")
@click.argument("description")
@click.pass_context
def task_add(ctx: click.Context, description: str) -> None:
    """Add a new task for today."""
    require_setup(ctx)

    storage = get_storage()
    today = storage.get_or_create_today()

    task = Task(day_id=today.id, description=description)
    storage.create_task(task)

    click.echo(f"Added task: {description}")


@task.command(name="done")
@click.argument("number", type=int)
@click.pass_context
def task_done(ctx: click.Context, number: int) -> None:
    """Mark a task as completed."""
    require_setup(ctx)

    storage = get_storage()
    today = storage.get_today()

    if not today:
        click.echo("No workday started.")
        return

    tasks = storage.get_tasks_for_day(today.id)
    if number <= 0 or number > len(tasks):
        click.echo(f"Invalid task number. You have {len(tasks)} tasks.")
        return

    task = tasks[number - 1]
    if task.completed:
        click.echo(f"Task already completed: {task.description}")
        return

    storage.complete_task(task.id)
    click.secho(f"✓ Completed: {task.description}", fg="green")


@task.command(name="list")
@click.pass_context
def task_list(ctx: click.Context) -> None:
    """List today's tasks."""
    require_setup(ctx)

    storage = get_storage()
    today = storage.get_today()

    if not today:
        click.echo("No workday started. Run 'workday start' to plan your day.")
        return

    tasks = storage.get_tasks_for_day(today.id)
    print_tasks(tasks)


# ============================================================================
# End of Day
# ============================================================================

@main.command()
@click.pass_context
def done(ctx: click.Context) -> None:
    """Complete your workday and show summary."""
    require_setup(ctx)

    cm = get_config_manager()
    config = cm.load()
    storage = get_storage()

    # Stop timer if running
    state = get_timer_status(cm)
    if state and state.status != TimerStatus.STOPPED:
        daemon = TimerDaemon(cm)
        daemon.stop()
        click.echo("Timer stopped.")

    # Get today's data
    today = storage.get_today()
    if not today:
        click.echo("No workday to complete.")
        return

    # Update pomodoro count
    today.actual_pomodoros = storage.get_completed_pomodoro_count(today.id)

    # Ask for satisfaction rating
    click.echo("\nHow satisfied are you with today's work?")
    click.echo("  1 - Not satisfied")
    click.echo("  2 - Somewhat satisfied")
    click.echo("  3 - Satisfied")
    click.echo("  4 - Very satisfied")
    satisfaction = click.prompt("Rating", type=click.IntRange(1, 4), default=3)
    today.satisfaction = satisfaction

    # Optional notes
    notes = click.prompt("Any notes for today?", default="", show_default=False)
    today.notes = notes

    storage.update_day(today)

    # Update streak
    streak = storage.update_streak(date.today().isoformat())

    # Reload with tasks
    today = storage.get_day(today.id)

    # Show summary
    print_day_summary(today, streak)

    # Send Telegram notification
    if config.telegram.enabled:
        notifier = TelegramNotifier(config.telegram)
        completed_tasks = sum(1 for t in today.tasks if t.completed)
        notifier.notify_day_complete(
            today.actual_pomodoros,
            today.planned_pomodoros,
            completed_tasks,
            len(today.tasks),
        )
        click.echo("\n📱 Summary sent to Telegram")


# ============================================================================
# Statistics
# ============================================================================

@main.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show overall statistics."""
    require_setup(ctx)

    storage = get_storage()

    print_header("Statistics")

    total_pomodoros = storage.get_total_pomodoros()
    total_days = storage.get_total_days()
    streak = storage.get_streak()

    click.echo(f"\nTotal pomodoros: {total_pomodoros}")
    click.echo(f"Active days: {total_days}")
    click.echo(f"Current streak: {streak.current_streak} days")
    click.echo(f"Longest streak: {streak.longest_streak} days")

    # Recent days
    recent = storage.get_recent_days(7)
    if recent:
        print_subheader("Recent Days")
        for day in recent:
            completed = day.actual_pomodoros
            planned = day.planned_pomodoros
            pct = (completed / planned * 100) if planned > 0 else 0
            status = "✓" if completed >= planned else " "
            click.echo(f"  {status} {day.date}: {completed}/{planned} ({pct:.0f}%)")


# ============================================================================
# History
# ============================================================================

@main.command()
@click.option("--days", "-d", default=7, help="Number of days to show")
@click.pass_context
def history(ctx: click.Context, days: int) -> None:
    """Show recent workday history."""
    require_setup(ctx)

    storage = get_storage()
    recent = storage.get_recent_days(days)

    if not recent:
        click.echo("No history yet.")
        return

    print_header(f"Last {len(recent)} Days")

    for day in recent:
        click.echo(f"\n{day.date}")
        click.echo(f"  Pomodoros: {day.actual_pomodoros}/{day.planned_pomodoros}")
        click.echo(f"  Breaks: {day.email_breaks} email, {day.rest_breaks} rest")
        if day.satisfaction:
            stars = "★" * day.satisfaction + "☆" * (4 - day.satisfaction)
            click.echo(f"  Satisfaction: {stars}")
        if day.notes:
            click.echo(f"  Notes: {day.notes}")


if __name__ == "__main__":
    main()
