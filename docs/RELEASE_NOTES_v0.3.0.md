## Twinwise 0.3.0 — security release

Make a safe twin of your spreadsheets before you use AI. Same layout, fake names, IDs and numbers, and totals that still add up. Runs entirely on your computer.

### ⚠️ Please upgrade

Versions up to 0.2.1 masked the cells of an Excel file but left **pivot tables, charts and images** in the twin. Excel stores a copy of the source data inside pivot tables and charts, and images are often logos, so real names and values could remain in the file even though the safety check reported 0 leaks.

If you made twins with 0.2.1 or earlier from workbooks that contain a pivot table, a chart or an image, make them again with 0.3.0 and stop sharing the old ones. CSV twins and plain worksheets are not affected.

### ⬇️ Download

| Your computer | File |
|---|---|
| Windows 10/11 | **Twinwise-Windows.zip**: unzip, double-click `Twinwise.exe` |
| Mac with Apple Silicon (M1–M4) | **Twinwise-macOS-AppleSilicon.zip**: unzip, double-click `Start Twinwise.command` |
| Linux x86-64 | **Twinwise-Linux-x86_64.tar.gz**: extract, run `start-twinwise.sh` |

The apps aren't code-signed yet, so Windows/macOS ask once. See the README inside the download.

📘 **Twinwise_User_Guide.pdf**: quick start · 📕 **Twinwise_User_Manual.pdf**: complete reference · 🛡️ [Threat model](https://github.com/Chalkduggo/Twinwise/blob/main/docs/THREAT_MODEL.md)

### 🔒 What's new

- **Hidden Excel parts are removed.** Pivot tables and their caches, charts, images, hyperlinks, drop-down lists, external links, defined names, custom properties and macros are taken out of the twin. The safety check lists what was removed.
- **The safety check now reads every part of the saved file**, not only the cells.
- **Row variation.** In Consistent mode each row gets its own small hidden change (±5% by default; Off, ±10% and ±20% are available). One known real figure no longer reveals a whole column. Totals, formulas, ratios inside a row and row trends still hold.
- **Password protection.** The key file and the library (names, IDs, hidden factors, history) can be encrypted with AES-256-GCM and scrypt. There is a new Security page, an unlock screen, and `twinwise protect` / `--key-password` on the command line. There is no password recovery.
- **Large files.** The review table pages through all rows, and *Next to review* finds red cells anywhere in the file. Before, cells past row 400 could not be reviewed.
- **Threat model.** A plain account of what a twin protects and what it does not. Twinwise does pseudonymisation, not anonymisation.

### 🔧 Also

- New risk warnings for One hidden factor mode, row variation off, and same factors every month
- With a password-protected key file, the report no longer lists original file names
- Demo files, screenshots and the video guide use fully invented place names
- New dependency for source installs: `cryptography`

### ↕️ Upgrading

Your templates, names and safe words carry over. Because of row variation, numbers in new twins differ slightly from twins of the same file made with 0.2.x. Set Row variation to Off if you need the old behaviour.

### Unchanged promises

- Runs only on your computer. No uploads, no telemetry.
- Export is blocked if the safety check finds a leak.
- Free and open source under Apache 2.0.
