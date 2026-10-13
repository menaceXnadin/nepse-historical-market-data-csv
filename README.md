# NEPSE Historical Market Data (CSV)

Daily price history for every traded stock, index and sub-index on the Nepal
Stock Exchange (NEPSE), plus company quarterly reports. Updated automatically
every evening by GitHub Actions.

| | |
|---|---|
| Stocks | 519 symbols, adjusted and unadjusted |
| Indices | NEPSE, FLOAT, SENSITIVE, SENFLOAT |
| Sub-indices | 13 sector indices (BANKING, HYDROPOWER, …) |
| Quarterly reports | ~6,600 rows, fiscal years 073/074 onward |
| History | NEPSE index from 1997; most stocks from their listing date |
| Update | Daily at 12:00 UTC (5:45 PM NPT), skipped on Saturdays |

## Layout

```
data/
├── stock/
│   ├── adjusted/        NABIL_adjusted.csv, …
│   └── unadjusted/      NABIL_unadjusted.csv, …
├── index/
│   ├── adjusted/
│   └── unadjusted/
├── subindices/
│   ├── adjusted/
│   └── unadjusted/
├── quarterly_reports.csv
└── sector.json          symbol → sector universe used by the fetcher
```

Files are named `{SYMBOL}_{adjusted|unadjusted}.csv`. A `/` in a symbol is
written as `_` (`GBD80/81` → `GBD80_81`).

## Price files

```csv
time,symbol,open,close,high,low,volume,category
2026-10-13,NEPSE,2597.93,2599.93,2600.95,2589.36,4736926409,index
```

| Column | Description |
|---|---|
| `time` | Trading date, `YYYY-MM-DD` |
| `symbol` | Stock, index or sub-index symbol |
| `open`, `high`, `low`, `close` | Prices in NPR (index points for indices) |
| `volume` | Shares traded; **for indices this is turnover in NPR** |
| `category` | `stock`, `index` or `subindex` |

**Adjusted** prices are corrected for bonus shares, rights and splits, so they
are comparable across time. **Unadjusted** prices are what actually traded on
the day. Use adjusted for returns and backtests.

See [docs/data-schema.md](docs/data-schema.md) for the quarterly report columns
and known data-quality caveats.

## Quick start

```python
import pandas as pd

base = "https://raw.githubusercontent.com/menaceXnadin/nepse-historical-market-data-csv/master/data"
nepse = pd.read_csv(f"{base}/index/adjusted/NEPSE_adjusted.csv", parse_dates=["time"])
nabil = pd.read_csv(f"{base}/stock/adjusted/NABIL_adjusted.csv", parse_dates=["time"])
```

## Sources

- Daily prices: [ShareHub Nepal](https://sharehubnepal.com) candle-chart API
- Quarterly reports and sector list: [Chukul](https://chukul.com)

This is an unofficial mirror, not data published by NEPSE itself. Check
anything important against an official source.

## Updating it yourself

```bash
pip install -r requirements.txt
python scripts/fetch_data.py
```

The fetcher is incremental: it reads the last date in each CSV and only
requests newer bars, so a run on an up-to-date checkout takes a few minutes.
