@AGENTS.md

## Claude Code
- The human tells you your track at session start. If they didn't, ask once.
- Git: you may run status, diff, add and commit on the current track branch. Never push, merge, rebase, reset --hard or force anything; the human does those. This is enforced in .claude/settings.json.
