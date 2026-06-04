# Security Policy

## Reporting a Vulnerability

Please open a private security advisory or contact the maintainer directly if you find a vulnerability that could expose credentials, repository contents, or CI artifacts.

Do not include real credentials in public issues, test fixtures, screenshots, or SARIF examples.

## Scope

`codex-context-probe` is a deterministic local/CI inspection tool. It does not call OpenAI APIs and should not require network access during normal checks.

Security-sensitive areas include:

- secret-like string detection in visible instruction files
- SARIF output paths and messages
- GitHub Action behavior
- handling of repository paths and generated reports

## Supported Versions

Only the latest tagged release is supported for security fixes.
