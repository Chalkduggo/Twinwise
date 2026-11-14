# Security policy

Twinwise exists to keep confidential data private, so security reports are taken seriously.

## Supported versions

Only the latest release gets security fixes. Please upgrade before reporting.

| Version | Supported |
|---|---|
| Latest 0.3.x | ✅ |
| 0.2.x and older | ❌ (0.2.1 and older can leak data through pivot tables, charts and images; see the 0.3.0 release notes) |

## How to report a problem

**Please don't open a public issue for a security problem.**

Report it privately through GitHub: [**Report a vulnerability**](https://github.com/Chalkduggo/Twinwise/security/advisories/new).

Please include:

- the Twinwise version (`twinwise --version`, or the version on the About screen) and your operating system
- what you did, what you expected, and what happened
- a small **made-up** file that shows the problem

**Never send real or confidential data**, not even a "masked" twin of it. If a problem only shows with a real file, describe its layout instead (column headings, kinds of values).

## What counts as a security problem

- Real values (names, IDs, numbers) that remain anywhere in a saved twin, its AI context files or its file name
- The safety check reporting 0 leaks when a real value is present
- Weaknesses in how key files or the library are encrypted
- The local server being reachable from other computers, or accepting requests from other websites
- Anything that sends data off your computer

Masking that is weaker than you'd like, as described in the [threat model](docs/THREAT_MODEL.md), is a known limit rather than a vulnerability, but suggestions are welcome as normal issues.

## What happens next

Twinwise is maintained by one person in their own time. I aim to reply within 7 days, agree a fix and a disclosure date with you, and credit you in the release notes unless you'd rather stay anonymous.
