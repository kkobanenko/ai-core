"""Разбор docs/agent-bridge/next-prompt.md (legacy + metadata) — v0.1.1."""

from __future__ import annotations

import re
from typing import Any, Optional

from tools.dev_coordinator.models import BridgePrompt, CoordState

# Front matter: блок между --- в начале файла.
_FRONT_MATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z",
    re.DOTALL,
)

# Legacy WAIT: markdown-заголовок "# WAIT".
_LEGACY_WAIT_RE = re.compile(r"(?m)^\s*#\s+WAIT\s*$")

_KNOWN_STATES = {s.value: s for s in CoordState}

# Обязательные поля для EXECUTOR_READY (все non-empty).
EXECUTOR_READY_REQUIRED = (
    "coord_version",
    "state",
    "prompt_id",
    "target_repo",
    "target_branch",
    "target_worktree",
    "base_sha",
    "hosted_ci",
    "max_executor_runs",
)


def _parse_simple_yaml_map(text: str) -> dict[str, Any]:
    """Плоский YAML map. Duplicate keys → ValueError (fail closed)."""
    result: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-") or (line and not line[0].isalnum() and line[0] != "_"):
            raise ValueError(f"unsupported YAML line: {raw_line!r}")
        if ":" not in line:
            raise ValueError(f"expected key: value, got: {raw_line!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"empty key in: {raw_line!r}")
        # v0.1.1: никаких last-value-wins.
        if key in result:
            raise ValueError(f"duplicate metadata key: {key!r}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key in ("coord_version", "max_executor_runs"):
            if value.isdigit():
                result[key] = int(value)
            else:
                result[key] = value
        elif value.lower() in ("true", "false"):
            result[key] = value.lower() == "true"
        else:
            result[key] = value
    return result


def _legacy_wait(text: str) -> bool:
    return bool(_LEGACY_WAIT_RE.search(text))


def _is_missing(value: Any) -> bool:
    """None или пустая строка = missing."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def parse_next_prompt(text: str) -> BridgePrompt:
    """Разобрать текст next-prompt.md (v0.1.1)."""
    raw = text if text is not None else ""
    match = _FRONT_MATTER_RE.match(raw)

    if not match:
        if _legacy_wait(raw):
            return BridgePrompt(
                has_metadata=False,
                state=CoordState.WAIT,
                prompt_id=None,
                target_repo=None,
                target_branch=None,
                target_worktree=None,
                base_sha=None,
                hosted_ci=None,
                max_executor_runs=1,
                raw_text=raw,
                body=raw,
                raw_metadata={},
                parse_error=None,
            )
        return BridgePrompt(
            has_metadata=False,
            state=None,
            prompt_id=None,
            target_repo=None,
            target_branch=None,
            target_worktree=None,
            base_sha=None,
            hosted_ci=None,
            max_executor_runs=1,
            raw_text=raw,
            body=raw,
            raw_metadata={},
            parse_error="legacy next-prompt without metadata and without # WAIT",
        )

    fm_text, body = match.group(1), match.group(2)
    try:
        meta = _parse_simple_yaml_map(fm_text)
    except ValueError as exc:
        return BridgePrompt(
            has_metadata=True,
            state=None,
            prompt_id=None,
            target_repo=None,
            target_branch=None,
            target_worktree=None,
            base_sha=None,
            hosted_ci=None,
            max_executor_runs=1,
            raw_text=raw,
            body=body,
            raw_metadata={},
            parse_error=f"invalid front matter: {exc}",
        )

    if "state" not in meta:
        return _meta_error(raw, body, meta, "missing required field: state")
    if "coord_version" not in meta:
        return _meta_error(raw, body, meta, "missing required field: coord_version")

    coord_version = meta.get("coord_version")
    if coord_version != 1:
        return _meta_error(
            raw, body, meta, f"unsupported coord_version: {coord_version!r}"
        )

    state_raw = meta.get("state")
    if not isinstance(state_raw, str):
        return _meta_error(raw, body, meta, f"state must be string, got {state_raw!r}")
    if re.search(r"[\s,|/]", state_raw.strip()):
        return _meta_error(raw, body, meta, f"multiple/invalid state: {state_raw!r}")
    state = _KNOWN_STATES.get(state_raw.strip())
    if state is None:
        return _meta_error(raw, body, meta, f"unknown state: {state_raw!r}")

    # EXECUTOR_READY: полный обязательный набор non-empty полей.
    if state == CoordState.EXECUTOR_READY:
        for field in EXECUTOR_READY_REQUIRED:
            if field not in meta or _is_missing(meta.get(field)):
                return _meta_error(
                    raw,
                    body,
                    meta,
                    f"EXECUTOR_READY missing required field: {field}",
                )
        max_runs = meta.get("max_executor_runs")
        if not isinstance(max_runs, int) or max_runs < 1:
            return _meta_error(
                raw, body, meta, f"invalid max_executor_runs: {max_runs!r}"
            )
        prompt_id = str(meta.get("prompt_id")).strip()
        if not prompt_id:
            return _meta_error(raw, body, meta, "prompt_id must be non-empty")
    else:
        # Для WAIT/DONE/… достаточно coord_version+state; max_runs опционален.
        max_runs = meta.get("max_executor_runs", 1)
        if max_runs is not None and (
            not isinstance(max_runs, int) or max_runs < 1
        ):
            return _meta_error(
                raw, body, meta, f"invalid max_executor_runs: {max_runs!r}"
            )
        if max_runs is None:
            max_runs = 1
        prompt_id = _opt_str(meta.get("prompt_id"))

    return BridgePrompt(
        has_metadata=True,
        state=state,
        prompt_id=prompt_id,
        target_repo=_opt_str(meta.get("target_repo")),
        target_branch=_opt_str(meta.get("target_branch")),
        target_worktree=_opt_str(meta.get("target_worktree")),
        base_sha=_opt_str(meta.get("base_sha")),
        hosted_ci=_opt_str(meta.get("hosted_ci")),
        max_executor_runs=int(max_runs),
        raw_text=raw,
        body=body,
        raw_metadata=meta,
        parse_error=None,
    )


def _opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return str(value)


def _meta_error(
    raw: str, body: str, meta: dict[str, Any], message: str
) -> BridgePrompt:
    return BridgePrompt(
        has_metadata=True,
        state=None,
        prompt_id=_opt_str(meta.get("prompt_id")),
        target_repo=_opt_str(meta.get("target_repo")),
        target_branch=_opt_str(meta.get("target_branch")),
        target_worktree=_opt_str(meta.get("target_worktree")),
        base_sha=_opt_str(meta.get("base_sha")),
        hosted_ci=_opt_str(meta.get("hosted_ci")),
        max_executor_runs=1,
        raw_text=raw,
        body=body,
        raw_metadata=meta,
        parse_error=message,
    )
