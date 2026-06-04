"""Command-line interface for codex-context-probe."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .changed import collect_git_changed_paths, inspect_changed_paths
from .contracts import apply_contracts, load_contracts
from .core import inspect_project
from .report import (
    print_changed,
    print_inspection,
    render_changed_markdown,
    render_inspection_markdown,
    render_json,
    write_output,
)
from .sarif import render_sarif


FAIL_LEVELS = ["none", "warning", "error"]
FORMATS = ["terminal", "json", "markdown"]


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="codex-context-probe")
def main() -> None:
    """Deterministic preflight for Codex PR instruction context."""


@main.command("inspect")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=".")
@click.option("--cwd", "cwd_value", type=click.Path(file_okay=False, dir_okay=True), default=None)
@click.option("--codex-home", type=click.Path(file_okay=False, dir_okay=True), default=None)
@click.option("--format", "output_format", type=click.Choice(FORMATS), default="terminal", show_default=True)
@click.option("--output", "-o", type=click.Path(dir_okay=False), default=None)
@click.option("--sarif", type=click.Path(dir_okay=False), default=None)
@click.option("--emit-context", type=click.Path(dir_okay=False), default=None)
@click.option("--fail-on", type=click.Choice(FAIL_LEVELS), default="error", show_default=True)
def inspect_command(
    path: str,
    cwd_value: str | None,
    codex_home: str | None,
    output_format: str,
    output: str | None,
    sarif: str | None,
    emit_context: str | None,
    fail_on: str,
) -> None:
    """Inspect Codex instruction discovery for one working directory."""

    root = Path(path)
    cwd = _resolve_cwd(root, cwd_value)
    inspection = inspect_project(
        root,
        cwd=cwd,
        codex_home=Path(codex_home) if codex_home else None,
        emit_context_path=Path(emit_context) if emit_context else None,
    )
    _emit_inspection(inspection, output_format, output)
    if sarif:
        write_output(Path(sarif), render_sarif(inspection))
    raise SystemExit(_exit_code(inspection.error_count, inspection.warning_count, fail_on))


@main.command("changed")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=".")
@click.option("--base", default="HEAD", show_default=True, help="Git revision or ref to diff against.")
@click.option("--codex-home", type=click.Path(file_okay=False, dir_okay=True), default=None)
@click.option("--contracts", type=click.Path(dir_okay=False), default=".codex-context.yml", show_default=True)
@click.option("--no-contracts", is_flag=True, help="Skip .codex-context.yml even if present.")
@click.option("--format", "output_format", type=click.Choice(FORMATS), default="terminal", show_default=True)
@click.option("--output", "-o", type=click.Path(dir_okay=False), default=None)
@click.option("--sarif", type=click.Path(dir_okay=False), default=None)
@click.option("--summary", type=click.Path(dir_okay=False), default=None, help="Write GitHub Step Summary markdown.")
@click.option("--fail-on", type=click.Choice(FAIL_LEVELS), default="error", show_default=True)
def changed_command(
    path: str,
    base: str,
    codex_home: str | None,
    contracts: str,
    no_contracts: bool,
    output_format: str,
    output: str | None,
    sarif: str | None,
    summary: str | None,
    fail_on: str,
) -> None:
    """Build a Codex context manifest for git-changed paths."""

    root = Path(path)
    changed_paths = collect_git_changed_paths(root, base)
    report = inspect_changed_paths(root, changed_paths, base=base, codex_home=Path(codex_home) if codex_home else None)
    _maybe_apply_contracts(report, root, contracts, no_contracts)
    _emit_changed(report, output_format, output)
    if sarif:
        write_output(Path(sarif), render_sarif(report))
    if summary:
        write_output(Path(summary), render_changed_markdown(report))
    raise SystemExit(_exit_code(report.error_count, report.warning_count, fail_on))


@main.command("verify")
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True), default=".")
@click.option("--base", default="HEAD", show_default=True, help="Git revision or ref to diff against.")
@click.option("--codex-home", type=click.Path(file_okay=False, dir_okay=True), default=None)
@click.option("--contracts", type=click.Path(dir_okay=False), default=".codex-context.yml", show_default=True)
@click.option("--no-contracts", is_flag=True, help="Skip .codex-context.yml even if present.")
@click.option("--format", "output_format", type=click.Choice(FORMATS), default="terminal", show_default=True)
@click.option("--output", "-o", type=click.Path(dir_okay=False), default=None)
@click.option("--sarif", type=click.Path(dir_okay=False), default=None)
@click.option("--summary", type=click.Path(dir_okay=False), default=None, help="Write GitHub Step Summary markdown.")
@click.option("--fail-on", type=click.Choice(FAIL_LEVELS), default="error", show_default=True)
def verify_command(
    path: str,
    base: str,
    codex_home: str | None,
    contracts: str,
    no_contracts: bool,
    output_format: str,
    output: str | None,
    sarif: str | None,
    summary: str | None,
    fail_on: str,
) -> None:
    """CI-friendly alias for changed."""

    ctx = click.get_current_context()
    ctx.invoke(
        changed_command,
        path=path,
        base=base,
        codex_home=codex_home,
        contracts=contracts,
        no_contracts=no_contracts,
        output_format=output_format,
        output=output,
        sarif=sarif,
        summary=summary,
        fail_on=fail_on,
    )


def _resolve_cwd(root: Path, cwd_value: str | None) -> Path | None:
    if not cwd_value:
        return None
    cwd = Path(cwd_value)
    return cwd if cwd.is_absolute() else root / cwd


def _maybe_apply_contracts(report, root: Path, contracts_path: str, no_contracts: bool) -> None:
    if no_contracts:
        return
    path = Path(contracts_path)
    if not path.is_absolute():
        path = root / path
    apply_contracts(report, load_contracts(path))


def _emit_inspection(inspection, output_format: str, output: str | None) -> None:
    if output_format == "terminal":
        print_inspection(inspection, Console())
        return
    content = render_json(inspection) if output_format == "json" else render_inspection_markdown(inspection)
    if output:
        write_output(Path(output), content)
    else:
        click.echo(content)


def _emit_changed(report, output_format: str, output: str | None) -> None:
    if output_format == "terminal":
        print_changed(report, Console())
        return
    content = render_json(report) if output_format == "json" else render_changed_markdown(report)
    if output:
        write_output(Path(output), content)
    else:
        click.echo(content)


def _exit_code(errors: int, warnings: int, fail_on: str) -> int:
    if fail_on == "none":
        return 0
    if fail_on == "warning" and (errors or warnings):
        return 1
    if fail_on == "error" and errors:
        return 1
    return 0


if __name__ == "__main__":
    main()
