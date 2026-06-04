## Summary

<!-- What changed and why? -->

## Context preflight impact

- [ ] This changes Codex instruction discovery behavior.
- [ ] This changes SARIF, Markdown, JSON, or terminal output.
- [ ] This changes GitHub Action behavior.
- [ ] This is docs-only.

## Validation

```bash
python -m compileall src tests
pytest
codex-context-probe --help
```

If context discovery changed, include before/after output from a nested `AGENTS.md` fixture or real repository layout.
