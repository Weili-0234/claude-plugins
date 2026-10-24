# claude-plugins

Personal [Claude Code](https://code.claude.com) plugin marketplace.

## Install

```
/plugin marketplace add Weili-0234/claude-plugins
/plugin install mlsys-code-walkthrough@weili-claude-plugins
/plugin install resume-codex@weili-claude-plugins
/plugin install handoff@weili-claude-plugins
```

## Plugins

| Plugin | What it does |
|---|---|
| [mlsys-code-walkthrough](./mlsys-code-walkthrough) | Skill for writing rigorous ML-systems code walk-through tutorials (Awesome-ML-SYS-Tutorial style): trace the key data structures through one lifecycle — which function touches which structure, tagged Allocate / Write / Update / Free — grounded in commit-pinned permalinks, with mermaid data-flow diagrams and programmatically-authored Excalidraw hero figures (generator kit + render + self-check loop included). |
| [resume-codex](./resume-codex) | Skill for resuming work from a local OpenAI Codex session (CLI, Desktop, VS Code) inside Claude Code. Discovery contract ported from [grok-build](https://github.com/xai-org/grok-build)'s foreign-session scanner: highest-generation `state_<N>.sqlite` thread index first, `sessions/YYYY/MM/DD/rollout-*.jsonl[.zst]` scan as fallback, seconds/millis timestamp normalization, synthetic-turn filtering. Builds a bounded, secret-redacted continuity packet (goals, changed files, errors, transcript tail, recovered commands) and reconciles it with the live repo before continuing. |
| [handoff](./handoff) | Skill for writing a self-contained handoff document when wrapping up or pausing a Claude Code session. Produces `handoff-<timestamp>.md` with eight required sections (Status, Done, Experiments & analyses, Todo, Decisions, Pitfalls, Next, Files), grounded in verified facts (`git status`, `grep`/Read) rather than memory, so another person or a future session can pick up the work cleanly. Since 0.2.0 it also ships a `PostToolUse` hook that asks Claude to run it when context reaches 600k tokens (see [Auto-handoff before auto-compact](#auto-handoff-before-auto-compact)). |

## Auto-handoff before auto-compact

The `handoff` plugin (0.2.0+) registers two hooks (`handoff/hooks/hooks.json`):

- `PostToolUse` runs `hooks/context-handoff-check.py`. When the **main** agent's live context reaches
  `CLAUDE_HANDOFF_TOKENS` (default 600000 in `hooks.json`), it prints a `systemMessage`
  (`Context N tokens ≥ 600,000: asking Claude to run /handoff:handoff before auto-compact.`) and an
  `additionalContext` telling Claude to invoke `handoff:handoff` and then keep working. It fires once per
  compaction cycle and skips subagent tool calls.
- `PostCompact` deletes the per-session sentinel `/tmp/claude-handoff-fired-<session_id>` so the next cycle can fire again.

A plugin cannot set the auto-compact window, so pair it with this in `~/.claude/settings.json` (or a project's
`.claude/settings.local.json`), keeping the compact window above the handoff threshold:

```json
{
  "autoCompactEnabled": true,
  "modelSettings": { "claude-opus-5-5": { "autoCompactWindow": 650000 } }
}
```

A top-level `"autoCompactWindow": 650000` works in project settings too. The 600k threshold only matters on
1M-context models; on a 200k window it never fires. Override the threshold with `CLAUDE_HANDOFF_TOKENS`;
log at `/tmp/claude-context-check.log` (`CLAUDE_HANDOFF_LOG`). If you already copied the hook into a project's
`settings.local.json`, drop it there: the sentinel prevents double firing but the check would run twice.

## Layout

```
.claude-plugin/marketplace.json        # marketplace manifest
mlsys-code-walkthrough/
  .claude-plugin/plugin.json           # plugin manifest
  skills/mlsys-code-walkthrough/
    SKILL.md                           # entry point: the method (six steps) + cardinal rules
    references/                        # per-topic deep dives, loaded on demand
      data-structures.md               #   Shape/Access/Value format, cross-linking via shared indices
      lifecycle-tracing.md             #   the core method: function -> mutation tracing
      diagrams.md                      #   mermaid conventions and templates
      excalidraw-plots.md              #   drawn hero figures: visual grammar, render, self-check
      narrative-and-format.md          #   concept->model->code ordering, bilingual titles, self-check
      finding-the-code.md              #   repo analysis recipes, commit pinning, permalinks
    templates/
      walkthrough-skeleton.md          #   article skeleton to copy
      excalidraw_kit.py                #   element builders for .excalidraw scenes
resume-codex/
  .claude-plugin/plugin.json           # plugin manifest
  skills/resume-codex/
    SKILL.md                           # entry point: workflow + discovery contract + safety rules
    scripts/
      codex_session.py                 #   list / resolve / resume CLI over ~/.codex session stores
handoff/
  .claude-plugin/plugin.json           # plugin manifest
  hooks/
    hooks.json                         # PostToolUse (context threshold) + PostCompact (re-arm) hooks
    context-handoff-check.py           #   threshold check script
  skills/handoff/
    SKILL.md                           # entry point: procedure + required sections + output skeleton
```
