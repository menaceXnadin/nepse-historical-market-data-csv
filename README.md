# NEPSE Historical Market Data CSV

This repository contains historical market data for the Nepal Stock Exchange (NEPSE), provided in CSV format. The data includes daily price information for individual stocks, market indices, and sub-indices.

## Data Structure

The data is organized in the following directory structure:

- `data/`
  - `index/`
    - `adjusted/`: Adjusted historical data for main indices (e.g., NEPSE, FLOAT, SENSITIVE)
    - `unadjusted/`: Unadjusted historical data for main indices
  - `stock/`
    - `adjusted/`: Adjusted historical data for individual stocks
    - `unadjusted/`: Unadjusted historical data for individual stocks
  - `subindices/`
    - `adjusted/`: Adjusted historical data for sub-indices (e.g., BANKING, FINANCE, etc.)
    - `unadjusted/`: Unadjusted historical data for sub-indices

## File Naming Convention

Files are named in the format: `{SYMBOL}_{type}.csv`

- `SYMBOL`: Stock symbol, index name, or sub-index name
- `type`: Either "adjusted" or "unadjusted"

## Usage

You can use these CSV files for analysis, backtesting trading strategies, or any other financial data processing needs. The data is historical and can be loaded into pandas, Excel, or other data analysis tools.

## Data Source

The data is sourced from NEPSE official records. Please note that historical data may be subject to adjustments for events like stock splits, dividends, etc. The "adjusted" versions account for these adjustments.

## Contributing

If you have additional data or improvements, feel free to contribute via pull requests.
