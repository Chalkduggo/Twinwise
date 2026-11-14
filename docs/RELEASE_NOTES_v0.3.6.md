## Twinwise 0.3.6 — install with pip, and security basics

Make a safe twin of your spreadsheets before you use AI. Same layout, fake names, IDs and numbers, and totals that still add up. Runs entirely on your computer.

This release changes how Twinwise is delivered and looked after. The app, the masking and the safety check are the same as 0.3.5.

### ⬇️ Download

| Your computer | File |
|---|---|
| Windows 10/11 | **Twinwise-Windows.zip**: unzip, double-click `Twinwise.exe` |
| Mac with Apple Silicon (M1–M4) | **Twinwise-macOS-AppleSilicon.zip**: unzip, double-click `Start Twinwise.command` |
| Linux x86-64 | **Twinwise-Linux-x86_64.tar.gz**: extract, run `start-twinwise.sh` |
| Any computer with Python 3.10+ | `pip install twinwise`, then `twinwise ui` |

**New: check your download.** Compare your file with `SHA256SUMS.txt` below. Windows: `certutil -hashfile Twinwise-Windows.zip SHA256` · macOS/Linux: `shasum -a 256 <file>`.

📘 **Twinwise_User_Guide.pdf** · 📕 **Twinwise_User_Manual.pdf** · 🛡️ [Threat model](https://github.com/Chalkduggo/Twinwise/blob/main/docs/THREAT_MODEL.md) · 🔒 [Security policy](https://github.com/Chalkduggo/Twinwise/blob/main/SECURITY.md)

### What's new

- **On PyPI**: `pip install twinwise`. Each GitHub release is published to PyPI automatically through trusted publishing, so no password or token is stored anywhere.
- **Security policy** with private reporting: found a problem? Report it [privately](https://github.com/Chalkduggo/Twinwise/security/advisories/new), not in a public issue.
- **Checksums** for every download.
- **Automatic checks**: Dependabot watches the libraries Twinwise uses, and OpenSSF Scorecard rates how safely the project is run.
- **Issue forms** that remind you never to attach real data.

### Upgrading

Nothing to do. Everything carries over, and twins match those made with 0.3.5.
