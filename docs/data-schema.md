# Data Schema

What the files in `data/` contain, and what to watch out for when using them.

## Price CSVs

`data/{stock,index,subindices}/{adjusted,unadjusted}/{SYMBOL}_{type}.csv`

| Column | Type | Notes |
|---|---|---|
| `time` | `YYYY-MM-DD` | Trading date (bars are stamped at midnight UTC by the source) |
| `symbol` | string | `/` replaced with `_` in the filename and value |
| `open` `high` `low` `close` | float | NPR for stocks, points for indices |
| `volume` | int | Share count for stocks; **rupee turnover for indices**, with the fractional part dropped |
| `category` | string | `stock`, `index` or `subindex` |

Rows are sorted by `time` with one row per date. Read columns by name rather
than position.

### Adjusted vs unadjusted

Adjustment is done by the source (ShareHub's `isAdjust` flag), not by this repo.
For example, NABIL's first bar (2012-01-01) opens at 79.31 adjusted and 873
unadjusted.

- **Adjusted files can go stale after a corporate action.** The fetcher only
  appends new rows, so when a company issues bonus or right shares, the rows
  already in its `adjusted/` file keep the old adjustment while new rows use
  the new one. Check for a jump on the book-closure date, or rebuild the
  series from the unadjusted file.
- **Indices are not adjusted.** Index and sub-index files are identical in both
  folders.
- Stocks with no corporate actions also have identical files in both folders.
- Don't mix adjusted and unadjusted series in the same analysis.

## `quarterly_reports.csv`

One row per company per reported quarter. Fiscal years use the Nepali calendar
(`082/083`), and `quarter` is `q1` to `q4`.

| Group | Columns |
|---|---|
| Identity | `stock_id`, `stock_name`, `symbol`, `sector`, `fiscal_year`, `quarter` |
| Per share / ratios | `eps`, `dps`, `roe`, `roa`, `pe_ratio`, `growth_rate`, `close` |
| Balance sheet | `paidup_capital`, `reserve_surplus`, `net_worth`, `total_equity`, `total_assets`, `deposit`, `investments`, `total_currentassets`, `total_currentliabilities` |
| Income statement | `operating_income`, `operating_expenses`, `administrative_expenses`, `depreciation`, `financial_expenses`, `net_profit` |

Mutual funds, promoter shares and debentures are excluded. The natural key is
`(stock_id, fiscal_year, quarter)`; if a company republishes a corrected report,
both versions may appear.

## Known caveats

- **Placeholder rows.** Some rows have `open == high == low == close` with
  `volume == 0`, especially in early index history and in bonds and
  debentures. Filter on `volume > 0` if you only want days with trades.
- **Not every symbol has data.** Some promoter shares, debentures and newly
  listed symbols return nothing from the source and have no file.
- **Unofficial source.** Prices come from ShareHub Nepal and reports from
  Chukul, not from NEPSE directly.
