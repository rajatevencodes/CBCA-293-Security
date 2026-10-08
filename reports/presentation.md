# Privacy-Preserving Credit Card Fraud Detection and Visual Analytics using Python and Tableau

CBCA293 Security and Privacy for Big Data Analytics · Bennett University · Rajat Sharma (S24BCAU0134) and team

## Slide 1: Title

* Privacy-Preserving Credit Card Fraud Detection and Visual Analytics
* Python pipeline + Tableau dashboard
* Team members and enrolment numbers
* Faculty guide: ____________________

*Speaker note: One line: we hide private customer details first, then find fraud and show it in Tableau.*

## Slide 2: Problem

* Card fraud losses worldwide: $33.83 billion in 2023 (Nilson Report)
* Transaction data holds names, addresses, birth dates and full card numbers
* Analysts need patterns, not identities
* Fraud is rare (0.52%), so accuracy is misleading

*Speaker note: The question is how to analyse fraud without exposing who the customers are.*

## Slide 3: Objectives

* Remove all direct identifiers before analysis
* Reach k-anonymity with k ≥ 5 on (age band, gender, region)
* Detect fraud with 4 explainable rules, tested on unseen data
* Build a Tableau dashboard with 6 KPIs, 6 charts, 6 filters

*Speaker note: Every objective has a number we can check, and each one is checked in the results.*

## Slide 4: Dataset

* Kaggle "Credit Card Transactions Fraud Detection Dataset", simulated with Sparkov (no real people)
* 1,852,394 transactions, 999 customers, 693 merchants, 14 categories
* Train 2019-01-01 to 2020-06-21, test 2020-06-21 to 2020-12-31
* 9,651 fraud rows (0.52%); 0 missing values

*Speaker note: Every merchant name starts with "fraud_", which is a simulator quirk, not a fraud label; we strip it.*

## Slide 5: Architecture

* Raw CSVs → Load → Privacy layer → Fraud rules → Evaluate → Charts → Tableau workbook
* Raw data is deleted from memory after the privacy layer
* Tableau only reads `transactions_protected.csv`
* One command runs everything in 114 seconds

*Speaker note: Show Figure 2.1; the privacy layer is the trust boundary.*

## Slide 6: Privacy layer

* Card number → `**** **** **** 2095` (masking) and `C_3298fc2482` (salted SHA-256)
* Names, address, coordinates, job deleted (13 columns)
* Date of birth → 5 age bands; state → 4 Census regions
* k-anonymity: before FAIL (659 customers exposed), after PASS (smallest group 5)

*Speaker note: We measured privacy instead of assuming it; the failure and the fix are both saved.*

## Slide 7: Fraud rules

* R1 amount above 99th percentile of its category
* R2 night hours (22 to 3), R3 risky categories (grocery_pos, misc_net, shopping_net)
* R4 amount ≥ 5× the customer's median spend
* Flag if 3 or more rules fire (best F1 on train)

*Speaker note: All limits are learned from the train file only, then frozen.*

## Slide 8: Results on the unseen test file

* Precision 34.1%, recall 57.1%, F1 0.427
* Caught 1,224, missed 921, false alarms 2,368
* Best single rule: F1 0.179; combining rules raises precision 2.7×
* Flag-nothing baseline: 99.61% accuracy but 0% recall

*Speaker note: Show the confusion matrix; explain why accuracy is not used to judge the system.*

## Slide 9: Live demo

* Run `uv run python src/run_pipeline.py` and show the console output
* Open `dashboard/fraud_dashboard.twb` in Tableau Desktop Public Edition
* Set Dataset Split = test: KPIs match the report (recall 57.1%, precision 34.1%)
* Filter by category or region and show the charts update

*Speaker note: About 5 minutes; if the run is slow, show the saved console output and open the workbook directly.*

## Slide 10: Conclusion and future scope

* Privacy and fraud detection did not conflict: the rules never needed identity fields
* Limits: simulated data, rules only, k-anonymity does not stop attribute disclosure, salt in code
* Next: l-diversity, differential privacy for KPIs, a machine learning layer, salt in a vault
* Questions

*Speaker note: End with the one-line takeaway: protect first, then analyse.*
