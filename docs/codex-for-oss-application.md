# Codex for OSS Application Draft

## Repository Qualification

`codex-context-probe` helps maintainers use Codex safely in pull request
workflows. It creates a deterministic preflight manifest showing which
`AGENTS.md` instructions each changed file can see, then flags truncation,
override shadowing, ignored Codex config keys, invalid instruction files, and
optional path-scoped context contract failures.

The project is important to the Codex OSS ecosystem because Codex-powered PR
review and maintainer automation depend on the right repository instructions
being visible. Existing AGENTS.md linters improve instruction quality; this
tool verifies instruction visibility for the specific files changed in a PR.

## API Credit Usage

API credits would be used to build optional Codex-powered follow-up workflows
after deterministic preflight passes: summarize context-risk reports, propose
AGENTS.md fixes, and help maintainers review PRs with verified context. The
default CLI and GitHub Action remain offline and do not require API keys.

## Evidence to Maintain

- `pytest` and smoke-test output for each release.
- A GitHub Actions CI template in `docs/github-actions-ci.yml`.
- `examples/monorepo` demonstrating nested AGENTS.md and context contracts.
- Generated Markdown and SARIF reports.
- Release tags and changelog entries.
- Public issues for real user feedback and roadmap items.

## Honesty Boundary

This repository should not claim broad adoption until usage exists. The initial
application should emphasize ecosystem importance and active maintenance, not
inflated stars or fabricated downloads.
