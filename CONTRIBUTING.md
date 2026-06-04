# Contributing

Thanks for helping improve `codex-context-probe`.

## Development Setup

```bash
git clone https://github.com/part676392/codex-context-probe
cd codex-context-probe
python -m pip install -e ".[dev]"
```

## Checks

Run these before opening a pull request:

```bash
python -m compileall src tests
pytest
codex-context-probe --help
```

For changes that affect reporting or context discovery, also run the tool against
a repository with nested `AGENTS.md` files and include the before/after output in
the PR description.

## Design Principles

- Prefer deterministic filesystem and Git inspection over model calls.
- Keep the default path aligned with what Codex can actually see.
- Put subjective instruction-quality checks behind explicit options or contracts.
- Avoid requiring an OpenAI API key for CI preflight use.
- Treat SARIF, Markdown, JSON, and terminal output as public API surfaces.

## Good First Issues

- Add a regression fixture for a real monorepo layout.
- Improve SARIF rule metadata and help text.
- Add examples for fallback filenames and `AGENTS.override.md` shadowing.
- Add package publishing automation once the project is ready for PyPI.
