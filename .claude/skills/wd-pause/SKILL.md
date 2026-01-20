---
name: wd-pause
description: Pause or resume the running timer
allowed-tools: "Bash(wd pause:*),Bash(wd resume:*),Bash(workday pause:*),Bash(workday resume:*)"
disable-model-invocation: true
---

# Pause/Resume Timer

Control the running timer.

## Pause

```bash
wd pause
```

## Resume

```bash
wd resume
```

The timer maintains its state - when you resume, it continues from where it was paused.
