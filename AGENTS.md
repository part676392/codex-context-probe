# AGENTS.md

## Project

This repository builds `codex-context-probe`, a deterministic CLI and GitHub Action for checking Codex instruction discovery before Codex-powered pull request work.

## Development

- Use Python 3.10 or newer.
- Run `pytest` before publishing changes.
- Keep inspection deterministic and offline by default.
- Do not add dependencies that call OpenAI, GitHub, or network services during inspection.
- Keep README examples aligned with the CLI and `action.yml`.
- Never commit secrets, tokens, cookies, local `.env` files, or raw credential material.
