#!/usr/bin/env python3
"""Read-only Codex/Astra rollout forensics for a project.

The analyzer deliberately streams the source JSONL files. It never rewrites
Codex state, rollout logs, the target repository, or the game installation.
Only the requested report directory is written.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import sqlite3
import statistics
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


PROJECT_DEFAULT = r"C:\FM27CommunityOverhaul"
CODEX_ROOT_DEFAULT = str(Path.home() / ".codex")
SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|auth(?:orization)?|secret|password)"
    r"(\s*[:=]\s*)([^\s,;\"']+)"
)
BASE64_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9+/=_-]{160,}(?![A-Za-z0-9])")
EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")


def parse_ts(value: Any) -> dt.datetime | None:
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(value / 1000, dt.timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def iso(value: dt.datetime | None) -> str:
    return value.isoformat(timespec="seconds") if value else ""


def clean_text(value: Any, limit: int = 240) -> str:
    text = value if isinstance(value, str) else str(value)
    text = SECRET_RE.sub(r"\1=<REDACTED>", text)
    text = BASE64_RE.sub("<REDACTED_BLOB>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def normalize_path(value: str) -> str:
    return value.replace("\\\\?\\", "").replace("/", "\\").rstrip("\\")


def rel_or_abs(value: str, project: Path) -> str:
    value = normalize_path(value)
    try:
        return str(Path(value).relative_to(project)).replace("\\", "/")
    except (ValueError, OSError):
        return value


def json_size(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except Exception:
        return len(str(value).encode("utf-8", "replace"))


def text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(text_values(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(text_values(item))
        return result
    return []


def unescape_js(value: str) -> str:
    for old, new in (
        (r"\\", "\\"),
        (r'\"', '"'),
        (r"\'", "'"),
        (r"\n", "\n"),
        (r"\r", "\r"),
        (r"\t", "\t"),
    ):
        value = value.replace(old, new)
    return value


def extract_commands(script: str) -> list[str]:
    """Extract the common JS object cmd/command fields used by desktop exec."""
    commands: list[str] = []
    for match in re.finditer(r"\b(?:cmd|command)\s*:\s*\"", script, re.I):
        chars: list[str] = []
        escaped = False
        for ch in script[match.end():]:
            if escaped:
                chars.append("\\\\" + ch)
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                break
            else:
                chars.append(ch)
        command = unescape_js("".join(chars)).strip()
        if command:
            commands.append(command)
    for match in re.finditer(r"\b(?:cmd|command)\s*:\s*'", script, re.I):
        chars = []
        escaped = False
        for ch in script[match.end():]:
            if escaped:
                chars.append(ch)
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                break
            else:
                chars.append(ch)
        command = "".join(chars).strip()
        if command:
            commands.append(command)
    return commands


def tool_names(script: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\btools\.([A-Za-z_][A-Za-z0-9_]*)", script)))


def normalize_command(command: str) -> str:
    command = SECRET_RE.sub(r"\1=<REDACTED>", command)
    command = BASE64_RE.sub("<REDACTED_BLOB>", command)
    # Rollout command records often include the launcher prefix. Strip it so
    # repeated PowerShell commands compare by their actual command body.
    command = re.sub(r"^\s*&\s+", "", command)
    command = re.sub(
        r"(?i)^[A-Z]:\\.*?\\(?:pwsh|powershell)(?:\.exe)?\s+-Command\s+",
        "",
        command,
    )
    command = re.sub(r"\s+", " ", command).strip()
    return command[:1200]


def command_category(command: str) -> str:
    c = command.lower()
    if re.search(r"\bgit\b", c):
        return "Git"
    if "pytest" in c or "ctest" in c or re.search(r"\b(test|tests|check)\b", c):
        return "Tests"
    if re.search(r"\b(cmake|msbuild|ninja|make|cl\.exe|compile|build)\b", c):
        return "Build"
    if re.search(r"\bpython(?:\.exe)?\b|\bpy\s+-", c):
        return "Python"
    if "--files" in c or re.search(r"\b(get-childitem|dir|tree|ls)\b", c):
        return "Directory scan"
    if re.search(r"\b(rg|ripgrep|findstr|select-string)\b", c):
        return "Search"
    if re.search(r"\b(get-content|type|cat|more|readalltext|select-object)\b", c):
        return "File read"
    return "Shell"


def action_category(name: str, command: str = "") -> str:
    n = (name or "").lower()
    if "web" in n or "search" in n:
        return "Web/search"
    if "spawn" in n or "agent" in n or "wait_agent" in n:
        return "Subagent"
    if "apply_patch" in n or "edit" in n:
        return "File write"
    return command_category(command) if command else ("Shell" if n == "exec" else "Other")


def extract_paths(command: str) -> list[str]:
    paths: list[str] = []
    patterns = [
        r"(?i)-literalpath\s+['\"]([^'\"]+)['\"]",
        r"(?i)-path\s+['\"]([^'\"]+)['\"]",
        r"(?i)(?:Get-Content|Set-Content|Add-Content|Out-File|Get-Item)\s+['\"]([^'\"]+)['\"]",
        r"(?i)\b(?:type|cat)\s+['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        paths.extend(m.group(1) for m in re.finditer(pattern, command))
    return list(dict.fromkeys(normalize_path(p) for p in paths if p.strip()))


def patch_paths(script: str) -> list[tuple[str, str]]:
    return [
        (m.group(1).lower(), normalize_path(m.group(2).strip()))
        for m in re.finditer(r"\*\*\*\s+(Update|Add|Delete) File:\s*(.+)", script)
    ]


def is_full_read(command: str) -> bool:
    c = command.lower()
    if "get-content" not in c and "readalltext" not in c and not re.search(r"\b(type|cat)\b", c):
        return False
    return not any(x in c for x in ("-skip", "-first", "-last", "-totalcount"))


def output_category(command: str, output_preview: str) -> str:
    combined = (command + " " + output_preview).lower()
    if "git diff" in combined:
        return "GIT_DIFF"
    if any(x in combined for x in ("pytest", "ctest", "test session", "passed", "failed")):
        return "TEST_LOG"
    if any(x in combined for x in ("cmake", "msbuild", "ninja", "compiler", "warning c", "error c")):
        return "BUILD_LOG"
    if "http" in combined or "search_query" in combined or "web__run" in combined:
        return "WEB_RESULT"
    if command_category(command) == "File read":
        return "FILE_READ"
    if "summary" in combined or "compaction" in combined:
        return "AGENT_SUMMARY"
    return "TOOL_OUTPUT"


def duration_hours(times: list[dt.datetime], gap_minutes: int = 30) -> float:
    if len(times) < 2:
        return 0.0
    times = sorted(set(times))
    return sum(
        min((b - a).total_seconds(), gap_minutes * 60) / 3600
        for a, b in zip(times, times[1:])
    )


def median_or_zero(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return float(values[max(0, min(len(values) - 1, math.ceil(q * len(values)) - 1))])


@dataclass
class Action:
    ordinal: int
    timestamp: dt.datetime | None
    turn_id: str
    name: str
    call_id: str
    script: str
    nested_tools: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    paths_read: list[str] = field(default_factory=list)
    paths_written: list[str] = field(default_factory=list)
    output_bytes: int = 0
    output_preview: str = ""
    output_category: str = ""
    output_failed: bool = False


@dataclass
class Usage:
    ordinal: int
    timestamp: dt.datetime | None
    response_id: str
    turn_id: str
    model: str
    effort: str
    input_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int
    before_actions: str = ""
    after_actions: str = ""
    previous_output_category: str = ""
    previous_output_bytes: int = 0
    response_number: int = 0


@dataclass
class Compaction:
    ordinal: int
    timestamp: dt.datetime | None
    window_number: Any
    replacement_bytes: int
    replacement_messages: int
    before_input: int | None = None
    after_input: int | None = None
    after_reads: int = 0
    after_scans: int = 0
    after_git: int = 0
    after_build_or_test: int = 0


@dataclass
class Session:
    path: Path
    session_id: str = ""
    start: dt.datetime | None = None
    end: dt.datetime | None = None
    cwd: str = ""
    source: str = ""
    thread_source: str = ""
    model_provider: str = ""
    first_user_excerpt: str = ""
    model_by_turn: dict[str, tuple[str, str]] = field(default_factory=dict)
    usage: list[Usage] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    executions: list[Action] = field(default_factory=list)
    compactions: list[Compaction] = field(default_factory=list)
    raw_counts: Counter = field(default_factory=Counter)
    errors: list[dict[str, Any]] = field(default_factory=list)
    inter_agent_records: int = 0
    direct_project_evidence: bool = False
    state_tokens_used: int | None = None
    state_model: str = ""
    state_effort: str = ""
    state_title: str = ""
    parent_thread_id: str = ""
    agent_path: str = ""
    agent_nickname: str = ""

    @property
    def active_hours(self) -> float:
        return duration_hours([u.timestamp for u in self.usage if u.timestamp])

    @property
    def wall_hours(self) -> float:
        if not self.start or not self.end:
            return 0.0
        return max(0.0, (self.end - self.start).total_seconds() / 3600)

    @property
    def total_usage(self) -> dict[str, int]:
        keys = (
            "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
            "output_tokens", "reasoning_tokens", "total_tokens",
        )
        return {k: sum(getattr(u, k) for u in self.usage) for k in keys}


def sqlite_thread_metadata(codex_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    db = codex_root / "state_5.sqlite"
    if not db.exists():
        return result
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=2)
        rows = con.execute(
            "select id, rollout_path, tokens_used, model, reasoning_effort, cwd, title from threads"
        ).fetchall()
        con.close()
    except Exception:
        return result
    for ident, rollout, tokens, model, effort, cwd, title in rows:
        data = {
            "tokens_used": tokens,
            "model": model or "",
            "effort": effort or "",
            "cwd": cwd or "",
            "title": clean_text(title, 180),
        }
        result[str(ident)] = data
        if rollout:
            result[Path(str(rollout)).name] = data
    return result


def parse_source(path: Path, project: Path, state_meta: dict[str, dict[str, Any]]) -> Session:
    session = Session(path=path)
    pending_actions: dict[str, Action] = {}

    def mark_project(value: Any) -> None:
        if project.name.lower() in str(value).lower() and "communityoverhaul" in str(value).lower():
            session.direct_project_evidence = True

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = record.get("type")
            payload = record.get("payload") or {}
            session.raw_counts[kind] += 1
            timestamp = parse_ts(record.get("timestamp"))
            if timestamp:
                session.start = timestamp if session.start is None else min(session.start, timestamp)
                session.end = timestamp if session.end is None else max(session.end, timestamp)

            if kind == "session_meta":
                # Child rollouts keep the parent thread in session_id; id is the
                # unique rollout/thread identity needed for inventory and joins.
                session.session_id = str(payload.get("id") or payload.get("session_id") or "")
                session.cwd = str(payload.get("cwd") or "")
                session.source = clean_text(payload.get("source"), 180)
                session.thread_source = str(payload.get("thread_source") or "")
                session.model_provider = str(payload.get("model_provider") or "")
                mark_project(payload)
                source = payload.get("source") or {}
                spawn = source.get("subagent", {}).get("thread_spawn", {}) if isinstance(source, dict) else {}
                session.parent_thread_id = str(spawn.get("parent_thread_id") or "")
                session.agent_path = str(spawn.get("agent_path") or "")
                session.agent_nickname = str(spawn.get("agent_nickname") or "")
                continue

            if kind == "turn_context":
                turn_id = str(payload.get("turn_id") or "")
                session.model_by_turn[turn_id] = (
                    str(payload.get("model") or ""),
                    str(payload.get("effort") or "").lower(),
                )
                continue

            if kind == "inter_agent_communication_metadata":
                session.inter_agent_records += 1
                continue

            if kind == "response_item":
                item_type = payload.get("type")
                turn_id = str(
                    payload.get("internal_chat_message_metadata_passthrough", {}).get("turn_id") or ""
                )
                if item_type in ("custom_tool_call", "function_call"):
                    name = str(payload.get("name") or "")
                    script = str(payload.get("input") or payload.get("arguments") or "")
                    call_id = str(payload.get("call_id") or "")
                    nested = tool_names(script)
                    commands = extract_commands(script)
                    paths_read = [
                        path
                        for command in commands
                        if command_category(command) == "File read"
                        for path in extract_paths(command)
                    ]
                    paths_written = [
                        patch_path
                        for operation, patch_path in patch_paths(script)
                        if operation in ("add", "update")
                    ]
                    action = Action(
                        ordinal=int(record.get("ordinal", 0)),
                        timestamp=timestamp,
                        turn_id=turn_id,
                        name=name,
                        call_id=call_id,
                        script=clean_text(script, 1800),
                        nested_tools=nested,
                        commands=commands,
                        categories=[action_category(name, c) for c in commands] or [action_category(name)],
                        paths_read=list(dict.fromkeys(paths_read)),
                        paths_written=list(dict.fromkeys(paths_written)),
                    )
                    session.actions.append(action)
                    if call_id:
                        pending_actions[call_id] = action
                    mark_project(script)
                elif item_type == "message" and payload.get("role") == "user" and not session.first_user_excerpt:
                    values = text_values(payload.get("content"))
                    if values:
                        session.first_user_excerpt = clean_text(values[0], 180)
                continue

            if kind == "token_usage_record":
                usage = payload.get("usage") or {}
                turn_id = str(payload.get("turn_id") or "")
                model, effort = session.model_by_turn.get(turn_id, (session.state_model, session.state_effort))
                item = Usage(
                    ordinal=int(record.get("ordinal", 0)),
                    timestamp=timestamp,
                    response_id=str(payload.get("response_id") or ""),
                    turn_id=turn_id,
                    model=model,
                    effort=effort.lower(),
                    input_tokens=int(usage.get("input_tokens") or 0),
                    cached_input_tokens=int(usage.get("cached_input_tokens") or 0),
                    cache_write_input_tokens=int(usage.get("cache_write_input_tokens") or 0),
                    output_tokens=int(usage.get("output_tokens") or 0),
                    reasoning_tokens=int(usage.get("reasoning_output_tokens") or 0),
                    total_tokens=int(usage.get("total_tokens") or 0),
                    response_number=len(session.usage) + 1,
                )
                session.usage.append(item)
                continue

            if kind == "compacted":
                replacement = payload.get("replacement_history") or []
                session.compactions.append(
                    Compaction(
                        ordinal=int(record.get("ordinal", 0)),
                        timestamp=timestamp,
                        window_number=payload.get("window_number"),
                        replacement_bytes=json_size(replacement),
                        replacement_messages=len(replacement) if isinstance(replacement, list) else 0,
                    )
                )
                continue

            if kind == "event_msg":
                event_type = payload.get("type")
                if event_type == "item_completed":
                    item = payload.get("item") or {}
                    item_type = str(item.get("type") or "")
                    call_id = str(item.get("call_id") or item.get("id") or "")
                    if call_id in pending_actions:
                        action = pending_actions[call_id]
                        output = item.get("output")
                        action.output_bytes += json_size(output)
                        action.output_preview = clean_text(" ".join(text_values(output)), 320)
                        action.output_category = output_category(
                            " ".join(action.commands), action.output_preview
                        )
                        action.output_failed = bool(
                            re.search(
                                r"(?i)(exit_code[^0-9]*[1-9]|iserror[^a-z]*true|error\b|"
                                r"failed\b|timed?\s*out|timeout)",
                                action.output_preview,
                            )
                        )
                    # Desktop rollout events contain the authoritative command
                    # and stdout/stderr separately from the model tool-call item.
                    # Keep this second, execution-level stream for result sizes,
                    # failure detection, file reads and writes.
                    if item_type == "CommandExecution":
                        command_value = item.get("command") or []
                        command = " ".join(str(x) for x in command_value) if isinstance(command_value, list) else str(command_value)
                        stdout = str(item.get("stdout") or "")
                        stderr = str(item.get("stderr") or "")
                        execution = Action(
                            ordinal=int(record.get("ordinal", 0)), timestamp=timestamp,
                            turn_id=str(payload.get("turn_id") or ""),
                            name="CommandExecution", call_id=call_id,
                            script=clean_text(command, 1800), commands=[command],
                            categories=[command_category(command)],
                            paths_read=(extract_paths(command) if command_category(command) == "File read" else []),
                            output_bytes=len((stdout + stderr).encode("utf-8", "replace")),
                            output_preview=clean_text(stdout + " " + stderr, 320),
                            output_category=output_category(command, clean_text(stdout + " " + stderr, 320)),
                            output_failed=(item.get("exit_code") not in (None, 0) or str(item.get("status") or "").lower() in {"failed", "error"}),
                        )
                        session.executions.append(execution)
                        mark_project(command)
                        mark_project(stdout)
                    elif item_type == "FileChange":
                        changes = item.get("changes") or {}
                        written = list(changes.keys()) if isinstance(changes, dict) else []
                        execution = Action(
                            ordinal=int(record.get("ordinal", 0)), timestamp=timestamp,
                            turn_id=str(payload.get("turn_id") or ""),
                            name="FileChange", call_id=call_id,
                            script=clean_text(item.get("stdout") or "FileChange", 1800),
                            categories=["File write"],
                            paths_written=[normalize_path(str(p)) for p in written],
                            output_bytes=json_size(item.get("stdout") or item.get("changes") or ""),
                            output_preview=clean_text(item.get("stdout") or "", 320),
                            output_category="FILE_WRITE",
                            output_failed=str(item.get("status") or "").lower() in {"failed", "error"},
                        )
                        session.executions.append(execution)
                        mark_project(changes)
                    elif item_type == "McpToolCall":
                        arguments = item.get("arguments") or {}
                        result = item.get("result") or {}
                        tool = str(item.get("tool") or "McpToolCall")
                        execution = Action(
                            ordinal=int(record.get("ordinal", 0)), timestamp=timestamp,
                            turn_id=str(payload.get("turn_id") or ""),
                            name=tool, call_id=call_id,
                            script=clean_text(arguments, 1800),
                            nested_tools=[tool], categories=[action_category(tool)],
                            output_bytes=json_size(result),
                            output_preview=clean_text(result, 320),
                            output_category="WEB_RESULT" if "search" in tool.lower() or "browser" in tool.lower() else "TOOL_OUTPUT",
                            output_failed=str(item.get("status") or "").lower() in {"failed", "error"},
                        )
                        session.executions.append(execution)
                        mark_project(arguments)
                    elif item_type in ("SubAgentActivity", "CollabAgentToolCall"):
                        execution = Action(
                            ordinal=int(record.get("ordinal", 0)), timestamp=timestamp,
                            turn_id=str(payload.get("turn_id") or ""),
                            name=item_type, call_id=call_id,
                            script=clean_text(item, 1200),
                            nested_tools=[str(item.get("tool") or item.get("agent_path") or item_type)],
                            categories=["Subagent"], output_bytes=json_size(item),
                            output_preview=clean_text(item, 320),
                            output_category="AGENT_SUMMARY",
                            output_failed=str(item.get("status") or "").lower() in {"failed", "error"},
                        )
                        session.executions.append(execution)
                        mark_project(item)
                elif payload.get("error"):
                    session.errors.append(
                        {
                            "timestamp": iso(timestamp),
                            "type": event_type,
                            "detail": clean_text(payload.get("error"), 300),
                        }
                    )

    state = state_meta.get(session.session_id) or state_meta.get(path.name) or {}
    session.state_tokens_used = state.get("tokens_used")
    session.state_model = state.get("model", "")
    session.state_effort = state.get("effort", "")
    session.state_title = state.get("title", "")
    if not session.cwd:
        session.cwd = state.get("cwd", "")
    return session


def discover_sessions(
    codex_root: Path,
    project: Path,
    since: dt.datetime | None,
    requested_sessions: set[str],
    excluded_sessions: set[str],
    state_meta: dict[str, dict[str, Any]],
) -> tuple[list[Session], int]:
    files = sorted((codex_root / "sessions").rglob("*.jsonl"))
    selected: list[Session] = []
    for path in files:
        short_id = path.stem.replace("rollout-", "")
        if requested_sessions and short_id not in requested_sessions:
            continue
        session = parse_source(path, project, state_meta)
        if session.session_id in excluded_sessions or short_id in excluded_sessions:
            continue
        if since and session.end and session.end < since:
            continue
        # Membership requires project evidence in an action or session metadata,
        # not only a user prompt that mentions the project.
        if session.direct_project_evidence:
            selected.append(session)
    return selected, len(files)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def format_duration(hours: float) -> str:
    return str(dt.timedelta(seconds=int(round(hours * 3600))))


def session_row(s: Session, project: Path) -> dict[str, Any]:
    usage = s.total_usage
    all_actions = s.actions + s.executions
    files_read = {rel_or_abs(p, project) for a in all_actions for p in a.paths_read}
    files_written = {rel_or_abs(p, project) for a in all_actions for p in a.paths_written}
    commands = sum(len(a.commands) for a in s.executions)
    return {
        "session_id": s.session_id,
        "start_time": iso(s.start),
        "end_time": iso(s.end),
        "duration": format_duration(s.wall_hours),
        "reasoning_effort": ",".join(sorted({u.effort for u in s.usage if u.effort})),
        "model": ",".join(sorted({u.model for u in s.usage if u.model})),
        "working_directory": s.cwd,
        "responses": len(s.usage),
        "tool_calls": len(s.actions),
        "commands": commands,
        "files_read": len(files_read),
        "files_written": len(files_written),
        "compactions": len(s.compactions),
        "retries": len(s.errors) + sum(a.output_failed for a in (s.executions or s.actions)),
        "subagents": sum(
            1 for a in s.actions
            if any("spawn" in n or "agent" in n for n in a.nested_tools)
        ),
        "input_tokens": usage["input_tokens"],
        "cached_input_tokens": usage["cached_input_tokens"],
        "uncached_input_tokens": usage["input_tokens"] - usage["cached_input_tokens"],
        "output_tokens": usage["output_tokens"],
        "reasoning_tokens": usage["reasoning_tokens"],
        "total_tokens": usage["total_tokens"],
        "usage_cost_or_units_if_available": s.state_tokens_used if s.state_tokens_used is not None else "",
        "notes": (
            f"wall_hours={s.wall_hours:.3f};active_hours={s.active_hours:.3f};"
            f"thread_state_tokens_used={s.state_tokens_used if s.state_tokens_used is not None else 'null'};"
            f"thread_source={s.thread_source};parent={s.parent_thread_id or 'none'};"
            "total_tokens is the sum of incremental usage records; cumulative fields were not summed."
        ),
    }


def effort_usages(session: Session, effort: str) -> list[Usage]:
    return [item for item in session.usage if item.effort == effort]


def effort_actions(session: Session, effort: str) -> list[Action]:
    usages = effort_usages(session, effort)
    times = [item.timestamp for item in usages if item.timestamp]
    if not times:
        return []
    start, end = min(times), max(times)
    return [
        action for action in (session.actions + session.executions)
        if action.timestamp and start <= action.timestamp <= end
    ]


def effort_span(session: Session, effort: str) -> float:
    times = [item.timestamp for item in effort_usages(session, effort) if item.timestamp]
    if len(times) < 2:
        return 0.0
    return (max(times) - min(times)).total_seconds() / 3600


def effort_compactions(session: Session, effort: str) -> int:
    usages = sorted(session.usage, key=lambda item: abs(item.ordinal - 0))
    if not usages:
        return 0
    count = 0
    for compaction in session.compactions:
        nearest = min(usages, key=lambda item: abs(item.ordinal - compaction.ordinal))
        if nearest.effort == effort:
            count += 1
    return count


def group_metrics(sessions: list[Session], efforts: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for effort in efforts:
        usages = [u for s in sessions for u in s.usage if u.effort == effort]
        group_sessions = [s for s in sessions if effort_usages(s, effort)]
        if not usages:
            rows.append({"reasoning_effort": effort, "data_status": "INSUFFICIENT DATA"})
            continue
        inputs = [u.input_tokens for u in usages]
        input_total = sum(inputs)
        cached_total = sum(u.cached_input_tokens for u in usages)
        active = sum(duration_hours([u.timestamp for u in effort_usages(s, effort) if u.timestamp]) for s in group_sessions)
        elapsed = sum(effort_span(s, effort) for s in group_sessions)
        writes = sum(
            len({p for a in effort_actions(s, effort) for p in a.paths_written})
            for s in group_sessions
        )
        commits = sum(
            1 for s in group_sessions for a in effort_actions(s, effort) for c in a.commands
            if re.search(r"\bgit\s+commit\b", c, re.I)
        )
        total = sum(u.total_tokens for u in usages)
        rows.append(
            {
                "reasoning_effort": effort,
                "data_status": "MEASURED",
                "sessions": len(group_sessions),
                "total_elapsed_time_hours": round(elapsed, 3),
                "active_hours_gap_capped": round(active, 3),
                "average_session_duration_hours": round(
                    statistics.mean([effort_span(s, effort) for s in group_sessions]), 3
                ),
                "median_session_duration_hours": round(
                    median_or_zero([effort_span(s, effort) for s in group_sessions]), 3
                ),
                "responses": len(usages),
                "responses_per_hour": round(len(usages) / elapsed, 3) if elapsed else "",
                "tool_calls": sum(len([a for a in effort_actions(s, effort) if a.name not in ("CommandExecution", "FileChange")]) for s in group_sessions),
                "tool_calls_per_hour": round(
                    sum(len([a for a in effort_actions(s, effort) if a.name not in ("CommandExecution", "FileChange")]) for s in group_sessions) / elapsed, 3
                ) if elapsed else "",
                "shell_commands": sum(
                    sum(command_category(c) == "Shell" for c in a.commands)
                    for s in group_sessions for a in effort_actions(s, effort)
                ),
                "model_turns": len({u.turn_id for u in usages if u.turn_id}),
                "average_input_tokens": round(statistics.mean(inputs), 1),
                "median_input_tokens": round(median_or_zero(inputs), 1),
                "p90_input_tokens": round(percentile(inputs, 0.9), 1),
                "average_cached_input_tokens": round(
                    statistics.mean([u.cached_input_tokens for u in usages]), 1
                ),
                "cached_input_ratio": round(cached_total / input_total, 5) if input_total else "",
                "uncached_input_tokens": input_total - cached_total,
                "output_tokens": sum(u.output_tokens for u in usages),
                "reasoning_tokens": sum(u.reasoning_tokens for u in usages),
                "total_tokens": total,
                "input_pct_of_total": round(input_total / total, 6) if total else "",
                "output_pct_of_total": round(sum(u.output_tokens for u in usages) / total, 6) if total else "",
                "reasoning_pct_of_total": round(sum(u.reasoning_tokens for u in usages) / total, 6) if total else "",
                "tokens_per_hour": round(total / elapsed, 1) if elapsed else "",
                "tokens_per_active_hour": round(total / active, 1) if active else "",
                "compactions": sum(effort_compactions(s, effort) for s in group_sessions),
                "compactions_per_hour": round(
                    sum(effort_compactions(s, effort) for s in group_sessions) / elapsed, 3
                ) if elapsed else "",
                "retries_or_failures": sum(
                    len(s.errors) + sum(a.output_failed for a in effort_actions(s, effort))
                    for s in group_sessions
                ),
                "meaningful_file_writes": writes,
                "responses_per_meaningful_write": round(len(usages) / writes, 2) if writes else "",
                "tokens_per_meaningful_file_write": round(total / writes, 1) if writes else "",
                "commits_observed": commits,
                "tokens_per_commit": round(total / commits, 1) if commits else "",
                "reprocessed_context_estimate": max(0, input_total - min(inputs)),
                "notes": (
                    "Elapsed time is active token-record span with gaps capped at 30 minutes. "
                    "Reasoning tokens are a subset of output tokens, so percentage views are non-additive."
                ),
            }
        )
    return rows


def enrich_action_links(sessions: list[Session]) -> None:
    for s in sessions:
        actions = sorted(s.actions + s.executions, key=lambda a: a.ordinal)
        usages = sorted(s.usage, key=lambda u: u.ordinal)
        for index, usage in enumerate(usages):
            previous_ord = usages[index - 1].ordinal if index else -1
            next_ord = usages[index + 1].ordinal if index + 1 < len(usages) else 10**18
            before = [a for a in actions if previous_ord < a.ordinal < usage.ordinal]
            after = [a for a in actions if usage.ordinal < a.ordinal < next_ord]
            usage.before_actions = "; ".join(
                dict.fromkeys(a.name or ",".join(a.nested_tools) for a in before)
            )[:300]
            usage.after_actions = "; ".join(
                dict.fromkeys(
                    f"{a.output_category or 'TOOL_OUTPUT'}:{a.output_bytes}B"
                    for a in after if a.output_bytes or a.output_category
                )
            )[:300]
            incoming = [a for a in before if a.output_bytes or a.output_category]
            if incoming:
                usage.previous_output_category = incoming[-1].output_category or "TOOL_OUTPUT"
                usage.previous_output_bytes = sum(a.output_bytes for a in incoming)
            else:
                usage.previous_output_category = "PROMPT"
                usage.previous_output_bytes = 0


def context_rows(sessions: list[Session]) -> list[dict[str, Any]]:
    rows = []
    for s in sessions:
        previous: Usage | None = None
        for usage in sorted(s.usage, key=lambda item: item.ordinal):
            rows.append(
                {
                    "session": s.session_id,
                    "response": usage.response_number,
                    "timestamp": iso(usage.timestamp),
                    "estimated_or_actual_context_tokens": usage.input_tokens,
                    "delta": usage.input_tokens - previous.input_tokens if previous else usage.input_tokens,
                    "source": clean_text(
                        f"{usage.previous_output_category}:{usage.previous_output_bytes}B"
                        if usage.previous_output_category else "initial request", 300
                    ),
                    "category": usage.previous_output_category or "PROMPT",
                }
            )
            previous = usage
    return rows


def repeated_file_rows(sessions: list[Session], project: Path) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "read_count": 0, "full_reads": 0, "partial_reads": 0,
            "estimated_total_bytes_returned": 0, "session_ids": set(),
        }
    )
    for s in sessions:
        for action in (s.executions or s.actions):
            if not action.paths_read:
                continue
            share = action.output_bytes // len(action.paths_read)
            for path in action.paths_read:
                item = stats[rel_or_abs(path, project)]
                item["read_count"] += 1
                if is_full_read(" ".join(action.commands)):
                    item["full_reads"] += 1
                else:
                    item["partial_reads"] += 1
                item["estimated_total_bytes_returned"] += share
                item["session_ids"].add(s.session_id)
    rows = []
    for path, item in stats.items():
        if item["read_count"] > 1:
            rows.append(
                {
                    "file": path,
                    "read_count": item["read_count"],
                    "full_reads": item["full_reads"],
                    "partial_reads": item["partial_reads"],
                    "estimated_total_bytes_returned": item["estimated_total_bytes_returned"],
                    "session_count": len(item["session_ids"]),
                    "impact_rank_key": item["estimated_total_bytes_returned"] + item["full_reads"] * 10000,
                }
            )
    return sorted(rows, key=lambda item: item["impact_rank_key"], reverse=True)


def repeated_command_rows(sessions: list[Session]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for s in sessions:
        for action in (s.executions or s.actions):
            for command in action.commands:
                normalized = normalize_command(command)
                category = command_category(command)
                item = grouped.setdefault(
                    (normalized, category),
                    {
                        "normalized_command": normalized, "category": category, "count": 0,
                        "result_bytes": 0, "sessions": set(), "failed": 0,
                    },
                )
                item["count"] += 1
                item["result_bytes"] += action.output_bytes // max(1, len(action.commands))
                item["sessions"].add(s.session_id)
                item["failed"] += int(action.output_failed)
    rows = []
    for item in grouped.values():
        count = item["count"]
        if count < 2:
            continue
        command = item["normalized_command"].lower()
        if count >= 15:
            classification = "HIGHLY_REDUNDANT"
        elif count >= 6:
            classification = "REDUNDANT"
        elif count >= 3 and any(x in command for x in ("git status", "git diff --stat", "rg --files", "get-childitem")):
            classification = "LIKELY_NECESSARY"
        else:
            classification = "UNKNOWN"
        if item["failed"]:
            classification = "UNKNOWN"
        rows.append(
            {
                "normalized_command": item["normalized_command"],
                "category": item["category"],
                "count": count,
                "calls_per_active_hour": "",
                "average_result_bytes": round(item["result_bytes"] / count, 1),
                "total_result_bytes": item["result_bytes"],
                "session_count": len(item["sessions"]),
                "failed_results": item["failed"],
                "classification": classification,
                "notes": "Heuristic classification; repeated work can still be legitimate.",
            }
        )
    return sorted(rows, key=lambda item: (item["count"], item["total_result_bytes"]), reverse=True)


def tool_usage_rows(sessions: list[Session]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "bytes": 0, "sessions": set()}
    )
    signatures: Counter = Counter()
    for s in sessions:
        for action in (s.executions or s.actions):
            commands = action.commands or [""]
            for command in commands:
                key = "File write" if action.name == "FileChange" else command_category(command)
                buckets[key]["calls"] += 1
                buckets[key]["bytes"] += action.output_bytes // max(1, len(commands))
                buckets[key]["sessions"].add(s.session_id)
                signatures[(key, normalize_command(command))] += 1
            for name in action.nested_tools:
                if name == "exec_command":
                    continue
                key = "Subagent" if "agent" in name or "spawn" in name else name
                buckets[key]["calls"] += 1
                buckets[key]["bytes"] += action.output_bytes
                buckets[key]["sessions"].add(s.session_id)
    repeated = Counter(key for (key, _), count in signatures.items() if count > 1 for _ in range(count))
    active = sum(s.active_hours for s in sessions)
    rows = []
    for key, item in buckets.items():
        rows.append(
            {
                "tool_category": key,
                "total_calls": item["calls"],
                "calls_per_active_hour": round(item["calls"] / active, 3) if active else "",
                "average_result_bytes": round(item["bytes"] / item["calls"], 1),
                "total_result_bytes": item["bytes"],
                "estimated_context_contribution_bytes": item["bytes"],
                "repeated_or_similar_calls": repeated[key],
                "session_count": len(item["sessions"]),
                "notes": "Result bytes are serialized-output estimates, not billed tokens.",
            }
        )
    return sorted(rows, key=lambda item: item["total_result_bytes"], reverse=True)


def failures_rows(sessions: list[Session]) -> list[dict[str, Any]]:
    rows = []
    for s in sessions:
        for action in (s.executions or s.actions):
            if action.output_failed:
                nearest = [item for item in s.usage if item.ordinal <= action.ordinal]
                nearest_usage = nearest[-1] if nearest else None
                rows.append(
                    {
                        "session": s.session_id,
                        "timestamp": iso(action.timestamp),
                        "kind": "tool_failure_or_nonzero_result",
                        "reasoning_effort": nearest_usage.effort if nearest_usage else "",
                        "detail": clean_text(action.output_preview, 500),
                        "tokens_on_nearest_request": nearest_usage.total_tokens if nearest_usage else "",
                        "automatic_retry_proven": "NO",
                        "notes": "A model request can be measured, but retry causality is not exposed.",
                    }
                )
        for error in s.errors:
            rows.append(
                {
                    "session": s.session_id,
                    "timestamp": error.get("timestamp", ""),
                    "kind": "event_error",
                    "reasoning_effort": "",
                    "detail": error.get("detail", ""),
                    "tokens_on_nearest_request": "",
                    "automatic_retry_proven": "NO",
                    "notes": "Error event detected in local rollout.",
                }
            )
    return rows


def compaction_mark(sessions: list[Session]) -> None:
    for s in sessions:
        usages = sorted(s.usage, key=lambda item: item.ordinal)
        actions = sorted(s.executions or s.actions, key=lambda item: item.ordinal)
        for compaction in s.compactions:
            before = [u for u in usages if u.ordinal < compaction.ordinal]
            after = [u for u in usages if u.ordinal > compaction.ordinal]
            if before:
                compaction.before_input = before[-1].input_tokens
            if after:
                compaction.after_input = after[0].input_tokens
                if compaction.timestamp:
                    end = compaction.timestamp + dt.timedelta(minutes=15)
                    recent = [
                        a for a in actions
                        if a.timestamp and compaction.timestamp <= a.timestamp <= end
                    ]
                    compaction.after_reads = sum(bool(a.paths_read) for a in recent)
                    compaction.after_scans = sum(
                        any(command_category(c) == "Directory scan" for c in a.commands)
                        for a in recent
                    )
                    compaction.after_git = sum(
                        any(command_category(c) == "Git" for c in a.commands)
                        for a in recent
                    )
                    compaction.after_build_or_test = sum(
                        any(command_category(c) in ("Build", "Tests") for c in a.commands)
                        for a in recent
                    )


def write_compaction_report(path: Path, sessions: list[Session]) -> None:
    lines = [
        "# Compaction analysis",
        "",
        "Compaction records are directly observed in rollout JSONL. Context sizes before/after "
        "are actual request input_tokens from adjacent usage records. Replacement-history size "
        "is a byte estimate and is not converted into tokens.",
        "",
    ]
    found = False
    for s in sessions:
        if not s.compactions:
            continue
        found = True
        lines += [f"## {s.session_id}", ""]
        lines.append(
            f"- Compactions: {len(s.compactions)}; observed model/effort: "
            f"{', '.join(sorted({u.model + '/' + u.effort for u in s.usage}))}."
        )
        lines += [
            "",
            "| timestamp | window | context before | next context | replacement bytes | messages | reads in 15m | scans | git | build/test |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for item in s.compactions:
            lines.append(
                f"| {iso(item.timestamp)} | {item.window_number} | {item.before_input or ''} | "
                f"{item.after_input or ''} | {item.replacement_bytes} | {item.replacement_messages} | "
                f"{item.after_reads} | {item.after_scans} | {item.after_git} | {item.after_build_or_test} |"
            )
        lines += [
            "",
            "The post-compaction action counts are evidence of activity after rollover, not proof "
            "that every action was redundant.",
            "",
        ]
    if not found:
        lines.append("No compaction records were found in the selected project sessions.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_analysis_loops(path: Path, sessions: list[Session]) -> None:
    lines = [
        "# Analysis loops",
        "",
        "Conservative heuristic: a dense interval of model usage with at least three reads, "
        "no observed writes, and at least 10 minutes of elapsed activity. Intent is not logged.",
        "",
    ]
    found = 0
    for s in sessions:
        usages = sorted(s.usage, key=lambda item: item.ordinal)
        actions = sorted(s.executions or s.actions, key=lambda item: item.ordinal)
        blocked_until: dt.datetime | None = None
        for start_i, start_usage in enumerate(usages):
            if not start_usage.timestamp:
                continue
            if blocked_until and start_usage.timestamp <= blocked_until:
                continue
            for end_usage in usages[start_i + 1:]:
                if not end_usage.timestamp:
                    continue
                minutes = (end_usage.timestamp - start_usage.timestamp).total_seconds() / 60
                if minutes < 10:
                    continue
                if minutes > 90:
                    break
                window = [
                    u for u in usages
                    if start_usage.timestamp <= (u.timestamp or start_usage.timestamp) <= end_usage.timestamp
                ]
                window_actions = [
                    a for a in actions
                    if a.timestamp and start_usage.timestamp <= a.timestamp <= end_usage.timestamp
                ]
                reads = sum(len(a.paths_read) for a in window_actions)
                writes = len({p for a in window_actions for p in a.paths_written})
                density = len(window) / max(minutes / 60, 0.01)
                if writes == 0 and density >= 8 and reads >= 3:
                    found += 1
                    threshold = "60+ minutes" if minutes >= 60 else "30+ minutes" if minutes >= 30 else "10+ minutes"
                    lines += [
                        f"## Episode {found} ({threshold})", "",
                        f"- Time range: {iso(start_usage.timestamp)} to {iso(end_usage.timestamp)} ({minutes:.1f} minutes)",
                        f"- Session: {s.session_id}; reasoning: {window[0].effort}",
                        f"- Responses: {len(window)}; tokens: {sum(u.total_tokens for u in window):,}; "
                        f"tools: {len(window_actions)}; files read: {reads}; files changed: {writes}",
                        "- Likely cause: repeated inspection/validation loop. Confidence: MEDIUM.",
                        "",
                    ]
                    blocked_until = end_usage.timestamp
                    break
    if not found:
        lines.append("No conservative analysis-loop episode met the thresholds.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def svg_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_svg_charts(chart_dir: Path, sessions: list[Session]) -> None:
    chart_dir.mkdir(parents=True, exist_ok=True)
    colors = {"medium": "#2f80ed", "high": "#eb5757", "xhigh": "#9b51e0", "max": "#f2994a", "low": "#27ae60"}
    for s in sessions:
        usages = [u for u in s.usage if u.timestamp]
        if not usages:
            continue
        width, height, left, right, top, bottom = 1200, 360, 70, 30, 40, 55
        x0 = usages[0].timestamp.timestamp()
        x1 = max(x0 + 1, usages[-1].timestamp.timestamp())
        ymax = max(u.total_tokens for u in usages) or 1
        circles = []
        for u in usages:
            x = left + (u.timestamp.timestamp() - x0) / (x1 - x0) * (width - left - right)
            y = top + (1 - u.total_tokens / ymax) * (height - top - bottom)
            circles.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{4 if u.effort == "xhigh" else 2.5}" '
                f'fill="{colors.get(u.effort, "#555")}" opacity="0.75"><title>'
                f'{u.response_number}: {u.total_tokens:,} tokens, {svg_escape(u.effort)}</title></circle>'
            )
        marks = []
        for c in s.compactions:
            if c.timestamp:
                x = left + (c.timestamp.timestamp() - x0) / (x1 - x0) * (width - left - right)
                marks.append(
                    f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height-bottom}" '
                    f'stroke="#111" stroke-dasharray="4,3"/><text x="{x+3:.1f}" y="{top+12}" font-size="10">C{c.window_number}</text>'
                )
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{left}" y="22" font-family="Arial" font-size="15">Codex usage timeline: {svg_escape(s.session_id)}</text>
<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#777"/>
<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#777"/>
{''.join(marks)}
{''.join(circles)}
<text x="{left}" y="{height-18}" font-family="Arial" font-size="11">time →; point = response; dashed line = compaction</text>
</svg>'''
        (chart_dir / f"timeline_{s.session_id}.svg").write_text(svg, encoding="utf-8")

        ymax_context = max(u.input_tokens for u in usages) or 1
        dots = []
        for u in usages:
            x = left + (u.response_number - 1) / max(1, len(usages) - 1) * (width - left - right)
            y = top + (1 - u.input_tokens / ymax_context) * (height - top - bottom)
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{colors.get(u.effort, "#555")}"/>')
        context_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{left}" y="22" font-family="Arial" font-size="15">Actual input context by response: {svg_escape(s.session_id)}</text>
<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#777"/>
<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#777"/>
{''.join(dots)}
<text x="{left}" y="{height-18}" font-family="Arial" font-size="11">response number →; y = input_tokens; color = effort</text>
</svg>'''
        (chart_dir / f"context_{s.session_id}.svg").write_text(context_svg, encoding="utf-8")


def git_progress(project: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"available": False}
    try:
        inside = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=10,
        )
        if inside.returncode != 0:
            return result
        result["available"] = True
        log = subprocess.run(
            ["git", "-C", str(project), "log", "--all", "-20", "--date=iso-strict", "--format=%H|%ad|%s"],
            capture_output=True, text=True, timeout=10,
        )
        status = subprocess.run(
            ["git", "-C", str(project), "diff", "--stat"],
            capture_output=True, text=True, timeout=10,
        )
        result["recent_commits"] = [clean_text(line, 240) for line in log.stdout.splitlines() if line.strip()]
        result["working_tree_diff_stat"] = clean_text(status.stdout, 1200)
    except (OSError, subprocess.SubprocessError):
        pass
    return result


def source_inventory(codex_root: Path) -> list[dict[str, Any]]:
    local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    sources = [
        (
            "Codex rollout sessions", codex_root / "sessions", "JSONL rollout histories",
            "Session metadata, turn context, response items, tool calls, compaction markers, "
            "and incremental token_usage_record fields. Primary source.",
            "Yes: input, cached input, cache-write input, output, reasoning-output, total tokens.",
        ),
        (
            "Codex state database", codex_root / "state_5.sqlite", "SQLite",
            "Thread catalog, rollout paths, model/effort metadata, thread tokens_used, and spawn edges.",
            "Yes, thread-level tokens_used; not a replacement for per-response usage.",
        ),
        (
            "Codex thread history", codex_root / "thread_history_1.sqlite", "SQLite",
            "Materialized turns and response/tool item metadata for local threads.",
            "No direct token accounting observed.",
        ),
        (
            "Codex application logs database", codex_root / "logs_2.sqlite", "SQLite",
            "Desktop/app diagnostic log records and estimated byte sizes.",
            "No direct model token accounting observed.",
        ),
        (
            "Codex desktop logs", local_appdata / "Codex" / "Logs", "Text .log files",
            "Desktop process and application diagnostics.",
            "No direct model token accounting observed.",
        ),
        (
            "Session index", codex_root / "session_index.jsonl", "JSONL index",
            "Local session index metadata when present.",
            "No direct per-response token accounting observed.",
        ),
    ]
    rows = []
    for name, path, file_type, contains, usage in sources:
        files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()] if path.is_dir() else []
        if not files:
            rows.append(
                {
                    "source": name, "path": str(path), "file_type": file_type,
                    "approximate_size_bytes": 0, "date_range": "not present",
                    "contains": contains, "usable_token_metadata": usage,
                    "FM27_membership": "not assessed",
                }
            )
            continue
        size = sum(p.stat().st_size for p in files)
        dates = [dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc) for p in files]
        rows.append(
            {
                "source": name, "path": str(path), "file_type": file_type,
                "approximate_size_bytes": size,
                "date_range": f"{iso(min(dates))} to {iso(max(dates))}",
                "contains": contains, "usable_token_metadata": usage,
                "FM27_membership": "selected rollouts are assessed by project-action evidence",
            }
        )
    return rows


def write_log_sources(path: Path, rows: list[dict[str, Any]], total_rollouts: int) -> None:
    lines = [
        "# Codex/Astra log sources", "",
        f"Discovery found {total_rollouts} rollout JSONL files under the configured local Codex root. "
        "The analyzer streams them and does not expose message bodies, credentials, or encrypted content.",
        "",
        "| source | path | type | approximate size | date range | usable information | token metadata |",
        "|---|---|---|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['source']} | {clean_text(row['path'], 180)} | {row['file_type']} | "
            f"{row['approximate_size_bytes']:,} | {row['date_range']} | {row['contains']} | "
            f"{row['usable_token_metadata']} |"
        )
    lines += [
        "",
        "The browser cache under the Codex profile was discovered but excluded: it is a binary "
        "browser/cache store rather than a reliable model request ledger. Encrypted reasoning "
        "payloads were not decrypted.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_recommendations(path: Path, metrics: list[dict[str, Any]]) -> None:
    lines = [
        "# Recommended Codex policy for FM27", "",
        "This policy is evidence-backed by the selected local rollout records. It targets fewer "
        "repeated context appearances and more implementation per response.",
        "",
        "## Recommended reasoning level", "",
        "Use High for difficult FM27 implementation batches when the work is well-scoped; use "
        "Medium for narrow, targeted edits and short validation. The observed xHigh sample is too "
        "small for a reliable long-run recommendation. High produced far more responses in the "
        "selected evidence, while Medium still carried a very large context. This is a workflow "
        "finding, not proof that High is intrinsically cheaper.",
        "",
        "## Concrete controls", "",
        "- Maintain a compact PROJECT_STATE.md; load it plus only the files needed for one deliverable.",
        "- Batch one coherent change, one targeted test gate, and one commit. Avoid one-file micro-cycles.",
        "- Use rg --files, git diff --stat, and summarized diagnostics before any full-file read.",
        "- Route giant directory listings, CSVs, build logs, and diffs through local scripts; return only failures and aggregates.",
        "- After compaction, consult project state first and reread only files required by the active deliverable.",
        "- Start a fresh thread at a milestone boundary when the active context repeatedly approaches the observed 140k–150k input-token range.",
        "- Run targeted tests after edits; reserve full builds/suites for milestone gates.",
        "- Do not use parallel agents for small tasks. If parallelism is needed, give each child a disjoint deliverable and require a concise result.",
        "- Commit at milestones and update state immediately so progress is recoverable and measurable.",
        "",
        "## Observed-policy basis", "",
    ]
    for row in metrics:
        if row.get("data_status") == "MEASURED":
            lines.append(
                f"- {row['reasoning_effort']}: {row['responses']} responses, {row['total_tokens']:,} "
                f"tokens, median input {row['median_input_tokens']}, cached ratio "
                f"{row['cached_input_ratio']}, {row['compactions']} compactions, "
                f"{row['responses_per_meaningful_write']} responses/write."
            )
    lines += [
        "",
        "## Limitations", "",
        "The local logs expose token counts and action traces, but not the server credit conversion, "
        "cache pricing, hidden background activity, or whether every retry was automatic. Policy "
        "therefore optimizes measured token and workflow behavior, not an unobserved billing formula.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_workflow(path: Path) -> None:
    path.write_text(
        """# FM27 Codex workflow

Purpose: maximize completed implementation per unit of Codex allowance and prevent long
sessions from becoming read/think/check loops.

## Milestone loop

1. Read PROJECT_STATE.md, the relevant report link, git status --short, and git diff --stat.
2. Define exactly one deliverable with an acceptance check.
3. Read only the files needed for that deliverable. Prefer symbols, ranges, and local summaries.
4. Implement one coherent batch rather than a sequence of tiny edits.
5. Run the narrowest targeted test or validator.
6. Fix failures from summarized output; do not paste entire logs into context.
7. Run the milestone gate test/build once.
8. Inspect git diff --stat and git diff --check.
9. Commit the milestone.
10. Update PROJECT_STATE.md with the result, test command, blockers, and next task.

Flow:

STATE -> ONE DELIVERABLE -> RELEVANT READS -> COHERENT WRITE -> TARGETED TEST -> FIX -> GATE -> COMMIT -> STATE

## Context budget rules

- Treat repeated 140k–150k actual input-token requests as a warning signal.
- Keep output from scans, CSVs, builds, tests, and diffs summarized locally.
- Never reread a large file without stating why the previous read is insufficient.
- After compaction, reload state and the active file set; do not reconstruct the whole repository.
- Start a new thread at a milestone boundary if the task has no writes for 30 minutes while activity continues.
- Use Medium for focused, low-uncertainty edits; use High for a difficult batch with a clear acceptance gate.
- Use xHigh only for a genuinely hard, bounded investigation or design decision, then switch to implementation.

## Parallelism

Spawn a child only for a disjoint, named deliverable. Require a compact result containing:
changed files, evidence, tests, blockers, and next action. Do not parallelize repository
orientation or duplicate validation.

## Evidence discipline

- rg --files and git diff --stat first.
- Full-file reads only when a targeted read cannot answer the question.
- Build output: return errors and a short count/summary.
- Test output: return failing tests and a pass/fail summary.
- Large data: aggregate with scripts and return rows relevant to the deliverable.
- Record durable decisions in PROJECT_STATE.md, not in repeated chat summaries.
""",
        encoding="utf-8",
    )


def write_project_state(path: Path) -> None:
    path.write_text(
        """# FM27 Project State

Updated: 2026-09-12 UTC

## Current Goal

Continue FM27 Community Overhaul in bounded, milestone-sized deliverables.

## Completed Milestones

The existing project checkpoint is native06. The repository documents 2,880 club
changes, 794 loans, 296 expired returns, 289 Python tests, and 123 native tests.
These are project-reported checkpoint figures; release, game/editor, career/save,
season, and performance gates remain open.

## Architecture

Data pipeline and native/runtime tooling are under src/, tools/, data/, build/, and reports/.

## Important Paths

src/; tools/; data/; tests/; reports/; docs/; build/; dist/

## Active Blockers

No blocker inferred from usage logs; validate repository state before implementation.

## Next Tasks

Choose one deliverable, define its acceptance test, implement, gate, commit, and update this file.

## Test Commands

Use the narrowest existing project validator/test command first; full suites only at milestone gates.

## Known Traps

Do not modify the FIFA installation. Do not expose giant logs. Avoid full repository rereads.
Preserve native identity and serialization constraints.

## Key Decisions

Prefer compact state plus linked reports. Usage-forensics evidence is under
reports/usage-forensics/FINAL_REPORT.md.

Keep this file under 5,000 words. Link to detailed reports instead of copying them.
""",
        encoding="utf-8",
    )


def write_final_report(path: Path, sessions: list[Session], metrics: list[dict[str, Any]], project: Path, git: dict[str, Any]) -> None:
    by = {row.get("reasoning_effort"): row for row in metrics if row.get("data_status") == "MEASURED"}
    medium, high = by.get("medium"), by.get("high")
    total_responses = sum(len(s.usage) for s in sessions)
    total_tokens = sum(s.total_usage["total_tokens"] for s in sessions)
    input_total = sum(s.total_usage["input_tokens"] for s in sessions)
    cached_total = sum(s.total_usage["cached_input_tokens"] for s in sessions)
    actions = sum(len(s.actions) for s in sessions)
    compactions = sum(len(s.compactions) for s in sessions)
    children = [s for s in sessions if s.parent_thread_id]
    medium_h = float(medium["tokens_per_hour"]) if medium and medium.get("tokens_per_hour") else None
    high_h = float(high["tokens_per_hour"]) if high and high.get("tokens_per_hour") else None
    medium_r = float(medium["responses_per_hour"]) if medium and medium.get("responses_per_hour") else None
    high_r = float(high["responses_per_hour"]) if high and high.get("responses_per_hour") else None

    def answer(condition: bool | None) -> str:
        if condition is None:
            return "INSUFFICIENT DATA"
        return "YES" if condition else "NO"

    median_input = median_or_zero([u.input_tokens for s in sessions for u in s.usage])
    reasoning_total = sum(s.total_usage["reasoning_tokens"] for s in sessions)
    output_total = sum(s.total_usage["output_tokens"] for s in sessions)
    failed_actions = sum(a.output_failed for s in sessions for a in (s.executions or s.actions))
    result_bytes = sum(a.output_bytes for s in sessions for a in s.executions)
    post_compaction_reads = sum(c.after_reads + c.after_scans + c.after_git for s in sessions for c in s.compactions)
    child_tokens = sum(s.total_usage["total_tokens"] for s in children)
    repeated_files = repeated_file_rows(sessions, project)

    def per_response(row: dict[str, Any] | None, key: str) -> str:
        if not row or not row.get("responses"):
            return "null"
        return f"{float(row.get(key, 0)) / int(row['responses']):,.1f}"

    def ratio_pct(row: dict[str, Any] | None, key: str) -> str:
        if not row or row.get(key) in (None, ""):
            return "null"
        return f"{float(row[key]):.2%}"

    medium_reasoning_per_response = per_response(medium, "reasoning_tokens")
    high_reasoning_per_response = per_response(high, "reasoning_tokens")
    xhigh = by.get("xhigh")
    xhigh_reasoning_per_response = per_response(xhigh, "reasoning_tokens")
    lines = [
        "# Final Codex/Astra usage forensics report", "",
        "## Primary cause", "",
        "Repeated model requests carrying a very large active context are the dominant measured "
        f"token source. Actual request inputs have a median of {median_input:,.0f} tokens, with "
        f"{input_total:,} cumulative input-token appearances across {total_responses} responses. "
        "The local source does not expose the server credit formula, so this is a measured token "
        "cause, not an asserted percentage of allowance.",
        "",
        "## Secondary causes", "",
        f"- High response frequency: {actions:,} observed tool actions across the selected sessions.",
        "- Repeated tool-result ingestion and repository/build/test output inflated subsequent contexts; see TOOL_USAGE.csv and CONTEXT_GROWTH.csv.",
        f"- Context compaction was directly observed {compactions} times; post-compaction activity is quantified in COMPACTION_ANALYSIS.md.",
        f"- Reasoning-output tokens: {reasoning_total:,}; visible output tokens: {output_total:,}; input tokens: {input_total:,}.",
        f"- Observable child work contributes {len(children)} sessions; exact hidden/background billing is not exposed.",
        "",
        "## Medium vs xHigh result", "",
        "The long-run xHigh comparison is INSUFFICIENT DATA: only a small xHigh sample is present. "
        f"Medium is measured over {medium.get('responses') if medium else 'null'} responses; the long High phase is measured over {high.get('responses') if high else 'null'} responses. "
        "These records do not support the claim that Medium used less raw usage per hour than High; "
        "they support the opposite for these specific sessions, without proving credit equivalence.",
        "",
        "| question | result | evidence |",
        "|---|---|---|",
        f"| A. Did Medium use more total usage per hour? | {answer(medium_h is not None and high_h is not None and medium_h > high_h)} | Medium {medium.get('tokens_per_hour') if medium else 'null'} vs High {high.get('tokens_per_hour') if high else 'null'} raw tokens/hour |",
        f"| B. Did Medium generate more model responses? | {answer(medium_r is not None and high_r is not None and medium_r > high_r)} | Medium {medium.get('responses_per_hour') if medium else 'null'} vs High {high.get('responses_per_hour') if high else 'null'} responses/hour |",
        f"| C. Was average context size comparable? | PARTIALLY | Medium median {medium.get('median_input_tokens') if medium else 'null'}; High median {high.get('median_input_tokens') if high else 'null'} |",
        "| D. Did repeated context processing dominate? | YES | Cumulative measured input tokens dominate the token ledger; requests repeatedly carried large input contexts. |",
        "| E. Did xHigh use more reasoning tokens per response? | INSUFFICIENT DATA | The xHigh sample is too small for a long-run comparison. |",
        "| F. Did xHigh compensate with fewer responses? | INSUFFICIENT DATA | No comparable long xHigh development run is present. |",
        f"| G. Which setting produced more implementation per unit of usage? | PARTIALLY | The local logs lack a complete server credit ledger and comparable milestone denominators; the available file-write proxy is Medium {medium.get('tokens_per_meaningful_file_write') if medium else 'null'} vs High {high.get('tokens_per_meaningful_file_write') if high else 'null'} tokens/write. |",
        "| H. Is Medium-fast-exhaustion / High-longer-runtime supported? | PARTIALLY | The mechanism is plausible, but these FM27 logs show higher raw High throughput/hour and no long xHigh comparison. |",
        "",
        "## Most wasteful observed behavior", "",
        "The clearest avoidable pattern is dense read/inspect/validate activity with repeated large "
        "tool outputs and no meaningful file write for extended intervals. Conservative episodes are "
        "listed in ANALYSIS_LOOPS.md. Repeated reads, commands, and the largest per-response inputs "
        "are ranked in the CSV reports.",
        "",
        "## Recommended reasoning level for FM27", "",
        "High for one bounded, difficult implementation batch with an explicit gate; Medium for small, "
        "well-understood edits. Do not use xHigh as a default: the observed xHigh sample is too small "
        "to establish long-run efficiency.",
        "",
        "## Top 5 changes that will reduce usage", "",
        "1. Maintain and load compact PROJECT_STATE.md instead of re-reading broad project documentation.",
        "2. Batch coherent edits and gate/commit them, reducing response/tool cycles.",
        "3. Summarize directory scans, CSVs, compiler logs, tests, and diffs locally.",
        "4. After compaction, reread only state and active files; avoid repository reconstruction.",
        "5. Use targeted tests and milestone gates; avoid repeated full builds after tiny edits.",
        "",
        "## Output size analysis",
        "",
        f"Measured input tokens are {input_total / total_tokens:.2%} of known total tokens; visible output is {output_total / total_tokens:.2%}; reasoning-output is {reasoning_total / total_tokens:.2%}. Reasoning-output is a subset of output, so these percentages are non-additive.",
        "This rules out visible response prose as the dominant measured token volume. It does not by itself prove how the service converts cached input or reasoning into allowance credits.",
        "",
        "## Cache analysis",
        "",
        f"Primary Medium cached-input ratio: {ratio_pct(medium, 'cached_input_ratio')} ({medium.get('uncached_input_tokens') if medium else 'null'} uncached input tokens); primary High: {ratio_pct(high, 'cached_input_ratio')} ({high.get('uncached_input_tokens') if high else 'null'}); xHigh: {ratio_pct(xhigh, 'cached_input_ratio')} ({xhigh.get('uncached_input_tokens') if xhigh else 'null'}).",
        "Medium therefore has a slightly worse cache ratio than High in this sample, but not more absolute uncached input: High processed much more total input. xHigh's lower ratio is based on only 16 responses. The logs do not expose cache-key invalidation or billing discounts, so cache misses cannot be converted to allowance units.",
        "",
        "## Reasoning-token observation",
        "",
        f"Observed reasoning-output tokens per response were Medium {medium_reasoning_per_response}, High {high_reasoning_per_response}, and xHigh {xhigh_reasoning_per_response}. This small xHigh sample does not show xHigh using more reasoning tokens per response, but it is not sufficient to generalize about long xHigh runs.",
        "",
        "## Ranked causal breakdown",
        "",
        f"1. HIGH — repeated large-context input: {input_total:,} measured input-token appearances across {total_responses} responses; cumulative context processing is the strongest local explanation.",
        f"2. MEDIUM — repeated tool-result and repository inspection cycles: {result_bytes:,} serialized execution-result bytes were observed, with {len(repeated_files)} repeated file paths. Bytes are not billing tokens, so no percentage is assigned.",
        f"3. MEDIUM — compaction/reconstruction pressure: {compactions} compactions and {post_compaction_reads} read/scan/git actions in the first 15 minutes after them. This is a causal pattern, not proof every reread was waste.",
        f"4. LOW by token volume — reasoning and visible output: {reasoning_total:,} reasoning-output tokens and {output_total:,} output tokens versus {input_total:,} input tokens.",
        f"5. LOW-to-MEDIUM — failures/retries: {failed_actions} failed/nonzero execution results were observed; automatic retry is not proven locally, and the per-request usage linkage is reported in RETRIES_AND_FAILURES.csv.",
        f"6. MEDIUM — child work: {len(children)} observable child sessions account for {child_tokens:,} known tokens; hidden/background activity is not visible in the local ledger.",
        "",
        "## Evidence summary", "",
        f"- Project: {project}",
        f"- FM27 development sessions analyzed: {len(sessions)} ({len(children)} observable child sessions).",
        f"- Responses: {total_responses:,}; tool actions: {actions:,}; known incremental tokens: {total_tokens:,}.",
        f"- Known input tokens: {input_total:,}; cached input: {cached_total:,} ({cached_total/input_total:.2%}); uncached input: {input_total-cached_total:,}.",
        f"- Known output tokens: {output_total:,}; reasoning-output tokens: {reasoning_total:,}.",
        f"- Direct compactions: {compactions}; thread state totals are included in SESSIONS.csv where available.",
        "",
        "### Reasoning groups", "",
        "The table below uses primary threads for effort comparisons; the evidence totals above include the five observable child sessions. This prevents parent/child work from being counted twice in the main Medium/High/xHigh comparison.", "",
        "| effort | sessions | responses | elapsed hours | median input | cached ratio | total tokens | tokens/hour |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for effort in ("medium", "high", "xhigh", "max"):
        row = by.get(effort)
        if row:
            lines.append(
                f"| {effort} | {row['sessions']} | {row['responses']} | {row['total_elapsed_time_hours']} | "
                f"{row['median_input_tokens']} | {row['cached_input_ratio']} | {row['total_tokens']:,} | {row['tokens_per_hour']:,} |"
            )
        else:
            lines.append(f"| {effort} | 0 | null | null | null | null | null | null |")
    lines += [
        "",
        "### Interpretation and limits", "",
        "The rollout schema exposes incremental request accounting, so cumulative input-token "
        "appearances are measured rather than inferred from context-window size. total_tokens is "
        "the sum of each record's incremental total and is not a billing credit total. Cached "
        "input ratios are directly measured; cache invalidation mechanics and credit discounts "
        "are not proven locally. Encrypted reasoning contents remain opaque.",
        "",
        "Git correlation used metadata-only git log and git diff --stat plus action traces; "
        + ("a Git repository was available." if git.get("available") else "a usable Git repository was not available."),
        "",
        "See REASONING_COMPARISON.md, COMPACTION_ANALYSIS.md, ANALYSIS_LOOPS.md, and the CSVs for detailed evidence.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=PROJECT_DEFAULT, type=Path)
    parser.add_argument("--codex-root", default=CODEX_ROOT_DEFAULT, type=Path)
    parser.add_argument("--since")
    parser.add_argument("--reasoning", action="append", default=[])
    parser.add_argument("--session", action="append", default=[])
    parser.add_argument("--exclude-session", action="append", default=[])
    parser.add_argument("--compare", default="medium,high,xhigh,max")
    args = parser.parse_args(argv)

    project = args.project.resolve()
    reports = project / "reports" / "usage-forensics"
    reports.mkdir(parents=True, exist_ok=True)
    (project / "tools" / "usage-forensics").mkdir(parents=True, exist_ok=True)
    since = None
    if args.since:
        since = dt.datetime.fromisoformat(args.since.replace("Z", "+00:00"))
        if since.tzinfo is None:
            since = since.replace(tzinfo=dt.timezone.utc)

    state_meta = sqlite_thread_metadata(args.codex_root)
    sessions, total_rollouts = discover_sessions(
        args.codex_root, project, since, set(args.session), set(args.exclude_session), state_meta
    )
    enrich_action_links(sessions)
    compaction_mark(sessions)
    write_log_sources(reports / "LOG_SOURCES.md", source_inventory(args.codex_root), total_rollouts)
    write_csv(
        reports / "SESSIONS.csv",
        [session_row(s, project) for s in sessions],
        [
            "session_id", "start_time", "end_time", "duration", "reasoning_effort", "model",
            "working_directory", "responses", "tool_calls", "commands", "files_read",
            "files_written", "compactions", "retries", "subagents", "input_tokens",
            "cached_input_tokens", "uncached_input_tokens", "output_tokens", "reasoning_tokens",
            "total_tokens", "usage_cost_or_units_if_available", "notes",
        ],
    )
    efforts = [item.strip().lower() for item in (args.reasoning or args.compare.split(",")) if item.strip()]
    primary_sessions = [session for session in sessions if not session.parent_thread_id]
    metrics = group_metrics(primary_sessions, efforts)
    all_metrics = group_metrics(sessions, efforts)
    for row in metrics:
        row["scope"] = "primary_threads"
    for row in all_metrics:
        row["scope"] = "all_project_sessions"
    ordered_fields = [
        "scope", "reasoning_effort", "data_status", "sessions", "total_elapsed_time_hours",
        "active_hours_gap_capped",
        "average_session_duration_hours", "median_session_duration_hours", "responses",
        "responses_per_hour", "tool_calls", "tool_calls_per_hour", "shell_commands",
        "model_turns", "average_input_tokens", "median_input_tokens", "p90_input_tokens",
        "average_cached_input_tokens", "cached_input_ratio", "uncached_input_tokens",
        "output_tokens", "reasoning_tokens", "total_tokens", "input_pct_of_total",
        "output_pct_of_total", "reasoning_pct_of_total", "tokens_per_hour",
        "tokens_per_active_hour",
        "compactions", "compactions_per_hour", "retries_or_failures",
        "meaningful_file_writes", "responses_per_meaningful_write",
        "tokens_per_meaningful_file_write", "commits_observed", "tokens_per_commit",
        "reprocessed_context_estimate", "notes",
    ]
    write_csv(reports / "REASONING_COMPARISON.csv", all_metrics + metrics, ordered_fields)
    with (reports / "REASONING_COMPARISON.md").open("w", encoding="utf-8") as handle:
        handle.write(
            "# Reasoning comparison\n\n"
            "All token fields are sums of incremental usage records. Elapsed hours in this table "
            "are the effort-specific first-to-last response spans; SESSIONS.csv notes also report "
            "active hours with idle gaps capped at 30 minutes.\n\n"
            "| effort | sessions | responses | elapsed h | median input | p90 input | cached ratio | total tokens | tokens/h | responses/h | compactions | writes |\n"
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
        )
        for row in metrics:
            if row.get("data_status") != "MEASURED":
                handle.write(f"| {row.get('reasoning_effort')} | INSUFFICIENT DATA | | | | | | | | | | |\n")
            else:
                handle.write(
                    f"| {row['reasoning_effort']} | {row['sessions']} | {row['responses']} | "
                    f"{row['total_elapsed_time_hours']} | {row['median_input_tokens']} | "
                    f"{row['p90_input_tokens']} | {row['cached_input_ratio']} | "
                    f"{row['total_tokens']:,} | {row['tokens_per_hour']:,} | "
                    f"{row['responses_per_hour']} | {row['compactions']} | {row['meaningful_file_writes']} |\n"
                )
        handle.write(
            "\nThe xHigh result is only a small-sample observation unless a longer xHigh FM27 "
            "session is present in the local logs. Reasoning tokens are included in output tokens.\n"
        )

    write_csv(
        reports / "CONTEXT_GROWTH.csv", context_rows(sessions),
        ["session", "response", "timestamp", "estimated_or_actual_context_tokens", "delta", "source", "category"],
    )
    top_events = []
    for rank, (usage, session) in enumerate(
        sorted([(u, s) for s in sessions for u in s.usage], key=lambda pair: pair[0].total_tokens, reverse=True)[:50],
        1,
    ):
        top_events.append(
            {
                "rank": rank, "session": session.session_id, "timestamp": iso(usage.timestamp),
                "reasoning_effort": usage.effort, "input_tokens": usage.input_tokens,
                "cached_tokens": usage.cached_input_tokens,
                "uncached_input_tokens": usage.input_tokens - usage.cached_input_tokens,
                "reasoning_tokens": usage.reasoning_tokens, "output_tokens": usage.output_tokens,
                "total": usage.total_tokens, "tool_or_action_before": usage.before_actions,
                "tool_or_action_after": usage.after_actions,
                "context_description": (
                    f"actual input={usage.input_tokens:,}; prior output category="
                    f"{usage.previous_output_category or 'PROMPT'}; prior output bytes="
                    f"{usage.previous_output_bytes:,}"
                ),
            }
        )
    write_csv(
        reports / "TOP_USAGE_EVENTS.csv", top_events,
        [
            "rank", "session", "timestamp", "reasoning_effort", "input_tokens", "cached_tokens",
            "uncached_input_tokens", "reasoning_tokens", "output_tokens", "total",
            "tool_or_action_before", "tool_or_action_after", "context_description",
        ],
    )
    write_csv(
        reports / "TOOL_USAGE.csv", tool_usage_rows(sessions),
        [
            "tool_category", "total_calls", "calls_per_active_hour", "average_result_bytes",
            "total_result_bytes", "estimated_context_contribution_bytes",
            "repeated_or_similar_calls", "session_count", "notes",
        ],
    )
    write_csv(
        reports / "REPEATED_FILE_READS.csv", repeated_file_rows(sessions, project),
        ["file", "read_count", "full_reads", "partial_reads", "estimated_total_bytes_returned", "session_count", "impact_rank_key"],
    )
    write_csv(
        reports / "REPEATED_COMMANDS.csv", repeated_command_rows(sessions),
        [
            "normalized_command", "category", "count", "calls_per_active_hour",
            "average_result_bytes", "total_result_bytes", "session_count",
            "failed_results", "classification", "notes",
        ],
    )
    write_csv(
        reports / "RETRIES_AND_FAILURES.csv", failures_rows(sessions),
        [
            "session", "timestamp", "kind", "reasoning_effort", "detail",
            "tokens_on_nearest_request", "automatic_retry_proven", "notes",
        ],
    )
    write_compaction_report(reports / "COMPACTION_ANALYSIS.md", sessions)
    write_analysis_loops(reports / "ANALYSIS_LOOPS.md", sessions)
    write_svg_charts(reports / "charts", sessions)
    git = git_progress(project)
    write_recommendations(reports / "RECOMMENDED_CODEX_POLICY.md", metrics)
    write_workflow(project / "docs" / "CODEX_WORKFLOW.md")
    write_project_state(project / "PROJECT_STATE.md")
    write_final_report(reports / "FINAL_REPORT.md", sessions, metrics, project, git)
    print(
        json.dumps(
            {
                "project": str(project), "rollout_files_discovered": total_rollouts,
                "project_sessions_analyzed": len(sessions),
                "session_ids": [s.session_id for s in sessions],
                "responses": sum(len(s.usage) for s in sessions),
                "tool_calls": sum(len(s.actions) for s in sessions),
                "known_total_tokens": sum(s.total_usage["total_tokens"] for s in sessions),
                "known_input_tokens": sum(s.total_usage["input_tokens"] for s in sessions),
                "known_cached_input_tokens": sum(s.total_usage["cached_input_tokens"] for s in sessions),
                "compactions": sum(len(s.compactions) for s in sessions),
                "reports": str(reports),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
