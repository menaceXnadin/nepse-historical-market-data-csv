# Pipeline Audit

Verified audit of the data ingestion pipeline. Every claim below was checked
against the code, the committed data, the live source APIs, and the git/LFS
history — not inferred from intent.

**Scope:** `asyncmain.py`, `asyncmain_incremental.py`, `main.py`,
`quarterly_reports.py`, `sectors.py`, `fix_csv_types.py`, `.github/workflows/`,
`data/`, LFS store.

**Not covered:** `ml/` (LSTM/XGBoost training) was not audited. Treat it as
unreviewed.

## Sources of truth

| Source | URL | Used for |
|---|---|---|
| ShareHub Nepal candles | `sharehubnepal.com/data/api/v1/candle-chart/history?symbol={sym}&resolution=1D&countback=0&isAdjust={bool}` | all price data |
| Chukul sectors | `chukul.com/api/sector/` | symbol universe, `can_trade`, sectors |
| Chukul stocks | `chukul.com/api/stock/` | 691 stocks, `is_delisted` |
| Chukul reports | `chukul.com/api/stock/{stock_id}/report/` | quarterly fundamentals |

Three *different* stock universes are used inconsistently: `sector.json` (cached,
price path), `/api/stock/` (reports path), and `sectormapping.csv` (dead
artifact from `sectors.py`).

---

## Priority summary

| # | Severity | Issue |
|---|---|---|
| 1 | 🔴 | **Workflows cannot run** — required files are gitignored and absent from HEAD |
| 2 | 🔴 | **7.1 GB LFS / 93k blobs** for a 60 MB dataset; GitHub quota will break |
| 3 | 🔴 | **`from=` is ignored by the API** — "incremental" refetches full history |
| 4 | 🔴 | **`quarterly_reports.csv` silently truncated** on partial failure |
| 5 | 🔴 | **`asyncio.gather` without `return_exceptions=True`** — one error kills the run |
| 6 | 🔴 | **Non-atomic writes**; `asyncmain.py` deletes before writing |
| 7 | 🟠 | **`actions/checkout` skips LFS** → pointer stubs force full refetch |
| 8 | 🟠 | **Two workflows write conflicting filenames**, ~1,073 renames/day |
| 9 | 🟠 | **Naive-local `fromtimestamp`** → wrong dates on negative-offset TZs |
| 10 | 🟠 | **4.8% of rows are flat/zero-volume placeholders** (64% of NEPSE index) |
| 11 | 🟡 | 126 symbols silently missing; ~216 files are byte-identical duplicates |
| 12 | 🟡 | No retries, no `User-Agent`, new `AsyncClient` per request |
| 13 | 🟡 | Sector 16 unmapped → `UNKNOWN_16`; no dedupe key on quarterly reports |

---

## 🔴 1. The GitHub Actions workflows cannot run

`HEAD` contains **only** `.gitignore`, `README.md`, and 1,073 CSVs. `.gitignore`
is `*` with a `.github/` exclusion, so the scripts themselves are untracked:

```
$ git check-ignore -v requirements.txt
.gitignore:2:* requirements.txt
$ git check-ignore -v .github/workflows/auto-update.yml
.gitignore:15:.github/    .github/workflows/auto-update.yml
```

Both workflows start with `pip install -r requirements.txt`, and that file is
**not in the repository**. A fresh clone fails at the install step before
reaching the fetch script. `QUICK_START.md:30` tells users to
`git add .github/workflows/auto-update.yml`, which git refuses without `-f`.

The daily commits in history (`Data update: October 02, 2026`, …) come from the
local `run_and_push.ps1` — **not** from CI. The automation is not actually
automated.

**Fix:** commit the scripts, `requirements.txt`, and workflows (add `!` exceptions
to `.gitignore`).

## 🔴 2. Git LFS churn will exhaust the GitHub quota

`.gitattributes` is a single blanket line: `*.csv filter=lfs diff=lfs merge=lfs -text`

| Metric | Value |
|---|---|
| Working tree `data/` | 59.9 MB |
| `.git/lfs/objects` | **7,121 MB (7.1 GB)** |
| Distinct LFS blobs | **93,104** |
| Files tracked | 1,073 |
| Commits since 2023-09-04 | 226 |

93,104 blobs for 1,073 files ≈ **87 full re-versions per file**. The cause is
`asyncmain_incremental.py:193`:

```python
combined_df.to_csv(file_path, index=False)   # full rewrite to append one row
```

LFS is content-addressed, so appending a single row makes the entire file a new
blob. One new row/day/symbol × 1,073 files ≈ **60 MB uploaded per run**; two
workflows run daily. GitHub's free tier allows 1 GB/month bandwidth and 10 GB
storage — **7.1 GB of the storage budget is already gone.**

**Fix options, best first.** Note that *appending* instead of rewriting does **not**
help: LFS hashes the whole file, so any byte change — appended or rewritten —
produces a new full-size object. Only changing what goes into a single object helps.

1. **Drop LFS for `data/`** and let plain git store it. These are text CSVs; git
   compresses them well. `.git/objects` is only 24.5 MB today for all history and
   metadata, and 60 MB of CSV is unremarkable for a plain repo. Verify with
   `git gc --aggressive` after removing the `filter=lfs` attribute.
2. **Partition by year**: `data/stock/adjusted/NABIL/2026.csv`. A daily append then
   creates a new ~50 KB year-file rather than a new 192 KB whole-history blob, and
   each year starts fresh instead of growing forever.
3. **Publish out of band** — keep `data/` untracked and ship it as a release asset
   or object store, committing only the code. Best if consumers can fetch it.
4. Then reclaim the space: `git lfs prune` removes local blobs, but the *remote*
   history keeps them, so a squash-and-rebase into a fresh single-commit history is
   the only thing that actually reclaims the GitHub quota.

## 🔴 3. "Incremental" is not incremental

Verified against the live API:

```
from=2026-10-03  n=6603  first=1997-07-20
from=2026-09-30  n=6603  first=1997-07-20
countback=5      n=5
countback=30     n=30
```

The `from` parameter is **completely ignored**. `asyncmain_incremental.py:129`
buys nothing; every one of the ~1,312 tasks downloads the full ~6,600-row history
on every run. The "incremental" part is purely client-side — read CSV, concat,
dedupe, rewrite.

That is what accidentally makes the missing retry logic survivable: a transient
per-symbol failure self-heals next run because "new" rows re-include the missed
dates. **If anyone adds a real `from` filter on the assumption the API honours
it, data will silently develop holes.**

## 🔴 4. `quarterly_reports.csv` is silently truncated

```python
# :239-240
except Exception:
    pass  # Silently skip errors
```
```python
# :322-326
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(all_reports)
```

`stocks_with_data` is computed and printed at `:297` but **never asserted**. If
Chukul returns HTTP 200 with an empty body for most stocks — a soft block, an API
change, a regional outage — the file is overwritten wholesale with the remnant
and the workflow commits it. Combined with `except: pass`, this is undetectable.

This is the **highest-severity data-loss path**: a single 1.2 MB file, 6,618
rows, no per-record redundancy.

**Fix:** require a minimum coverage ratio (e.g. >80% of prior row count) before
overwriting; log exceptions instead of `pass`.

## 🔴 5. `asyncio.gather` without `return_exceptions=True`

```python
# :419
await asyncio.gather(*tasks)
```

The `try/except` inside `fetch_and_save_incremental` starts at `:135`. Before it:
`get_existing_file_path` (`:114`) calls **`os.rename` at `:96`, unguarded** — on
Windows a locked file raises `PermissionError`. And `symbol_name.replace('/', '_')`
(`:110`) raises `AttributeError` on a non-string symbol.

One unhandled exception propagates out of `gather` and **abandons every other
in-flight task**, cancelling coroutines mid-`to_csv` and leaving **truncated CSVs
on disk**. `run_and_push.ps1:19-21` then throws and skips the commit, so the local
path survives by accident — CI has no such guard.

## 🔴 6. Non-atomic writes

`asyncmain_incremental.py:193` and `:322` both truncate-then-write in place. An
OOM-kill or Ctrl-C mid-write leaves a half-written CSV. Recovery is silent:
`get_last_fetched_date`'s `except` at `:72-74` prints a warning and triggers a
full refetch.

`asyncmain.py:38-52` is strictly worse — it **deletes the old file first**:

```python
old_files = glob.glob(f"data/{folder_type}/{folder}/{safe_symbol_name}_*.csv")
for old_file in old_files:
    os.remove(old_file)
```

Any failure between the delete and the successful write is total, unrecoverable
loss for that symbol.

**Fix:** write to `path.tmp` then `os.replace()` — atomic on both POSIX and
Windows.

## 🟠 7. `actions/checkout` does not fetch LFS

Both workflows use `actions/checkout@v4` **without `lfs: true`** (default is
`false`). On a fresh runner all 1,073 CSVs check out as 3-line pointer stubs.
Then `get_last_fetched_date` → `pd.read_csv(pointer)` → no `time` column →
`None` → the code takes the **full-refetch branch** and overwrites every pointer.

## 🟠 8. The two workflows fight over filenames

`update-data.yml` runs `asyncmain.py` (dated filenames, deletes old). Fifteen
minutes later `auto-update.yml` runs `asyncmain_incremental.py`, whose
`get_existing_file_path` (`:88-97`) finds the dated file and **renames it back**.
~1,073 renames per cycle — maximum LFS churn, and the documented naming convention
(`README.md:22`) is violated half the time.

Neither workflow has a `concurrency:` group, so a `workflow_dispatch` overlapping a
scheduled run produces a non-fast-forward push failure. Both also run on Saturdays
and Nepali market holidays — no weekday guard.

`update-data.yml` is additionally **missing `permissions: contents: write`**
(`auto-update.yml:15-16` has it). On a repo with read-only default workflow
permissions its `git push` fails.

## 🟠 9. Timezone-dependent dates

```python
# :169, :204
datetime.fromtimestamp(row_copy["time"]/1000).strftime("%Y-%m-%d")
```

`fromtimestamp` with no `tz` uses machine-local time. API epochs are **exactly
midnight UTC**, so on any negative-offset machine (America/*) every row lands on
the previous calendar day.

The same flaw poisons the resume arithmetic at `:118-119`:

```python
from_date = last_fetched_date + timedelta(days=1)
from_timestamp = int(from_date.timestamp() * 1000)
```

On a negative-offset runner this **skips one trading day permanently**. Latent
today (dev machine and runners are ≥UTC) but it makes dataset correctness depend
on an undeclared environment variable.

**Fix:** `datetime.fromtimestamp(ms/1000, tz=timezone.utc)`.

## 🟠 10. Unvalidated placeholder rows

53,974 of 1,124,057 rows (4.8%) are flat with zero volume. For `NEPSE` it is
**64%**; some files are ~100% synthetic (`NMBEB92_93`, `ADBLB86` at 99%). No
filtering or quality flag exists. This is committed to LFS and will poison any
model trained on it.

## 🟡 11-13. Smaller items

- **126 of 639 symbols** produce no CSV (`10NICD208586`, `ALDBLP`, `GASY`,
  `MNMF2`, `SFF`…) — mostly promoter shares, debentures, bonds. Requested every
  run for nothing; ~20% wasted budget.
- **~216 files are byte-identical pairs** (182 stock + 34 index/subindex) — the
  indices are *always* identical because indices have no corporate actions.
- No retries or backoff anywhere; no `User-Agent`; a **new `AsyncClient` per
  task** (`:136`, `:256`) meaning a fresh TLS handshake for all ~1,312 requests.
  Concurrency semaphores are 15/15/10.
- `asyncio.sleep(0.1)` at `:218` sits **inside** the `async with semaphore` block,
  so it occupies a slot while idle; and the early `return`s at `:125` and `:145`
  bypass it entirely, so already-current symbols hammer the API at full
  concurrency with zero delay.
- **Sector 16** is unmapped in both `quarterly_reports.py:18-31` and
  `asyncmain_incremental.py:24-37` (which handle 1-12), and `EXCLUDED_SECTORS` is
  `{13,14,15}`. Those rows land as `UNKNOWN_16`.
- **`quarterly_reports.csv` has no dedupe key.** Natural key is
  `(stock_id, fiscal_year, quarter)`.
- **`main.py` is broken and dead** — direct subscripts at `:19` and `:23` raise
  `KeyError` on any API hiccup, killing the sweep. A 4th filename convention, no
  `category` column, no numeric casting, no index coverage.
- **`sectors.py` executes at import time** — no `__main__` guard, so importing it
  fires two HTTP GETs and overwrites `sectormapping.csv`.
- **`fix_csv_types.py` is dead and unsafe** — in-place full rewrites, and
  `.astype('int64')` raises on float columns with NaN. The writers already cast.
- `run_and_push.ps1:36` uses `git status --porcelain`, but `sector.json` is
  ignored — a run where only the sector list changed reports "No changes
  detected". No row-count or freshness assertion anywhere.

## What is genuinely fine

Worth preserving during any refactor:

- **Dedupe on the append path (`:185`) works** — verified **0 duplicate `time`
  values and 0 unsorted files** across all 1,072 CSVs. `keep='last'` correctly
  lets fresh data overwrite corrected history.
- **Symbol normalisation is collision-free** — verified no two distinct symbols
  collide after `/` → `_`.
- **0 negative-volume rows.**
- Working tree and LFS index are internally consistent — no orphaned files.
- `k.get("can_trade") == True` in the async fetchers is the correct defensive
  form (unlike `main.py:19`); all 685 `sector.json` entries do have the key.

## Suggested order of work

1. Commit the scripts + workflows (issue 1) — everything else is unverifiable in CI until then.
2. Make writes atomic (issue 6) — cheap, removes the worst data-loss path.
3. Add the coverage assertion to reports (issue 4) and `return_exceptions=True` (issue 5).
4. Fix the timezone handling (issue 9) and set `lfs: true` (issue 7).
5. Decide the LFS strategy (issue 2) before quota exhaustion forces it.
6. Collapse to one workflow (issue 8) and delete `main.py` / `sectors.py` / `fix_csv_types.py`.
7. Add a flat/zero-volume quality filter (issue 10).
8. Accept that `from=` is ignored (issue 3) — document it, don't build on it.