# Privacy-Preserving Credit Card Fraud Detection and Visual Analytics

**Course:** CBCA293 Security and Privacy for Big Data Analytics · BCA, Bennett University
**Team:** Rajat Sharma (S24BCAU0134) · Student 2 · Student 3 · Student 4

A Python pipeline takes **1,852,394** credit card transactions, **hides the private customer details**, **flags suspicious transactions with 4 simple rules**, and feeds the safe result into a **Tableau dashboard**.

```text
Raw CSVs → Load → Privacy layer → Fraud rules → Evaluate → Charts → Tableau workbook (.twb)
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
uv sync                               # install Python 3.13 + packages
uv run python src/run_pipeline.py     # run everything (about 2 minutes)
```

Then open `dashboard/fraud_dashboard.twb` in **Tableau Desktop Public Edition**.
New to this? Follow **[setup.md](setup.md)** step by step.

## Project structure

```text
├── README.md                  this file
├── setup.md                   step-by-step guide for a junior developer
├── pyproject.toml, uv.lock    uv project (Python 3.13)
├── data/raw/                  fraudTrain.csv, fraudTest.csv (Kaggle dataset)
├── data/processed/            transactions_protected.csv (the only file Tableau reads)
├── src/
│   ├── config.py              all settings: paths, salt, rule settings
│   ├── load_data.py           step 1: load, combine, clean, profile
│   ├── privacy.py             step 2: mask, hash, generalize, k-anonymity
│   ├── fraud_rules.py         steps 3-4: rules, risk score, metrics
│   ├── make_charts.py         step 5: report charts
│   ├── build_dashboard.py     step 6: writes the Tableau .twb (dashboard as code)
│   └── run_pipeline.py        runs steps 1-6 in order
├── dashboard/                 fraud_dashboard.twb, screenshots/
├── outputs/                   data_profile.json, privacy_report.json, rule_tuning.csv, metrics.json, charts/
├── reports/                   report chapters (Markdown) and presentation content
└── docs/                      requirements and design notes
```

## Where each submission item is

| University requirement | File(s) |
|---|---|
| Report, Chapters 1 to 2 (Milestone 1) | `reports/00_front_matter.md`, `01_chapter1.md`, `02_chapter2.md` |
| Report, Chapters 3 to 5 (Milestone 2) | `reports/03_chapter3.md`, `04_chapter4.md`, `05_chapter5.md`, `appendix_a.md` |
| Presentation content | `reports/presentation.md` |
| Source code with comments | `src/` |
| Dataset files | `data/raw/` and `data/processed/` |
| Screenshots | `outputs/charts/`, `dashboard/screenshots/` |
| Requirements (merged) | `docs/cbca-293-doc.md` |

## Dataset

Kaggle, [Credit Card Transactions Fraud Detection Dataset](https://www.kaggle.com/datasets/kartik2112/fraud-detection) (simulated with Sparkov, CC0 licence). It covers US customers, with amounts in US dollars, from 2019 to 2020.
