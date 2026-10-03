# AGENTS.md

Guidance for AI agents working in this repository.

## What this repo is

A **data publisher**, not an application. It scrapes daily NEPSE (Nepal Stock
Exchange) price history and company quarterly reports, writes them as CSV, and
commits them to Git. Consumers read the CSVs; there is no server, no API, and
no web UI here.

- `data/` — the product. ~1,072 price CSVs + `quarterly_reports.csv`. Tracked in Git LFS.
- `ml/` — LSTM/XGBoost training. **Gitignored, still in progress, not production.**

## Read this before changing anything

**[`docs/pipeline-audit.md`](docs/pipeline-audit.md)** — a verified audit of the
ingestion pipeline with prioritised defects. Read it before touching
`asyncmain*.py`, the workflows, or `data/`.

**[`docs/ml-audit.md`](docs/ml-audit.md)** — a verified audit of `ml/`. **There is
an off-by-one in `lstm_model.py:119` that makes `ml/results/model_comparison.csv`
invalid**, plus test-set threshold tuning and an alpha figure that is really just
cash exposure. Do not quote those metrics.

**[`docs/data-schema.md`](docs/data-schema.md)** — column definitions, filename
conventions, adjusted vs unadjusted, and known data-quality traps.

## Hard rules

1. **Never hand-edit anything under `data/`.** It is generated and overwritten on
   every run. Fix the generator, then re-run.
2. **Data loss is the default failure mode here.** Writes are non-atomic and
   `asyncmain.py` deletes the old file before writing the new one. If you touch
   write paths, make them atomic (write temp, then `os.replace`).
3. **`.gitignore` is `*` with narrow exceptions** (`data/`, `.github/`). Any new
   top-level file you create is untracked and invisible to git. Add an explicit
   `!` exception if it should be committed.
4. **Do not add retries-free network calls, and do not remove the client-side
   dedupe.** The dedupe at `asyncmain_incremental.py:185` is what keeps the
   append path correct; the missing retry logic is a known gap, not a style choice.
5. **Mind the timezone.** Timestamps are derived with naive-local
   `datetime.fromtimestamp`, which silently shifts dates on negative-offset
   machines. See audit BUG 8.

## Commands

```powershell
# Full incremental update (what the daily automation runs)
.\run_and_push.ps1

# Fetch only, no commit
python asyncmain_incremental.py

# Update quarterly reports only
python quarterly_reports.py
```

Neither fetcher has retry/backoff and neither sets a `User-Agent`. They lean on
the fact that a transient per-symbol failure self-heals on the next run — do not
remove that property when refactoring.

## Conventions

- Python, 4-space indent, `snake_case` functions, `PascalCase` classes.
- Progress is `print`-only. There is no structured logging; keep it that way
  unless you are deliberately adding logging.
- Prices are written as `float`, volume as `int`. Note that **index volume is
  actually rupee turnover** and is truncated by the `int()` cast.

## Git

Data commits look like `Data update: October 02, 2026`. Do not amend or squash
them. Be aware that LFS churn on this repo is severe (see audit, issue 2) — a
full-file rewrite of `data/` uploads ~60 MB per run.