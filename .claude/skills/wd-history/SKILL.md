---
name: wd-history
description: Show recent workday history
allowed-tools: "Bash(wd history:*),Bash(workday history:*)"
argument-hint: "[-d days]"
---

# Workday History

View your recent workday history.

```bash
# Last 7 days (default)
wd history

# Last 14 days
wd history -d 14

# Last 30 days
wd history -d 30
```

Shows for each day:
- Duration (if tracked)
- Pomodoros completed vs planned
- Breaks taken
- Satisfaction rating
- Notes
