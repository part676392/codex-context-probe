"""Report rendering for codex-context-probe."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import ChangedReport, Finding, Inspection


def render_json(obj: Inspection | ChangedReport) -> str:
    return json.dumps(obj.to_dict(), ensure_ascii=False, indent=2)


def render_inspection_markdown(inspection: Inspection) -> str:
    lines = [
        "# codex-context-probe inspection",
        "",
        f"- Project root: `{inspection.project_root}`",
        f"- CWD: `{inspection.cwd}`",
        f"- Codex home: `{inspection.codex_home}`",
        f"- Byte budget: `{inspection.total_included_bytes}/{inspection.max_bytes}`",
        f"- Findings: `{inspection.error_count}` errors, `{inspection.warning_count}` warnings, `{inspection.info_count}` info",
        "",
        "## Instruction Files",
        "",
        "| Status | Scope | Bytes | Included | File | Reason |",
        "|---|---:|---:|---:|---|---|",
    ]
    for candidate in inspection.candidates:
        if not candidate.selected and candidate.status == "candidate":
            continue
        lines.append(
            f"| {candidate.status} | {candidate.scope} | {candidate.size_bytes} | "
            f"{candidate.included_bytes} | `{candidate.path}` | {(candidate.reason or '').replace('|', '\\|')} |"
        )
    lines.extend(["", "## Findings", ""])
    _append_findings_markdown(lines, inspection.findings)
    return "\n".join(lines) + "\n"


def render_changed_markdown(report: ChangedReport) -> str:
    lines = [
        "# codex-context-probe changed-path report",
        "",
        f"- Project root: `{report.project_root}`",
        f"- Base: `{report.base or '-'}`",
        f"- Changed paths: `{len(report.changed_paths)}`",
        f"- Findings: `{report.error_count}` errors, `{report.warning_count}` warnings",
        "",
        "## Changed Path Context",
        "",
        "| Path | CWD | Included instruction files | Bytes | Findings |",
        "|---|---|---|---:|---:|",
    ]

    for item in report.changed_paths:
        included = "<br>".join(Path(candidate.path).name for candidate in item.inspection.included_files) or "-"
        lines.append(
            f"| `{item.path}` | `{item.cwd}` | {included} | "
            f"{item.inspection.total_included_bytes}/{item.inspection.max_bytes} | "
            f"{item.inspection.error_count} errors, {item.inspection.warning_count} warnings |"
        )

    lines.extend(["", "## Findings", ""])
    all_findings = []
    for item in report.changed_paths:
        for finding in item.inspection.findings:
            all_findings.append((item.path, finding))
    if not all_findings:
        lines.append("No findings.")
    else:
        lines.extend(["| Changed path | Severity | Rule | Location | Message | Suggestion |", "|---|---|---|---|---|---|"])
        for changed_path, finding in all_findings:
            location = finding.path or "-"
            if finding.line:
                location = f"{location}:{finding.line}"
            lines.append(
                f"| `{changed_path}` | {finding.severity} | {finding.rule_id} | `{location}` | "
                f"{finding.message.replace('|', '\\|')} | {(finding.suggestion or '').replace('|', '\\|')} |"
            )

    return "\n".join(lines) + "\n"


def print_inspection(inspection: Inspection, console: Console | None = None) -> None:
    console = console or Console()
    _print_panel(
        console,
        title="codex-context-probe inspection",
        status_errors=inspection.error_count,
        lines=[
            f"Project: {inspection.project_root}",
            f"CWD: {inspection.cwd}",
            f"Codex home: {inspection.codex_home}",
            f"Budget: {inspection.total_included_bytes}/{inspection.max_bytes} bytes",
            f"Findings: {inspection.error_count} errors, {inspection.warning_count} warnings, {inspection.info_count} info",
        ],
    )
    _print_instruction_table(inspection, console)
    _print_findings(inspection.findings, console)


def print_changed(report: ChangedReport, console: Console | None = None) -> None:
    console = console or Console()
    _print_panel(
        console,
        title="codex-context-probe changed paths",
        status_errors=report.error_count,
        lines=[
            f"Project: {report.project_root}",
            f"Base: {report.base or '-'}",
            f"Changed paths: {len(report.changed_paths)}",
            f"Findings: {report.error_count} errors, {report.warning_count} warnings",
        ],
    )

    table = Table(title="Changed path context")
    table.add_column("Path")
    table.add_column("CWD")
    table.add_column("Included files")
    table.add_column("Budget", justify="right")
    table.add_column("Findings", justify="right")
    for item in report.changed_paths:
        table.add_row(
            item.path,
            item.cwd,
            ", ".join(Path(candidate.path).name for candidate in item.inspection.included_files) or "-",
            f"{item.inspection.total_included_bytes}/{item.inspection.max_bytes}",
            f"{item.inspection.error_count}e/{item.inspection.warning_count}w",
        )
    console.print(table)

    findings = []
    for item in report.changed_paths:
        findings.extend(item.inspection.findings)
    _print_findings(findings, console)


def write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append_findings_markdown(lines: list[str], findings: list[Finding]) -> None:
    if not findings:
        lines.append("No findings.")
        return
    lines.extend(["| Severity | Rule | Location | Message | Suggestion |", "|---|---|---|---|---|"])
    for finding in findings:
        location = finding.path or "-"
        if finding.line:
            location = f"{location}:{finding.line}"
        lines.append(
            f"| {finding.severity} | {finding.rule_id} | `{location}` | "
            f"{finding.message.replace('|', '\\|')} | {(finding.suggestion or '').replace('|', '\\|')} |"
        )


def _print_panel(console: Console, title: str, status_errors: int, lines: list[str]) -> None:
    status = "FAIL" if status_errors else "PASS"
    style = "red" if status_errors else "green"
    console.print(Panel("\n".join(lines), title=f"{title} [{status}]", border_style=style))


def _print_instruction_table(inspection: Inspection, console: Console) -> None:
    table = Table(title="Instruction discovery")
    table.add_column("Status")
    table.add_column("Scope")
    table.add_column("Bytes", justify="right")
    table.add_column("Included", justify="right")
    table.add_column("File")
    table.add_column("Reason")

    rows = [
        c
        for c in inspection.candidates
        if c.selected or c.status in {"ignored_empty", "shadowed", "truncated", "excluded_by_cap"}
    ]
    if not rows:
        console.print(Text("No instruction files discovered.", style="yellow"))
        return

    for candidate in rows:
        table.add_row(
            candidate.status,
            candidate.scope,
            str(candidate.size_bytes),
            str(candidate.included_bytes),
            candidate.path,
            candidate.reason,
        )
    console.print(table)


def _print_findings(findings: list[Finding], console: Console) -> None:
    if not findings:
        console.print(Text("No findings.", style="bold green"))
        return

    table = Table(title="Findings")
    table.add_column("Severity")
    table.add_column("Rule")
    table.add_column("Location")
    table.add_column("Message")
    table.add_column("Suggestion")

    for finding in sorted(findings, key=_finding_sort_key):
        style = {"error": "bold red", "warning": "yellow", "info": "dim"}.get(finding.severity, "")
        location = finding.path or "-"
        if finding.line:
            location = f"{location}:{finding.line}"
        table.add_row(
            Text(finding.severity, style=style),
            finding.rule_id,
            location,
            finding.message,
            finding.suggestion or "",
        )
    console.print(table)


def _finding_sort_key(finding: Finding) -> tuple[int, str]:
    order = {"error": 0, "warning": 1, "info": 2}
    return (order.get(finding.severity, 9), finding.rule_id)
