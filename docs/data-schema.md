# Data Schema Reference

Companion to [`pipeline-audit.md`](pipeline-audit.md). Describes what the CSVs in
`data/` contain and which parts of them to distrust.

## Layout

```
data/
├── quarterly_reports.csv        1.2 MB, 6,618 rows, 27 columns
├── stock/
│   ├── adjusted/                519 CSVs
│   └── unadjusted/              519 CSVs
├── index/
│   ├── adjusted/                FLOAT, NEPSE, SENFLOAT, SENSITIVE
│   └── unadjusted/              byte-identical duplicates
└── subindices/
    ├── adjusted/                13 sector indices
    └── unadjusted/              byte-identical duplicates
```

Total ~1,072 price CSVs, ~59.9 MB in the working tree.

## Price CSV schema (8 columns)

```csv
time,symbol,open,close,high,low,volume,category
2026-10-02,NEPSE,2592.26,2587.25,2600.47,2582.36,4293774181,index
2026-10-02,NABIL,529.0,528.7,533.0,525.0,60404,stock
```

| Column | Type | Notes |
|---|---|---|
| `time` | `YYYY-MM-DD` string | Derived from epoch-ms via **naive-local** `fromtimestamp` |
| `symbol` | string | `/` replaced with `_` (`GBD80/81` → `GBD80_81`) |
| `open` `close` `high` `low` | `float` | |
| `volume` | `int` | **For indices this is rupee turnover, not share count** |
| `category` | literal | `stock` / `index` / `subindex` |

Column *order* is taken from whatever the API returns that day
(`asyncmain_incremental.py:199`), so do not rely on positional indexing — always
read by name.

### Raw API response

```
['time','symbol','open','close','high','low','volume']
{'time': 1790899200000, 'symbol':'NEPSE', 'open':2592.26, 'volume': 4293774181.11}
```

Epoch-ms values sit at **exactly midnight UTC**.

## Filename conventions — three incompatible schemes

| Producer | Pattern |
|---|---|
| `asyncmain_incremental.py:148` | `{SYMBOL}_{adjusted\|unadjusted}.csv` ← what README documents |
| `asyncmain.py:52` | `{SYMBOL}_{YYYY_MM_DD}_{adjusted\|unadjusted}.csv` |
| `main.py:27` | `{SYMBOL}_{folder}_upto_{YYYY_MM_DD}.csv` (dead code) |

`asyncmain.py:38-40` globs `{SYMBOL}_*.csv` and deletes matches — which includes
the static-name files. The two scheduled workflows therefore rename 1,073 files
back and forth daily. See audit BUG 1.

## Adjusted vs unadjusted

Entirely server-side, driven by ShareHub's `isAdjust` flag. **No adjustment logic
exists in this repo.** Example on NABIL's first bar (2012-01-02):

| | open | close |
|---|---|---|
| `isAdjust=true` | 79.31 | 79.85 |
| `isAdjust=false` | 873 | 879 |

Three consequences:

1. **Adjustment factors change retroactively.** A split or bonus announced today
   rewrites every historical bar in `adjusted/`. Nothing here pins factors, so
   the adjusted series is not reproducible across time.
2. **Indices are unaffected.** Every `*_adjusted.csv` index and sub-index file is
   **byte-identical** to its unadjusted twin — 34 files, ~7 MB of pure duplication.
3. **182 of 519 stock pairs are also byte-identical** (no corporate action ever).
   Together that is ~216 files of wasted LFS storage.

Do not use adjusted and unadjusted series in the same model without accounting
for the ~11x scale difference.

## `quarterly_reports.csv`

27 columns, written by `asyncmain_incremental.py:305-312`. Supersedes
`quarterly_reports.py`, which declares 51 columns — **24 fields are dropped**,
including `eps_a`, `peg_value`, `gram_value`, `loansandlong_termliabilities`,
`sister_holding`.

- No dedupe key. The natural upsert key is `(stock_id, fiscal_year, quarter)`;
  a republished corrected report yields duplicate rows.
- Sector `16` is unmapped — those rows are labelled `UNKNOWN_16`.

## Data-quality traps

**Flat zero-volume placeholder rows.** Across all 1,072 files, 53,974 of
1,124,057 rows (4.8%) are `open==close==high==low` with `volume==0`. For NEPSE
index specifically it is **64%** of rows. Some files are almost entirely synthetic
(`NMBEB92_93`, `ADBLB86` at 99%). There is no validation or quality flag anywhere —
this junk is committed and will poison any model trained on it.

**Missing symbols.** 126 of 639 requested symbols produce no CSV at all
(`10NICD208586`, `ALDBLP`, `BENI`, `GASY`, `MNMF2`, `SFF`…). These are mostly
promoter shares (`*PO`/`*P` suffixes), debentures, and bonds. The fetcher
requests them every run, gets nothing, and moves on — ~20% wasted request budget.

**Truncated volume.** Index volume arrives as a float (`4293774181.11`) and is
cast with `int()`, silently dropping the fraction.

## Proven clean

Verified across all 1,072 price CSVs:

- **0 duplicate `time` values** and **0 unsorted files** — the client-side dedupe
  at `asyncmain_incremental.py:185` works.
- **0 negative-volume rows.**
- **No symbol collisions** after the `/` → `_` normalisation.
- Working tree and LFS index are internally consistent; no half-migrated files.

## Attribution

`README.md:33` credits "NEPSE official records". The actual source is
**ShareHub Nepal**, a third-party mirror, via
`sharehubnepal.com/data/api/v1/candle-chart/history`. Fix the attribution.