# Twinwise user guide

Twinwise makes a **data twin** of a spreadsheet: the same layout, with names, IDs and numbers replaced, so you can share it with an AI tool without exposing real data. Everything runs on your own computer.

🎬 Prefer video? Watch the [98-second user guide](Twinwise_User_Guide.mp4).

---

## 1. Start Twinwise

| You have | Do this |
|---|---|
| **Windows** | Download `Twinwise-Windows.zip` from the [Releases page](https://github.com/Chalkduggo/Twinwise/releases/latest), unzip it and double-click `Twinwise.exe`. If Windows shows *"Windows protected your PC"*, click **More info → Run anyway** (the app isn't code-signed yet). |
| **Mac (M1/M2/M3/M4)** | Download `Twinwise-macOS-AppleSilicon.zip`, unzip it and double-click `Start Twinwise.command`. If macOS blocks it: **System Settings → Privacy & Security → Open Anyway**. |
| **Linux** | Download `Twinwise-Linux-x86_64.tar.gz`, extract it, run `./start-twinwise.sh`. |
| **With Python 3.10+** | Download the code, double-click `Start-Twinwise.bat` (Windows) or run `./start-twinwise.sh` (Mac/Linux). |
| **Mac / Linux / developers** | `pip install -e .` then `twinwise ui` |

Your browser opens at `http://127.0.0.1:8765`. This address only works on your own computer. Keep the black window open while you work, and close it to stop Twinwise.

## 2. Drop in your files

![Upload](screenshots/01-upload.png)

Drag in Excel (`.xlsx`), CSV, or a ZIP of them. Several files at once is fine, and names stay consistent across all of them.

## 3. Read the plan

![Review](screenshots/02-review.png)

| Colour | Meaning |
|---|---|
| 🔵 Blue | Number, will be changed |
| 🟠 Amber | Name or ID, will be replaced |
| ⚪ Grey | Date, kept |
| White | Ordinary text, kept |
| 🔴 Red | New text Twinwise hasn't seen before. It's masked until you decide |

The row under the column letters shows what each column was recognised as (*Region · replace*, *Count · scale*, *Formula · recalc*…).

![Columns](screenshots/03-columns.png)

## 4. Decide on anything new

Click **Next to review** (or any cell). The **Cell** panel shows the original value, the twin value and three choices:

![Cell decision](screenshots/04-cell.png)

- **Automatic**: replace the names and codes Twinwise found
- **Keep as is**: the words are added to your safe-word list
- **Replace the whole cell**: one label for the entire text

Your decision is remembered for next time.

![Decided](screenshots/05-decided.png)

## 5. Change a whole column (optional)

Click a column letter. You can say what the column holds, keep public data unchanged, or turn price rounding on or off.

![Column](screenshots/06-column.png)

## 6. Choose how numbers change

In **Summary**:

![Modes](screenshots/07-summary.png)

- **Consistent** (recommended): each column gets its own hidden factor, and totals and formulas are recalculated, so the twin adds up.
- **One hidden factor**: every amount is multiplied by the same factor.
- **Random**: independent noise. Most private, but totals won't add up.

In Consistent mode you can also set **Row variation** (Off, ±5%, ±10%, ±20%). Each row gets a small hidden extra change, so someone who knows one real figure cannot work out the rest of the column exactly. ±5% is the default and suits most uses.

## 7. Compare original and twin

Use **Plan / Original / Twin** at the top right.

![Twin view](screenshots/08-twin.png)

## 8. Safety check

Click **Continue**. Twinwise saves the twin and searches it for every value it replaced: cells, sheet names, the file name and every hidden part inside the file. If anything is found, export is blocked.

Pivot tables, charts, images, hyperlinks and comments are **removed from the twin**, because Excel keeps copies of real values in them. The check lists what was removed.

On this page you can also type a **password for the key file**. Do this whenever the twin is going outside your team.

![Safety check](screenshots/09-verify.png)

Warnings such as *small counts* or *kept text you may want to glance at* are there to help you decide. They don't block export.

## 9. Export

![Export](screenshots/10-export.png)

You get:

- **The twin** (`…_TWIN.xlsx` / `.csv`). Upload this to ChatGPT, Claude, Copilot or any other AI tool.
<<<<<<< Updated upstream
- **The key file** (`twin-key_….json`). **Private.** Never upload or share it. With a password it is stored encrypted.
=======
- **The key file** (`twin-key_….json`). **Private.** Never upload or share it.
>>>>>>> Stashed changes
- **AI context** (`…_CONTEXT.md`): a data card that explains the twin to an AI. It covers column meanings, formulas, totals and summary figures. Upload it together with the twin for better answers.
- **RAG chunks** (`…_chunks.jsonl`): ready-made pieces for a RAG / vector-database pipeline, one JSON object per line with `id`, `type`, `text` and `metadata`.
- A report of the checks (`twin-report_….json`)

The context files are built only from the twin and are leak-tested like the twin itself.

Files are saved in `Documents\..\Twinwise\exports` (your home folder → `Twinwise\exports`).

## 10. Bring the AI's answer back

Open **Restore AI answer**, choose the key file and paste the AI's answer. Fake names become real again.

![Restore](screenshots/11-restore.png)

Numbers that appear in the twin are mapped back exactly. Numbers the AI calculated itself (sums, averages, growth) can't be mapped back exactly. Percent changes and rankings stay valid in Consistent mode.

## 11. Next month

Drop in next month's file from the same partner. Twinwise recognises the layout, applies your rules and reuses the same fake names. Usually there's nothing to review.

![Next month](screenshots/12-next-month.png)

## 12. Your library

Everything Twinwise learns is stored on your computer in `.twinwise` in your home folder:

- **Templates**: one per report layout, with your column rules
- **Name library**: real name → fake label (add, edit or mark safe)
- **Safe words**: text that's never masked
- **History**: a local record of every export

The name library holds your real names. Open **Security** and turn on **Library protection** to store it encrypted. Twinwise then asks for the password when it starts, and new key files use the same password by default. There is no password recovery, so keep it somewhere safe.

![Security](screenshots/15-security.png)

![Templates](screenshots/13-templates.png)
![Names](screenshots/14-names.png)

---

## Tips

- Review red cells the first time you use a new layout. It takes a minute and makes every later month automatic.
- Keep the key file next to the twin, but never upload it. Give it a password.
- In large files, **Next to review** jumps to the next red cell wherever it is, and the arrows above the table move through the rows 400 at a time.
- A twin hides names and values from a reader. It doesn't make the data public-safe; see the [threat model](THREAT_MODEL.md).
- Small counts (1–4) can still point to a real customer. Group or remove those rows if that matters.
- To start fresh, delete the `.twinwise` folder in your home directory.

## Command line (optional)

```bash
twinwise twin "Partner report.xlsx" -o out/
twinwise restore --key out/twin-key_2026-11-09.json answer.txt
twinwise protect            # password-protect your library
twinwise demo
```
