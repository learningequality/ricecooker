# Migrate to uv + ruff + pyproject.toml — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate ricecooker from pip/tox/setup.py/black/flake8 to uv/ruff/pyproject.toml, matching the Kolibri ecosystem approach (learningequality/kolibri#14457).

**Architecture:** Replace `setup.py` + `setup.cfg` with a single `pyproject.toml` using setuptools backend with setuptools-scm for versioning and PEP 735 dependency groups. Replace tox with direct `uv run pytest` in CI. Replace black/flake8/reorder-python-imports with ruff. Replace pre-commit with prek. Update all three CI workflows accordingly.

**Tech Stack:** uv, ruff, setuptools-scm, prek, astral-sh/setup-uv@v7, PEP 735 dependency groups

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `pyproject.toml` | Single source of project metadata, dependencies, build config, ruff config, pytest config |
| Delete | `setup.py` | Replaced by pyproject.toml |
| Delete | `setup.cfg` | Replaced by pyproject.toml (flake8 config → ruff, bumpversion → setuptools-scm) |
| Delete | `tox.ini` | Replaced by direct uv invocation in CI |
| Delete | `pytest.ini` | Merged into pyproject.toml `[tool.pytest.ini_options]` |
| Delete | `MANIFEST.in` | Not needed with modern setuptools + pyproject.toml |
| Modify | `ricecooker/__init__.py` | Remove hardcoded `__version__`, use importlib.metadata |
| Modify | `docs/conf.py` | Update version import to use importlib.metadata |
| Modify | `.pre-commit-config.yaml` | Replace black/flake8/reorder-python-imports with ruff + add uv-lock hook, use prek |
| Modify | `.github/workflows/pythontest.yml` | Replace setup-python/tox with setup-uv/uv run |
| Modify | `.github/workflows/pre-commit.yml` | Replace pre-commit/action with prek |
| Modify | `.github/workflows/python-publish.yml` | Use uv for build |
| Modify | `.github/dependabot.yml` | Change pip ecosystem to uv |
| Modify | `.readthedocs.yml` | Use uv for install |
| Modify | `Makefile` | Update targets to use uv and ruff |
| Modify | `CONTRIBUTING.md` | Update developer setup instructions for uv |
| Modify | `.gitignore` | Add uv-specific entries, remove tox entries |

## Task Dependencies

Tasks **1 → 2 → 3 → 4** are strictly sequential — each depends on the previous. Task 5 depends on Task 4 (needs `uv sync --group dev` to have run). Tasks 6–13 are independent of each other but all depend on Tasks 1–4 being complete. Task 14 must run last.

```
1 → 2 → 3 → 4 → 5 ──→ 14
                  ├→ 6 ─┤
                  ├→ 7 ─┤
                  ├→ 8 ─┤
                  ├→ 9 ─┤
                  ├→ 10 ┤
                  ├→ 11 ┤
                  ├→ 12 ┤
                  └→ 13 ┘
```

---

### Task 1: Create pyproject.toml with project metadata and dependencies

This is the foundational task. All subsequent tasks depend on the package being defined here.

**Files:**
- Create: `pyproject.toml`
- Read (reference only): `setup.py`, `setup.cfg`, `pytest.ini`

- [x] **Step 1: Create pyproject.toml with build system, metadata, and dependencies**

```toml
[build-system]
requires = ["setuptools>=75.0", "setuptools-scm>=8"]
build-backend = "setuptools.build_meta"

[project]
name = "ricecooker"
description = "API for adding content to the Kolibri content curation server"
authors = [
    {name = "Learning Equality", email = "dev@learningequality.org"},
]
license = "MIT"
readme = "README.md"
keywords = ["ricecooker"]
requires-python = ">=3.9, <3.14"
dynamic = ["version"]
classifiers = [
    "Intended Audience :: Developers",
    "Development Status :: 5 - Production/Stable",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Natural Language :: English",
    "Topic :: Education",
]
dependencies = [
    "requests>=2.11.1",
    "le_utils>=0.2.10",
    "requests_file",
    "beautifulsoup4>=4.6.3,<4.9.0",
    "selenium==4.36.0",
    "yt-dlp>=2024.12.23",
    "html5lib",
    "cachecontrol==0.14.3",
    "filelock==3.19.1",
    "css-html-js-minify==2.5.5",
    "pypdf2==1.26.0",
    "dictdiffer>=0.8.0",
    "Pillow==11.3.0",
    "colorlog>=4.1.0,<6.11",
    "chardet==5.2.0",
    "ffmpy>=0.2.2",
    "pdf2image==1.17.0",
    "le-pycaption>=2.2.0a1",
    "EbookLib>=0.17.1",
    "filetype>=1.1.0",
    "urllib3==2.6.3",
    "langcodes[data]==3.5.1",
]

[project.optional-dependencies]
google_drive = ["google-api-python-client", "google-auth"]
sentry = ["sentry-sdk>=2.32.0"]

[project.scripts]
corrections = "ricecooker.utils.corrections:correctionsmain"

[project.urls]
Homepage = "https://github.com/learningequality/ricecooker"

[dependency-groups]
test = [
    "requests-cache==1.2.1",
    "pytest==8.4.2",
    "pytest-env==1.1.5",
    "vcrpy==7.0.0; python_version >='3.10'",
    "mock==5.2.0",
]
dev = [
    {include-group = "test"},
    "ruff>=0.11",
]

[tool.setuptools-scm]

[tool.setuptools.packages.find]
include = ["ricecooker*"]

[tool.uv]
exclude-newer = "7 days"
exclude-newer-package = ["le-utils"]

[tool.pytest.ini_options]
testpaths = ["tests"]
norecursedirs = ["docs", "examples", "resources"]
env = [
    "RICECOOKER_STORAGE=./.pytest_storage",
    "RICECOOKER_FILECACHE=./.pytest_filecache",
]

[tool.ruff]
line-length = 160
exclude = ["docs", "examples"]

[tool.ruff.lint]
select = ["E", "F", "W", "C90"]
ignore = ["E226", "E203", "E741"]
# W503 does not exist in ruff (it uses Wxxx for whitespace)
# E41 (ambiguous) is not a ruff code; individual E4xx codes can be ignored if needed

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.isort]
known-first-party = ["ricecooker"]
force-single-line = true
```

Note: The current `setup.py` concatenates `README.md` + `docs/history.rst` for PyPI long_description. The `pyproject.toml` `readme` field only supports a single file. This is an intentional simplification — the changelog in `docs/history.rst` is stale (last entry 2020) and not useful on PyPI.

**⚠ Verify at implementation time:** Run `uv help` or check uv docs to confirm that `exclude-newer = "7 days"` (relative duration) and `exclude-newer-package` are supported in `[tool.uv]`. If `exclude-newer` only accepts RFC 3339 dates, use today's date (e.g., `"2026-04-01"`) and add a comment explaining to update it periodically. If `exclude-newer-package` is not supported, remove it and add a comment noting that le-utils is not exempt.

- [x] **Step 2: Verify pyproject.toml parses correctly**

Run: `python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb')); print('OK')"`
Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add pyproject.toml with project metadata, dependencies, and tool config"
```

---

### Task 2: Update version management to setuptools-scm

Replace the hardcoded `__version__` in `ricecooker/__init__.py` with dynamic version from `importlib.metadata`, and update `docs/conf.py` to match.

**Files:**
- Modify: `ricecooker/__init__.py`
- Modify: `docs/conf.py:24`

- [x] **Step 1: Update ricecooker/__init__.py**

Replace the entire contents of `ricecooker/__init__.py` with:

```python
# -*- coding: utf-8 -*-

__author__ = "Learning Equality"
__email__ = "info@learningequality.org"

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

try:
    __version__ = version("ricecooker")
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"


import sys

if sys.version_info < (3, 9, 0):
    raise RuntimeError("Ricecooker only supports Python 3.9+")
```

- [x] **Step 2: Update docs/conf.py version import**

In `docs/conf.py`, replace line 24:
```python
from ricecooker import __version__ as current_ricecooker_version
```
with:
```python
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version

try:
    current_ricecooker_version = get_version("ricecooker")
except PackageNotFoundError:
    current_ricecooker_version = "0.0.0.dev0"
```

Also remove the `from ricecooker import __version__ as current_ricecooker_version` import line.

Note: `docs/conf.py` uses `current_ricecooker_version` in later lines for `version` and `release` assignments — those remain unchanged.

- [x] **Step 3: Commit**

```bash
git add ricecooker/__init__.py docs/conf.py
git commit -m "feat: switch to setuptools-scm for version management"
```

---

### Task 3: Delete legacy build/config files

Remove `setup.py`, `setup.cfg`, `tox.ini`, `pytest.ini`, and `MANIFEST.in` — all replaced by `pyproject.toml`.

**Files:**
- Delete: `setup.py`
- Delete: `setup.cfg`
- Delete: `tox.ini`
- Delete: `pytest.ini`
- Delete: `MANIFEST.in`

- [x] **Step 1: Delete legacy files**

```bash
git rm setup.py setup.cfg tox.ini pytest.ini MANIFEST.in
```

- [x] **Step 2: Verify the package metadata resolves from pyproject.toml alone**

Run: `python -c "import tomllib; data = tomllib.load(open('pyproject.toml', 'rb')); assert data['project']['name'] == 'ricecooker'; assert 'version' in data['project']['dynamic']; print('OK')"`
Expected: `OK`

- [x] **Step 3: Verify uv can resolve the project**

Run: `uv lock --check 2>&1 || uv lock 2>&1 | tail -5`
Expected: uv can resolve the project with only `pyproject.toml` (no `setup.py`). If this fails, it will be caught and fixed here rather than in Task 4.

- [x] **Step 4: Commit**

```bash
git commit -m "chore: remove setup.py, setup.cfg, tox.ini, pytest.ini, MANIFEST.in"
```

---

### Task 4: Generate uv.lock

Initialize the uv lockfile so all dependency resolution is pinned.

**Files:**
- Create: `uv.lock` (generated)

- [x] **Step 1: Run uv lock**

Run: `uv lock`
Expected: Creates `uv.lock` without errors.

**Troubleshooting `exclude-newer`:**
- If `uv lock` fails with an error about the `exclude-newer` or `exclude-newer-package` config keys, check the installed uv version's docs. The `exclude-newer` field may only accept RFC 3339 dates (e.g., `"2026-04-01"`), not relative durations like `"7 days"`. Similarly, `exclude-newer-package` may not exist — if so, remove it and add a comment.
- If `exclude-newer` causes resolution failures because packages were published outside the window, temporarily remove the `exclude-newer` line, run `uv lock`, then add it back. The constraint only affects future resolutions — existing locked versions are preserved.

- [x] **Step 2: Verify uv sync works**

Run: `uv sync --group dev`
Expected: Installs all dependencies including dev group without errors.

- [x] **Step 3: Verify tests can run**

Run: `uv run pytest tests/ -x --timeout=60 -q 2>&1 | head -30`
Expected: Tests start running (some may fail due to missing system deps like ffmpeg, but pytest itself should start).

- [x] **Step 4: Commit**

```bash
git add uv.lock
git commit -m "chore: add uv.lock"
```

---

### Task 5: Replace pre-commit config with ruff + prek

Replace black/flake8/reorder-python-imports hooks with ruff, add uv-lock hook, and configure for use with prek instead of pre-commit.

**Files:**
- Modify: `.pre-commit-config.yaml`

- [x] **Step 1: Replace .pre-commit-config.yaml contents**

Replace the entire `.pre-commit-config.yaml` with:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.1.0
    hooks:
      - id: trailing-whitespace
      - id: check-yaml
      - id: check-added-large-files
        exclude: '^tests/cassettes'
      - id: debug-statements
      - id: end-of-file-fixer
        exclude: '^.+?\.json$'
  - repo: https://github.com/google/yamlfmt
    rev: v0.14.0
    hooks:
      - id: yamlfmt
        exclude: '^tests/cassettes'
  - repo: https://github.com/rhysd/actionlint
    rev: v1.7.7
    hooks:
      - id: actionlint
        # Expects shellcheck to be installed on the system
        # https://github.com/koalaman/shellcheck#installing
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.7.2
    hooks:
      - id: uv-lock
```

Note: The exact `rev` for ruff-pre-commit and uv-pre-commit should be checked at implementation time. Use the latest stable versions. The versions above are approximate — check https://github.com/astral-sh/ruff-pre-commit/releases and https://github.com/astral-sh/uv-pre-commit/releases for the current latest.

- [x] **Step 2: Verify prek can run the hooks**

Run: `uvx prek run --all-files 2>&1 | tail -20`
Expected: All hooks run. Ruff may report formatting/lint fixes on first run — that's expected and will be addressed next.

- [x] **Step 3: Apply ruff formatting fixes across the codebase**

Run: `uv run --group dev ruff check --fix . && uv run --group dev ruff format .`
Expected: Ruff applies auto-fixes for import sorting and formatting.

- [x] **Step 4: Run prek again to verify all hooks pass**

Run: `uvx prek run --all-files 2>&1 | tail -20`
Expected: All hooks pass.

- [x] **Step 5: Run tests to verify ruff changes didn't break anything**

Run: `uv run pytest tests/ -x -q 2>&1 | tail -20`
Expected: Tests pass (same results as before ruff changes).

- [x] **Step 6: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "feat: replace black/flake8/reorder-python-imports with ruff, add uv-lock hook"
```

- [x] **Step 7: Commit ruff formatting changes separately**

```bash
git add -u
git commit -m "style: apply ruff formatting and import sorting across codebase"
```

---

### Task 6: Update CI workflow — pythontest.yml

Replace setup-python + tox with setup-uv + uv run pytest.

**Files:**
- Modify: `.github/workflows/pythontest.yml`

- [x] **Step 1: Replace pythontest.yml contents**

Replace the entire `.github/workflows/pythontest.yml` with:

```yaml
name: Python tests
on:
  push:
    branches:
      - develop
      - main
  pull_request:
    branches:
      - develop
      - main
jobs:
  pre_job:
    name: Path match check
    runs-on: ubuntu-latest
    # Map a step output to a job output
    outputs:
      should_skip: ${{ steps.skip_check.outputs.should_skip }}
    steps:
      - id: skip_check
        uses: fkirc/skip-duplicate-actions@master
        with:
          github_token: ${{ github.token }}
          paths: '["**.py", "pyproject.toml", "uv.lock", ".github/workflows/pythontest.yml"]'
  unit_test:
    name: Python unit tests
    needs: pre_job
    runs-on: ${{ matrix.os }}
    strategy:
      max-parallel: 5
      fail-fast: false
      matrix:
        os: [windows-latest, ubuntu-latest, macos-latest]
        python-version: ['3.9', '3.10', '3.11', '3.12', '3.13']
    steps:
      - uses: actions/checkout@v6
        if: ${{ needs.pre_job.outputs.should_skip != 'true' }}
      - name: Set up uv
        if: ${{ needs.pre_job.outputs.should_skip != 'true' }}
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-python: true
          python-version: ${{ matrix.python-version }}
      - name: Install Ubuntu dependencies
        run: |
          sudo apt-get -y -qq update
          sudo apt-get install -y ffmpeg
          sudo apt-get install -y poppler-utils
        if: ${{ needs.pre_job.outputs.should_skip != 'true' && startsWith(matrix.os, 'ubuntu') }}
      - name: Cache Mac dependencies
        uses: actions/cache@v5
        if: needs.pre_job.outputs.should_skip != 'true' && matrix.os == 'macos-latest'
        with:
          path: ~/Library/Caches/Homebrew
          key: ${{ runner.os }}-brew-${{ hashFiles('.github/workflows/pythontest.yml') }}
      - name: Unlink Homebrew Python 3.13 if not testing 3.13
        if: needs.pre_job.outputs.should_skip != 'true' && matrix.os == 'macos-latest' && matrix.python-version != '3.13'
        run: brew unlink python@3.13 || true
      - name: Install Mac dependencies
        run: |
          # Conditionally link python@3.13 to avoid conflicts when testing Python 3.13
          # See: https://github.com/actions/runner-images/issues/9966
          if [[ "${{ matrix.python-version }}" != "3.13" ]]; then
            echo "Linking Homebrew python@3.13"
            brew link --overwrite python@3.13
          else
            echo "Skipping Homebrew python@3.13 linking for Python 3.13 test."
          fi
          brew install ffmpeg poppler
        if: needs.pre_job.outputs.should_skip != 'true' && matrix.os == 'macos-latest'
      - name: Windows dependencies cache
        id: windowscache
        if: needs.pre_job.outputs.should_skip != 'true' && matrix.os == 'windows-latest'
        uses: actions/cache@v5
        with:
          path: ${{ github.workspace }}\tools
          key: ${{ runner.os }}-${{ matrix.python-version }}-tools-${{ hashFiles('.github/workflows/pythontest.yml') }}
      - name: Download Windows dependencies if needed
        if: needs.pre_job.outputs.should_skip != 'true' && matrix.os == 'windows-latest'
        shell: pwsh
        run: |
          # Create tools directory if it doesn't exist
          New-Item -Path "tools" -ItemType Directory -Force -ErrorAction SilentlyContinue

          # Check and download FFmpeg if needed
          if (-not (Test-Path "$env:GITHUB_WORKSPACE\tools\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe")) {
            Write-Output "FFmpeg not found, downloading..."
            curl.exe --output ffmpeg.zip -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip
            7z x ffmpeg.zip -otools -y
          } else {
            Write-Output "FFmpeg already exists, skipping download"
          }

          # Check and download Poppler if needed
          if (-not (Test-Path "$env:GITHUB_WORKSPACE\tools\poppler-21.11.0\Library\bin\pdfinfo.exe")) {
            Write-Output "Poppler not found, downloading..."
            curl.exe --output poppler.zip -L https://github.com/oschwartz10612/poppler-windows/releases/download/v21.11.0-0/Release-21.11.0-0.zip
            7z x poppler.zip -otools -y
          } else {
            Write-Output "Poppler already exists, skipping download"
          }
      - name: Set paths to Windows dependencies
        if: needs.pre_job.outputs.should_skip != 'true' && matrix.os == 'windows-latest'
        shell: pwsh
        run: |
          Add-Content -Path $env:GITHUB_PATH -Value "$env:GITHUB_WORKSPACE\tools\ffmpeg-master-latest-win64-gpl\bin" -Encoding utf8
          Add-Content -Path $env:GITHUB_PATH -Value "$env:GITHUB_WORKSPACE\tools\poppler-21.11.0\Library\bin" -Encoding utf8
      - name: Run tests
        if: ${{ needs.pre_job.outputs.should_skip != 'true' }}
        run: uv run --group test --extra google_drive pytest
```

Key changes from the original:
- `actions/setup-python` → `astral-sh/setup-uv@v7` with `enable-cache: true` and `cache-python: true`
- Removed pip install tox, tox env cache steps
- `tox -e py${{ matrix.python-version }}` → `uv run --group test --extra google_drive pytest`
- Updated `paths` in skip check: `setup.py` → `pyproject.toml`, added `uv.lock`
- **New:** Added Homebrew Python 3.13 unlinking workaround for macOS (not in original workflow — addresses [actions/runner-images#9966](https://github.com/actions/runner-images/issues/9966))
- Note: If Windows has issues with `cache-python: true`, it can be turned off for the Windows matrix entries — the CI run will surface this.
- Note: The other workflow files (`call-pull-request-target.yml`, `call-*.yml`, `community-contribution-labeling.yml`) do not use Python/pip directly and need no changes.

- [x] **Step 2: Commit**

```bash
git add .github/workflows/pythontest.yml
git commit -m "ci: replace tox with uv run pytest in test workflow"
```

---

### Task 7: Update CI workflow — pre-commit.yml

Replace pre-commit/action with prek via uv.

**Files:**
- Modify: `.github/workflows/pre-commit.yml`

- [x] **Step 1: Replace pre-commit.yml contents**

Replace the entire `.github/workflows/pre-commit.yml` with:

```yaml
name: Linting
on:
  push:
    branches:
      - develop
      - main
  pull_request:
    branches:
      - develop
      - main
jobs:
  pre_job:
    name: Path match check
    runs-on: ubuntu-latest
    # Map a step output to a job output
    outputs:
      should_skip: ${{ steps.skip_check.outputs.should_skip }}
    steps:
      - id: skip_check
        uses: fkirc/skip-duplicate-actions@master
        with:
          github_token: ${{ github.token }}
          paths_ignore: '["**.po", "**.json"]'
  linting:
    name: All file linting
    needs: pre_job
    if: ${{ needs.pre_job.outputs.should_skip != 'true' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - name: Set up uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-python: true
      - name: Run prek
        run: uvx prek run --all-files
```

Key changes:
- Removed `actions/setup-python` (uv manages Python)
- Replaced `pre-commit/action@v3.0.1` with `uvx prek run --all-files`

- [x] **Step 2: Commit**

```bash
git add .github/workflows/pre-commit.yml
git commit -m "ci: replace pre-commit/action with prek in linting workflow"
```

---

### Task 8: Update CI workflow — python-publish.yml

Replace pip/setuptools build with uv build.

**Files:**
- Modify: `.github/workflows/python-publish.yml`

- [x] **Step 1: Replace python-publish.yml contents**

Replace the entire `.github/workflows/python-publish.yml` with:

```yaml
# This workflow will upload a Python Package using pypa/gh-action-pypi-publish when a release is created

name: Upload Python Package
on:
  release:
    types: [published]
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      # IMPORTANT: this permission is mandatory for trusted publishing
      id-token: write
    steps:
      - uses: actions/checkout@v6
      - name: Set up uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-python: true
      - name: Build distribution
        run: uv build
      - name: Publish package distributions to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

Key changes:
- Removed `actions/setup-python`, pip install setuptools/wheel/pre-commit
- Replaced `make dist` with `uv build`

- [x] **Step 2: Commit**

```bash
git add .github/workflows/python-publish.yml
git commit -m "ci: use uv build in publish workflow"
```

---

### Task 9: Update dependabot.yml

Change the pip ecosystem to uv so dependabot tracks `uv.lock`.

**Files:**
- Modify: `.github/dependabot.yml`

- [x] **Step 1: Update dependabot.yml**

Replace the pip ecosystem section. Change:
```yaml
  - package-ecosystem: "pip"
```
to:
```yaml
  - package-ecosystem: "uv"
```

The rest of the pip section (directory, schedule, cooldown) stays the same.

- [x] **Step 2: Commit**

```bash
git add .github/dependabot.yml
git commit -m "ci: switch dependabot from pip to uv ecosystem"
```

---

### Task 10: Update Makefile

Update targets to use uv and ruff instead of pip, tox, and pre-commit.

**Files:**
- Modify: `Makefile`

- [x] **Step 1: Update Makefile**

Replace the entire `Makefile` with:

```makefile
.PHONY: clean clean-test clean-pyc clean-build docs help
.DEFAULT_GOAL := help
define BROWSER_PYSCRIPT
import os, webbrowser, sys
try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT
BROWSER := python -c "$$BROWSER_PYSCRIPT"

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts


clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -f .coverage
	rm -fr htmlcov/
	rm -rf tests/testcontent/downloaded/*
	rm -rf tests/testcontent/generated/*

lint: ## run linting with prek
	uvx prek run --all-files

test: clean-test ## run tests quickly with the default Python
	uv run --group test pytest

test-all: clean-test ## run tests on every Python version
	for py in 3.9 3.10 3.11 3.12 3.13; do \
		echo "Testing Python $$py"; \
		uv run --python $$py --group test pytest || exit 1; \
	done

integration-test:
	echo "Testing against hotfixes"
	CONTENTWORKSHOP_URL=https://hotfixes.studio.learningequality.org uv run python tests/test_chef_integration.py
	echo "Testing against unstable"
	CONTENTWORKSHOP_URL=https://unstable.studio.learningequality.org uv run python tests/test_chef_integration.py
	echo "Testing against production"
	CONTENTWORKSHOP_URL=https://studio.learningequality.org uv run python tests/test_chef_integration.py

coverage: ## check code coverage quickly with the default Python
	uv run --group test --with coverage coverage run --source ricecooker -m pytest
	uv run --with coverage coverage report -m
	uv run --with coverage coverage html
	$(BROWSER) htmlcov/index.html

docsclean:
	$(MAKE) -C docs clean
	rm -f docs/_build/*

docs: ## generate Sphinx HTML documentation
	uv run --with-requirements docs/requirements.txt $(MAKE) -C docs clean
	uv run --with-requirements docs/requirements.txt $(MAKE) -C docs html

latexdocs:
	uv run --with-requirements docs/requirements.txt $(MAKE) -C docs clean
	uv run --with-requirements docs/requirements.txt $(MAKE) -C docs latex

servedocs: docs ## compile the docs watching for changes
	watchmedo shell-command -p '*.rst' -c '$(MAKE) -C docs html' -R -D .

dist: clean ## build source and wheel distributions
	uv build

release: dist ## package and upload a release
	uv run --with twine twine upload dist/*

install: clean ## install the package to the active Python's site-packages
	uv sync
```

Key changes:
- `pre-commit run --all-files` → `uvx prek run --all-files`
- `pytest` → `uv run --group test pytest`
- `tox` → loop over Python versions with `uv run --python`
- `pip install ...` → `uv run --with ...`
- `python setup.py sdist bdist_wheel` → `uv build`
- Removed `.tox/` from `clean-test`
- `make install` → `uv sync`

- [x] **Step 2: Commit**

```bash
git add Makefile
git commit -m "chore: update Makefile to use uv, ruff, and prek"
```

---

### Task 11: Update .readthedocs.yml

Update ReadTheDocs config to use uv for installation.

**Files:**
- Modify: `.readthedocs.yml`

- [x] **Step 1: Update .readthedocs.yml**

Replace the entire `.readthedocs.yml` with:

```yaml
version: 2
formats: all
build:
  os: ubuntu-22.04
  tools:
    python: "3.11"
  jobs:
    pre_install:
      - pip install uv
      - uv pip install -e . --system
sphinx:
  configuration: docs/conf.py
python:
  install:
    - requirements: docs/requirements.txt
```

Note: ReadTheDocs doesn't natively support uv yet, so we use `pip install uv` in the pre_install step and then `uv pip install -e . --system` to install the package into RTD's managed environment (NOT `uv sync`, which would create an isolated `.venv` that RTD ignores). The `--system` flag tells uv to install into the active environment. The docs/requirements.txt is still installed separately by RTD's Python config.

- [x] **Step 2: Commit**

```bash
git add .readthedocs.yml
git commit -m "ci: update ReadTheDocs config to use uv"
```

---

### Task 12: Update .gitignore

Add uv-specific entries and remove obsolete tox entries.

**Files:**
- Modify: `.gitignore`

- [x] **Step 1: Update .gitignore**

Add to the end of `.gitignore` (before any blank trailing lines):

```
# uv
.venv/
```

Remove the `.tox/` line from the test artifacts section (it's no longer used).

Note: `uv.lock` should NOT be in `.gitignore` — it must be committed.

- [x] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: update .gitignore for uv, remove tox entry"
```

---

### Task 13: Update CONTRIBUTING.md

Update developer setup instructions to use uv.

**Files:**
- Modify: `CONTRIBUTING.md`

- [x] **Step 1: Update CONTRIBUTING.md**

Replace the "Becoming a ricecooker developer" section — from the heading `Becoming a ricecooker developer` through the end of step 6 (ends at `To get `flake8` and `tox`, just `pip install` them into your virtualenv.`). Keep everything before this section and step 7 onward unchanged.

Replace with:
```markdown
Becoming a ricecooker developer
-------------------------------

Ready to contribute? In order to work on the `ricecooker` code you'll first need
to have [Python 3.9+](https://www.python.org/downloads/) on your computer.

Here are the steps for setting up `ricecooker` for local development:

1. Fork the `ricecooker` repo on GitHub.
   The result will be your very own copy repository for the ricecooker
   codebase `https://github.com/<your-github-username>/ricecooker`.
2. Clone your fork of the repository locally, and go into the `ricecooker` directory:

    ```
    git clone git@github.com:<your-github-username>/ricecooker.git
    cd ricecooker/
    ```

3. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it already:

    ```
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    On Windows:
    ```
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

4. Install the `ricecooker` code and its dependencies:

    ```
    uv sync --group dev
    ```

5. Create a branch for local development:

    ```
    git checkout -b name-of-your-bugfix-or-feature
    ```

   Now you can make your changes locally.


6. When you're done making changes, check that your changes pass linting
   and the `ricecooker` test suite:

   Run linting:
    ```
    uvx prek run --all-files
    ```

   Run the tests:
    ```
    uv run --group test pytest
    ```

   Run tests across all supported Python versions:
    ```
    make test-all
    ```
```

Also update the "Pull Request Guidelines" section. Find the text:
```
3. The pull request should work for Python 3.5+. Check
   https://travis-ci.org/github/learningequality/ricecooker/pull_requests
   and make sure that the tests pass for all supported Python versions.
```
Replace with:
```
3. The pull request should work for Python 3.9+. Check the GitHub Actions CI
   and make sure that the tests pass for all supported Python versions.
```

- [x] **Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: update CONTRIBUTING.md for uv-based development workflow"
```

---

### Task 14: Simplify pass — review all changes

Run the /simplify skill to review all changed files for reuse, quality, and efficiency.

**Files:**
- All files modified in Tasks 1–13

- [x] **Step 1: Review pyproject.toml for redundancy**

Check that:
- No duplicate dependencies between `[project.dependencies]` and `[dependency-groups]`
- Ruff config doesn't duplicate defaults unnecessarily
- `[tool.setuptools.packages.find]` include pattern is correct

- [x] **Step 2: Verify all tests still pass**

Run: `uv run --group test pytest tests/ -x -q 2>&1 | tail -20`
Expected: Tests pass.

- [x] **Step 3: Verify linting passes**

Run: `uvx prek run --all-files 2>&1 | tail -20`
Expected: All hooks pass.

- [x] **Step 4: Verify package builds correctly**

Run: `uv build 2>&1 | tail -10`
Expected: sdist and wheel built successfully.

- [x] **Step 5: Verify setuptools-scm version works**

Run: `uv run python -c "import ricecooker; print(ricecooker.__version__)"`
Expected: Prints a version string (may be `0.0.0.dev0` if no git tags match, or a scm-derived version if tags exist).

- [x] **Step 6: Fix any issues found and commit**

If any issues are found, fix them and create a commit describing the fix.

---

## Acceptance Criteria Traceability

| Acceptance Criterion | Task |
|---------------------|------|
| `pyproject.toml` replaces `setup.py`/`setup.cfg` | Tasks 1, 3 |
| Versioning handled by setuptools-scm | Task 2 |
| `tox.ini` removed; CI uses uv directly | Tasks 3, 6 |
| Linting/formatting handled by ruff | Tasks 1 (config), 5 (hooks + formatting) |
| Pre-commit uses prek | Tasks 5, 7 |
| CI workflows use `astral-sh/setup-uv@v7` | Tasks 6, 7, 8 |
| `exclude-newer` cooldown configured | Task 1 (pyproject.toml `[tool.uv]`) |
| `uv-lock` pre-commit hook added | Task 5 |
| All existing tests pass | Task 14 |
| Developer documentation updated | Task 13 |
