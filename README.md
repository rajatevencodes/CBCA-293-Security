# Privacy-Preserving Credit Card Fraud Detection and Visual Analytics

**Course:** CBCA293 Security and Privacy for Big Data Analytics · BCA, Bennett University
**Team:** Rajat Sharma (S24BCAU0134) · Ishan Chaudary (S24BCAU0002) · Piyush Agarwal (S24BCAU0182) · Suraj Tiwari (S24BCAU0136)
**Faculty:** Ms. Monia

A Python pipeline takes **1,852,394** credit card transactions, **hides the private customer details**, **flags suspicious transactions with 4 simple rules**, and feeds the safe result into a **Tableau dashboard**.

```text
Raw CSVs → Load → Privacy layer → Fraud rules → Evaluate → Charts → Tableau extract + workbook (.twbx)
```

## Results at a glance

| What | Result |
|---|---|
| Privacy: k-anonymity (k = 5) before generalization | FAIL: 659 of 999 customers in groups smaller than 5 |
| Privacy: after (age band, gender, region) | PASS: smallest group has 5 customers |
| Fraud rules on the unseen test file | Precision 34.1% · Recall 57.1% · F1 0.427 |
| Caught / missed / false alarms (test) | 1,224 / 921 / 2,368 |

## Quick start

```bash
uv sync                                             # install Python 3.13 + packages
uv run python src/run_pipeline.py                   # run everything (about 2 minutes)
open dashboard/fraud_dashboard.twbx                 # open the dashboard in Tableau Public
```

In Tableau, set the **Dataset Split** filter to `test` to match the report numbers.
New to this? Follow **[setup.md](setup.md)** step by step.

**Why a .twbx and a .hyper file?** Tableau Public only opens workbooks whose data is a Tableau *extract*.
`src/make_extract.py` turns the protected CSV into `data/processed/transactions_protected.hyper`, and
`src/build_dashboard.py` packs the dashboard and that extract into `dashboard/fraud_dashboard.twbx`.
To rebuild the extract after changing the data:

```bash
uv run --with tableauhyperapi python src/run_pipeline.py
```

## Project structure

```text
├── README.md                  this file
├── setup.md                   step-by-step guide for a beginner
├── pyproject.toml, uv.lock    uv project (Python 3.13)
├── data/raw/                  fraudTrain.csv, fraudTest.csv (Kaggle dataset, not in git)
├── data/processed/            transactions_protected.csv (not in git) and transactions_protected.hyper (Tableau extract)
├── src/
│   ├── config.py              all settings: paths, salt, rule settings
│   ├── load_data.py           step 1: load, combine, clean, profile
│   ├── privacy.py             step 2: mask, hash, generalize, k-anonymity
│   ├── fraud_rules.py         steps 3-4: rules, risk score, metrics
│   ├── make_charts.py         step 5: report charts
│   ├── make_extract.py        step 6: Tableau extract (.hyper) from the protected CSV
│   ├── build_dashboard.py     step 6: writes the Tableau .twb and packaged .twbx (dashboard as code)
│   └── run_pipeline.py        runs steps 1-6 in order
├── dashboard/                 fraud_dashboard.twbx (open this), fraud_dashboard.twb, screenshots/
├── outputs/                   data_profile.json, privacy_report.json, rule_tuning.csv, metrics.json, charts/
├── reports/                   report chapters (Markdown), presentation, final milestone PDFs
└── docs/                      requirements and design notes
```

## Where each submission item is

| University requirement | File(s) |
|---|---|
| Milestone 1 report (Chapters 1 and 2) | `reports/CBCA293_Milestone1_Ch1-2.pdf` (source: `reports/00_front_matter.md`, `01_chapter1.md`, `02_chapter2.md`) |
| Milestone 2 report (Chapters 3 to 5, Appendix A) | `reports/CBCA293_Milestone2_Ch3-5.pdf` (source: `reports/03_chapter3.md`, `04_chapter4.md`, `05_chapter5.md`, `appendix_a.md`) |
| Presentation content | `reports/presentation.md` |
| Source code with comments | `src/` |
| Dataset files | `data/raw/` and `data/processed/` (CSV files are too large for GitHub; see setup.md step 4) |
| Screenshots | `dashboard/screenshots/`, `outputs/charts/` |
| Requirements (merged) | `docs/cbca-293-doc.md` |

## Dataset

Kaggle, [Credit Card Transactions Fraud Detection Dataset](https://www.kaggle.com/datasets/kartik2112/fraud-detection) (simulated with Sparkov, CC0 licence). It covers US customers, with amounts in US dollars, from 2019 to 2020.
