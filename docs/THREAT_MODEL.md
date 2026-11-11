# Twinwise threat model

This page says plainly what a twin protects, what it does not, and why. Read it before you decide what a twin may be used for.

## The short version

Twinwise does **pseudonymisation**, not anonymisation. It replaces names, IDs and numbers so that a person or an AI tool reading the twin does not see your real values. Someone who already knows part of your real data can still learn more from a twin. Treat a twin as "much safer to share than the original", not as "public".

If your data is covered by GDPR, HIPAA, a contract or an NDA, a twin is normally still covered by it. Ask your legal or security team before you share one outside the company.

## What Twinwise protects against

| Situation | Protected? |
|---|---|
| An AI provider, or anyone reading the uploaded file, sees real partner names, customer names, IDs, emails, URLs | Yes. They are replaced, and the saved file is searched to prove it. |
| Real figures (revenue, subscriber counts, rates) are read straight from the file | Yes. No masked number keeps its real value. |
| Real values hide in parts of an Excel file you don't see: pivot-table caches, chart data, images and logos, hyperlinks, comments, drop-down lists, external links, defined names, author properties, custom style names | Yes. These parts are removed from the twin, and every part of the saved file is searched. |
| Someone opens your Twinwise folder or finds a key file | Only if you turned on password protection (Security page, or a key password at export). |

## What it does not protect against

**1. Someone who knows one real figure (known-plaintext).**
In Consistent mode each column has a hidden factor. Since 0.3.0 every row also gets its own small hidden variation (±5% by default), so knowing one real number no longer reveals the rest of the column exactly. It does still give an estimate: with ±5% variation, the other values in that column can be estimated to within roughly ±10%. Higher variation (±10%, ±20%) widens this at the cost of accuracy. With variation off, or in One hidden factor mode, one known figure reveals its column (or the whole file) exactly.

**2. Someone who knows your business.**
Labels hide names, not shapes. If one partner is five times larger than all others, an insider will guess who "Partner 1" is. Rankings, market shares and seasonal patterns survive on purpose, because that is what makes the twin useful.

**3. Prices and percentages.**
Equal prices stay equal, and price points come from a small set (3.99, 4.99…). Someone who knows your price list can often map twin prices back. Percentages change only gently. If a rate or revenue split is itself confidential, mask that column with Random or remove it.

**4. Month-to-month linking.**
With "same hidden factors every month" on, the same column and the same row get the same factor in every twin. That keeps trends true, and it also means a figure learned from one month helps estimate the others. Turn it off for one-off sharing.

**5. Small counts.**
A count of 1 in a small town can point to a real customer even after masking. Twinwise warns about small counts; it does not remove them.

**6. Text Twinwise judged ordinary.**
The leak test proves that everything Twinwise replaced is gone. It cannot know that a word it kept is sensitive to you. That is what the red review cells and the *Kept text* list are for.

**7. Dates.**
Dates are kept as they are.

**8. Your own computer.**
Twinwise does not protect against malware, a shared login, or someone with access to your unlocked computer while Twinwise is open. Original files you upload are copied to a temporary folder for the session.

## Password protection

- The key file and the library (names, IDs, hidden factors, history) can be encrypted with AES-256-GCM. The key is derived from your password with scrypt. Both come from the widely used `cryptography` package; there is no home-made cryptography.
- The password is never written to disk. It is held in memory while Twinwise runs.
- There is no recovery. A lost password means the library or key file cannot be opened.
- Protection is only as strong as the password. Use a long passphrase.
- Templates and safe words are not encrypted. They hold column headings and your rules, not data values. When the key file is password-protected, the report file no longer lists the original file names.

## What is removed from Excel twins

Pivot tables and their caches, charts, images and drawings, hyperlinks, comments, data-validation lists, conditional-formatting rules that contain text, table definitions, external links, defined names, headers and footers, document and custom properties, custom cell-style names, and macros (`.xlsm` twins are saved as `.xlsx`).

Cell values, formulas, number formats, column widths, fonts and fills are kept.

## Not independently audited

Twinwise has automated tests and a leak test on every export, but it has had no external security review. Please report problems through the GitHub issue tracker; do not include real data in a report.
