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

Files are named in the format: `{SYMBOL}_{DATE}_{type}.csv`

- `SYMBOL`: Stock symbol, index name, or sub-index name
- `DATE`: Date in YYYY_MM_DD format
- `type`: Either "adjusted" or "unadjusted"

## Scripts

- `main.py`: Main script for data processing
- `asyncmain.py`: Asynchronous version of the main script
- `sectors.py`: Script related to sector classification
- `sector.json`: JSON file containing sector information
- `sectormapping.csv`: CSV mapping stocks to sectors

## Usage

You can use these CSV files for analysis, backtesting trading strategies, or any other financial data processing needs. The data is historical and can be loaded into pandas, Excel, or other data analysis tools.

## Data Source

The data is sourced from NEPSE official records. Please note that historical data may be subject to adjustments for events like stock splits, dividends, etc. The "adjusted" versions account for these adjustments.

## Automated Data Updates

This repository uses GitHub Actions to automatically fetch and update NEPSE data daily at 6:00 PM Nepal Time (12:15 UTC). The workflow runs the `asyncmain.py` script and commits any new data to the repository.

### Setup Instructions

#### 1. Enable GitHub Actions

1. Push this repository to GitHub
2. Go to your repository on GitHub
3. Navigate to **Settings** → **Actions** → **General**
4. Under "Workflow permissions", select **"Read and write permissions"**
5. Click **Save**

#### 2. Manual Trigger (Optional)

You can manually trigger the workflow at any time:
1. Go to **Actions** tab in your repository
2. Select **"Update NEPSE Data"** workflow
3. Click **"Run workflow"** button
4. Select the branch and click **"Run workflow"**

#### 3. Monitor Workflow Runs

- Go to **Actions** tab to see all workflow runs
- Click on any run to see detailed logs
- Failed runs will be highlighted in red

### API Secrets

Currently, this project doesn't require API keys as it uses public endpoints:
- `https://chukul.com/api/sector/` - For sector data
- `https://sharehubnepal.com/data/api/v1/candle-chart/history` - For historical price data

If you need to add API secrets in the future:
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Add your secret name and value
4. Update the workflow file to use: `${{ secrets.YOUR_SECRET_NAME }}`

### Local Development

To run the script locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the script
python asyncmain.py
```

### Schedule Customization

The workflow is scheduled to run daily at 12:15 UTC (6:00 PM Nepal Time). To change the schedule:

1. Open `.github/workflows/update-data.yml`
2. Modify the cron expression under `schedule`
3. Cron format: `minute hour day month day-of-week`
4. Use [crontab.guru](https://crontab.guru/) for help with cron expressions

Example schedules:
- Every 6 hours: `'0 */6 * * *'`
- Every weekday at noon UTC: `'0 12 * * 1-5'`
- Twice daily (6 AM & 6 PM Nepal Time): `'15 0,12 * * *'`

## Contributing

If you have additional data or improvements, feel free to contribute via pull requests.
