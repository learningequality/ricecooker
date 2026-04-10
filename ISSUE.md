---
issue: 662
target_branch: main
repo: learningequality/ricecooker
updated_at: "2026-03-31T21:48:28Z"
---

<!---HEADER START-->

<img height="20px" src="https://i.imgur.com/c7hUeb5.jpeg">

❌ **This issue is not open for contribution. Visit <a href="https://learningequality.org/contributing-to-our-open-code-base/" target="_blank">Contributing guidelines</a>** to learn about the contributing process and how to find suitable issues.

<img height="20px" src="https://i.imgur.com/c7hUeb5.jpeg">

<!---HEADER END-->

## Overview

Migrate from pip/tox/setup.py to uv, and replace flake8/black/reorder-python-imports with ruff, following the same approach as learningequality/kolibri#14457.

**Complexity:** Low
**Target branch:** main

### Context

Kolibri has migrated to uv for Python version management, virtual environments, dependency resolution, and CI. The same migration should be applied across the ecosystem for consistency. Ricecooker already has yamlfmt and actionlint in its pre-commit config.

### The Change

- Convert `setup.py`/`setup.cfg` to `pyproject.toml` with PEP 735 dependency groups
- Replace custom versioning with setuptools-scm
- Replace tox with direct uv invocation in CI
- Replace flake8/black/reorder-python-imports with ruff
- Replace pre-commit with prek
- Update CI workflows to use `astral-sh/setup-uv` with `enable-cache: true` and `cache-python: true` (this may need to be turned off for Windows workflows - can check on CI)
- Configure `exclude-newer = "7 days"` with `exclude-newer-package` exemption for `le-utils` in `[tool.uv]` for supply chain safety
- Add `uv-lock` pre-commit hook (from `astral-sh/uv-pre-commit`) to keep `uv.lock` in sync
- Update developer documentation

### Acceptance Criteria

- [ ] `pyproject.toml` replaces `setup.py`/`setup.cfg` as the single source of project metadata and configuration
- [ ] Versioning handled by setuptools-scm
- [ ] `tox.ini` removed; CI uses uv directly
- [ ] Linting and formatting handled by ruff (replacing black, flake8, reorder-python-imports)
- [ ] Pre-commit uses prek
- [ ] CI workflows use `astral-sh/setup-uv@v7`
- [ ] `exclude-newer` cooldown configured in pyproject.toml
- [ ] `uv-lock` pre-commit hook added to `.pre-commit-config.yaml`
- [ ] All existing tests pass
- [ ] Developer documentation updated

### References

- https://github.com/learningequality/kolibri/pull/14457 — Kolibri uv migration (reference implementation)

## AI usage

This issue was drafted by Claude Code based on the Kolibri uv migration work.
