---
name: wd
description: >
  Pomodoro timer CLI for focused work sessions. Use when user wants to plan
  their day, start focus timers, track tasks, or review productivity.
allowed-tools: "Bash(workday:*),Bash(wd:*)"
---

# Workday CLI - Pomodoro Timer

Command-line pomodoro timer with Telegram notifications. Helps track focused work sessions with alternating breaks.

## Quick Reference

| Command | Description |
|---------|-------------|
| `wd start` | Plan your day with tasks |
| `wd timer` | Start a pomodoro (25min focus) |
| `wd status` | Show current progress |
| `wd pause` / `wd resume` | Control the timer |
| `wd done` | End day and see summary |
| `wd task add "..."` | Add a task |
| `wd task done N` | Complete task #N |

## Typical Workflow

```bash
# Morning: Plan your day
wd start

# Work: Start timer on a task
wd timer -t 1

# Check progress anytime
wd status

# End of day: Review and rate
wd done
```

## Timer Flow

1. **Focus** (25 min) - Deep work
2. **Break** (5 min) - Alternates between:
   - Email break - Check inbox
   - Rest break - Step away, stretch
3. **Long break** (15 min) - Every 4 pomodoros

## All Commands

### Planning
- `wd setup` - Configure Telegram notifications
- `wd start` - Plan day with tasks and pomodoro estimate

### Timer Control
- `wd timer [-t N]` - Start timer (optionally on task N)
- `wd pause` - Pause timer
- `wd resume` - Resume timer
- `wd skip` - Skip current focus/break
- `wd stop` - Stop timer completely

### Progress
- `wd status` - Current timer and day progress
- `wd stats` - Overall statistics
- `wd history [-d N]` - Last N days

### Tasks
- `wd task list` - Show today's tasks
- `wd task add "description"` - Add task
- `wd task done N` - Mark task N complete

### Completion
- `wd done` - End day, rate satisfaction, see summary
