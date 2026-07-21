# Page-archiving example

Renders a JS/SPA page to an offline HTML5 zip using
[single-file-cli](https://github.com/gildas-lormeau/single-file-cli) for capture
and the ricecooker pipeline for `data:`-URI localization and media conversion.

## How it works

1. `build_file_pipeline` returns `make_page_archiving_pipeline(...)`, which
   prepends `SingleFileRenderHandler` to the DOWNLOAD stage.
2. A `ContentNode` whose `uri` starts with `singlefile+` marks render intent.
   `context={"crawl_max_depth": ..., "crawl_inner_links_only": ...}` controls
   crawl depth and link scope (parity with the old `link_policy`).
3. The handler shells out to the `single-file` binary, which renders the page
   with Chromium and inlines assets as `data:` URIs.
4. The CONVERT stage explodes each `data:` URI into a real file, converts /
   compresses it, and rewrites the reference — yielding a real HTML5 zip.

## Prerequisites (page archiving only)

The core `pip install ricecooker` does **not** require these; they are only
needed for the `singlefile+` render handler:

```bash
npm install -g single-file-cli
```

plus a Chromium/Chrome browser on `PATH`. If it is not on `PATH`, pass its
location via the node `context`: `{"browser_executable_path": "/path/to/chrome"}`.

## Manual offline-render verification

The `single-file` binary and Chromium are **not** available in CI, so the
end-to-end render is verified by hand. Whoever has the toolchain runs this once
and records the outcome below.

1. Install `single-file-cli` + Chromium locally.
2. Check the argv builder in `ricecooker/utils/singlefile.py` against
   `single-file --help` — flag names, `=true/false` syntax, and the entry-output
   naming that must yield a top-level `index.html` (crawl mode, `crawl_max_depth
   > 1`, uses `--filename-template`). Fix any mismatch and note it here.
3. Run the sample chef against the real SPA (a dry run is enough — file
   processing needs no upload token).
4. Confirm the `.zip` has `index.html`, exploded asset files (no residual
   `data:` URIs), and rewritten references, then load it in a local Kolibri /
   kolibri-zip preview and confirm it renders offline.

### Verification record

- Target URL:
- Date / environment:
- single-file-cli version + flag check result:
- Result (pass/fail):
- Notes:
