# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Extended Architecture

### End-to-End Flow

Chef script builds node tree → `uploadchannel()` validates → processes all files (download, convert, extract metadata) → diffs against Studio → uploads missing files → uploads channel structure → optionally publishes.

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
