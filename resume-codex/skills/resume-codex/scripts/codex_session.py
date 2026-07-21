#!/usr/bin/env python3
"""Discover OpenAI Codex sessions and build bounded continuity packets.

Discovery contract ported from grok-build's foreign-session scanner
(crates/codegen/xai-grok-workspace/src/foreign_sessions/codex/):

- Codex home is $CODEX_HOME, else ~/.codex.
- Preferred index: the highest-generation state_<N>.sqlite database,
  table `threads` (columns are probed, not assumed). Falls back to
  scanning sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl[.zst] files.
- `updated_at` may be seconds or milliseconds; values below
  2020-01-01 in millis are treated as seconds.
- `source` is 'cli', 'vscode', or JSON like {"custom":"atlas"}.
- The first user message skips synthetic <environment_context> /
  <user_instructions> turns.
"""

from __future__ import annotations

import argparse
import difflib
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

DEFAULT_MAX_AGE_DAYS = 30
DEFAULT_MAX_SESSIONS = 50
DEFAULT_MESSAGES = 32
DEFAULT_MAX_TEXT_CHARS = 4_000
DEFAULT_MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_DB_CANDIDATES = 200
# Wider than grok-build's 10-record/64KiB head: Codex Desktop rollouts put
# ~90KiB of session_meta + synthetic context before the first user message.
MAX_HEAD_RECORDS = 64
MAX_HEAD_BYTES = 256 * 1024
ALLOWED_DB_SOURCES = ("cli", "vscode", '{"custom":"atlas"}', '{"custom":"chatgpt"}')
# Millis below this are actually seconds (grok-build's MIN_EPOCH_MILLIS, 2020-01-01).
MIN_EPOCH_MILLIS = 1_577_836_800_000
ROLLOUT_NAME = re.compile(
    r"^rollout-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})-([0-9a-fA-F-]{36})\.jsonl(\.zst)?$"
)
# grok-build filters the first two; newer Codex versions inject more
# synthetic user-role turns (plugin ads, AGENTS.md, permission banners).
SYNTHETIC_PREFIXES = (
    "<environment_context>",
    "<user_instructions>",
    "<permissions",
    "<recommended_plugins>",
    "<collaboration_mode",
    "# AGENTS.md instructions",
)
SHELL_TOOL_NAMES = {"shell", "local_shell", "exec_command", "container.exec", "shell_command"}

SECRET_PATTERNS = (
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{12,})\b"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"\b(AKIA[0-9A-Z]{16})\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]{12,}"), r"\1[REDACTED_TOKEN]"),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)"
            r"(\s*[:=]\s*)['\"]?[^\s'\",;]{8,}"
        ),
        r"\1\2[REDACTED]",
    ),
)


@dataclass
class SessionInfo:
    session_id: str
    rollout_path: str
    cwd: str
    updated_at: str
    title: str
    branch: str | None
    source: str
    origin: str  # "db" or "files"
    size_bytes: int


def redact(text: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def compact_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    text = redact(text)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def codex_home(override: str | None = None) -> Path:
    if override:
        return canonical(Path(override))
    configured = os.environ.get("CODEX_HOME")
    return canonical(Path(configured) if configured else Path.home() / ".codex")


def git_output(cwd: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def workspace_paths(cwd: Path) -> list[Path]:
    paths = [canonical(cwd)]
    root = git_output(cwd, "rev-parse", "--show-toplevel")
    if root:
        paths.append(canonical(Path(root)))
    common = git_output(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common:
        common_path = canonical(Path(common))
        if common_path.name == ".git":
            paths.append(common_path.parent)
    seen: set[Path] = set()
    return [path for path in paths if not (path in seen or seen.add(path))]


def iso_from_epoch(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def normalize_updated_at(value: int) -> float:
    """Return epoch seconds from a seconds-or-millis integer."""
    millis = value * 1_000 if value < MIN_EPOCH_MILLIS else value
    return millis / 1_000


def normalize_source(value: Any) -> str | None:
    if isinstance(value, str):
        if value in ("cli", "vscode"):
            return value
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return None
    if isinstance(value, dict):
        custom = value.get("custom")
        if custom in ("atlas", "chatgpt"):
            return custom
    return None


def rollout_id_from_name(path: Path) -> str | None:
    match = ROLLOUT_NAME.match(path.name)
    if not match:
        return None
    try:
        return str(uuid.UUID(match.group(2)))
    except ValueError:
        return None


def existing_rollout_path(root: Path, value: str, expected_id: str) -> Path | None:
    """Resolve a DB rollout_path to a real file under sessions/ or archived_sessions/."""
    raw = Path(value)
    if ".." in raw.parts:
        return None
    base = raw if raw.is_absolute() else root / raw
    allowed = [canonical(root / name) for name in ("sessions", "archived_sessions")]
    for candidate in (base, Path(str(base) + ".zst")):
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_file():
            continue
        if rollout_id_from_name(resolved) != expected_id:
            continue
        if any(resolved.is_relative_to(prefix) for prefix in allowed):
            return resolved
    return None


def open_rollout_text(path: Path) -> io.TextIOBase:
    """Open a rollout JSONL, transparently decompressing .zst when supported."""
    if path.suffix == ".zst":
        try:
            from compression.zstd import ZstdFile  # Python >= 3.14

            return io.TextIOWrapper(ZstdFile(path), encoding="utf-8", errors="replace")
        except ImportError:
            pass
        try:
            import zstandard

            handle = path.open("rb")
            reader = zstandard.ZstdDecompressor().stream_reader(handle)
            return io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
        except ImportError as error:
            raise OSError(
                f"cannot read {path.name}: install Python 3.14+ or the 'zstandard' package"
            ) from error
    return path.open("r", encoding="utf-8", errors="replace")


def payload_of(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload")
    return payload if isinstance(payload, dict) else {}


def response_item_user_text(payload: dict[str, Any]) -> str:
    """Extract genuine user text from a response_item message record."""
    if payload.get("type") != "message" or payload.get("role") != "user":
        return ""
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") in ("input_text", "text") and isinstance(item.get("text"), str):
            text = item["text"]
            if not text.strip().startswith(SYNTHETIC_PREFIXES):
                return text
            return ""
    return ""


@dataclass
class HeadMetadata:
    session_id: str | None = None
    cwd: str | None = None
    source: str | None = None
    branch: str | None = None
    first_user_message: str = ""


def parse_head(path: Path) -> HeadMetadata | None:
    metadata = HeadMetadata()
    fallback_user_text = ""
    total = 0
    try:
        with open_rollout_text(path) as handle:
            for _ in range(MAX_HEAD_RECORDS):
                line = handle.readline()
                if not line:
                    break
                total += len(line)
                if total > MAX_HEAD_BYTES:
                    break
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                payload = payload_of(record)
                if record.get("type") == "session_meta" and metadata.session_id is None:
                    raw_id = payload.get("id") or payload.get("session_id")
                    metadata.session_id = raw_id if isinstance(raw_id, str) else None
                    stored_cwd = payload.get("cwd")
                    metadata.cwd = stored_cwd if isinstance(stored_cwd, str) else None
                    metadata.source = normalize_source(payload.get("source"))
                    git_info = payload.get("git")
                    branch = None
                    if isinstance(git_info, dict):
                        branch = git_info.get("branch")
                    branch = branch or payload.get("git_branch")
                    metadata.branch = branch if isinstance(branch, str) and branch else None
                # Genuine user input arrives as a user_message event; user-role
                # response items are often synthetic context, so keep them only
                # as a fallback for older rollout formats.
                if not metadata.first_user_message:
                    if payload.get("type") == "user_message" and isinstance(
                        payload.get("message"), str
                    ):
                        metadata.first_user_message = payload["message"]
                    elif not fallback_user_text:
                        fallback_user_text = response_item_user_text(payload)
                if metadata.session_id and metadata.first_user_message:
                    break
    except OSError:
        return None
    if not metadata.first_user_message:
        metadata.first_user_message = fallback_user_text
    return metadata


def state_databases(root: Path) -> list[Path]:
    """Highest-generation state_<N>.sqlite first."""
    found: list[tuple[int, Path]] = []
    for path in root.glob("state_*.sqlite"):
        match = re.fullmatch(r"state_(\d+)\.sqlite", path.name)
        if match and path.is_file():
            found.append((int(match.group(1)), path))
    return [path for _, path in sorted(found, reverse=True)]


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return set()
    return {row[1] for row in rows}


def scan_database(db_path: Path, root: Path) -> list[dict[str, Any]] | None:
    """Return raw thread rows from one state DB, or None if unusable."""
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
    except sqlite3.Error:
        return None
    try:
        columns = table_columns(connection, "threads")
        required = {"id", "rollout_path", "source", "cwd", "archived"}
        if not required <= columns:
            return None
        updated_column = (
            "updated_at_ms"
            if "updated_at_ms" in columns
            else "updated_at"
            if "updated_at" in columns
            else None
        )
        if updated_column is None:
            return None
        title_column = "title" if "title" in columns else "''"
        first_column = "first_user_message" if "first_user_message" in columns else "''"
        branch_column = "git_branch" if "git_branch" in columns else "NULL"
        placeholders = ", ".join("?" for _ in ALLOWED_DB_SOURCES)
        sql = (
            f"SELECT id, rollout_path, {updated_column}, source, cwd, "
            f"{title_column}, {first_column}, {branch_column} "
            "FROM threads "
            "WHERE typeof(id) = 'text' AND typeof(rollout_path) = 'text' "
            f"  AND typeof({updated_column}) = 'integer' "
            "  AND typeof(archived) = 'integer' AND archived = 0 "
            f"  AND source IN ({placeholders}) "
            f"ORDER BY {updated_column} DESC, id ASC LIMIT {MAX_DB_CANDIDATES}"
        )
        try:
            rows = connection.execute(sql, ALLOWED_DB_SOURCES).fetchall()
        except sqlite3.Error:
            return None
    finally:
        connection.close()
    threads = []
    for row in rows:
        threads.append(
            {
                "id": row[0],
                "rollout_path": row[1],
                "updated_at": row[2],
                "source": row[3],
                "cwd": row[4],
                "title": row[5] if isinstance(row[5], str) else "",
                "first_user_message": row[6] if isinstance(row[6], str) else "",
                "branch": row[7] if isinstance(row[7], str) and row[7] else None,
            }
        )
    return threads


def db_sessions(
    root: Path,
    requested_cwds: set[str],
    max_age_days: int,
    session_id: str | None,
) -> list[SessionInfo] | None:
    """Sessions from the newest usable state DB; None means fall back to files."""
    now = datetime.now(timezone.utc).timestamp()
    for db_path in state_databases(root):
        rows = scan_database(db_path, root)
        if rows is None:
            continue
        sessions: list[SessionInfo] = []
        for row in rows:
            try:
                native_id = str(uuid.UUID(row["id"]))
            except (ValueError, TypeError):
                continue
            if session_id and native_id != session_id:
                continue
            source = normalize_source(row["source"])
            if source is None:
                continue
            if requested_cwds and str(canonical(Path(row["cwd"]))) not in requested_cwds:
                continue
            updated_seconds = normalize_updated_at(row["updated_at"])
            if max_age_days >= 0 and (now - updated_seconds) / 86_400 > max_age_days:
                continue
            rollout = existing_rollout_path(root, row["rollout_path"], native_id)
            if rollout is None:
                continue
            title = compact_text(row["title"], 200) or compact_text(
                row["first_user_message"], 200
            )
            sessions.append(
                SessionInfo(
                    session_id=native_id,
                    rollout_path=str(rollout),
                    cwd=row["cwd"],
                    updated_at=iso_from_epoch(updated_seconds),
                    title=title or "Untitled Codex session",
                    branch=compact_text(row["branch"] or "", 200) or None,
                    source=source,
                    origin="db",
                    size_bytes=rollout.stat().st_size,
                )
            )
        if sessions:
            return sessions
    return None


def rollout_files(root: Path, session_id: str | None) -> Iterator[Path]:
    for base in ("sessions", "archived_sessions"):
        base_dir = root / base
        if not base_dir.is_dir():
            continue
        pattern = (
            f"*/*/*/rollout-*-{session_id}.jsonl*" if session_id else "*/*/*/rollout-*.jsonl*"
        )
        yield from base_dir.glob(pattern)


def file_sessions(
    root: Path,
    requested_cwds: set[str],
    max_age_days: int,
    session_id: str | None,
    limit: int,
) -> list[SessionInfo]:
    now = datetime.now(timezone.utc).timestamp()
    candidates: list[tuple[float, str, Path]] = []
    for path in rollout_files(root, session_id):
        native_id = rollout_id_from_name(path)
        if native_id is None or path.is_symlink() or not path.is_file():
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if max_age_days >= 0 and (now - mtime) / 86_400 > max_age_days:
            continue
        candidates.append((mtime, native_id, path))
    candidates.sort(key=lambda item: (-item[0], item[1]))

    sessions: list[SessionInfo] = []
    seen_ids: set[str] = set()
    for mtime, native_id, path in candidates:
        if native_id in seen_ids:
            continue
        metadata = parse_head(path)
        if metadata is None or metadata.session_id is None:
            continue
        try:
            if str(uuid.UUID(metadata.session_id)) != native_id:
                continue
        except ValueError:
            continue
        if metadata.cwd is None or metadata.source is None:
            continue
        if requested_cwds and str(canonical(Path(metadata.cwd))) not in requested_cwds:
            continue
        seen_ids.add(native_id)
        sessions.append(
            SessionInfo(
                session_id=native_id,
                rollout_path=str(path),
                cwd=metadata.cwd,
                updated_at=iso_from_epoch(mtime),
                title=compact_text(metadata.first_user_message, 200)
                or "Untitled Codex session",
                branch=compact_text(metadata.branch or "", 200) or None,
                source=metadata.source,
                origin="files",
                size_bytes=path.stat().st_size,
            )
        )
        if len(sessions) >= limit:
            break
    return sessions


def discover_sessions(args: argparse.Namespace) -> list[SessionInfo]:
    root = codex_home(args.codex_home)
    cwd = canonical(Path(args.cwd))
    requested = set() if args.all_workspaces else {str(path) for path in workspace_paths(cwd)}
    session_id = getattr(args, "id", None)
    if session_id:
        try:
            session_id = str(uuid.UUID(session_id))
        except ValueError as error:
            raise ValueError(f"--id must be a UUID: {session_id}") from error
    sessions: list[SessionInfo] | None = None
    if args.scan in ("auto", "db"):
        sessions = db_sessions(root, requested, args.max_age_days, session_id)
    if sessions is None and args.scan in ("auto", "files"):
        sessions = file_sessions(root, requested, args.max_age_days, session_id, args.limit)
    sessions = sessions or []
    sessions.sort(key=lambda item: (item.updated_at, item.session_id), reverse=True)
    return sessions[: args.limit]


def normalize_session_name(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def format_candidates(sessions: Iterable[SessionInfo], limit: int = 8) -> str:
    values = list(sessions)[:limit]
    return "; ".join(f"{item.title!r} ({item.session_id})" for item in values)


def resolve_session_name(name: str, sessions: list[SessionInfo]) -> SessionInfo:
    query = normalize_session_name(name)
    if not query:
        raise ValueError("session name is empty after normalization; no session ID found")
    exact = [item for item in sessions if normalize_session_name(item.title) == query]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(
            "session name is ambiguous; matching session IDs: " + format_candidates(exact)
        )
    partial = [item for item in sessions if query in normalize_session_name(item.title)]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        raise ValueError(
            "session name is ambiguous; partial matches: " + format_candidates(partial)
        )
    by_norm: dict[str, list[SessionInfo]] = {}
    for item in sessions:
        by_norm.setdefault(normalize_session_name(item.title), []).append(item)
    close = difflib.get_close_matches(query, by_norm.keys(), n=5, cutoff=0.55)
    suggestions = [item for value in close for item in by_norm[value]]
    detail = f"; closest sessions: {format_candidates(suggestions, 5)}" if suggestions else ""
    raise ValueError(f"no session ID found for session name {name!r}{detail}")


def add_unique(items: list[str], value: str, limit: int) -> None:
    value = value.strip()
    if value and value not in items and len(items) < limit:
        items.append(value)


def add_recent_unique(items: deque[str], value: str) -> None:
    value = value.strip()
    if not value:
        return
    try:
        items.remove(value)
    except ValueError:
        pass
    items.append(value)


def shell_command_text(arguments: Any) -> str:
    if not isinstance(arguments, str):
        return ""
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    command = parsed.get("command") or parsed.get("cmd")
    if isinstance(command, list):
        return " ".join(str(part) for part in command)
    if isinstance(command, str):
        return command
    return ""


def output_error_text(output: Any, limit: int) -> str:
    """Return a snippet when a tool output records a non-zero exit."""
    if not isinstance(output, str):
        return ""
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    metadata = parsed.get("metadata")
    exit_code = metadata.get("exit_code") if isinstance(metadata, dict) else None
    if exit_code in (None, 0):
        return ""
    body = parsed.get("output")
    snippet = compact_text(body if isinstance(body, str) else output, limit)
    return f"exit_code={exit_code}: {snippet}" if snippet else f"exit_code={exit_code}"


def build_packet(info: SessionInfo, args: argparse.Namespace) -> dict[str, Any]:
    path = Path(info.rollout_path)
    if info.size_bytes > args.max_file_bytes:
        raise ValueError(
            f"session is {info.size_bytes} bytes, above --max-file-bytes={args.max_file_bytes}"
        )
    meta: dict[str, Any] = {}
    context: dict[str, Any] = {}
    summaries: list[str] = []
    goals: deque[str] = deque(maxlen=6)
    files: deque[str] = deque(maxlen=40)
    commands: deque[str] = deque(maxlen=12)
    errors: deque[str] = deque(maxlen=12)
    transcript: deque[dict[str, str]] = deque(maxlen=args.messages)
    fallback_transcript: deque[dict[str, str]] = deque(maxlen=args.messages)
    tool_counts: Counter[str] = Counter()
    aborted_turns = 0
    compactions = 0

    with open_rollout_text(path) as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            record_type = record.get("type")
            payload = payload_of(record)

            if record_type == "session_meta" and not meta:
                for key in ("id", "cwd", "originator", "cli_version", "timestamp"):
                    value = payload.get(key)
                    if isinstance(value, str):
                        meta[key] = value
                meta["source"] = normalize_source(payload.get("source")) or "unknown"
            elif record_type == "turn_context":
                for key in ("model", "approval_policy", "cwd", "effort"):
                    value = payload.get(key)
                    if isinstance(value, str):
                        context[key] = value
                sandbox = payload.get("sandbox_policy")
                if isinstance(sandbox, dict) and isinstance(sandbox.get("type"), str):
                    context["sandbox_policy"] = sandbox["type"]
            elif record_type == "compacted":
                compactions += 1
                message = payload.get("message")
                if isinstance(message, str):
                    summary = compact_text(message, args.max_text_chars)
                    if summary:
                        add_unique(summaries, summary, 8)
            elif record_type == "event_msg":
                event_type = payload.get("type")
                if event_type == "user_message" and isinstance(payload.get("message"), str):
                    text = compact_text(payload["message"], args.max_text_chars)
                    if text:
                        transcript.append(
                            {"role": "user", "text": text, "line": str(line_number)}
                        )
                elif event_type == "agent_message" and isinstance(payload.get("message"), str):
                    text = compact_text(payload["message"], args.max_text_chars)
                    if text:
                        transcript.append(
                            {"role": "assistant", "text": text, "line": str(line_number)}
                        )
                elif event_type == "patch_apply_end":
                    changes = payload.get("changes")
                    if isinstance(changes, dict):
                        for changed_path in changes:
                            if isinstance(changed_path, str):
                                add_recent_unique(files, redact(changed_path))
                elif event_type == "turn_aborted":
                    aborted_turns += 1
                elif event_type == "thread_goal_updated":
                    goal = payload.get("goal") or payload.get("text")
                    if isinstance(goal, dict):
                        objective = goal.get("objective")
                        status = goal.get("status")
                        goal = (
                            f"[{status}] {objective}"
                            if isinstance(objective, str)
                            else json.dumps(goal, default=str)
                        )
                    goal_text = compact_text(
                        goal if isinstance(goal, str) else json.dumps(payload, default=str),
                        min(args.max_text_chars, 600),
                    )
                    if goal_text:
                        add_recent_unique(goals, goal_text)
            elif record_type == "response_item":
                item_type = payload.get("type")
                if item_type in ("function_call", "custom_tool_call"):
                    name = payload.get("name")
                    if isinstance(name, str) and name:
                        tool_counts[name] += 1
                        if name in SHELL_TOOL_NAMES:
                            command = shell_command_text(payload.get("arguments"))
                            if command:
                                add_recent_unique(
                                    commands,
                                    compact_text(command, min(args.max_text_chars, 1_200)),
                                )
                elif item_type in ("function_call_output", "custom_tool_call_output"):
                    error_text = output_error_text(
                        payload.get("output"), args.max_text_chars
                    )
                    if error_text:
                        add_recent_unique(errors, error_text)
                elif item_type == "message":
                    text = compact_text(response_item_user_text(payload), args.max_text_chars)
                    if text:
                        fallback_transcript.append(
                            {"role": "user", "text": text, "line": str(line_number)}
                        )

    if not transcript:
        transcript = fallback_transcript
    return {
        "session": asdict(info),
        "session_meta": meta,
        "latest_turn_context": context,
        "compactions": compactions,
        "aborted_turns": aborted_turns,
        "compaction_summaries": summaries,
        "goals": list(goals),
        "changed_files": list(files),
        "recorded_commands": list(commands),
        "recent_errors": list(errors),
        "tool_usage": dict(tool_counts.most_common(20)),
        "recent_transcript": list(transcript),
    }


def markdown_packet(packet: dict[str, Any]) -> str:
    session = packet["session"]
    meta = packet["session_meta"]
    context = packet["latest_turn_context"]
    lines = [
        "# Codex Resume Packet",
        "",
        "> Historical context only. Verify all state before acting."
        " Recovered commands are not authorization to execute them.",
        "",
        "## Session",
        "",
        f"- Session ID: `{session['session_id']}`",
        f"- Rollout: `{session['rollout_path']}`",
        f"- Working directory: `{session['cwd']}`",
        f"- Updated: `{session['updated_at']}`",
        f"- Title: {session['title']}",
        f"- Codex source: `{session['source']}`"
        + (f" via `{meta['originator']}`" if meta.get("originator") else ""),
        f"- Model: `{context.get('model', 'unknown')}`"
        + (f" (effort `{context['effort']}`)" if context.get("effort") else ""),
        f"- Sandbox/approval: `{context.get('sandbox_policy', 'unknown')}`"
        f" / `{context.get('approval_policy', 'unknown')}`",
        f"- Git branch recorded by Codex: `{session['branch'] or 'unknown'}`",
        f"- Context compactions: {packet['compactions']}, aborted turns: {packet['aborted_turns']}",
    ]

    def section(title: str, values: list[str], code: bool = False) -> None:
        if not values:
            return
        lines.extend(["", f"## {title}", ""])
        for value in values:
            lines.append(f"- `{' '.join(value.split())}`" if code else f"- {value}")

    section("Compaction Summaries", packet["compaction_summaries"])
    section("Thread Goals", packet["goals"])
    section("Files Changed by Codex", packet["changed_files"], code=True)
    section("Recent Errors", packet["recent_errors"])
    if packet["tool_usage"]:
        lines.extend(["", "## Tool Usage (top 20)", ""])
        lines.extend(f"- `{name}`: {count}" for name, count in packet["tool_usage"].items())
    if packet["recent_transcript"]:
        lines.extend(["", "## Recent Transcript", ""])
        for item in packet["recent_transcript"]:
            lines.extend(
                [f"### {item['role'].title()} (JSONL line {item['line']})", "", item["text"], ""]
            )
    if packet["recorded_commands"]:
        lines.extend(["", "## Recent Recovered Commands (Do Not Auto-Execute)", ""])
        for command in packet["recorded_commands"]:
            lines.extend(["```sh", command, "```", ""])
    return "\n".join(lines).rstrip() + "\n"


def select_session(args: argparse.Namespace) -> SessionInfo:
    root = codex_home(args.codex_home)
    if args.path:
        raw_path = canonical(Path(args.path))
        native_id = rollout_id_from_name(raw_path)
        if native_id is None or not raw_path.is_file():
            raise ValueError(
                f"--path must be an existing rollout-<ts>-<uuid>.jsonl[.zst] file: {raw_path}"
            )
        if not raw_path.is_relative_to(root):
            raise ValueError(f"session path must live under {root}: {raw_path}")
        metadata = parse_head(raw_path)
        if metadata is None or metadata.session_id is None:
            raise ValueError(f"could not parse session_meta from {raw_path}")
        requested = set() if args.all_workspaces else {
            str(item) for item in workspace_paths(canonical(Path(args.cwd)))
        }
        stored_cwd = metadata.cwd or ""
        if requested and str(canonical(Path(stored_cwd))) not in requested:
            raise ValueError(
                "session working directory does not match --cwd; use --all-workspaces to override"
            )
        return SessionInfo(
            session_id=str(uuid.UUID(metadata.session_id)),
            rollout_path=str(raw_path),
            cwd=stored_cwd,
            updated_at=iso_from_epoch(raw_path.stat().st_mtime),
            title=compact_text(metadata.first_user_message, 200) or "Untitled Codex session",
            branch=metadata.branch,
            source=metadata.source or "unknown",
            origin="files",
            size_bytes=raw_path.stat().st_size,
        )
    sessions = discover_sessions(args)
    if not sessions:
        detail = f" with ID {args.id}" if args.id else ""
        if args.name:
            detail = f" with name {args.name!r}; no session ID found"
        raise ValueError(f"no matching Codex sessions found{detail}")
    if args.name:
        return resolve_session_name(args.name, sessions)
    if not args.latest and not args.id and len(sessions) > 1:
        raise ValueError("multiple sessions match; pass --latest, --name, --id, or --path")
    return sessions[0]


def print_session_list(sessions: list[SessionInfo], as_json: bool) -> None:
    if as_json:
        print(json.dumps([asdict(session) for session in sessions], indent=2, ensure_ascii=False))
        return
    if not sessions:
        print("No matching Codex sessions found.")
        return
    for session in sessions:
        branch = session.branch or "-"
        print(
            f"{session.updated_at}\t{session.session_id}\t{session.source}\t{branch}"
            f"\t{session.title}\t{session.rollout_path}"
        )


def print_resolved_session(session: SessionInfo, as_json: bool) -> None:
    if as_json:
        print(json.dumps(asdict(session), indent=2, ensure_ascii=False))
        return
    print(f"{session.session_id}\t{session.title}\t{session.rollout_path}")


def add_discovery_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    default_limit: int = DEFAULT_MAX_SESSIONS,
) -> None:
    parser.add_argument("--cwd", default=os.getcwd(), help="Workspace used to match sessions")
    parser.add_argument("--all-workspaces", action="store_true", help="Do not filter by workspace")
    parser.add_argument("--max-age-days", type=int, default=default_max_age_days)
    parser.add_argument("--limit", type=int, default=default_limit)
    parser.add_argument(
        "--scan",
        choices=("auto", "db", "files"),
        default="auto",
        help="auto: state DB first, rollout-file scan as fallback",
    )
    parser.add_argument("--codex-home", default=None, help="Override $CODEX_HOME / ~/.codex")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("list", help="List matching Codex sessions")
    add_discovery_arguments(listing)
    listing.add_argument("--json", action="store_true", help="Emit JSON")

    resolver = subparsers.add_parser("resolve", help="Resolve a session name to a UUID")
    add_discovery_arguments(resolver, default_max_age_days=-1, default_limit=500)
    resolver.add_argument("--name", required=True, help="Codex session title")
    resolver.add_argument("--json", action="store_true", help="Emit JSON")

    resume = subparsers.add_parser("resume", help="Build a continuity packet")
    add_discovery_arguments(resume, default_max_age_days=-1, default_limit=500)
    selection = resume.add_mutually_exclusive_group(required=True)
    selection.add_argument("--latest", action="store_true", help="Select the newest matching session")
    selection.add_argument("--name", help="Resolve and select a Codex session title")
    selection.add_argument("--id", help="Select a Codex session UUID")
    selection.add_argument("--path", help="Select a Codex rollout JSONL path")
    resume.add_argument("--messages", type=int, default=DEFAULT_MESSAGES)
    resume.add_argument("--max-text-chars", type=int, default=DEFAULT_MAX_TEXT_CHARS)
    resume.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    resume.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.limit <= 0:
            raise ValueError("--limit must be positive")
        if args.command == "list":
            print_session_list(discover_sessions(args), args.json)
            return 0
        if args.command == "resolve":
            sessions = discover_sessions(args)
            if not sessions:
                raise ValueError(
                    f"no session ID found for session name {args.name!r} in workspace {args.cwd}"
                )
            print_resolved_session(resolve_session_name(args.name, sessions), args.json)
            return 0
        if args.messages <= 0 or args.max_text_chars <= 0 or args.max_file_bytes <= 0:
            raise ValueError("packet limits must be positive")
        packet = build_packet(select_session(args), args)
        if args.json:
            print(json.dumps(packet, indent=2, ensure_ascii=False))
        else:
            print(markdown_packet(packet), end="")
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
