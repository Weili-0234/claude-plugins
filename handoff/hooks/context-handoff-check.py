#!/usr/bin/env python3
"""PostToolUse hook: when the MAIN agent's live context passes a token threshold, tell the main agent to
run /handoff:handoff once (per compaction cycle). Auto-compact (autoCompactWindow) then fires on its own
shortly after. The sentinel is cleared by the PostCompact hook.

Design notes (Claude Code 2.1.300+):
1. The hook also runs for subagent tool calls (same session_id and transcript_path), and its message goes
   only to the agent whose tool call triggered it. A call is skipped when its input carries agent_id:
   subagent tool calls have it, the main agent's calls do not. Looking up tool_use_id in the main
   transcript does not work: the main transcript is often written only after this hook runs.
2. Right after a compaction the newest assistant usage in the transcript is still the pre-compaction one,
   so usage older than the newest compact_boundary is ignored.
3. A sentinel older than the newest compact_boundary is removed, in case the PostCompact hook missed it.

Env: CLAUDE_HANDOFF_TOKENS (threshold, default 520000), CLAUDE_HANDOFF_LOG, CLAUDE_HANDOFF_SENTINEL_DIR.
"""
import datetime, json, os, sys, time

THRESHOLD = int(os.environ.get("CLAUDE_HANDOFF_TOKENS", "520000"))
LOG = os.environ.get("CLAUDE_HANDOFF_LOG", "/tmp/claude-context-check.log")
SENTINEL_DIR = os.environ.get("CLAUDE_HANDOFF_SENTINEL_DIR", "/tmp")
TAIL_BYTES = 4_000_000


def read_tail(path):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - TAIL_BYTES))
            return f.read().decode("utf-8", "replace")
    except OSError:
        return None


def scan(text):
    """Newest main-agent context size after the newest compact_boundary, and that boundary's epoch time."""
    tokens, boundary = None, None
    for line in reversed(text.splitlines()):
        if '"compact_boundary"' in line:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("subtype") == "compact_boundary":
                try:
                    boundary = datetime.datetime.fromisoformat(
                        o.get("timestamp", "").replace("Z", "+00:00")).timestamp()
                except ValueError:
                    boundary = None
                break  # everything older is pre-compaction context
        if tokens is None and ('"type":"assistant"' in line or '"type": "assistant"' in line):
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("isSidechain") or o.get("agentId"):
                continue
            u = (o.get("message") or {}).get("usage")
            if u:
                tokens = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                          + u.get("cache_creation_input_tokens", 0) + u.get("output_tokens", 0))
    return tokens, boundary


def caller(inp):
    return "sub:agent_id" if inp.get("agent_id") else "main"


def main():
    try:
        inp = json.load(sys.stdin)
    except Exception:
        return
    sid = inp.get("session_id", "unknown")
    path = inp.get("transcript_path")
    if not path:
        return
    who = caller(inp)
    keys_marker = os.path.join(SENTINEL_DIR, f"claude-handoff-keys-{sid}")
    if not os.path.exists(keys_marker):
        try:
            with open(keys_marker, "w") as f:
                f.write(" ".join(sorted(inp)) + "\n")
        except OSError:
            pass
    if who.startswith("sub"):
        with open(LOG, "a") as lg:
            lg.write(f"{time.strftime('%FT%T')} sid={sid} skip={who} thr={THRESHOLD}\n")
        return
    text = read_tail(path)
    if text is None:
        return
    tokens, boundary = scan(text)
    with open(LOG, "a") as lg:
        lg.write(f"{time.strftime('%FT%T')} sid={sid} tokens={tokens} thr={THRESHOLD} caller={who}\n")
    if tokens is None or tokens < THRESHOLD:
        return
    sentinel = os.path.join(SENTINEL_DIR, f"claude-handoff-fired-{sid}")
    if os.path.exists(sentinel):
        if boundary is not None and boundary > os.path.getmtime(sentinel):
            os.remove(sentinel)  # a compaction happened after the last firing; PostCompact missed it
        else:
            return
    with open(sentinel, "w") as f:
        f.write(str(tokens))
    msg = ("Context has reached the handoff threshold. Before starting new work, invoke the "
           "Skill tool with skill 'handoff:handoff' and finish the handoff. Mention the handoff "
           "path in your next update to the user, then continue the current task; "
           "auto-compaction runs on its own at autoCompactWindow.")
    print(json.dumps({
        "systemMessage": f"Context {tokens:,} tokens ≥ {THRESHOLD:,}: asking Claude to run /handoff:handoff before auto-compact.",
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg},
    }))


if __name__ == "__main__":
    main()
