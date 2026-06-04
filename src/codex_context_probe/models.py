"""Data structures for Codex context inspection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ConfigLayer:
    """One Codex config file considered during inspection."""

    path: str
    scope: str
    parsed: bool
    keys: list[str] = field(default_factory=list)
    ignored_project_keys: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InstructionCandidate:
    """An instruction-like file that existed on disk during discovery."""

    path: str
    scope: str
    directory: str
    filename: str
    size_bytes: int
    non_empty: bool
    selected: bool = False
    reason: str = ""
    status: str = "candidate"
    included_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    """A diagnostic finding from inspection."""

    rule_id: str
    severity: str
    message: str
    path: str | None = None
    line: int | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Inspection:
    """Complete inspection result for one target working directory."""

    project_root: str
    cwd: str
    codex_home: str
    max_bytes: int
    fallback_filenames: list[str]
    total_selected_bytes: int
    total_included_bytes: int
    truncated: bool
    config_layers: list[ConfigLayer] = field(default_factory=list)
    candidates: list[InstructionCandidate] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def selected_files(self) -> list[InstructionCandidate]:
        return [candidate for candidate in self.candidates if candidate.selected]

    @property
    def included_files(self) -> list[InstructionCandidate]:
        return [candidate for candidate in self.selected_files if candidate.status in {"included", "truncated"}]

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "info")

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "cwd": self.cwd,
            "codex_home": self.codex_home,
            "max_bytes": self.max_bytes,
            "fallback_filenames": self.fallback_filenames,
            "total_selected_bytes": self.total_selected_bytes,
            "total_included_bytes": self.total_included_bytes,
            "truncated": self.truncated,
            "summary": {
                "selected_files": len(self.selected_files),
                "included_files": len(self.included_files),
                "errors": self.error_count,
                "warnings": self.warning_count,
                "info": self.info_count,
            },
            "config_layers": [layer.to_dict() for layer in self.config_layers],
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass
class ChangedPathInspection:
    """Inspection result for one changed file or directory."""

    path: str
    cwd: str
    inspection: Inspection

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "cwd": self.cwd,
            "inspection": self.inspection.to_dict(),
        }


@dataclass
class ChangedReport:
    """Inspection report for a set of changed paths."""

    project_root: str
    base: str | None
    changed_paths: list[ChangedPathInspection]

    @property
    def error_count(self) -> int:
        return sum(item.inspection.error_count for item in self.changed_paths)

    @property
    def warning_count(self) -> int:
        return sum(item.inspection.warning_count for item in self.changed_paths)

    @property
    def uncovered_count(self) -> int:
        return sum(1 for item in self.changed_paths if not item.inspection.included_files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "base": self.base,
            "summary": {
                "changed_paths": len(self.changed_paths),
                "errors": self.error_count,
                "warnings": self.warning_count,
                "uncovered_paths": self.uncovered_count,
            },
            "changed_paths": [item.to_dict() for item in self.changed_paths],
        }


def normalize_path(path: Path) -> str:
    """Return a stable path string without requiring POSIX-only formatting."""

    return str(path.resolve())
