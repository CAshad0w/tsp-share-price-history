# TSP Share Price History

Historical Thrift Savings Plan (TSP) fund share prices in a public CSV for
spreadsheets, notebooks, and other projects.

[Download the CSV](data/tsp-share-price-history.csv?raw=1)

## About the data

The CSV has one row per published price date, sorted oldest to newest. `Date`
uses `YYYY-MM-DD`. Fund columns contain share prices in U.S. dollars and cover
the individual and Lifecycle funds included in the source exports. Blank cells
indicate that the dataset has no price for that fund on that date.

This is an independent mirror of exports from the
[official TSP share price history page](https://www.tsp.gov/share-price-history/).
For the exact coverage of this copy, check the first and last data rows. To
reproduce an analysis, use the CSV from a specific Git commit.

## How updates work

The dataset starts with an export of all-time TSP share price data. Each update downloads the
**All share prices** export with the **5 days** filter and merges every returned
row by price date. New dates are added, overlapping dates are refreshed, and
holidays receive no placeholder rows. If the download or validation fails,
the existing CSV stays in place.

## Run the updater locally

From the repo root on macOS or Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade playwright
.venv/bin/python -m playwright install chromium
.venv/bin/python update_tsp_history.py --output data/tsp-share-price-history.csv
```

The script opens Chromium by default. Add `--headless` for unattended runs
after verifying that mode works on your machine.
