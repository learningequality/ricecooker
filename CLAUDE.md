# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Ricecooker

A Python framework for converting educational content into Kolibri content channels and uploading them to Kolibri Studio. Content integration scripts ("chefs") subclass `SushiChef`, build a tree of nodes and files, and call `main()` to process and upload everything.

## Commands

```bash
pip install -e '.[test,dev]'        # install for development (use uv pip if venv was created with uv)
pytest                              # run all tests
pytest tests/test_files.py          # run a single test file
pytest -k 'test_something'         # filter by test name
pre-commit run --all-files          # lint (the only way to run linting)
```

**System dependencies required:** `ffmpeg` and `poppler-utils`.

**Code style:** max line length is 160 characters, enforced by black via pre-commit.

## Architecture

### End-to-End Flow

Chef script builds node tree → `uploadchannel()` validates → processes all files (download, convert, extract metadata) → diffs against Studio → uploads missing files → uploads channel structure → optionally publishes.

### Key Modules

- **`chefs.py`**: `SushiChef` base class (override `construct_channel()`), plus `JsonTreeChef`, `LineCook`, `YouTubeSushiChef`
- **`classes/nodes.py`**: `ChannelNode` (root), `TopicNode` (folders), `ContentNode` subclasses (`VideoNode`, `AudioNode`, `DocumentNode`, `HTML5AppNode`, `ExerciseNode`, `SlideshowNode`)
- **`classes/files.py`**: `DownloadFile` subclasses (`VideoFile`, `AudioFile`, `DocumentFile`, `HTMLZipFile`, `H5PFile`, etc.)
- **`managers/tree.py`**: `ChannelManager` — orchestrates validation, processing, upload
- **`utils/pipeline/`**: File processing pipeline (see below)

### File Processing Pipeline (`utils/pipeline/`)

The pipeline is the best-architected part of the codebase. **Use it as the reference model for new code.**

Three stages with ordered handlers: **transfer** (download) → **convert** (compress/transform) → **extract_metadata**. Handlers implement `should_handle()` / `execute()`. Transfer uses `FirstHandlerOnly` mode; convert and metadata use `AllHandlers` mode.

### le_utils Dependency

`le_utils` provides constants defining the Kolibri content model: `content_kinds`, `file_formats`, `format_presets`, `licenses`, `languages`, and label taxonomies. It increasingly includes validation schemas that ricecooker should conform to.

## Development Notes

- The pipeline code is the reference architecture — follow its OOP patterns when writing new code.
- Older code (especially `ricecooker/classes/`) has less test coverage. Take extra care when modifying it.
- PRs target `main` on `learningequality/ricecooker`. CI tests Python 3.9–3.13 on Linux, macOS, and Windows.

### Adding support for new file types

Adding a new file type requires exactly two changes to the pipeline:
1. A conversion handler in `convert.py` (subclass `ArchiveProcessingBaseHandler` for zip-based formats) — registered in `ConversionStageHandler.DEFAULT_CHILDREN`
2. A metadata extractor in `extract_metadata.py` (subclass `MetadataExtractor`, add extension-to-preset mapping in `PRESETS_FROM_EXTENSIONS`) — registered in `ExtractMetadataStageHandler.DEFAULT_CHILDREN`

The pipeline automatically infers content kind and preset from file extensions. Since the pipeline refactor, most dedicated `File` subclasses (e.g., `HTMLZipFile`, `DocumentFile`) and `Node` subclasses (e.g., `HTML5AppNode`, `DocumentNode`) are essentially backwards-compatibility APIs — in most cases the same effect is achieved by using `ContentNode` with a `uri` parameter. Do **not** create new `File` or `Node` subclasses, or modify existing ones to add presets, when adding new file type support. Only modify `classes/` modules if explicitly asked or if runtime context beyond what the pipeline provides is needed (e.g., subtitles, exercise questions).

Each handler should implement only the validation logic specified in its requirements. Do not copy validation logic from other handlers (e.g., HTML body parsing) unless the requirements call for it.

### Test organization

Pipeline tests go in `tests/pipeline/` (e.g. `test_convert.py`, `test_extract_metadata.py`). Add new tests to existing files in the appropriate directory rather than creating new top-level test files.
