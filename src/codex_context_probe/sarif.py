"""SARIF output for GitHub code scanning."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ChangedReport, Finding, Inspection


def render_sarif(obj: Inspection | ChangedReport) -> str:
    findings = _findings(obj)
    rules = {
        finding.rule_id: {
            "id": finding.rule_id,
            "name": finding.rule_id,
            "shortDescription": {"text": finding.message},
        }
        for finding in findings
    }
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "codex-context-probe",
                        "informationUri": "https://github.com/part676392/codex-context-probe",
                        "rules": list(rules.values()),
                    }
                },
                "results": [_finding_to_result(finding, _project_root(obj)) for finding in findings],
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _findings(obj: Inspection | ChangedReport) -> list[Finding]:
    if isinstance(obj, Inspection):
        return obj.findings
    findings: list[Finding] = []
    for item in obj.changed_paths:
        findings.extend(item.inspection.findings)
    return findings


def _project_root(obj: Inspection | ChangedReport) -> str:
    return obj.project_root


def _finding_to_result(finding: Finding, project_root: str) -> dict:
    level = {"error": "error", "warning": "warning", "info": "note"}.get(finding.severity, "note")
    result = {
        "ruleId": finding.rule_id,
        "level": level,
        "message": {"text": finding.message},
    }
    if finding.path:
        result["locations"] = [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": _relative_uri(finding.path, project_root)},
                    "region": {"startLine": finding.line or 1},
                }
            }
        ]
    return result


def _relative_uri(path: str, project_root: str) -> str:
    try:
        candidate = Path(path)
        if not candidate.is_absolute():
            return candidate.as_posix()
        return candidate.resolve().relative_to(Path(project_root).resolve()).as_posix()
    except ValueError:
        return Path(path).name
