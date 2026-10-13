# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

HL7 v2.x message toolkit: web viewer, terminal TUI, Python parsing library, and MCP server for AI agents.

## Tools

### Interactive HL7 Viewer (`hl7-viewer.html`)

Single self-contained HTML/CSS/JS file. Open directly in Firefox (`file://` works, no server needed).

**Features:**
- Three-panel layout: Input (paste/drag-drop/Open button) | Parsed table | Field detail | Compare (field-level diff)
- **Compare tab**: paste/open a second message, get a field-by-field diff with character-level highlighting of changed characters, summary bar, filter toggle, and side-by-side component breakdown in detail panel
- Embedded HL7 v2.3, v2.5, and v2.8 segment/field definitions (~22–37 segments) with data type component breakdowns (~49 types) — **generated from Python** via `tools/gen_js_defs.py`
- Auto-detects HL7 version from MSH-12 (v2.3.1 maps to v2.3, v2.8.x maps to v2.8 definitions)
- Correct MSH field numbering: MSH-1 = `|` (field separator), MSH-2 = encoding characters
- Component (`^`) and subcomponent (`&`) splitting, field repetition (`~`) handling
- Loadable integration profile JSON files via `<input type="file">` for custom field names, descriptions, notes, value maps
- Profile-driven validation: required-empty fields (red), value map mismatches (orange), missing segments (summary bar)
- Live search/filter (works in both Parsed and Compare tabs), collapsible segment groups, hide empty fields toggle (`E` key, persisted in localStorage), keyboard navigation, click-to-highlight raw view correspondence
- Dark theme with color coding: segments (rose), field names (green), data types (orange), addresses (blue)
- Encoding/charset awareness: byte-level detection (UTF-8/Latin-1/ASCII via BOM + heuristic), MSH-18 parsing, mismatch warnings in encoding info bar
- File Open button reads files as ArrayBuffer with automatic encoding detection (not just UTF-8)
- localStorage integration: external components can inject messages via `hl7viewer.pending` key (raw text or base64 bytes + optional profile)

**Integration Profiles** (`profiles/` directory):
- JSON files that overlay custom field names, descriptions, notes, and value maps onto the parsed view
- Profile fields support `required: true` and `valueMap` validation (enforced in web viewer, TUI, CLI output, and MCP `hl7_validate`)
- `profiles/sample-profile.json` — documented example showing all supported schema options
- Profiles are loaded via the toolbar file picker; work from `file://` protocol

### MCP Server (`hl7view/mcp_server.py`)

Exposes HL7 parsing capabilities to LLM agents via the Model Context Protocol (MCP).

**Setup:**
```bash
python3 -m venv venv
venv/bin/pip install -e ".[dev]"
```

Or without packaging: `venv/bin/pip install -r requirements-mcp.txt`

**Run:** Registered in `~/.claude.json` under `mcpServers.hl7` — starts automatically with Claude Code.

**Tools (8):**
- `hl7_parse` — Parse raw HL7 into structured JSON with definitions and profile overlays
- `hl7_get_field` — Extract a specific field by address (e.g. "PID-5", "MSH-9.1")
- `hl7_validate` — Check message for structural issues (missing required fields, length violations, unknown segments); with a profile: enforces `required` fields and `valueMap` value checks
- `hl7_anonymize` — Strip PHI from PID/NK1/GT1/IN1/MRG segments
- `hl7_transform` — Modify field values by address (e.g. `{"PID-5": "DOE^JOHN"}`)
- `hl7_send` — Send message via MLLP with optional TLS/mTLS
- `hl7_diff` — Compare two messages field-by-field, returns structured JSON diff with per-field status and values
- `hl7_explain` — Look up HL7 definitions (segments, fields, data types) without a message

**Resources (3):**
- `hl7://samples/{name}` — Sample HL7 messages from `samples/` directory
- `hl7://profiles/{name}` — Integration profiles from `profiles/` directory
- `hl7://definitions/{version}` — HL7 v2.3/v2.5/v2.8 definition summaries

### Terminal TUI (`hl7view/tui.py`)

Interactive terminal viewer using Textual. Launched via `hl7view/cli.py`.

**Keybindings:**
- Navigation: `↑`/`↓` or `j`/`k` (vi-style), `Enter` expand/edit, `b`/`f` history back/forward
- File: `o` open file, `p` paste from clipboard
- Display: `/` search, `v` cycle HL7 version (auto/2.3/2.5/2.8), `e` toggle empty fields, `r` raw view, `c` copy value
- Anonymization: `a` toggle anon, `n` switch name pool (ASCII/Estonian), `t` transliterate non-ASCII
- Integration: `i` load profile, `s` send via MLLP, `l` load MLLP response
- General: `?` help screen, `Esc` close overlay/cancel, `q` quit

**CLI non-interactive mode** (when piped or with flags):
- `--field SEG-N` extract single field, `--raw` raw segments, `--verbose` with components
- `--diff FILE_A FILE_B` field-level comparison, `--anon` anonymize, `--profile PATH` load profile
- `--send host:port` send via MLLP with optional `--tls`/`--tls-insecure`

## Definition Codegen

HL7 segment/data type definitions are maintained in `hl7view/definitions.py` (single source of truth) and generated into `hl7-viewer.html` for the web viewer.

**Workflow:** After editing `definitions.py`, regenerate the JS:
```bash
venv/bin/python tools/gen_js_defs.py
```

- The generator replaces the block between `@@GENERATED_DEFS_START@@` / `@@GENERATED_DEFS_END@@` markers in `hl7-viewer.html`
- `test_js_defs_in_sync` in `tests/test_definitions.py` fails if they're out of sync
- CI runs the generator and fails if `hl7-viewer.html` has uncommitted changes
- Never hand-edit definitions in `hl7-viewer.html` — edit `definitions.py` and regenerate
- Commit both `definitions.py` and `hl7-viewer.html` together

## HL7 Parsing Notes

- MSH-1 is the field separator `|` (implicit, not in pipe-split output). MSH-2 is encoding characters. MSH-3 onwards = `fields[2], fields[3], ...` with field number = array index + 1
- All other segments: `fields[1]` = SEG-1, `fields[2]` = SEG-2, etc.
- Repeated segments use bracket notation: `PID[2]-3`
- `replaceIllegalNewLines` / `normalizeMessage` handles HL7 messages where `\r` segment delimiters have been mixed with `\n` characters

## Tests

```bash
venv/bin/pytest tests/ -v
```

100 tests covering core modules (parser, encoding, profile, anonymize, definitions, diff) plus performance benchmarks (500-OBX parse/serialize/validate) and a JS codegen sync check. Uses all 4 sample messages as fixtures. Browser security regression tests in `tests/test_web_viewer_security.py` run separately in CI using Chromium and also exercise the standalone `file://` viewer. To run locally:

```bash
venv/bin/pip install -e ".[dev,browser]"
venv/bin/python -m playwright install chromium
venv/bin/pytest tests/test_web_viewer_security.py -v
```

The browser tests are skipped when Playwright is not installed.

- `pytest.ini` sets `pythonpath = .` so no install step needed
- `tests/conftest.py` — shared fixtures (parsed messages, sample profile)

## Sample Messages

`samples/` directory — included in repo:
- `adt-a01-admit-v25.hl7` — ADT^A01 admission (v2.5), 5 segments: MSH, EVN, PID, NK1, PV1
- `orm-o01-order-v23.hl7` — ORM^O01 radiology order (v2.3.1), 6 segments including ZDS custom segment, non-ASCII Estonian names, ISO-8859-1 charset
- `oru-r01-lab-v25.hl7` — ORU^R01 lab results (v2.5), 11 segments with 5 OBX (numeric, coded, string, formatted text with escape sequences, repeating values), NTE
- `oru-r01-lab-v28.hl7` — ORU^R01 CBC lab results (v2.8), 13 segments with SFT, SPM, 5 OBX with performing organization (fields 23–25), CWE types
- `oru-r01-large-500obx.hl7` — Synthetic ORU^R01 (v2.8), 507 segments with 500 OBX for performance testing
