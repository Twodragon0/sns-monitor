# OpenCode Automation (Centralized)

This repository is included in centralized hourly automation.

## Control plane

- Runner: `$HOME/Desktop/.twodragon0/bin/hourly-opencode-git-pull.sh`
- Cron installer: `$HOME/Desktop/.twodragon0/bin/install-system-cron.sh`
- Repo registry: `$HOME/Desktop/.twodragon0/repos.list`
- Path policy: use `$HOME`-based paths (no fixed username paths).

## Guardrails

- `git pull --ff-only` only.
- Skip dirty repositories.
- Single-run lock to avoid overlap.
