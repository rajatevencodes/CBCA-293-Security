# Chapter 4. Results and discussion

The results come from `outputs/`, the console output in Figure 3.1 and, where stated, row counts from the protected CSV.

## 4.1 Experimental setup

The run uses the protocol from Section 2.6.

| Item | Value |
|---|---|
| Hardware | MacBook Air, Apple Silicon (arm64), macOS |
| Software | Python 3.13.15, pandas 3.0.6, NumPy 2.5.3, Matplotlib 3.11.2, run with uv |
| Training data | `fraudTrain.csv`: 1,296,675 rows, 7,506 fraud (0.58%), 2019-01-01 00:00:18 to 2020-06-21 12:13:37 |
| Test data | `fraudTest.csv`: 555,719 rows, 2,145 fraud (0.39%), 2020-06-21 12:14:25 to 2020-12-31 23:59:34 |
| Split | By time, as given by the two files. No shuffling. |
| Learned from train only | Overall fraud rate, category 99th percentiles, night hours, risky categories, customer medians, category medians, score threshold |
| Reported on | Test rows only |
| Run time | 114 seconds for all six steps |

The test file starts 48 seconds after the training file ends. Every test transaction is later than the data used to learn the rules.

### What was learned from the training file

`metrics.json` gives a training fraud rate of 0.5789%. R2 and R3 mark an hour or category as risky at twice that rate, or 1.158% and above.

**Table 4.1: Rule limits learned from the training file**

| Rule | Learned value | Evidence |
|---|---|---|
| R1 High amount | One 99th percentile amount per category (14 limits) | Kept in memory by `learn_limits()` |
| R2 Night time | Hours 0, 1, 2, 3, 22 and 23 | `metrics.json`, console |
| R3 Risky category | `grocery_pos`, `misc_net`, `shopping_net` | `metrics.json`, console |
| R4 Above usual spend | Median spend of each of the 983 customers in the training file; category median for others | Counted from the protected CSV |

The six selected night hours have training fraud rates from 1.42% to 2.88%, with hour 22 highest. Every other hour is between 0.10% and 0.14%. The selected categories are `shopping_net` at 1.76%, `misc_net` at 1.45% and `grocery_pos` at 1.41%. The next category, `shopping_pos`, is below the 1.158% cutoff at 0.72%. Of the 924 customers in the test file, 16 are absent from training. R4 uses the category median for them.

### Threshold tuning on the training file

`outputs/rule_tuning.csv` compares thresholds 1 through 4 on the training rows.

**Table 4.2: Threshold tuning on the training file (1,296,675 rows, 7,506 fraud)**

| Threshold (flag if risk_score ≥) | Flagged | TP | FP | FN | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|---|---|---|---|
| 1 | 530,962 | 7,208 | 523,754 | 298 | 1.36% | 96.03% | 0.0268 | 59.58% |
| 2 | 108,984 | 5,411 | 103,573 | 2,095 | 4.96% | 72.09% | 0.0929 | 91.85% |
| **3** | **9,357** | **3,934** | **5,423** | **3,572** | **42.04%** | **52.41%** | **0.4666** | **99.31%** |
| 4 | 1,485 | 1,237 | 248 | 6,269 | 83.30% | 16.48% | 0.2752 | 99.50% |

Threshold 3 has the highest F1 at 0.4666, so the pipeline uses **risk_score ≥ 3**. At threshold 1, recall reaches 96.03% but produces 523,754 false alarms. Threshold 4 raises precision to 83.30% but catches only 16.48% of the fraud.

## 4.2 Output results

### 4.2.1 Dataset profile

`outputs/data_profile.json`, written by `load_data.py`, contains the following counts.

| Fact | Value |
|---|---|
| Total rows | 1,852,394 |
| Fraud rows | 9,651 (0.52%) |
| Missing values | 0 |
| Duplicate rows (full row) | 0 |
| Duplicate transaction IDs | 0 |
| Customers (cards) | 999 |
| States / categories / merchants | 51 / 14 / 693 |
| Customer age at transaction | 13 to 96 |

### 4.2.2 Privacy results: one record before and after

Table 4.3 takes the first record from `outputs/privacy_report.json` before and after protection. The simulated row does not describe a real person.

**Table 4.3: Example record before and after the privacy layer**

| Field | Before (raw) | After (protected) | Technique |
|---|---|---|---|
| Card number | `2703186189652095` | `**** **** **** 2095` | Masking |
| Customer identifier | (the card number) | `C_3298fc2482` | Salted SHA-256 pseudonym |
| Name | Jennifer Banks | removed | Suppression |
| Date of birth | 1988-03-09 | `25-39` | Generalization to age band |
| Street, city, ZIP | 561 Perry Cove, Moravian Falls, 28654 | removed | Suppression |
| State | NC | South | Generalization to Census region |

Sixteen raw columns do not reach the output unchanged. The pipeline deletes 13 of them: `first`, `last`, `street`, `city`, `zip`, `lat`, `long`, `city_pop`, `job`, `merch_lat`, `merch_long`, `trans_num` and `unix_time`. It replaces `cc_num` with `card_masked` and `customer_id`, `dob` with `age_band`, and `state` with `region`.

### 4.2.3 k-anonymity before and after generalization

**Table 4.4: k-anonymity check with k = 5 (999 customers)**

| Measure | Before | After |
|---|---|---|
| Quasi-identifiers | narrow age band (7 bands), gender, state | age band (5 bands), gender, region |
| Number of groups | 461 | 40 |
| Smallest group (customers) | 1 | 5 |
| Groups smaller than 5 | 395 | 0 |
| Customers in groups smaller than 5 | 659 (66% of 999) | 0 |
| Result | **FAIL** | **PASS** |

![k-anonymity before and after](../outputs/charts/k_anonymity_before_after.png)

**Figure 4.1: Customers in groups smaller than k = 5, before and after generalization**

Exact states and narrow age bands split the data into 461 groups. Of these, 395 have fewer than 5 customers, and the smallest has one. That customer can be singled out by age band, gender and state. Generalizing to 4 regions and 5 age bands produces all 40 possible combinations (5 x 2 x 4). The smallest contains 5 customers, and none falls below k. This meets Objective 4.

### 4.2.4 Files produced

| Output | Content |
|---|---|
| `data/processed/transactions_protected.csv` | 1,852,394 rows, 19 columns, about 265 MB. The only input of Tableau. |
| `outputs/data_profile.json` | Dataset facts (Section 4.2.1) |
| `outputs/privacy_report.json` | k-anonymity before and after, example record, removed columns |
| `outputs/rule_tuning.csv` | Table 4.2 |
| `outputs/metrics.json` | Learned rule settings and all test metrics (Section 4.3) |
| `outputs/charts/*.png` | Figures 3.2 to 3.6 |
| `dashboard/fraud_dashboard.twb` | Tableau workbook: 12 worksheets, 6 calculated fields, 6 shared filters, validated |

The protected CSV has the 19 columns listed in `docs/01_project_understanding.md`, Section 4: `transaction_time`, `hour`, `dataset_split`, `customer_id`, `card_masked`, `merchant`, `category`, `amount`, `gender`, `age_band`, `region`, the four rule columns, `risk_score`, `flagged`, `is_fraud` and `outcome`.

## 4.3 Performance analysis

### 4.3.1 Test results for each rule and the combined score

**Table 4.5: Results on the unseen test file (555,719 rows, 2,145 fraud)**

| Rule | Flagged | TP (caught) | FP (false alarms) | FN (missed) | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|---|---|---|---|
| R1 High amount | 5,315 | 666 | 4,649 | 1,479 | 12.53% | 31.05% | 0.1786 | 98.90% |
| R2 Night time | 130,139 | 1,807 | 128,332 | 338 | 1.39% | 84.24% | 0.0273 | 76.85% |
| R3 Risky category | 121,699 | 1,258 | 120,441 | 887 | 1.03% | 58.65% | 0.0203 | 78.17% |
| R4 Above usual spend | 20,073 | 1,518 | 18,555 | 627 | 7.56% | 70.77% | 0.1366 | 96.55% |
| **Combined (risk_score ≥ 3)** | **3,592** | **1,224** | **2,368** | **921** | **34.08%** | **57.06%** | **0.4267** | **99.41%** |
| Flag-nothing baseline | 0 | 0 | 0 | 2,145 | 0.00% | 0.00% | 0.0000 | 99.61% |

![Rule performance on the test file](../outputs/charts/rule_comparison.png)

**Figure 4.2: Precision, recall and F1 on the test file**

### 4.3.2 Confusion matrix of the combined rules

| | Actually fraud | Actually normal |
|---|---|---|
| **Flagged** | 1,224 (Caught) | 2,368 (False alarm) |
| **Not flagged** | 921 (Missed) | 551,206 (Correctly passed) |

![Confusion matrix](../outputs/charts/confusion_matrix.png)

**Figure 4.3: Confusion matrix of the combined rules on the test file**

The combined rules flag 3,592 transactions, or 0.65% of the test file. They catch 1,224 frauds, which is 57.1% of all test fraud. One in 3 alerts is correct (34.1%). The test fraud rate is 0.39%, so a flagged transaction is about 88 times more likely to be fraud than a random test transaction.

### 4.3.3 Why accuracy is misleading

The flag-nothing baseline has **99.61% accuracy**, above the combined rules at 99.41%, but its recall is **0%**. It catches no fraud. Since 99.6% of rows are normal, accuracy mainly measures how often normal rows are left alone [20]. R2 and R3 show the opposite failure. Their recall is 84.2% and 58.7%, but they flag about 23% and 22% of all test transactions, leaving precision close to the base rate. Precision, recall and F1 give the useful comparison.

### 4.3.4 Why combining the rules raises precision

No single rule is precise. R2 and R3 each fire on more than 120,000 test transactions, almost all normal. R1 and R4 are narrower but remain below 13% precision. A normal transaction may trigger one rule, such as a late-night online purchase, but few trigger three. Only 2,368 of 553,574 normal test transactions, or 0.43%, reach a score of 3. By comparison, 1,224 of 2,145 frauds, or 57.1%, reach that score. Requiring 3 rules removes most normal transactions while retaining more than half the fraud.

The combined score has 2.7 times the precision of the best single rule, 34.1% against 12.5% for R1. Its F1 is 2.4 times as high, 0.427 against 0.179.

### 4.3.5 Train compared with test

| Data | Precision | Recall | F1 |
|---|---|---|---|
| Train (threshold 3) | 42.04% | 52.41% | 0.4666 |
| Test (threshold 3) | 34.08% | 57.06% | 0.4267 |

Test F1 falls from 0.4666 to 0.4267, while recall rises from 52.41% to 57.06%. The rules still detect later transactions rather than only fitting the training rows. Precision falls partly because fraud is less common in the test file, 0.39% against 0.58%, so each alert has fewer frauds available to find.

## 4.4 Discussion

The 114-second run removed every direct identifier and measured k-anonymity at k = 5. Four one-line rules reached an F1 of 0.427 on later test data. An alert can be traced to its conditions, such as a large amount at night in an online shopping category. The generated Tableau workbook passed its structural checks and can be rebuilt from the protected CSV.

The threshold controls the balance between missed fraud and investigator workload. At 3, the test run produces 2,368 false alarms and misses 921 frauds, about 2 false alarms per fraud caught. On training data, threshold 2 reaches 72% recall but creates more than 10 times as many alerts. Threshold 4 reaches 83% precision and misses most fraud. F1 selects threshold 3 here. A bank would instead compare the cost of missed fraud with the cost of checking an alert [3], [4].

Generalization removes state-level and exact-age analysis from the dashboard. It keeps only 4 regions and 5 age bands. The detailed version left 659 customers in groups below 5, so that loss of detail was needed to meet the chosen k. The fraud rules use amount, hour, category and customer pseudonym, none of which the generalization removes. Their inputs are unchanged by this privacy step.

A tested distance rule did not separate the classes. The average is 76.1 km for normal transactions and 76.3 km for fraud. Dropping that rule also allowed the pipeline to remove the home and merchant coordinates.

By default, the dashboard combines training and test rows. The Rule Recall % tile then shows 53.4%, or 5,158 of 9,651 frauds caught. Rule Precision % shows 39.8%, or 5,158 of 12,949 alerts. Tables 4.2 and 4.5 provide those counts. They are not test results because the rules learned from the training rows. Setting **Dataset Split** to `test` changes the tiles to 57.1% recall and 34.1% precision, matching Table 4.5 and Figure 3.8.

These numbers describe simulated data, not expected performance at a bank. Real fraud is more varied and changes over time [3]. Section 5.2 covers the remaining limits.
