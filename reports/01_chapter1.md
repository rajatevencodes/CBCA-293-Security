# Chapter 1. Problem analysis and introduction

## 1.1 Background of the study

Credit and debit card payments generate transaction records in shops and online. A large bank can produce millions each day. Their volume, speed and continuous arrival make card transactions a big data problem.

Card fraud is costly. According to The Nilson Report, card fraud losses worldwide reached $33.83 billion in 2023, or 6.58 cents for every $100 of total card volume [1]. Fraud also costs customers time and trust.

Bolton and Hand distinguish fraud detection from prevention. Prevention tries to stop fraud before it happens. Detection tries to identify it quickly after it has happened [2]. Detection methods examine transactions for unusual amounts, times or changes in a customer's spending.

Fraud is rare. Only 0.52% of the 1,852,394 transactions used here are fraud. This class imbalance makes accuracy misleading [3]. Fraud patterns also change, so a method tuned on old data needs to be tested on newer transactions [3].

Transaction records also contain personal information. One row can include a name, home address, date of birth, job and full card number. The European Union's General Data Protection Regulation (GDPR) defines information about an identified or identifiable person as "personal data" [7]. The US National Institute of Standards and Technology (NIST) uses the term personally identifiable information (PII) and advises organisations to minimise its use, collection and retention [8]. The Payment Card Industry Data Security Standard (PCI DSS) also limits how much of a card number may appear on screens and in reports [5], [6].

Fraud analysts need transaction patterns, not customer identities. Giving analysts or a dashboard the raw file adds another copy that can leak. The pipeline deals with this by protecting the data before fraud analysis or Tableau can access it.

## 1.2 Problem statement

Fraud analysis needs transaction data, but the same data contains names, addresses, dates of birth and full card numbers. Giving the raw file to analysts or a BI tool exposes those fields. Simply deleting columns is not enough. A rare combination such as age and state may still identify someone, while deleting too much can make fraud detection useless.

The research question is:

> *How can a large set of credit card transactions be protected so that no individual can be identified, and still be used to detect fraud with simple, explainable rules and to present the results in an interactive Tableau dashboard, with both the privacy level and the detection quality measured rather than assumed?*

Four practical questions follow:

1. Which columns are direct identifiers, which are quasi-identifiers, and how should each be treated (masked, hashed, generalized or deleted)?
2. How can we prove that the protected data meets a stated privacy level, such as k-anonymity with k = 5?
3. Can a small set of readable rules, learned only from older data, find fraud in newer data that the rules have never seen, and how well?
4. How can the protected results be shown in a dashboard that tells a clear story without ever loading the raw data?

## 1.3 Objectives

Each objective has a measurable target. Chapter 4 reports the results.

1. Load both source files (1,296,675 + 555,719 = 1,852,394 rows), count missing values and duplicate rows, and save the profile to `outputs/data_profile.json`.
2. Keep names, street address, city, ZIP code, coordinates, job, date of birth and full card number out of Tableau. Of the 23 raw columns, delete 13 personal or linkable columns and the row-number column. Transform the card number, date of birth and state.
3. Show no more than the last 4 digits of a card, which is stricter than the PCI DSS limit of the BIN plus the last 4 digits [6]. Replace the full number with a salted SHA-256 pseudonym that links the customer's transactions without displaying the number.
4. Reach k-anonymity with k ≥ 5 for age band, gender and region. Every combination must contain at least 5 distinct customers. Run the check on a detailed version (state and 7 age bands) and the final version (region and 5 age bands), then save both results to `outputs/privacy_report.json`.
5. Build four readable fraud rules for high amount, night time, risky category and spending above the customer's usual amount. Learn their limits from `fraudTrain.csv` only, add them into a score from 0 to 4, and choose the score threshold with the best training F1. Save the comparison to `outputs/rule_tuning.csv`.
6. Apply the fixed rules to the 555,719 rows in `fraudTest.csv`. Report precision, recall, F1, accuracy and a confusion matrix for every rule and the combined score in `outputs/metrics.json`. Compare them with a "flag nothing" baseline.
7. Build a Tableau dashboard that reads only the protected file. It must have at least 6 KPIs, 6 charts and 5 filters. The design uses 6 of each.
8. Run the full pipeline, from raw CSV files to the Tableau workbook, with one command and get the same outputs each time.

## 1.4 Scope

### In scope

* The public Kaggle "Credit Card Transactions Fraud Detection Dataset" [16], both files (train and test).
* A Python pipeline that loads, cleans and profiles the data.
* A privacy layer using masking, pseudonymization, generalization and suppression, plus an automatic k-anonymity check.
* Four rule-based fraud indicators, a combined risk score, and threshold tuning on the training file.
* Evaluation on the test file with standard metrics.
* Report charts made with Matplotlib.
* A Tableau workbook (generated by Python) with KPIs, charts and filters, opened and saved locally in Tableau Desktop Public Edition.

### Out of scope

* Machine learning models are excluded. Only rules are used, so every decision can be explained in plain words. Section 1.5 reviews machine learning for comparison.
* No real customer data is used. The dataset is simulated.
* The pipeline works on files in batch mode, not on real-time or streaming data.
* Advanced privacy models such as l-diversity and differential privacy are reviewed in Section 1.5 and left for further work.
* Infrastructure security, including encryption at rest, access control and big data platforms (Hadoop, Spark, Kerberos, Ranger), belongs to other course tracks.
* The dashboard is not published on Tableau Public, where published work is visible to everyone [15]. It is kept locally.

## 1.5 Review of existing systems

The project combines fraud detection, privacy protection and business intelligence (BI). The following review explains the choice of methods and tools.

### 1.5.1 Fraud detection approaches

#### Rule-based systems

Fraud experts write "if-then" rules such as "if the amount is very large and the card is used at night, raise an alert". Le Borgne et al. describe a layered system in which blocking rules stop clearly fraudulent payments at the terminal and scoring rules assign a fraud score to accepted transactions [4]. Rules are fast and readable, but they catch only known patterns. Different experts may write different rules, and a large set becomes hard to maintain [4].

#### Machine learning systems

A decision tree, random forest or neural network can learn from past transactions labelled as fraud or genuine, then assign a fraud probability to a new transaction. Bolton and Hand cover both supervised methods, which use labels, and unsupervised methods, which look for unusual behaviour without them [2]. These models can find patterns that rules miss. Their decisions are harder to explain, and training must account for class imbalance and changing fraud patterns [3], [4].

#### Hybrid systems

Banks use rules and models together. In the system described by Le Borgne et al., both produce alerts for human investigators [4]. Investigators can review only a limited number each day, so false alarms matter. Dal Pozzolo et al. make the same point using data from an industry partner: evaluation has to reflect class imbalance, changing fraud and limited review time [3].

This project implements a small scoring-rules layer. Each decision can be traced to a readable rule. The limits, including what counts as a high amount, come from training data rather than an expert guess. Later transactions are kept aside for testing [3].

### 1.5.2 Privacy protection techniques

#### Direct identifiers and quasi-identifiers

A *direct identifier* points to one person on its own, such as a name or a full card number. A *quasi-identifier* does not identify anyone alone, but a combination of them can. For example, age, gender and state together may match only one person in a dataset. NIST lists removing direct identifiers and transforming quasi-identifiers as two of the main de-identification methods [9].

#### Masking

Masking hides part of a value when it is displayed. PCI DSS v4.0 was published by the PCI Security Standards Council in March 2022 [5]. Its Requirement 3.4.1 says that the card number (Primary Account Number, PAN) must be masked when displayed, so that no more than the BIN (the first digits, which identify the issuer) and the last four digits are shown, unless there is a documented business need [6]. Masking is simple and familiar ("card ending 2095"), but it does not let an analyst follow one customer, because many cards share the same last four digits.

#### Pseudonymization (hashing)

GDPR Article 4(5) defines pseudonymisation as processing personal data so that it "can no longer be attributed to a specific data subject without the use of additional information", which must be stored separately and protected [7]. One method replaces an identifier with a cryptographic hash such as SHA-256. The hash does not reveal the original value directly. A structured input such as a card number is still vulnerable to guessing: an attacker can hash possible numbers and compare the outputs. Adding a secret *salt* before hashing blocks that comparison unless the attacker also obtains the salt. The salt is the additional information that must be kept separate.

#### Generalization and suppression

Generalization replaces an exact value with a broader one, for example a date of birth with an age band, or a state with a region. Suppression deletes a value or a whole column. Both reduce the detail in the data so that people are harder to single out [9].

#### k-anonymity

Sweeney proposed k-anonymity as a formal privacy model [10]. A released table is k-anonymous if every person in it cannot be distinguished from at least k − 1 other people on the quasi-identifiers. For example, with k = 5, every combination of age band, gender and region must cover at least 5 people. k-anonymity is easy to understand and easy to check, which is why it is used in this project. Its known weakness is that if all people in a group share the same sensitive value, an attacker still learns that value [11].

#### l-diversity

Machanavajjhala et al. showed two attacks on k-anonymity: the *homogeneity attack*, where everyone in a group has the same sensitive value, and the *background knowledge attack*, where the attacker uses outside information [11]. They proposed l-diversity, which requires each group to contain at least l "well-represented" values of the sensitive attribute [11].

#### Differential privacy

Dwork introduced differential privacy, which limits how much an analysis can change when one person's data is added or removed [12]. Implementations usually add calibrated random noise. It gives a stronger formal guarantee than the other methods reviewed here, but the noise reduces accuracy and row-level dashboards are a poor fit.

Table 1.1 compares these techniques.

**Table 1.1: Comparison of privacy protection techniques**

| Technique | What it does | Main strength | Main weakness | Used in this project |
|---|---|---|---|---|
| Masking | Hides most digits when displayed | Simple, required by PCI DSS [6] | Cannot link transactions of one customer | Yes, card number |
| Salted hashing (pseudonymization) | Replaces an identifier with a one-way code | Keeps linkage without revealing identity | Data is still personal data if the salt leaks [7] | Yes, card number |
| Generalization | Replaces exact values with ranges or groups | Reduces re-identification risk | Loses detail | Yes, date of birth, state |
| Suppression | Deletes values or columns | Removes risk completely | Information is lost | Yes, 13 columns |
| k-anonymity | Guarantees groups of at least k people [10] | Easy to check and explain | Weak if a group shares one sensitive value [11] | Yes, k = 5 |
| l-diversity | Requires varied sensitive values per group [11] | Stops homogeneity attack | More complex, more data loss | No (future work) |
| Differential privacy | Adds calibrated noise to results [12] | Strongest formal guarantee | Reduces accuracy, harder to explain | No (future work) |

### 1.5.3 Business intelligence tools

The course allows Microsoft Power BI or Tableau. Both have the required charts, filters, slicers and KPIs. The operating system decides the choice here (Table 1.2).

**Table 1.2: Comparison of BI tools for this project**

| Point | Microsoft Power BI Desktop | Tableau Desktop Public Edition |
|---|---|---|
| Cost | Free desktop app | Free desktop app |
| Operating system | Windows 10 or later only [14] | Windows and macOS |
| Saving work locally | Yes | Yes, since April 2024 [13] |
| Private data | Supported | Supported when saved locally [15] |
| Fit for this project (Apple Silicon Mac) | Not possible without a Windows machine | Runs natively |

Power BI Desktop requires Windows [14], while the project laptop is an Apple Silicon Mac. Tableau Desktop Public Edition is free and, since April 2024, can save workbooks locally and work offline [13]. Tableau's documentation notes that workbooks published to a Tableau Public profile "are not private and are freely accessible to anyone" [15]. That matters for a privacy project, so the dashboard is kept local and reads only the protected file.

### 1.5.4 Comparison and identified gap

Table 1.3 compares common existing approaches with this project on the features that matter for the course: detecting fraud, protecting privacy, explaining decisions and showing results visually.

**Table 1.3: Existing approaches compared with this project**

| Approach | Detects fraud | Protects personal data | Privacy level measured | Explainable decisions | Tested on unseen later data | Interactive dashboard |
|---|---|---|---|---|---|---|
| Expert rule engine [4] | Yes | Not its purpose | No | Yes | Depends on the team | No |
| Machine learning model [2], [3] | Yes | Not its purpose | No | Limited | Yes, when done well [3] | No |
| Industry hybrid system [4] | Yes | Inside a secure bank system | Not public | Partly | Yes | Internal tools |
| Privacy models alone (k-anonymity, l-diversity, DP) [10]-[12] | No | Yes | Yes | Not applicable | Not applicable | No |
| BI dashboard on raw data | Shows patterns only | No | No | Not applicable | No | Yes |
| **This project** | **Yes (4 rules + score)** | **Yes (mask, hash, generalize, suppress)** | **Yes (k ≥ 5 check)** | **Yes** | **Yes (train/test by time)** | **Yes (Tableau)** |

The reviewed work usually treats fraud detection, privacy protection and visual analytics separately. Fraud studies measure detection quality [2]-[4]. Privacy research studies safe data release [10]-[12]. BI tools display the result. This project puts the three parts in one student-scale pipeline: it measures privacy before analysis, tests readable rules on later data, and keeps raw personal data out of the dashboard.

### 1.5.5 Feasibility analysis

#### Technical

The raw files contain 1,852,394 rows and take about 502 MB (351 MB and 150 MB). They fit in laptop memory and pandas can process them without a cluster. Python and its libraries provide the required hashing, grouping, percentile, median and counting operations. Tableau Desktop Public Edition runs on macOS. The files have no missing values or duplicate rows, so cleaning is limited.

#### Cost

The project has no direct software or data cost. Python, uv, pandas, NumPy and Matplotlib are free and open source. Tableau Desktop Public Edition is free [13], and Kaggle distributes the dataset under the CC0 public-domain licence [16]. The remaining inputs are an existing laptop and student time.

#### Operation

A user can read why a transaction was flagged, for example, "the amount is at least 5 times the customer's usual spend." Dashboard filters for date, category, region, age band, gender and dataset split require no code. The dashboard reads only the protected file, so it can be shown in class without exposing the raw personal fields. One command reruns the pipeline for the demo.

#### Schedule

The course has two fixed milestones. Table 1.4 assigns the work to them.

**Table 1.4: Project schedule**

| Phase | Dates | Work | Deliverable |
|---|---|---|---|
| M1: Research definition and planning | 1 to 10 October 2026 | Problem analysis, review, design, dataset study | Report Chapters 1 and 2 |
| Implementation | October 2026 | Pipeline code, privacy layer, rules, evaluation, charts, Tableau workbook | Source code and outputs |
| M2: Final report, demo and presentation | 15 October to 5 November 2026 | Results, screenshots, final report, presentation, live demo | Report Chapters 3 to 5, Appendix A, presentation, code and data |

The schedule depends on the narrow scope: rules instead of machine learning, and k-anonymity instead of differential privacy.

## References

Reference numbers follow the consolidated list in Section 5.4.

[1] The Nilson Report, "Payment Card Fraud Losses Approach $34 Billion," press release, Jan. 6, 2025. [Online]. Available: https://www.fintechfutures.com/press-releases/payment-card-fraud-losses-approach-34-billion

[2] R. J. Bolton and D. J. Hand, "Statistical fraud detection: A review," *Statistical Science*, vol. 17, no. 3, pp. 235-249, 2002, doi: 10.1214/ss/1042727940.

[3] A. Dal Pozzolo, O. Caelen, Y.-A. Le Borgne, S. Waterschoot, and G. Bontempi, "Learned lessons in credit card fraud detection from a practitioner perspective," *Expert Systems with Applications*, vol. 41, no. 10, pp. 4915-4928, 2014, doi: 10.1016/j.eswa.2014.02.026.

[4] Y.-A. Le Borgne, W. Siblini, B. Lebichot, and G. Bontempi, *Reproducible Machine Learning for Credit Card Fraud Detection: Practical Handbook*. Brussels, Belgium: Université Libre de Bruxelles, 2022. [Online]. Available: https://fraud-detection-handbook.github.io/fraud-detection-handbook/Chapter_2_Background/FDS.html

[5] PCI Security Standards Council, "Securing the future of payments: PCI SSC publishes PCI Data Security Standard v4.0," press release, Mar. 31, 2022. [Online]. Available: https://www.pcisecuritystandards.org/about_us/press_releases/securing-the-future-of-payments-pci-ssc-publishes-pci-data-security-standard-v4-0/

[6] PCI Security Standards Council, "How can an entity meet PCI DSS requirements for PAN masking and truncation if it has migrated to 8-digit BINs?," FAQ 1492, Apr. 2024. [Online]. Available: https://www.pcisecuritystandards.org/faqs/1492/

[7] European Parliament and Council of the European Union, "Regulation (EU) 2016/679 (General Data Protection Regulation)," Art. 4(1) and Art. 4(5), Apr. 27, 2016. [Online]. Available: https://eur-lex.europa.eu/eli/reg/2016/679/oj

[8] E. McCallister, T. Grance, and K. Scarfone, "Guide to protecting the confidentiality of personally identifiable information (PII)," NIST Special Publication 800-122, Apr. 2010, doi: 10.6028/NIST.SP.800-122.

[9] S. Garfinkel, J. Near, A. Dajani, P. Singer, and B. Guttman, "De-identifying government datasets: Techniques and governance," NIST Special Publication 800-188, Sep. 2023, doi: 10.6028/NIST.SP.800-188.

[10] L. Sweeney, "k-anonymity: A model for protecting privacy," *International Journal of Uncertainty, Fuzziness and Knowledge-Based Systems*, vol. 10, no. 5, pp. 557-570, 2002, doi: 10.1142/S0218488502001648.

[11] A. Machanavajjhala, D. Kifer, J. Gehrke, and M. Venkitasubramaniam, "l-diversity: Privacy beyond k-anonymity," *ACM Transactions on Knowledge Discovery from Data*, vol. 1, no. 1, Art. 3, Mar. 2007, doi: 10.1145/1217299.1217302.

[12] C. Dwork, "Differential privacy," in *Automata, Languages and Programming (ICALP 2006)*, Lecture Notes in Computer Science, vol. 4052. Berlin, Germany: Springer, 2006, pp. 1-12, doi: 10.1007/11787006_1.

[13] B. Staniar, "Local file save with Tableau Desktop Public Edition," Tableau Blog, Apr. 30, 2024. [Online]. Available: https://www.tableau.com/en-gb/blog/local-file-save-tableau-desktop-public-edition

[14] Microsoft, "Download Power BI Desktop," Microsoft Learn. [Online]. Available: https://learn.microsoft.com/en-us/power-bi/fundamentals/desktop-get-the-desktop (accessed Oct. 8, 2026).

[15] Tableau, "Save workbooks to Tableau Public," Tableau Desktop Help. [Online]. Available: https://help.tableau.com/current/pro/desktop/en-us/publish_workbooks_tableaupublic.htm (accessed Oct. 8, 2026).

[16] K. Shenoy, "Credit Card Transactions Fraud Detection Dataset," Kaggle, 2020. [Online]. Available: https://www.kaggle.com/datasets/kartik2112/fraud-detection
