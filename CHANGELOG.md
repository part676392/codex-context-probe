# Changelog

## Unreleased

- Align default content checks with the project goal: scan only instruction files that Codex can actually see for the target path.
- Add `--scan-shadowed` for broader hygiene checks over shadowed non-selected instruction files.
- Add regression tests for default visible-only scanning and explicit shadowed scanning.
- Add a real GitHub Actions CI workflow under `.github/workflows/ci.yml`.
- Clarify README output examples and GitHub Action usage.
- Add contribution guidelines.

## 0.1.0 - 2026-06-04

- Initial public release.
- Added `inspect`, `changed`, and `verify` CLI commands.
- Added Codex instruction discovery reconstruction for `AGENTS.override.md`, `AGENTS.md`, fallback filenames, and byte-budget checks.
- Added JSON, Markdown, SARIF, terminal, and GitHub Step Summary output.
- Added optional `.codex-context.yml` path-scoped contracts.
