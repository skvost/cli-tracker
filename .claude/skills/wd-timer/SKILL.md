---
name: wd-timer
description: Start the pomodoro timer for a focus session
allowed-tools: "Bash(wd timer:*),Bash(workday timer:*),Bash(wd status:*)"
disable-model-invocation: true
argument-hint: "[-t task-number]"
---

# Start Pomodoro Timer

Run `wd timer` to start a 25-minute focus session.

```bash
# Start timer (no specific task)
wd timer

# Start timer on task #1
wd timer -t 1

# Start timer on task #2
wd timer -t 2
```

The timer runs in the background and survives terminal disconnection.

## Timer Controls

- `wd pause` - Pause the timer
- `wd resume` - Resume paused timer
- `wd skip` - Skip current period
- `wd stop` - Stop timer completely
- `wd status` - Check current state
