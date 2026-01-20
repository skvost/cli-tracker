---
name: wd-task
description: Manage today's tasks - add, complete, or list
allowed-tools: "Bash(wd task:*),Bash(workday task:*)"
argument-hint: "[add|done|list] [args]"
---

# Task Management

Manage tasks for today's workday.

## List Tasks

```bash
wd task list
```

## Add a Task

```bash
wd task add "Write documentation"
wd task add "Review pull requests"
```

## Complete a Task

```bash
# Mark task #1 as done
wd task done 1

# Mark task #2 as done
wd task done 2
```

Tasks are numbered in order they were added.
