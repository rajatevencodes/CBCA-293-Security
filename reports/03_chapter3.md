# Chapter 3. Project implementation

The Chapter 2 design is implemented in `src/`. Reference numbers in Chapters 3 to 5 use the consolidated list in Section 5.4.

## 3.1 Development environment

| Item | Version / detail | Role |
|---|---|---|
| Computer | MacBook Air, Apple Silicon (arm64), macOS | Development and running the pipeline |
| Python | 3.13.15 | Programming language |
| uv | installed on the Mac | Creates the virtual environment and installs the locked packages [21] |
| pandas | 3.0.6 | Data loading, grouping, percentiles, CSV output [22] |
| NumPy | 2.5.3 | Numeric support for pandas [26] |
| Matplotlib | 3.11.2 | Report charts [25] |
| hashlib, xml.etree.ElementTree, csv, json | Python standard library | SHA-256 hashing [18], writing the Tableau XML [24], reading/writing files |
| Tableau Desktop Public Edition | free edition, workbook saved locally | Opening and using the dashboard [13], [15] |
| Editor | VS Code and the macOS terminal | Writing and running code |

This is a uv project. `pyproject.toml` lists the three libraries, `uv.lock` fixes their versions, and `.python-version` selects Python 3.13. Two commands set up and run the project:

```bash
uv sync                               # create .venv and install the locked packages
uv run python src/run_pipeline.py     # run steps 1 to 6
```

After the protected CSV exists, `uv run python src/build_dashboard.py` rebuilds only the Tableau workbook.

The code uses this folder structure:

```text
cbca-293-security/
├── data/raw/            fraudTrain.csv, fraudTest.csv (Kaggle, never changed)
├── data/processed/      transactions_protected.csv (the only file Tableau reads)
├── src/                 the 7 Python modules
├── outputs/             data_profile.json, privacy_report.json, rule_tuning.csv,
│                        metrics.json, charts/*.png
├── dashboard/           fraud_dashboard.twb, screenshots/
└── reports/             this report
```

## 3.2 Module description

Each pipeline step has its own module. Table 3.1 lists its inputs, outputs and main functions.

**Table 3.1: Modules of the system**

| Module | Step | Input | Output | Main functions |
|---|---|---|---|---|
| `config.py` | Settings | none | Settings used by all modules | `SALT`, `K_ANONYMITY`, `AGE_BINS`, `NARROW_AGE_BINS`, `STATE_TO_REGION`, rule settings |
| `load_data.py` | 1. Load | `data/raw/*.csv` | Combined table, `outputs/data_profile.json` | `load_raw()`, `profile()` |
| `privacy.py` | 2. Privacy layer | Combined raw table | Protected table, `outputs/privacy_report.json` | `mask_card()`, `pseudonymize()`, `age_at_transaction()`, `k_anonymity()`, `protect()` |
| `fraud_rules.py` | 3. Rules, 4. Evaluate | Protected table | Rule columns, `outputs/rule_tuning.csv`, `outputs/metrics.json` | `learn_limits()`, `apply_rules()`, `score()`, `tune_threshold()`, `evaluate()`, `add_decision()` |
| `make_charts.py` | 5. Charts | Protected table, limits, metrics, privacy report | 5 PNG files in `outputs/charts/` | `fraud_by_hour()`, `fraud_by_category()`, `rule_comparison()`, `confusion_matrix()`, `k_anonymity()` |
| `build_dashboard.py` | 6. Tableau workbook | `transactions_protected.csv` | `dashboard/fraud_dashboard.twb` | `build_datasource()`, `build_shared_views()`, `build_worksheet()`, `build_dashboard()`, `build()`, `validate()` |
| `run_pipeline.py` | All | Raw files | All outputs | `main()`, `save_json()` |

`config.py` holds the salt, k = 5, age bands, state-to-region map and rule factors. The factors are the 99th percentile, 2 times the overall fraud rate and 5 times the usual spend. Other modules import these values.

## 3.3 Code implementation

The excerpts below come from the source files. Their comments describe the individual operations.

### 3.3.1 Loading and cleaning (`load_data.py`)

```python
for split, path in config.RAW_FILES.items():
    df = pd.read_csv(path, usecols=RAW_COLUMNS,
                     dtype={c: "category" for c in CATEGORY_COLUMNS})
    df["dataset_split"] = split
    parts.append(df)
df = pd.concat(parts, ignore_index=True)
...
df["merchant"] = df["merchant"].astype(str).str.removeprefix("fraud_")
```

The loop reads both files and stacks them into one table. `dataset_split` records the source file for each row. `usecols` skips the unnamed row-number field, while pandas stores text fields with few distinct values as `category` to reduce memory use. The last line removes the simulator's `fraud_` prefix from merchant names.

### 3.3.2 Masking (`privacy.py`)

```python
def mask_card(card_number: int) -> str:
    """Keep only the last 4 digits, like a printed receipt."""
    return "**** **** **** " + str(card_number)[-4:]
```

The masked value keeps only the last four digits, within the PCI DSS display rule [6]. Its format stays the same for any input length.

### 3.3.3 Pseudonymization with salted SHA-256 (`privacy.py`)

```python
def pseudonymize(card_number: int, salt: str = config.SALT) -> str:
    digest = hashlib.sha256((salt + str(card_number)).encode("utf-8")).hexdigest()
    return "C_" + digest[:10]
```

The function places the salt before the card number and hashes the combined text with SHA-256 [17], [18]. The first 10 hexadecimal characters form the `customer_id`, such as `C_3298fc2482`. `protect()` hashes each of the 999 distinct cards once, then maps the result to its rows. It does not repeat the hash across all 1.85 million rows.

### 3.3.4 Generalization (`privacy.py` and `config.py`)

```python
AGE_BINS = [0, 24, 39, 54, 69, 200]
AGE_LABELS = ["<25", "25-39", "40-54", "55-69", "70+"]
...
age = age_at_transaction(raw)
df["age_band"] = pd.cut(age, config.AGE_BINS, labels=config.AGE_LABELS)
df["region"] = raw["state"].astype(str).map(config.STATE_TO_REGION)
```

Age is calculated at the transaction date by dividing the days since birth by 365.25 and keeping whole years. `pd.cut` assigns one of 5 bands. The state code becomes its US Census region [19]. The function builds the protected table one column at a time. Names, address, coordinates, job and other omitted fields never enter it.

### 3.3.5 k-anonymity check (`privacy.py`)

```python
def k_anonymity(df: pd.DataFrame, quasi_identifiers: list[str], k: int = config.K_ANONYMITY) -> dict:
    sizes = df.groupby(quasi_identifiers, observed=True)["customer_id"].nunique()
    small = sizes[sizes < k]
    exposed = df.loc[df.set_index(quasi_identifiers).index.isin(small.index), "customer_id"].nunique()
    return {
        ...
        "result": "PASS" if sizes.min() >= k else "FAIL",
    }
```

The function groups the data by its quasi-identifiers and counts distinct customers in each group [10]. Counting rows would overstate group size because each customer has many transactions. It lists groups below k and counts their customers as "exposed." `protect()` runs the check first on narrow age band, gender and state, then on age band, gender and region.

### 3.3.6 Learning the rule limits (`fraud_rules.py`)

```python
def learn_limits(train: pd.DataFrame) -> RuleLimits:
    overall = train["is_fraud"].mean()
    hour_rate = train.groupby("hour")["is_fraud"].mean()
    cat_rate = train.groupby("category", observed=True)["is_fraud"].mean()
    return RuleLimits(
        overall_fraud_rate=float(overall),
        category_p99=train.groupby("category", observed=True)["amount"]
                          .quantile(config.HIGH_AMOUNT_PERCENTILE).to_dict(),
        night_hours=sorted(int(h) for h in hour_rate[hour_rate >= config.RISK_FACTOR * overall].index),
        risky_categories=sorted(str(c) for c in cat_rate[cat_rate >= config.RISK_FACTOR * overall].index),
        customer_median=train.groupby("customer_id")["amount"].median().to_dict(),
        category_median=train.groupby("category", observed=True)["amount"].median().to_dict(),
    )
```

This function receives training rows only. It calculates each category's 99th amount percentile, finds hours and categories with at least 2 times the overall fraud rate, and records the median spend for every customer and category. The night hours come from that rate test rather than a fixed list.

### 3.3.7 Applying the rules (`fraud_rules.py`)

```python
usual = df["customer_id"].map(limits.customer_median).fillna(category.map(limits.category_median))
df["rule_high_amount"] = (df["amount"] > category.map(limits.category_p99)).astype(int)
df["rule_night"] = df["hour"].isin(limits.night_hours).astype(int)
df["rule_risky_category"] = category.isin(limits.risky_categories).astype(int)
df["rule_above_usual"] = (df["amount"] >= config.ABOVE_USUAL_FACTOR * usual).astype(int)
df["risk_score"] = df[RULE_COLUMNS].sum(axis=1)
```

Each rule returns 0 or 1. `fillna` assigns the category median as the usual spend when a customer has no training history. Adding the four columns gives the risk score.

### 3.3.8 Scoring and threshold tuning (`fraud_rules.py`)

```python
def score(predicted: pd.Series, actual: pd.Series) -> dict:
    p, a = predicted.astype(bool), actual.astype(bool)
    tp, fp = int((p & a).sum()), int((p & ~a).sum())
    fn, tn = int((~p & a).sum()), int((~p & ~a).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
```

`score()` builds the confusion matrix and metrics from Section 2.4.7, including guards against division by zero. `tune_threshold()` tests thresholds 1 through 4 on the training rows and keeps the highest F1. On the test rows, `evaluate()` scores each rule, the combined decision and a "flag nothing" baseline. The baseline uses `risk_score > 99`, which is always false. `add_decision()` then writes `flagged` and one of four `outcome` labels: `Caught`, `Missed`, `False alarm` or `Correctly passed`.

### 3.3.9 Keeping raw data out of later steps (`run_pipeline.py`)

```python
df, privacy_report = privacy.protect(raw)
del raw  # the raw data is not used after this point
```

After `privacy.protect()` returns, the pipeline drops its reference to the raw table. Steps 3 through 6 receive only the protected table, matching the trust boundary in Figure 2.1. The protected CSV has exactly 19 columns (Section 4.2).

### 3.3.10 Generating and validating the Tableau workbook (`build_dashboard.py`)

A Tableau workbook (`.twb`) is an XML text file. `build_dashboard.py` writes it with Python's `xml.etree.ElementTree` module [24]. One command can rebuild the workbook. The script defines:

* a text data-source connection to the 19 columns in `transactions_protected.csv`;
* six KPI calculated fields in Tableau's formula language, for example:

```python
"recall": Calc("Calculation_7310000000000000005", "Rule Recall %", "real",
               "SUM([flagged] * [is_fraud]) / SUM([is_fraud])", FMT_PCT1),
"precision": Calc("Calculation_7310000000000000006", "Rule Precision %", "real",
                  "SUM([flagged] * [is_fraud]) / SUM([flagged])", FMT_PCT1),
```

* six shared filters for date range, category, region, age band, gender and dataset split, applied to every worksheet that uses the source;
* twelve worksheets: 6 KPI tiles (Total Transactions, Fraud Transactions, Fraud Rate %, Fraud Amount $, Rule Recall %, Rule Precision %) and 6 charts (Fraud Rate by Hour, Fraud Count by Category, Fraud by Age Band, Fraud by Region, Monthly Fraud Trend, Rule Outcomes);
* a 1400 x 900 pixel dashboard named "Fraud & Privacy Dashboard," with a title, 6 KPI tiles, a 2 x 3 chart grid and a filter panel.

The "Rule Outcomes" chart omits the much larger `Correctly passed` group so the `Caught`, `Missed` and `False alarm` bars remain readable. "Fraud by Age Band" uses a manual order because alphabetical sorting would put `<25` last.

After writing the file, `build()` calls `validate()` and reads the XML back. It checks that the XML parses, referenced fields exist, worksheets declare their fields, the dashboard contains every worksheet, layout zones stay inside their parents and each sheet has a tab. A failed check stops the script. The final run printed: `Validated fraud_dashboard.twb: 12 worksheets, 6 calculated fields, 6 shared filters.`

The workbook stores an absolute path to the CSV folder. On another computer, `--tableau-data-dir` rebuilds it with the correct folder.

## 3.4 System interface and screenshots

### 3.4.1 Pipeline console output

The terminal command is `uv run python src/run_pipeline.py`. Its final output is below.

```text
[1/6] Loading raw Kaggle files ...
   1,852,394 rows, 9,651 fraud (0.52%)
   saved outputs/data_profile.json
[2/6] Privacy layer: mask, hash, generalize, suppress ...
   k-anonymity before: FAIL (smallest group 1, 659 customers in groups < 5)
   k-anonymity after: PASS (smallest group 5, 0 customers in groups < 5)
   saved outputs/privacy_report.json
[3/6] Learning rule limits from the TRAIN file ...
   night hours [0, 1, 2, 3, 22, 23], risky categories ['grocery_pos', 'misc_net', 'shopping_net']
   best threshold on train: risk_score >= 3
[4/6] Evaluating on the unseen TEST file ...
   precision 34.1%, recall 57.1%, F1 0.427
   saved outputs/metrics.json
[5/6] Drawing report charts ...
   saved outputs/charts/*.png
[6/6] Writing protected CSV and Tableau workbook ...
   saved data/processed/transactions_protected.csv
Validated fraud_dashboard.twb: 12 worksheets, 6 calculated fields, 6 shared filters.
   saved dashboard/fraud_dashboard.twb
Done in 114 seconds.
```

**Figure 3.1: Console output of the complete pipeline run**

The MacBook Air processed 1.85 million raw rows and wrote the Tableau workbook in 114 seconds.

### 3.4.2 Report charts produced by the pipeline

![Fraud rate by hour of day](../outputs/charts/fraud_rate_by_hour.png)

**Figure 3.2: Fraud rate by hour of day (all data). Orange bars are the night hours learned for rule R2.**

![Fraud rate by merchant category](../outputs/charts/fraud_rate_by_category.png)

**Figure 3.3: Fraud rate by merchant category (all data). Orange bars are the risky categories learned for rule R3.**

![Rule performance on the unseen test file](../outputs/charts/rule_comparison.png)

**Figure 3.4: Precision, recall and F1 of each rule and of the combined score on the test file**

![Confusion matrix of the combined rules](../outputs/charts/confusion_matrix.png)

**Figure 3.5: Confusion matrix of the combined rules on the test file**

![k-anonymity before and after generalization](../outputs/charts/k_anonymity_before_after.png)

**Figure 3.6: Customers in groups smaller than k = 5, before and after generalization**

Chapter 4 discusses these results.

### 3.4.3 Tableau dashboard

`dashboard/fraud_dashboard.twb` opens in Tableau Desktop Public Edition. Figure 3.7 uses all rows. Figure 3.8 sets Dataset Split to `test`, which makes the KPIs match Chapter 4.

<!-- screenshot pending: capture after opening in Tableau -->
![Tableau dashboard overview](../dashboard/screenshots/01_dashboard_overview.png)

**Figure 3.7: Fraud & Privacy Dashboard, all data (train and test)**

<!-- screenshot pending: capture after opening in Tableau -->
![Tableau dashboard filtered to the test file](../dashboard/screenshots/02_dashboard_test_filter.png)

**Figure 3.8: Fraud & Privacy Dashboard with Dataset Split = test**

Six KPI tiles run across the top. Six charts fill the middle and bottom rows, and the right panel contains 6 filters that update every view. Only protected fields appear. A customer is represented by a pseudonym and masked card number, a location by its region, and an age by its band.
