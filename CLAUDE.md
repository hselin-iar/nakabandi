@AGENTS.md

## Claude Code
- The human tells you your track at session start. If they didn't, ask once.
- Git: you may run status, diff, add and commit on the current track branch. Never push, merge, rebase, reset --hard or force anything; the human does those. This is enforced in .claude/settings.json.
- If a fix does not work on the first attempt, use the systematic-debugging skill before trying another fix. AGENTS.md step and track rules win over it: no changes outside the current step's scope, and remove temporary diagnostic logging before committing.
- After 3 failed fix attempts, stop and follow the BLOCKED protocol in AGENTS.md. The superpowers:* skills that systematic-debugging mentions are not installed; ignore those references.
