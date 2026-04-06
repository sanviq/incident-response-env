---
title: Incident Response Env
emoji: 🚨
colorFrom: red
colorTo: pink
sdk: docker
pinned: false
tags:
  - openenv
---

# 🚨 Incident Response Triage Environment

An OpenEnv environment where an AI agent acts as an on-call SRE, responding to real-world production system alerts.

## Tasks

- **classify-alert** (Easy): Classify a single alert as low/medium/critical
- **select-remediation** (Medium): Pick the correct fix from 4 options
- **cascading-alerts** (Hard): Prioritise and resolve 3 simultaneous alerts

## API

- `POST /reset` — start a new episode
- `POST /step` — send an action
- `GET /state` — current state
- `GET /health` — health check

## Baseline Scores

| Task | Score |
|------|-------|
| classify-alert | 0.72 |
| select-remediation | 0.65 |
| cascading-alerts | 0.58 |
