"""Optional path-scoped context contracts."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import ChangedReport, Finding, Inspection


@dataclass
class Assertion:
    kind: str
    value: str


@dataclass
class Contract:
    id: str
    paths: list[str]
    assertions: list[Assertion]
    severity: str = "error"


def load_contracts(path: Path) -> list[Contract]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    contracts = []
    for item in data.get("contracts", []):
        assertions = []
        for raw_assertion in item.get("assertions", []):
            if isinstance(raw_assertion, dict):
                assertions.append(Assertion(kind=str(raw_assertion.get("type", "contains")), value=str(raw_assertion.get("value", ""))))
            else:
                assertions.append(Assertion(kind="contains", value=str(raw_assertion)))
        # Backward-friendly shorthand.
        for value in item.get("must_contain", []):
            assertions.append(Assertion(kind="contains", value=str(value)))
        contracts.append(
            Contract(
                id=str(item["id"]),
                paths=[str(pattern) for pattern in item.get("paths", [])],
                assertions=assertions,
                severity=str(item.get("severity", "error")),
            )
        )
    return contracts


def apply_contracts(report: ChangedReport, contracts: list[Contract]) -> None:
    """Append contract findings to matching changed-path inspections."""

    if not contracts:
        return

    for item in report.changed_paths:
        context = effective_context(item.inspection)
        for contract in contracts:
            if not _matches_any(item.path, contract.paths):
                continue
            for assertion in contract.assertions:
                if _assertion_passes(context, assertion):
                    continue
                item.inspection.findings.append(
                    Finding(
                        rule_id="CON001",
                        severity=_severity(contract.severity),
                        path=item.path,
                        message=f"Context contract '{contract.id}' failed: {assertion.kind} {assertion.value!r}.",
                        suggestion="Update the applicable AGENTS.md chain or relax the contract if the requirement changed.",
                    )
                )


def effective_context(inspection: Inspection) -> str:
    chunks = []
    for candidate in inspection.included_files:
        path = Path(candidate.path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if candidate.status == "truncated":
            text = text.encode("utf-8")[: candidate.included_bytes].decode("utf-8", errors="ignore")
        chunks.append(text)
    return "\n\n".join(chunks)


def _matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern.replace("\\", "/")) for pattern in patterns)


def _assertion_passes(context: str, assertion: Assertion) -> bool:
    if assertion.kind == "contains":
        return assertion.value in context
    if assertion.kind == "regex":
        return re.search(assertion.value, context, flags=re.MULTILINE) is not None
    raise ValueError(f"unsupported assertion type: {assertion.kind}")


def _severity(value: str) -> str:
    return value if value in {"error", "warning", "info"} else "error"
