# AI Compute Capex Tracker

Tracks quarterly capital expenditure of the largest AI cloud spenders (Microsoft, Alphabet, Amazon, Meta, Oracle), or any US-listed company, using the free SEC XBRL API. Hyperscaler capex is the main demand signal for the whole AI compute supply chain (GPUs, custom chips, memory, networking, power), and the biggest swing factor in the hyperscalers' own free cash flow.

Beyond capex, it pulls revenue, operating cash flow and depreciation to answer: **who is spending most aggressively, and what is it doing to their cash flow and future margins?**

## Metrics

| Metric | Definition | Question it answers |
|---|---|---|
| Capex YoY / QoQ | Growth vs. same quarter last year / last quarter | Who is accelerating? |
| Capex TTM | Sum of last four quarters | Smooths quarterly noise |
| Share of group capex | Company capex ÷ group total | Who drives demand for suppliers? |
| Capex / Revenue | Capex intensity | Who reinvests the most of each revenue dollar? |
| FCF, FCF TTM, FCF margin | Operating cash flow − capex | Whose cash generation is being consumed by capex? |
| Capex / D&A | Capex ÷ depreciation & amortization | Above 1x: depreciation will keep rising and weigh on margins |
| Capex trend | Accelerating if YoY growth > prior quarter's | Is the spending cycle speeding up or slowing? |

## What it does

1. **Fetch**: downloads each company's XBRL facts from `data.sec.gov` (cached locally)
2. **Extract**: pulls capex, revenue, operating cash flow and D&A from 10-Q and 10-K filings
3. **Clean**: removes duplicate and restated figures, converts year-to-date cash flows into single quarters, and maps different fiscal years onto calendar quarters
4. **Metrics**: computes the measures above
5. **Export**: Excel workbook (metrics as live formulas), charts, CSVs, and a Markdown summary with auto-generated findings

## The data problems it solves

- **Different labels for the same thing.** Companies tag the same line item differently in XBRL (e.g. `PaymentsToAcquirePropertyPlantAndEquipment` vs `PaymentsToAcquireProductiveAssets`). The tracker checks a priority list of tags per metric, processes each tag separately so a year-to-date subtraction never mixes two line items, and records which tag was used.
- **Year-to-date cash flows.** 10-Q cash flow statements report cumulative figures (6 months, 9 months). Single quarters are derived by subtracting the prior YTD value. Missing filings are skipped rather than producing a misleading number.
- **Different fiscal years.** Microsoft's fiscal year ends in June and Oracle's in May. Each period is assigned to the calendar quarter containing its midpoint so companies are comparable.
- **Different reporting dates.** Oracle reports about a month before the others. The latest quarters are trimmed until every company has reported, so totals are never understated.
- **Restatements.** The same period appears in many filings; the most recently filed value is used.

- **Gaps in the SEC API.** Some quarters are missing from the API, e.g. when a company tagged capex with its own custom XBRL element. The tracker skips them rather than guessing; they can be filled by hand in `manual_overrides.csv` with the filing cited, and are labelled "manual" in the audit trail.

## Setup

```bash
pip install -r requirements.txt
```

Edit `USER_AGENT` in `capex_tracker.py` to your name and email (required by the SEC).

```bash
python capex_tracker.py                   # the five hyperscalers (default)
python capex_tracker.py NVDA              # any single company, by ticker
python capex_tracker.py NVDA AVGO MU      # any group of companies
python capex_tracker.py --refresh         # re-download the latest filings
python -m pytest tests/                   # run the tests
```

Tickers are mapped to SEC CIK numbers automatically. Each run writes to its own folder, e.g. `output/hyperscalers/` or `output/NVDA/`.

## Outputs (in `output/<tickers>/`)

| File | Contents |
|---|---|
| `capex_tracker.xlsx` | Summary snapshot, cross-company capex and share, YoY growth, one sheet per company with all metrics as formulas, audit trail linking each input to its filing, notes |
| `capex_trend.png` | Stacked bar chart of quarterly capex |
| `metrics_dashboard.png` | Capex YoY, capex/revenue, FCF margin and capex/D&A for the last four years |
| `capex_summary.md` | Key findings, snapshot table and last 8 quarters, ready for a knowledge base |
| `capex_quarterly.csv` | Clean long-format input data with sources |
| `metrics.csv` | All computed metrics per company and quarter |

## Filling missing quarters

Add rows to `manual_overrides.csv`, using numbers read from the filing's cash flow statement:

```
ticker,cal_quarter,metric,value_usd_millions,source
NVDA,2022Q1,capex,123,10-Q for quarter ended 2022-05-01
META,2026Q2,da,4567,10-Q cash flow statement
```

`metric` is one of `capex`, `revenue`, `ocf`, `da`. The older layout without a `metric` column (`ticker,cal_quarter,capex_usd_millions,source`) still works and is treated as capex.

## Limitations

- Capex here is **cash paid** for property and equipment. Assets acquired under **finance leases** are excluded, and they are material for some companies, so company-reported "total capex" figures can be higher.
- Capex covers all property and equipment, not only AI infrastructure.
- D&A definitions differ by company, so compare Capex / D&A within a company over time more than across companies.
- Revenue is total company revenue; cloud segment revenue (Azure, AWS, Google Cloud) is not in this API.
