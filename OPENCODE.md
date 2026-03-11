# OpenCode Automation (Centralized)

This repository is included in centralized hourly automation.

## Control plane

- Runner: `/Users/namyongkim/Desktop/.twodragon0/bin/hourly-opencode-git-pull.sh`
- Cron installer: `/Users/namyongkim/Desktop/.twodragon0/bin/install-system-cron.sh`
- Repo registry: `/Users/namyongkim/Desktop/.twodragon0/repos.list`

## Guardrails

- `git pull --ff-only` only.
- Skip dirty repositories.
- Single-run lock to avoid overlap.
