# 03. Plan and Project Structure

```text
cbca-293-security/
├── README.md                  what the project is, plus a 3-command quick start
├── setup.md                   step-by-step guide for a junior developer
├── pyproject.toml, uv.lock    uv project (Python 3.13)
├── .python-version            3.13
├── data/
│   ├── raw/                   fraudTrain.csv, fraudTest.csv (Kaggle)
│   └── processed/             transactions_protected.csv (Tableau input)
├── src/
│   ├── config.py              paths, salt, rule settings
│   ├── load_data.py           step 1: load, combine, clean, profile
│   ├── privacy.py             step 2: mask, hash, generalize, k-anonymity
│   ├── fraud_rules.py         steps 3-4: rules, score, metrics
│   ├── make_charts.py         step 5: report charts
│   ├── build_dashboard.py     step 6: writes the Tableau .twb
│   └── run_pipeline.py        runs steps 1-6 in order
├── dashboard/                 fraud_dashboard.twb, screenshots/
├── outputs/                   JSON/CSV results, charts/*.png
├── reports/                   00_front_matter.md … 05_chapter5.md, appendix_a.md, presentation.md, assets/
└── docs/                      cbca-293-doc.md, 01 understanding, 02 decisions, 03 plan
```

| Step | Output | Status |
|---|---|---|
| 1 | Requirements merged, dataset downloaded, uv project | Done |
| 2 | Pipeline code (`src/`) and outputs | Done |
| 3 | Tableau `.twb` generator | Done in code. Visual check in Tableau pending |
| 4 | Reports Ch 1 to 5, appendix, presentation (.md) | Done (dashboard screenshots pending) |
| 5 | README and setup.md | Done |
| 6 | Rerun from scratch, consistency check across docs, code and reports | Done |
