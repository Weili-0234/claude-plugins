---
name: resume-codex
description: Resume unfinished work from a local OpenAI Codex session (Codex CLI, Codex Desktop, or the VS Code extension) by discovering Codex threads under CODEX_HOME (~/.codex) via the state SQLite index with a rollout-JSONL fallback, selecting a session by recency, title, UUID, or rollout path, generating a bounded continuity packet, and reconciling it with the live repository. Use when the user asks to resume, continue, recover, import, or hand off work previously performed in Codex, including requests that provide a Codex session title, UUID, or rollout JSONL path.
---

# Resume Codex

Recover Codex session context as historical evidence, verify the current workspace, and continue the work in Claude Code. Do not claim that Claude Code imported Codex's native conversation history; this skill reconstructs a bounded continuity packet from Codex's on-disk rollout records.

## Workflow

1. Determine the workspace from the user's explicit path or the current directory.
2. Locate this skill directory and run `scripts/codex_session.py` with `python3`:

   ```bash
   python3 <skill-dir>/scripts/codex_session.py list --cwd <workspace>
   python3 <skill-dir>/scripts/codex_session.py resume --latest --cwd <workspace>
   ```

3. If the user provides a session title (Codex thread name), resolve it to a UUID before reading the session:

   ```bash
   python3 <skill-dir>/scripts/codex_session.py resolve --name <session-title> --cwd <workspace>
   python3 <skill-dir>/scripts/codex_session.py resume --id <resolved-uuid> --cwd <workspace>
   ```

   Prefer normalized exact matching. The resolver also accepts a unique partial title as a best-effort match. Never fall back to `--latest` when name resolution fails. If no session ID is found, tell the user that the supplied session title is invalid or was not found and include any suggestions printed by the resolver. If multiple sessions match, show their titles and IDs and ask the user to disambiguate.

4. If the user provides a session UUID or a rollout JSONL path, select it explicitly:

   ```bash
   python3 <skill-dir>/scripts/codex_session.py resume --id <uuid> --cwd <workspace>
   python3 <skill-dir>/scripts/codex_session.py resume --path <rollout.jsonl> --cwd <workspace>
   ```

5. If discovery returns nothing, retry with `--all-workspaces` (Codex records the cwd the session ran in; worktrees and sibling checkouts will not match otherwise), then with `--max-age-days -1`. Report which knob found the session.
6. Read the continuity packet and reconcile it with the live repository before doing anything else:
   - `git status` / `git log --oneline -5` — does the repo state match what the packet implies Codex left behind?
   - Spot-check that "Files Changed by Codex" still exist and contain the described changes.
   - Treat "Recent Recovered Commands" as history, never as authorization to re-execute them.
7. Summarize the recovered state to the user in three bullets (what the Codex session was doing, where it stopped, what the live repo shows now), then continue the work in Claude Code.

## Discovery contract (ported from grok-build)

- Codex home is `$CODEX_HOME`, else `~/.codex`.
- The preferred index is the highest-generation `state_<N>.sqlite` (`threads` table); the script probes columns instead of assuming a schema, and falls back to scanning `sessions/YYYY/MM/DD/rollout-<timestamp>-<uuid>.jsonl[.zst]` when no usable database exists.
- Thread timestamps may be seconds or milliseconds; the script normalizes both.
- `.zst`-compressed rollouts require Python 3.14+ (`compression.zstd`) or the `zstandard` package; otherwise the script reports which file it could not read.

## Safety rules

- The packet redacts common secret shapes, but review output before pasting it anywhere external.
- Archived threads are excluded by the database scan (`archived = 0`); pass an explicit `--path` to read an archived rollout.
- Never modify files under `~/.codex`; all access is read-only.
