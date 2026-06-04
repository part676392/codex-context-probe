"""Changed-path inspection for pull request context manifests."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .core import inspect_project
from .models import ChangedPathInspection, ChangedReport, normalize_path


def collect_git_changed_paths(project_root: Path, base: str) -> list[str]:
    """Return changed paths from git without depending on third-party actions."""

    result = subprocess.run(
        ["git", "-C", str(project_root), "diff", "--name-only", base, "--"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git diff failed for base {base}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def inspect_changed_paths(
    project_root: Path,
    changed_paths: list[str],
    base: str | None = None,
    codex_home: Path | None = None,
) -> ChangedReport:
    """Inspect effective Codex context for each changed path."""

    root = project_root.resolve()
    cwd_cache = {}
    results: list[ChangedPathInspection] = []

    for rel_path in sorted(dict.fromkeys(changed_paths)):
        cwd = _cwd_for_changed_path(root, rel_path)
        cache_key = str(cwd)
        if cache_key not in cwd_cache:
            cwd_cache[cache_key] = inspect_project(root, cwd=cwd, codex_home=codex_home)
        results.append(
            ChangedPathInspection(
                path=rel_path,
                cwd=normalize_path(cwd),
                inspection=cwd_cache[cache_key],
            )
        )

    return ChangedReport(project_root=normalize_path(root), base=base, changed_paths=results)


def _cwd_for_changed_path(root: Path, rel_path: str) -> Path:
    path = root / rel_path
    if path.exists() and path.is_dir():
        return path.resolve()

    candidate = path.parent
    while not candidate.exists() and candidate != root and candidate != candidate.parent:
        candidate = candidate.parent
    if not candidate.exists() or not candidate.is_dir():
        return root
    return candidate.resolve()
