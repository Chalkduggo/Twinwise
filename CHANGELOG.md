# Changelog

## 0.3.5 — accessibility and small screens

- **Keyboard**: the menu, the file picker, the key-file picker and the sheet now work without a mouse. Arrow keys move through the sheet, Enter opens the column, and the Cell panel has a *Column settings* button
- **Screen readers**: every field is linked to its label; toggles, tabs and choices announce whether they are selected; the steps bar says which step you are on; errors are announced straight away; each page has its own window title, and focus moves to the page heading when you switch pages
- **Visible focus ring** on every control, and a *Skip to content* link
- **Phones and narrow windows**: the menu becomes a row of tabs instead of disappearing, the steps bar and status bar fit, and the sheet no longer overlaps the status bar
- **Contrast**: small grey labels (menu headings, row numbers, step numbers) are darker so they meet WCAG AA
- Buttons give a small press response; motion is switched off when your system asks for reduced motion
- Removed an old duplicate Windows build workflow, so each release has one set of downloads
- Checked with the axe accessibility checker on every screen: no issues found

## 0.3.0 — security release

**Upgrade if you use Excel files with pivot tables, charts, images or logos.** Earlier versions masked the cells but left these parts in the twin, and the safety check did not look inside them. Twins made with 0.2.1 or earlier from such files should be re-made and the old ones not shared.

- **Hidden Excel parts are removed**: pivot tables and their caches, charts, images, hyperlinks, drop-down lists, conditional-formatting text, table definitions, external links, defined names, custom properties, custom style names and macros (`.xlsm` twins are saved as `.xlsx`). The safety check lists what was removed.
- **The safety check reads every part of the saved file**, not only cells and properties
- **Row variation** (Consistent mode, ±5% by default): each row gets its own hidden change, so one known real figure no longer reveals a whole column. Totals, formulas, in-row ratios and row trends still hold. `--variation` on the command line.
- **Password protection**: the key file and the library (names, IDs, factors, history) can be encrypted with AES-256-GCM and scrypt. New Security page, unlock screen, `twinwise protect`, `--key-password`.
- With a protected key file, the report no longer lists original file names
- **Large files**: the review table pages through all rows, and *Next to review* finds red cells anywhere in the file (before, cells past row 400 could not be reviewed)
- New risk warnings for One hidden factor mode, row variation off and stable factors
- New [threat model](docs/THREAT_MODEL.md); the docs now say "pseudonymisation"
- New dependency: `cryptography`

## 0.2.1 — stable release of 0.2

- Everything in 0.2.0: AI-ready context (`_CONTEXT.md` data card and `_chunks.jsonl` for RAG), Windows / macOS / Linux apps, safer file names, smarter learning
- Fixed: tests now read files as UTF-8, so the Windows build passes
- Packaging updated to the current licence format (no more build warnings)
- Pre-releases (tags like `v0.3.0-beta.1`) now stay marked as pre-release when the apps are attached

## 0.2.0 — AI context and all platforms

- **AI-ready context**: every twin now comes with `_CONTEXT.md` (a data card: what each column means, formulas in plain words, totals, summary figures) and `_chunks.jsonl` (overview, column, totals and per-row chunks with metadata for RAG / vector databases). Both are built from twin values only and pass the same leak test.
- **Downloads for Windows, macOS (Apple Silicon) and Linux**, built and smoke-tested by GitHub Actions on every version tag
- File and sheet names now also mask lower-case partner words (`harbor_media_statement.csv` → `Company 1 statement`); the leak test checks this
- Choosing "Replace the whole cell" also teaches Twinwise the names inside it
- `--no-context` option on the command line

## 0.1.0 — first open-source release

- Excel (.xlsx/.xlsm), CSV/TSV and ZIP input
- Automatic analysis: header rows (including two-row headers), column roles, key–value blocks, totals rows, calculated columns (×, ÷100, −, +, average, max)
- Three number modes: consistent (default, the twin adds up), scale, random; price points; stable factors across months
- Name, ID, code, email and URL masking with a consistent name library
- Review screen: plan, original and twin views; cell and column decisions; next-to-review
- Templates that recognise next month's file and re-apply your column rules
- Safety check on the saved file (leak test) and basic re-identification warnings
- Key file and "Restore AI answer"
- Local-only server, no telemetry
- Windows app: `Twinwise.exe` built automatically by GitHub Actions on every version tag
- User guide (docs/USER_GUIDE.md) and 98-second video guide
