## Twinwise 0.2.0: AI context and all platforms

Make a safe twin of your spreadsheets before you use AI. Same layout, fake names, IDs and numbers, and totals that still add up. Runs entirely on your computer.

### ⬇️ Download

| Your computer | File |
|---|---|
| Windows 10/11 | **Twinwise-Windows.zip**: unzip, double-click `Twinwise.exe` |
| Mac with Apple Silicon (M1–M4) | **Twinwise-macOS-AppleSilicon.zip**: unzip, double-click `Start Twinwise.command` |
| Linux x86-64 | **Twinwise-Linux-x86_64.tar.gz**: extract, run `start-twinwise.sh` |

The apps aren't code-signed yet, so Windows/macOS ask once. See the README inside the download.

📘 **Twinwise_User_Guide.pdf**: quick start (10 minutes)
📕 **Twinwise_User_Manual.pdf**: complete reference
🎬 98-second video guide in the README

### ✨ What's new

- **AI-ready context with every twin.** `_CONTEXT.md` is a data card that explains the columns, the formulas in plain words, the totals and summary figures. `_chunks.jsonl` holds ready-made chunks for RAG / vector databases. Both are built from the twin only and leak-tested.
- **Windows, macOS and Linux apps**, built and smoke-tested automatically.
- **Safer file names.** Lower-case partner words in file and sheet names are now masked, and the leak test checks them.
- **Smarter learning.** "Replace the whole cell" also teaches Twinwise the names inside it, so next month's file needs no review.
- New `--no-context` command-line option.

### 🔒 Unchanged promises

No uploads, no telemetry, no AI making masking decisions. Export is blocked if any replaced value is found in the twin.

**Full changelog:** see CHANGELOG.md
