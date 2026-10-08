# 01. Project Understanding

This is the **single source of truth** for the project. The code, the dashboard and the reports must all match this file.

**Title:** Privacy-Preserving Credit Card Fraud Detection and Visual Analytics using Python and Tableau

**One line:** A Python pipeline takes 1.85 million credit card transactions, hides the private customer details, flags suspicious transactions with 4 simple rules, and sends the safe result to a Tableau dashboard.

```text
Raw CSVs → [1] Load → [2] Privacy layer → [3] Fraud rules → [4] Evaluate → [5] Charts → [6] Tableau workbook
```

Tableau only ever sees the protected file. It never sees the raw data.

## 1. Dataset (facts measured by `src/load_data.py`)

**Source:** Kaggle "Credit Card Transactions Fraud Detection Dataset" (`kartik2112/fraud-detection`). It was generated with the Sparkov simulator, so it describes no real people.

| Fact | Value |
|---|---|
| Files | `fraudTrain.csv` (1,296,675 rows) and `fraudTest.csv` (555,719 rows) |
| Total rows | 1,852,394 |
| Period | Train: 2019-01-01 to 2020-06-21. Test: 2020-06-21 to 2020-12-31 |
| Fraud | 9,651 rows (0.52%). Train 0.58%, test 0.39% |
| Customers (cards) | 999 |
| States / categories / merchants | 51 / 14 / 693 |
| Missing values, duplicate rows | 0, 0 |
| Country, currency | USA, US dollars |
| Customer age at transaction | 13 to 96 |

**Data quirk:** every merchant name starts with `fraud_` (for example `fraud_Rippin, Kub and Mann`). It is an artifact of the simulator and does **not** mean fraud. We strip it.

## 2. Privacy layer (`src/privacy.py`)

| Raw column | Technique | Output column | Example |
|---|---|---|---|
| `cc_num` | **Masking** (keep the last 4 digits) | `card_masked` | `**** **** **** 2095` |
| `cc_num` | **Pseudonymization** with salted SHA-256, first 10 hex characters | `customer_id` | `C_3298fc2482` |
| `first`, `last` | **Suppression** (deleted) | none | none |
| `dob` | **Generalization** to an age band at transaction time | `age_band` | `<25`, `25-39`, `40-54`, `55-69`, `70+` |
| `state` | **Generalization** to a US Census region | `region` | Northeast, Midwest, South, West |
| `street`, `city`, `zip`, `lat`, `long`, `city_pop`, `job`, `merch_lat`, `merch_long`, `trans_num`, `unix_time` | **Suppression** | none | none |
| `merchant` | Cleaning (strip `fraud_`) | `merchant` | `Rippin, Kub and Mann` |

**Why salt?** Without a secret salt, anyone could hash every possible card number and match the hashes. The salt lives in `src/config.py`. In a real system it would be stored in a secret vault.

**k-anonymity check (k = 5):** count the distinct customers in every combination of (`age_band`, `gender`, `region`). Every group must contain at least 5 customers, which means nobody can be picked out of a group smaller than 5.

* **With state and 7 narrow age bands:** 659 of 999 customers are in groups smaller than 5 (smallest group: 1 customer). FAIL.
* **With region and 5 age bands:** the smallest group has 5 customers. PASS.

The pipeline runs both checks and saves them to `outputs/privacy_report.json`. Showing the failure and then the fix is part of the story.

## 3. Fraud rules (`src/fraud_rules.py`)

All limits are learned from `fraudTrain.csv` **only**. Results are reported on `fraudTest.csv`, which the rules never saw.

| Rule | Fires when | Learned from train |
|---|---|---|
| **R1 High amount** | the amount is above the 99th percentile of its category | percentile per category |
| **R2 Night time** | the hour is 22, 23, 0, 1, 2 or 3 | the hours with a high fraud rate |
| **R3 Risky category** | the category's fraud rate is at least 2× the overall rate | `grocery_pos`, `misc_net`, `shopping_net` |
| **R4 Above usual spend** | the amount is at least 5× the customer's median spend | median per `customer_id` (falls back to the category median for unseen customers) |

* `risk_score` = number of rules fired (0 to 4).
* `flagged` = 1 when `risk_score` ≥ 3. The value 3 is the score threshold with the best F1 on train, recorded in `outputs/rule_tuning.csv`.

**Tested and dropped:** customer to merchant distance. The average is 76.1 km for normal transactions and 76.3 km for fraud, so it carries no signal.

**Metrics (on test):** precision, recall, F1, accuracy and a confusion matrix, for each rule alone and for the combined score. Accuracy is misleading here: flagging nothing at all would still score 99.6%, because fraud is so rare.

## 4. Output file for Tableau: `data/processed/transactions_protected.csv`

| Column | Type | Meaning |
|---|---|---|
| `transaction_time` | datetime `YYYY-MM-DD HH:MM:SS` | when the payment happened |
| `hour` | int 0 to 23 | hour of day |
| `dataset_split` | `train` / `test` | which source file |
| `customer_id` | text | pseudonym |
| `card_masked` | text | masked card number |
| `merchant` | text | merchant name |
| `category` | text | one of 14 categories |
| `amount` | float | amount in $ |
| `gender` | `F` / `M` | gender |
| `age_band` | text | `<25`, `25-39`, `40-54`, `55-69`, `70+` |
| `region` | text | Northeast, Midwest, South, West |
| `rule_high_amount`, `rule_night`, `rule_risky_category`, `rule_above_usual` | 0/1 | each rule |
| `risk_score` | int 0 to 4 | rules fired |
| `flagged` | 0/1 | the rule engine's decision |
| `is_fraud` | 0/1 | the true answer |
| `outcome` | text | `Caught`, `Missed`, `False alarm`, `Correctly passed` |

## 5. Tableau dashboard (`dashboard/fraud_dashboard.twb`, written by `src/build_dashboard.py`)

* **KPIs:** Total Transactions · Fraud Transactions · Fraud Rate % · Fraud Amount $ · Rule Recall % · Rule Precision %
* **Charts:** Fraud Rate by Hour · Fraud Count by Category · Fraud by Age Band · Fraud by Region · Monthly Fraud Trend · Rule Outcomes (Caught / Missed / False alarm)
* **Filters:** date range, category, region, age band, gender, dataset split

## 6. Other outputs (`outputs/`)

* `data_profile.json`: the dataset facts in section 1.
* `privacy_report.json`: the k-anonymity checks (FAIL then PASS) and before/after examples.
* `rule_tuning.csv`: train F1 for each score threshold.
* `metrics.json`: test metrics for each rule and for the combined score.
* `charts/*.png`: report figures (fraud by hour, fraud by category, rule comparison, confusion matrix, k-anonymity group sizes).
