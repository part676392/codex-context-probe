from pathlib import Path

from codex_context_probe.changed import inspect_changed_paths
from codex_context_probe.contracts import apply_contracts, load_contracts
from codex_context_probe.core import DEFAULT_MAX_BYTES, inspect_project


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_discovers_global_root_and_nested_in_order(tmp_path):
    codex_home = tmp_path / "home" / ".codex"
    repo = tmp_path / "repo"
    service = repo / "services" / "payments"

    write(codex_home / "AGENTS.md", "# Global\nUse `pytest`.\n")
    write(repo / "AGENTS.md", "# Root\nRun `make test`.\n")
    write(service / "AGENTS.md", "# Payments\nRun `make test-payments`.\n")

    result = inspect_project(repo, cwd=service, codex_home=codex_home)

    selected = [Path(item.path).name for item in result.selected_files]
    assert selected == ["AGENTS.md", "AGENTS.md", "AGENTS.md"]
    assert [Path(item.path).parent for item in result.selected_files] == [codex_home, repo, service]
    assert result.error_count == 0


def test_override_shadows_base_file(tmp_path):
    repo = tmp_path / "repo"
    service = repo / "service"
    write(repo / "AGENTS.md", "# Root\nUse `pytest`.\n")
    write(service / "AGENTS.md", "# Base\nUse `npm test`.\n")
    write(service / "AGENTS.override.md", "# Override\nUse `make service-test`.\n")

    result = inspect_project(repo, cwd=service, codex_home=tmp_path / "home")

    selected_paths = [Path(item.path) for item in result.selected_files]
    assert service / "AGENTS.override.md" in selected_paths
    base = next(item for item in result.candidates if Path(item.path) == service / "AGENTS.md")
    assert base.status == "shadowed"
    assert any(finding.rule_id == "DISC003" for finding in result.findings)


def test_fallback_filename_from_config(tmp_path):
    repo = tmp_path / "repo"
    write(repo / ".codex" / "config.toml", 'project_doc_fallback_filenames = ["TEAM_GUIDE.md"]\n')
    write(repo / "TEAM_GUIDE.md", "# Team guide\nRun `pytest`.\n")

    result = inspect_project(repo, codex_home=tmp_path / "home")

    assert result.fallback_filenames == ["TEAM_GUIDE.md"]
    assert len(result.selected_files) == 1
    assert Path(result.selected_files[0].path).name == "TEAM_GUIDE.md"


def test_byte_budget_reports_truncated_file(tmp_path):
    repo = tmp_path / "repo"
    write(repo / ".codex" / "config.toml", "project_doc_max_bytes = 80\n")
    write(repo / "AGENTS.md", "# Root\n" + "a" * 200)

    result = inspect_project(repo, codex_home=tmp_path / "home")

    assert result.truncated
    assert result.error_count == 1
    assert result.selected_files[0].status == "truncated"
    assert result.selected_files[0].included_bytes == 80


def test_project_config_ignored_keys_are_reported(tmp_path):
    repo = tmp_path / "repo"
    write(repo / ".codex" / "config.toml", 'openai_base_url = "https://example.invalid/v1"\n')
    write(repo / "AGENTS.md", "# Root\nRun `pytest`.\n")

    result = inspect_project(repo, codex_home=tmp_path / "home")

    assert any(finding.rule_id == "CFG001" for finding in result.findings)
    assert result.warning_count >= 1


def test_secret_detection(tmp_path):
    repo = tmp_path / "repo"
    write(repo / "AGENTS.md", '# Root\napi_key = "example-secret-value-123456"\n')

    result = inspect_project(repo, codex_home=tmp_path / "home")

    assert any(finding.rule_id == "SEC001" for finding in result.findings)
    assert result.error_count >= 1


def test_default_budget_is_32_kib(tmp_path):
    repo = tmp_path / "repo"
    write(repo / "AGENTS.md", "# Root\nRun `pytest`.\n")

    result = inspect_project(repo, codex_home=tmp_path / "home")

    assert result.max_bytes == DEFAULT_MAX_BYTES


def test_changed_paths_use_nearest_existing_directory(tmp_path):
    repo = tmp_path / "repo"
    service = repo / "services" / "payments"
    write(repo / "AGENTS.md", "# Root\nRun `pytest`.\n")
    write(service / "AGENTS.md", "# Payments\nRun `make test-payments`.\n")
    write(service / "handler.py", "print('ok')\n")

    report = inspect_changed_paths(repo, ["services/payments/handler.py"], base="HEAD", codex_home=tmp_path / "home")

    assert len(report.changed_paths) == 1
    included = [Path(item.path).name for item in report.changed_paths[0].inspection.included_files]
    assert included == ["AGENTS.md", "AGENTS.md"]
    assert "services" in report.changed_paths[0].cwd


def test_contract_failure_is_added_to_matching_changed_path(tmp_path):
    repo = tmp_path / "repo"
    service = repo / "services" / "payments"
    write(repo / "AGENTS.md", "# Root\nRun `pytest`.\n")
    write(service / "AGENTS.md", "# Payments\nRun `make test-payments`.\n")
    write(service / "handler.py", "print('ok')\n")
    write(
        repo / ".codex-context.yml",
        """
contracts:
  - id: payments-release-rule
    paths:
      - services/payments/**
    assertions:
      - type: contains
        value: Never deploy on Friday
    severity: error
""".strip()
        + "\n",
    )

    report = inspect_changed_paths(repo, ["services/payments/handler.py"], base="HEAD", codex_home=tmp_path / "home")
    apply_contracts(report, load_contracts(repo / ".codex-context.yml"))

    assert report.error_count == 1
    assert any(finding.rule_id == "CON001" for finding in report.changed_paths[0].inspection.findings)
