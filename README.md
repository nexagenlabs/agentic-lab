# The Agentic Lab

Companion code for **The Agentic Lab: Build AI Agents for Biotech and Pharma
R&D** by Suryaprakash Tripathy.

Each folder under `builds/` corresponds to one build in the book. Clone once
and you have everything.

```bash
git clone https://github.com/nexagenlabs/agentic-lab.git
cd agentic-lab
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## The builds

| # | Build | Chapter |
|---|---|---|
| 01 | First Agent | 3 |
| 02 | Tool Belt | 3 |
| 03 | Triage Agent | 4 |
| 04 | Dual Screen | 4 |
| 05 | Wrangler | 5 |
| 06 | Plate Mapper | 6 |
| 07 | Protocol Adapter | 6 |
| 08 | Dock Loop | 7 |
| 09 | ELN Bridge | 8 |
| 10 | Run Manifest | 9 |
| 11 | Red Team | 10 |
| 12 | Repurposing Desk | 12 |

Chapters 1 and 2 ship no code. Chapter 11 ships paperwork rather than a build,
and it lives in [templates/](templates/).

Each build folder has its own README saying what it does, which files the
chapter prints, and how to run it.

## What else is here

| | |
|---|---|
| [`templates/`](templates/) | Chapter 11's Context of Use, plus the Chapter 2 and Chapter 4 templates. |
| [`listings/`](listings/) | The code as printed, and the manifest that holds the repository to it. |
| [`tools/`](tools/) | Reference, URL and QR checks. Run by hand, never by the test suite. |
| [`references/`](references/) | Appendix D, with every citation resolved against Crossref. |
| [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) | How the repository is organised and why, including the decisions that are easy to undo by accident. |

[REVIEW.md](REVIEW.md) is an adversarial review of this repository performed
against a fresh clone, [CLAIMS.md](CLAIMS.md) lists the behavioural claims the
book makes that no gate can check, and [PLAN.md](PLAN.md) records what was
fixed in response and what was not.

## Run the tests

```bash
pytest
```

No API key is needed and nothing reaches the network: every model response in
every build comes from a committed fixture replayed by a stub client. To run
one build on its own, `pytest builds/05-wrangler/tests/`.

## Model names

Model names change faster than books do. See [MODELS.md](MODELS.md) for the
current list, with a dated changelog.

## Errata

Found an error in the book or the code? Open an issue, or email
biotech.suryaprakash@gmail.com if you would rather not use GitHub.

## Licence

Code is MIT licensed. Book text is not.
