# AGENTS.md

Guidance for AI coding agents working in this repository.

## Quick Start

```bash
pip install -e '.[test,dev]'        # install (use uv pip if venv was created with uv)
pytest                              # run all tests
pytest tests/test_files.py          # run a single test file
pytest -k 'test_something'         # filter by test name
pre-commit run --all-files          # lint (the ONLY way to run linting)
```

**System dependencies:** `ffmpeg` and `poppler-utils`.

## Critical Gotchas

- **Linting:** Always use `pre-commit run --all-files`. Never run black, flake8, or other tools directly.
- **Line length:** 160 characters, enforced by pre-commit.
- **New file types require exactly two changes:** (1) a conversion handler in `convert.py`, (2) a metadata extractor in `extract_metadata.py`. That's it. Do NOT touch `classes/files.py` or `classes/nodes.py` — the existing File/Node subclasses there are legacy backwards-compatibility APIs that are NOT needed for new file types. The pipeline infers kinds and presets automatically.
- **Test placement:** Pipeline tests go in `tests/pipeline/` — add to existing files like `test_convert.py` and `test_extract_metadata.py`. Do not create new test files.
- **Validation logic:** Each handler implements only the validation its spec requires. Do not copy validation from other handlers (e.g., do not add HTML body parsing or empty-body checks unless the spec explicitly requires them).
- **le_utils constants:** Always verify constants exist by running `python3 -c "from le_utils.constants import file_formats, format_presets; print(file_formats.CONSTANT_NAME); print(format_presets.CONSTANT_NAME)"`. Names are often non-obvious (e.g., `file_formats.HTML5_ARTICLE` for kpub, `format_presets.KPUB_ZIP` not `format_presets.KPUB`).

## Project Overview

Ricecooker converts educational content into Kolibri content channels and uploads to Kolibri Studio. Chef scripts subclass `SushiChef`, build a node/file tree, and call `main()`.

## Key Architecture

- **`utils/pipeline/`**: File processing pipeline — transfer → convert → extract_metadata. Reference architecture for new code.
- **`classes/nodes.py`**: Node tree (`ChannelNode`, `TopicNode`, `ContentNode` subclasses) — legacy, do not add new subclasses
- **`classes/files.py`**: File classes (`DownloadFile` subclasses) — legacy, do not add new subclasses
- **`chefs.py`**: `SushiChef` base class
- **`le_utils`**: External package providing content model constants (`file_formats`, `format_presets`, `content_kinds`, `licenses`)
