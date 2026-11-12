## Twinwise 0.3.5 — accessibility and small screens

Make a safe twin of your spreadsheets before you use AI. Same layout, fake names, IDs and numbers, and totals that still add up. Runs entirely on your computer.

This release makes Twinwise usable without a mouse, with a screen reader, and in a narrow window or on a phone. Masking, the safety check and file formats are unchanged from 0.3.0.

### ⬇️ Download

| Your computer | File |
|---|---|
| Windows 10/11 | **Twinwise-Windows.zip**: unzip, double-click `Twinwise.exe` |
| Mac with Apple Silicon (M1–M4) | **Twinwise-macOS-AppleSilicon.zip**: unzip, double-click `Start Twinwise.command` |
| Linux x86-64 | **Twinwise-Linux-x86_64.tar.gz**: extract, run `start-twinwise.sh` |

The apps aren't code-signed yet, so Windows/macOS ask once. See the README inside the download.

📘 **Twinwise_User_Guide.pdf**: quick start · 📕 **Twinwise_User_Manual.pdf**: complete reference · 🛡️ [Threat model](https://github.com/Chalkduggo/Twinwise/blob/main/docs/THREAT_MODEL.md)

### ♿ What's new

- **Full keyboard use.** The menu, both file pickers and the sheet are reachable with Tab. In the sheet, arrow keys move from cell to cell and Enter opens the column's settings.
- **Screen readers.** Fields are linked to their labels, toggles and tabs announce their state, the steps bar says where you are, and errors are read out immediately.
- **Visible focus** on every control, plus a *Skip to content* link.
- **Phones and narrow windows.** The menu turns into a row of tabs instead of disappearing, and the steps bar, status bar and sheet fit the screen.
- **Better contrast** for small grey labels, to meet WCAG AA.
- **Reduced motion** is respected.

Every screen was checked with the axe accessibility checker at phone and laptop widths.

### 🔧 Also

- Removed an old duplicate Windows build, so each release has one clean set of downloads

### ↕️ Upgrading

Nothing to do. Your templates, names, safe words and password protection carry over, and twins match those made with 0.3.0.

### Unchanged promises

- Runs only on your computer. No uploads, no telemetry.
- Export is blocked if the safety check finds a leak.
- Free and open source under Apache 2.0.
