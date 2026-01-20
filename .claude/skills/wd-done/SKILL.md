---
name: wd-done
description: Complete your workday and see summary with duration
allowed-tools: "Bash(wd done:*),Bash(workday done:*)"
disable-model-invocation: true
---

# Complete Your Workday

Run `wd done` to end your workday.

This will:
1. Stop any running timer
2. Show workday duration (start to end time)
3. Ask for satisfaction rating (1-4)
4. Allow optional notes
5. Update your streak
6. Display full summary

```bash
wd done
```

The summary includes:
- Total workday duration
- Pomodoros completed vs planned
- Tasks completed
- Breaks taken
- Current streak
