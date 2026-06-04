"""SARIF output for GitHub code scanning."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ChangedReport, Finding, Inspection

REPOSITORY_URL = "https://github.com/part676392/codex-context-probe"

RULE_METADATA = {
    "BUD001": {
        "name": "instruction-budget-exhausted",
        "description": "The effective instruction chain exceeds project_doc_max_bytes, so part of the guidance is not visible.",
        "help": "Reduce instruction file size, split guidance by path, or raise project_doc_max_bytes when appropriate.",
        "tags": ["codex", "instructions", "budget"],
    },
    "CFG000": {
        "name": "invalid-codex-config",
        "description": "A Codex config file could not be parsed as TOML.",
        "help": "Fix TOML syntax before relying on the config layer.",
        "tags": ["codex", "config"],
    },
    "CFG001": {
        "name": "ignored-project-config-key",
        "description": "A project-scoped Codex config contains keys that are ignored outside user-level config.",
        "help": "Move provider, profile, notification, or telemetry settings to user-level config.",
        "tags": ["codex", "config"],
    },
    "CNT001": {
        "name": "invalid-instruction-encoding",
        "description": "An instruction file is not valid UTF-8.",
        "help": "Re-save the file as UTF-8 so it can be read consistently.",
        "tags": ["instructions", "encoding"],
    },
    "CNT002": {
        "name": "long-instruction-line",
        "description": "A very long instruction line is hard to review and easy for maintainers to miss.",
        "help": "Split the instruction into shorter, direct bullets.",
        "tags": ["instructions", "reviewability"],
    },
    "CNT003": {
        "name": "ambiguous-instruction-phrase",
        "description": "An instruction contains vague wording that may be interpreted inconsistently.",
        "help": "Replace vague wording with a concrete command, condition, or threshold.",
        "tags": ["instructions", "reviewability"],
    },
    "CON001": {
        "name": "context-contract-failed",
        "description": "A path-scoped context contract did not match the effective instruction chain.",
        "help": "Update the applicable instruction chain or adjust the contract if the requirement changed.",
        "tags": ["codex", "contracts", "ci"],
    },
    "DISC001": {
        "name": "no-instruction-files",
        "description": "No non-empty instruction files were discovered for the target path.",
        "help": "Add AGENTS.md at the repository root or configure project_doc_fallback_filenames.",
        "tags": ["codex", "discovery"],
    },
    "DISC002": {
        "name": "empty-instruction-file",
        "description": "An instruction file exists but is empty, so it is skipped.",
        "help": "Remove the file or add instructions if it should affect the agent context.",
        "tags": ["codex", "discovery"],
    },
    "DISC003": {
        "name": "override-shadows-base",
        "description": "AGENTS.override.md shadows AGENTS.md in the same directory.",
        "help": "Keep override files temporary or document why the base file is intentionally bypassed.",
        "tags": ["codex", "discovery", "override"],
    },
    "SEC001": {
        "name": "secret-like-instruction-content",
        "description": "A visible instruction file contains a string that resembles a secret or credential.",
        "help": "Move credentials to environment variables or a private secret store.",
        "tags": ["security", "instructions"],
    },
}


def render_sarif(obj: Inspection | ChangedReport) -> str:
    findings = _findings(obj)
    rule_ids = sorted({finding.rule_id for finding in findings})
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "codex-context-probe",
                        "semanticVersion": "0.1.0",
                        "informationUri": REPOSITORY_URL,
                        "rules": [_rule_to_sarif(rule_id) for rule_id in rule_ids],
                    }
                },
                "results": [_finding_to_result(finding, _project_root(obj)) for finding in findings],
            }
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _rule_to_sarif(rule_id: str) -> dict:
    metadata = RULE_METADATA.get(rule_id, {})
    name = metadata.get("name", rule_id)
    description = metadata.get("description", f"codex-context-probe finding {rule_id}")
    help_text = metadata.get("help", "Review the generated finding and update the applicable instruction context.")
    tags = metadata.get("tags", [])
    return {
        "id": rule_id,
        "name": name,
        "shortDescription": {"text": description},
        "fullDescription": {"text": description},
        "help": {"text": help_text, "markdown": help_text},
        "helpUri": f"{REPOSITORY_URL}#how-this-differs-from-agentsmd-linters",
        "properties": {"tags": tags},
    }


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
