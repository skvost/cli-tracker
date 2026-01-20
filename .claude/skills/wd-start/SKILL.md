---
name: wd-start
description: Start planning your workday with tasks and pomodoro estimates
allowed-tools: "Bash(wd start:*),Bash(workday start:*)"
disable-model-invocation: true
---

# Plan Your Workday

Run `wd start` to plan your workday interactively.

This will:
1. Prompt you to enter tasks (3-5 recommended)
2. Ask for pomodoro estimate
3. Show timeline for the day
4. Record the start time for duration tracking

```bash
wd start
```

If you already have a plan for today, it will show it and ask if you want to create a new one.
