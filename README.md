# Workday CLI

A command-line pomodoro timer for Linux servers with Telegram notifications.

## Features

- **Pomodoro Timer**: 25-minute focus sessions with 5-minute breaks
- **Daemon Mode**: Timer runs in background, survives terminal disconnection
- **Telegram Notifications**: Get notified when focus/break periods start and end
- **Day Planning**: Plan tasks and estimate pomodoros each morning
- **Progress Tracking**: Track pomodoros, tasks, and streaks
- **Alternating Breaks**: Email breaks and rest breaks for balanced recovery

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd cli-tracker

# Install with pip (editable mode for development)
pip install -e .

# Or install directly
pip install .
```

After installation, both `workday` and `wd` commands are available.

## Quick Start

```bash
# Initial setup (configure Telegram, optional)
workday setup

# Plan your day
workday start

# Start the timer
workday timer

# Check status
workday status

# End your day
workday done
```

## Commands

### Setup & Configuration

```bash
workday setup              # Interactive setup wizard
```

### Day Planning

```bash
workday start              # Plan your day with tasks and pomodoro estimate
```

### Timer Control

```bash
workday timer              # Start the pomodoro timer
workday timer -t 1         # Start timer on task #1
workday pause              # Pause the timer
workday resume             # Resume paused timer
workday skip               # Skip current focus/break period
workday stop               # Stop the timer completely
```

### Status & Progress

```bash
workday status             # Show timer status and day progress
workday stats              # Show overall statistics
workday history            # Show recent workday history
workday history -d 14      # Show last 14 days
```

### Task Management

```bash
workday task list          # List today's tasks
workday task add "Task"    # Add a new task
workday task done 1        # Mark task #1 as completed
```

### End of Day

```bash
workday done               # Complete workday, rate satisfaction, add notes
```

## Telegram Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the bot token
4. Message [@userinfobot](https://t.me/userinfobot) to get your chat ID
5. Run `workday setup` and enter both values

## How It Works

### Timer Flow

1. **Focus** (25 min) - Deep work on your task
2. **Break** (5 min) - Alternates between:
   - **Email Break** - Check inbox, respond to messages
   - **Rest Break** - Step away, stretch, breathe
3. **Long Break** (15 min) - Every 4 pomodoros

### Data Storage

All data is stored in `~/.workday/`:
- `config.toml` - Configuration file
- `workday.db` - SQLite database
- `timer.state` - Current timer state (JSON)
- `timer.pid` - Daemon process ID

## Configuration

Default timer settings can be customized during setup:

| Setting | Default | Description |
|---------|---------|-------------|
| Focus duration | 25 min | Length of focus sessions |
| Short break | 5 min | Length of regular breaks |
| Long break | 15 min | Length of break after 4 pomodoros |

## Tips

- **Start your day** with `workday start` to set intentions
- **Use task numbers** with `workday timer -t 1` to track which task you're on
- **Check status** regularly with `workday status` (or just `workday`)
- **End your day** with `workday done` to review and rate your satisfaction

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT
