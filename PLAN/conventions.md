# Ricecooker Development Conventions

## Pre-Migration State (current)

- **Tooling**: setuptools with `setup.py` + `setup.cfg`
- **Package manager**: pip (no uv)
- **Python**: 3.9, 3.10, 3.11, 3.12, 3.13
- **Version management**: bumpversion (setup.cfg `current_version = 0.1.0`), `__version__ = "0.8.0"` in `ricecooker/__init__.py`
- **Entry points**: `corrections` console script
- **Extras**: `[test]`, `[dev]` (just pre-commit), `[google_drive]`, `[sentry]`
- **Lint**: black 21.12b0, flake8 (max-line-length=160, max-complexity=10), reorder-python-imports v2.6.0
- **Pre-commit hooks**: black, flake8, pre-commit-hooks, reorder-python-imports, yamlfmt v0.14.0, actionlint v1.7.7
- **Test runner**: pytest 8.4.2, tox for multi-version; VCR cassettes in `tests/cassettes/`
- **CI**: tox in pythontest.yml, pre-commit/action in pre-commit.yml, `make dist` in python-publish.yml
- **Docs**: Sphinx with RTD, `pip install -e .` in `.readthedocs.yml`
- **Install for dev**: `pip install -e .[dev]`

## Post-Migration Target

- **Tooling**: setuptools with `pyproject.toml` (PEP 621 + PEP 735 dependency groups)
- **Package manager**: uv
- **Version management**: setuptools-scm (dynamic version from git tags)
- **Dependency groups**: `test` (pytest, vcrpy, etc.), `dev` (includes test + ruff)
- **Optional deps**: `google_drive`, `sentry` (user-facing, stay as `[project.optional-dependencies]`)
- **Lint/format**: ruff (replaces black, flake8, reorder-python-imports)
- **Pre-commit**: prek (run via `uvx prek`), hooks: ruff, ruff-format, pre-commit-hooks, yamlfmt, actionlint, uv-lock
- **CI**: `astral-sh/setup-uv@v7` with `enable-cache: true` + `cache-python: true`, `uv run --group test pytest`
- **Supply chain**: `exclude-newer = "7 days"` with `exclude-newer-package = ["le-utils"]`
- **Docs**: RTD uses `pip install uv && uv pip install -e . --system`
- **Install for dev**: `uv sync --group dev`

## Code Style (unchanged)

- **Line length**: 160 chars
- **Indentation**: 4 spaces (`.editorconfig`)
- **EOL**: LF, UTF-8, final newline yes, trim trailing whitespace
- **Makefile**: uses tabs (per `.editorconfig`)
- **Imports**: managed by ruff isort (force-single-line, known-first-party = ricecooker)
- **Naming**: PascalCase classes, snake_case functions/methods, UPPER_SNAKE_CASE constants

## Project Structure (unchanged)

```
ricecooker/          # Main package
  __init__.py        # Version via importlib.metadata + Python version check
  chefs.py           # SushiChef base class
  commands.py        # CLI implementation
  config.py          # Configuration & logging
  exceptions.py      # Custom exceptions
  classes/           # Node, file, license, question models
  managers/          # Progress and tree management
  utils/             # Utility modules
tests/               # pytest tests + cassettes/
docs/                # Sphinx docs (RTD, Python 3.11, Ubuntu 22.04)
examples/            # Sample implementations
```
