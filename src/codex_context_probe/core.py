"""Codex AGENTS.md discovery inspection."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable

import toml

from .models import ConfigLayer, Finding, Inspection, InstructionCandidate, normalize_path


DEFAULT_MAX_BYTES = 32 * 1024
BASE_FILENAMES = ["AGENTS.override.md", "AGENTS.md"]
IGNORED_PROJECT_CONFIG_KEYS = {
    "openai_base_url",
    "chatgpt_base_url",
    "apps_mcp_product_sku",
    "model_provider",
    "model_providers",
    "notify",
    "profile",
    "profiles",
    "experimental_realtime_ws_base_url",
    "otel",
}

SECRET_PATTERNS = [
    (re.compile("sk-" + r"[A-Za-z0-9_-]{20,}"), "OpenAI-style API key"),
    (re.compile("ghp" + "_" + r"[A-Za-z0-9]{36}"), "GitHub personal access token"),
    (re.compile(r"(?i)\b(api[_-]?key|token|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]"), "inline secret"),
]

AMBIGUOUS_PHRASES = [
    "as needed",
    "as appropriate",
    "when necessary",
    "適宜",
    "いい感じ",
    "うまく",
]


def inspect_project(
    project_root: Path,
    cwd: Path | None = None,
    codex_home: Path | None = None,
    emit_context_path: Path | None = None,
    scan_shadowed: bool = False,
) -> Inspection:
    """Inspect the instruction files Codex would load for a project and cwd.

    By default, content-level checks run only on selected instruction files. This
    keeps the tool aligned with its core promise: report what Codex can actually
    see for the target working directory. Pass ``scan_shadowed=True`` when a
    caller wants a broader repository hygiene pass over shadowed instruction
    files as well.
    """

    root = project_root.resolve()
    if not root.is_dir():
        raise ValueError(f"project root is not a directory: {root}")

    target_cwd = (cwd or root).resolve()
    if not target_cwd.is_dir():
        raise ValueError(f"cwd is not a directory: {target_cwd}")
    if not _is_relative_to(target_cwd, root):
        raise ValueError(f"cwd must be inside project root: {target_cwd}")

    codex_home_path = (codex_home or _default_codex_home()).resolve()
    config_layers, merged_config, config_findings = _load_config(root, target_cwd, codex_home_path)
    max_bytes = _read_max_bytes(merged_config)
    fallback_filenames = _read_fallback_filenames(merged_config)

    candidates: list[InstructionCandidate] = []
    findings: list[Finding] = list(config_findings)

    _select_first_non_empty(
        codex_home_path,
        BASE_FILENAMES,
        scope="global",
        candidates=candidates,
        findings=findings,
    )

    for directory in _directory_chain(root, target_cwd):
        filenames = _dedupe(BASE_FILENAMES + fallback_filenames)
        _select_first_non_empty(
            directory,
            filenames,
            scope="project",
            candidates=candidates,
            findings=findings,
        )

    if not any(candidate.selected for candidate in candidates):
        findings.append(
            Finding(
                rule_id="DISC001",
                severity="warning",
                message="No non-empty Codex instruction files were discovered.",
                suggestion="Add AGENTS.md at the repository root or configure project_doc_fallback_filenames.",
            )
        )

    _apply_byte_budget(candidates, max_bytes, findings)
    _scan_content(_content_scan_targets(candidates, scan_shadowed=scan_shadowed), findings)

    total_selected_bytes = sum(c.size_bytes for c in candidates if c.selected)
    total_included_bytes = sum(c.included_bytes for c in candidates if c.selected)
    truncated = any(c.status in {"truncated", "excluded_by_cap"} for c in candidates if c.selected)

    if emit_context_path:
        _write_effective_context(candidates, emit_context_path)

    return Inspection(
        project_root=normalize_path(root),
        cwd=normalize_path(target_cwd),
        codex_home=normalize_path(codex_home_path),
        max_bytes=max_bytes,
        fallback_filenames=fallback_filenames,
        total_selected_bytes=total_selected_bytes,
        total_included_bytes=total_included_bytes,
        truncated=truncated,
        config_layers=config_layers,
        candidates=candidates,
        findings=findings,
    )


def _default_codex_home() -> Path:
    value = os.environ.get("CODEX_HOME")
    if value:
        return Path(value)
    return Path.home() / ".codex"


def _load_config(root: Path, cwd: Path, codex_home: Path) -> tuple[list[ConfigLayer], dict[str, Any], list[Finding]]:
    layers: list[ConfigLayer] = []
    merged: dict[str, Any] = {}
    findings: list[Finding] = []

    global_config = codex_home / "config.toml"
    if global_config.exists():
        _merge_config_file(global_config, "global", merged, layers, findings)

    for directory in _directory_chain(root, cwd):
        project_config = directory / ".codex" / "config.toml"
        if project_config.exists():
            _merge_config_file(project_config, "project", merged, layers, findings)

    return layers, merged, findings


def _merge_config_file(
    path: Path,
    scope: str,
    merged: dict[str, Any],
    layers: list[ConfigLayer],
    findings: list[Finding],
) -> None:
    try:
        data = toml.load(path)
    except Exception as exc:
        layers.append(ConfigLayer(path=normalize_path(path), scope=scope, parsed=False, error=str(exc)))
        findings.append(
            Finding(
                rule_id="CFG000",
                severity="error",
                path=normalize_path(path),
                message=f"Codex config could not be parsed: {exc}",
                suggestion="Fix TOML syntax before relying on this config layer.",
            )
        )
        return

    keys = sorted(data.keys())
    ignored = sorted(key for key in keys if scope == "project" and key in IGNORED_PROJECT_CONFIG_KEYS)
    layers.append(
        ConfigLayer(
            path=normalize_path(path),
            scope=scope,
            parsed=True,
            keys=keys,
            ignored_project_keys=ignored,
        )
    )

    if ignored:
        findings.append(
            Finding(
                rule_id="CFG001",
                severity="warning",
                path=normalize_path(path),
                message=f"Project config contains keys Codex ignores in project scope: {', '.join(ignored)}.",
                suggestion="Move provider, profile, notification, or telemetry settings to user-level config.",
            )
        )

    if scope == "project":
        merged.update({key: value for key, value in data.items() if key not in IGNORED_PROJECT_CONFIG_KEYS})
    else:
        merged.update(data)


def _read_max_bytes(config: dict[str, Any]) -> int:
    raw = config.get("project_doc_max_bytes", DEFAULT_MAX_BYTES)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_BYTES
    return max(1, value)


def _read_fallback_filenames(config: dict[str, Any]) -> list[str]:
    raw = config.get("project_doc_fallback_filenames", [])
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item).strip()]


def _directory_chain(root: Path, cwd: Path) -> list[Path]:
    relative = cwd.relative_to(root)
    directories = [root]
    current = root
    for part in relative.parts:
        current = current / part
        directories.append(current)
    return directories


def _select_first_non_empty(
    directory: Path,
    filenames: Iterable[str],
    scope: str,
    candidates: list[InstructionCandidate],
    findings: list[Finding],
) -> InstructionCandidate | None:
    existing: list[InstructionCandidate] = []

    for filename in filenames:
        path = directory / filename
        if not path.exists() or not path.is_file():
            continue
        size = path.stat().st_size
        non_empty = _is_non_empty(path)
        candidate = InstructionCandidate(
            path=normalize_path(path),
            scope=scope,
            directory=normalize_path(directory),
            filename=filename,
            size_bytes=size,
            non_empty=non_empty,
        )
        existing.append(candidate)
        candidates.append(candidate)

    selected: InstructionCandidate | None = None
    for candidate in existing:
        if not candidate.non_empty:
            candidate.reason = "empty files are skipped by Codex"
            candidate.status = "ignored_empty"
            findings.append(
                Finding(
                    rule_id="DISC002",
                    severity="info",
                    path=candidate.path,
                    message=f"{candidate.filename} is empty and will be skipped.",
                    suggestion="Remove it or add instructions if it should affect Codex.",
                )
            )
            continue
        selected = candidate
        candidate.selected = True
        candidate.reason = "first non-empty file for this scope and directory"
        break

    if selected:
        for candidate in existing:
            if candidate is selected or candidate.status == "ignored_empty":
                continue
            candidate.reason = f"shadowed by {selected.filename} in the same directory"
            candidate.status = "shadowed"

        if selected.filename == "AGENTS.override.md":
            base = next((c for c in existing if c.filename == "AGENTS.md" and c.non_empty), None)
            if base:
                findings.append(
                    Finding(
                        rule_id="DISC003",
                        severity="info",
                        path=selected.path,
                        message="AGENTS.override.md shadows AGENTS.md in the same directory.",
                        suggestion="Keep override files temporary or document why the base file is intentionally bypassed.",
                    )
                )

    return selected


def _apply_byte_budget(candidates: list[InstructionCandidate], max_bytes: int, findings: list[Finding]) -> None:
    used = 0
    stopped = False

    for candidate in [c for c in candidates if c.selected]:
        separator = 2 if used else 0
        if stopped:
            candidate.status = "excluded_by_cap"
            candidate.reason = "combined instruction budget was already exhausted"
            candidate.included_bytes = 0
            continue

        needed = separator + candidate.size_bytes
        if used + needed <= max_bytes:
            candidate.status = "included"
            candidate.included_bytes = candidate.size_bytes
            used += needed
            continue

        remaining = max(0, max_bytes - used - separator)
        candidate.status = "truncated" if remaining > 0 else "excluded_by_cap"
        candidate.included_bytes = remaining
        candidate.reason = f"combined instruction budget exceeds project_doc_max_bytes={max_bytes}"
        stopped = True
        findings.append(
            Finding(
                rule_id="BUD001",
                severity="error",
                path=candidate.path,
                message=(
                    f"Codex instruction budget is exhausted at {candidate.filename}; "
                    f"{candidate.size_bytes - remaining} bytes are not available to Codex."
                ),
                suggestion="Raise project_doc_max_bytes or split critical guidance into smaller nested files.",
            )
        )


def _content_scan_targets(candidates: list[InstructionCandidate], scan_shadowed: bool) -> list[InstructionCandidate]:
    if scan_shadowed:
        return [candidate for candidate in candidates if candidate.non_empty]
    return [candidate for candidate in candidates if candidate.selected and candidate.non_empty]


def _scan_content(candidates: list[InstructionCandidate], findings: list[Finding]) -> None:
    for candidate in candidates:
        path = Path(candidate.path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            findings.append(
                Finding(
                    rule_id="CNT001",
                    severity="error",
                    path=candidate.path,
                    message="Instruction file is not valid UTF-8.",
                    suggestion="Re-save the file as UTF-8 so Codex can read it consistently.",
                )
            )
            continue

        for line_number, line in enumerate(lines, 1):
            for pattern, label in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            rule_id="SEC001",
                            severity="error",
                            path=candidate.path,
                            line=line_number,
                            message=f"Possible {label} found in an instruction file.",
                            suggestion="Move secrets to environment variables or a private secret store.",
                        )
                    )
                    break

            if len(line) > 500:
                findings.append(
                    Finding(
                        rule_id="CNT002",
                        severity="warning",
                        path=candidate.path,
                        line=line_number,
                        message=f"Line is {len(line)} characters; very long instructions are easy to miss.",
                        suggestion="Split the rule into shorter, direct bullets.",
                    )
                )

        lowered = "\n".join(lines).lower()
        for phrase in AMBIGUOUS_PHRASES:
            if phrase.lower() in lowered:
                findings.append(
                    Finding(
                        rule_id="CNT003",
                        severity="warning",
                        path=candidate.path,
                        message=f"Ambiguous phrase '{phrase}' appears in instructions.",
                        suggestion="Replace vague wording with a concrete command, condition, or threshold.",
                    )
                )
                break


def _write_effective_context(candidates: list[InstructionCandidate], output_path: Path) -> None:
    chunks: list[str] = []
    for candidate in [c for c in candidates if c.status in {"included", "truncated"}]:
        text = Path(candidate.path).read_text(encoding="utf-8")
        if candidate.status == "truncated":
            encoded = text.encode("utf-8")[: candidate.included_bytes]
            text = encoded.decode("utf-8", errors="ignore")
        chunks.append(f"<!-- Source: {candidate.path} -->\n{text}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(chunks), encoding="utf-8")


def _is_non_empty(path: Path) -> bool:
    try:
        return bool(path.read_text(encoding="utf-8").strip())
    except UnicodeDecodeError:
        return path.stat().st_size > 0


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
