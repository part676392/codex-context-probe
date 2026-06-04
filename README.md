# codex-context-probe

Deterministic CI preflight for Codex-powered pull request workflows.

`codex-context-probe` answers a narrow question before you ask Codex to review or
edit a PR:

> Which `AGENTS.md` instructions can each changed file actually see?

It reconstructs Codex instruction discovery for each changed path, produces a
context manifest, and fails CI only when objective context problems are found or
when you opt into path-scoped contracts.

## Why This Exists

AGENTS.md linters improve instruction quality. This tool checks instruction
visibility.

In a monorepo, a PR can touch `services/payments/handler.py` while Codex is
started from the wrong directory, a local `AGENTS.override.md` shadows root
security rules, or a large file gets cut off by the 32 KiB default instruction
budget. Those are not normal markdown quality issues. They are PR-context
preflight issues.

`codex-context-probe` is designed to run before Codex-powered PR review,
maintainer automation, or release work.

## Features

- Reconstructs Codex AGENTS.md discovery:
  - `CODEX_HOME` guidance
  - project root to target cwd walk
  - `AGENTS.override.md`
  - `AGENTS.md`
  - `project_doc_fallback_filenames`
  - `project_doc_max_bytes` budget
- Maps `git diff --name-only` changed paths to their effective instruction chain.
- Emits terminal, JSON, Markdown, and SARIF.
- Writes GitHub Step Summary markdown.
- Reports objective failures:
  - instruction truncation or excluded bytes
  - ignored project-scoped Codex config keys
  - invalid UTF-8 in visible instruction files
  - secret-like strings in visible instruction files
- Supports optional `.codex-context.yml` contracts for path-scoped context tests.
- Requires no OpenAI API key for the deterministic path.

By default, content-level checks run only on instruction files that Codex can
actually see for the changed path. Use `--scan-shadowed` when you also want to
scan shadowed, non-selected instruction files as a broader hygiene check.

## Install

```bash
pip install "codex-context-probe @ git+https://github.com/part676392/codex-context-probe.git"
```

From source:

```bash
git clone https://github.com/part676392/codex-context-probe
cd codex-context-probe
pip install -e .
```

## CLI

Inspect one working directory:

```bash
codex-context-probe inspect . --cwd services/payments
```

Inspect changed paths in a PR:

```bash
codex-context-probe changed . --base origin/main --format markdown
```

CI verification:

```bash
codex-context-probe verify . \
  --base origin/main \
  --format markdown \
  --output codex-context-report.md \
  --sarif codex-context.sarif
```

## Example Output

Terminal output is intentionally compact so it works in local development and CI
logs:

```text
╭─ codex-context-probe changed paths [PASS] ─────────────────────────────╮
│ Project: /repo                                                         │
│ Base: origin/main                                                      │
│ Changed paths: 1                                                       │
│ Findings: 0 errors, 1 warnings                                         │
╰────────────────────────────────────────────────────────────────────────╯

Changed path context
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Path                         ┃ CWD                  ┃ Included files       ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ services/payments/handler.py │ /repo/services/pay…  │ AGENTS.md, AGENTS.md │
└──────────────────────────────┴──────────────────────┴──────────────────────┘
```

Markdown output is designed for PR summaries:

```markdown
# codex-context-probe changed-path report

- Changed paths: `1`
- Findings: `0` errors, `1` warnings

| Path | CWD | Included instruction files | Bytes | Findings |
|---|---|---|---:|---:|
| `services/payments/handler.py` | `/repo/services/payments` | AGENTS.md<br>AGENTS.md | 612/32768 | 0 errors, 1 warnings |
```

## GitHub Action

```yaml
name: Codex context preflight

on:
  pull_request:
  push:

jobs:
  codex-context:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: part676392/codex-context-probe@v0.1.1
        with:
          base: origin/main
          sarif: codex-context.sarif
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: codex-context.sarif
```

For stricter environments, pin third-party actions and this action by commit SHA.

The repository includes its own CI workflow at `.github/workflows/ci.yml` and a
copyable CI template at `docs/github-actions-ci.yml`.

## Optional Contracts

Add `.codex-context.yml` only when you want path-scoped assertions.

```yaml
contracts:
  - id: payments-test-command
    paths:
      - services/payments/**
    assertions:
      - type: contains
        value: make test-payments
      - type: regex
        value: Never rotate API keys|Do not rotate API keys
    severity: error
```

Contracts apply only to matching changed paths. Without this file, the tool
fails only on objective context failures.

## How This Differs From AGENTS.md Linters

Linters ask whether instruction files are well written.

`codex-context-probe` asks whether the changed files in this PR can see the
right Codex instructions.

It is meant to complement tools such as `agnix`, `ctxlint`, `agents-lint`,
`AgentLint`, and `instrlint`, not replace them.

## Codex for OSS Fit

Codex for OSS supports maintainers using Codex for pull request review,
maintainer automation, release workflows, and other core OSS work. This project
targets the preflight step for that workflow: before Codex reviews a PR, verify
that Codex is operating from the intended repository guidance.

## License

MIT
