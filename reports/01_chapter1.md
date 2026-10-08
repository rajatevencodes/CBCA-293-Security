# Chapter 1. Problem Analysis Introduction

## 1.1 Background of the Study

Credit and debit cards are one of the most common ways to pay, in shops and online. Every payment creates a transaction record, and a large bank produces millions of them each day. Card data is therefore a clear example of big data: large in volume, arriving continuously, and needing quick analysis.

Card fraud is costly. According to The Nilson Report, card fraud losses worldwide reached $33.83 billion in 2023, or 6.58 cents for every $100 of total card volume [1]. Fraud also costs customers time and trust.

Bolton and Hand describe fraud detection as the task of identifying fraud as quickly as possible once it has been committed, as opposed to fraud prevention, which tries to stop it from happening at all [2]. Detection is usually done by analysing transaction data and looking for unusual patterns, such as very large amounts, payments at unusual times, or spending that does not match the customer's normal behaviour.

Fraud detection has two well-known difficulties. First, fraud is rare. In the dataset used in this project, only 0.52% of 1,852,394 transactions are fraud. This is called class imbalance, and it makes simple measures such as accuracy misleading [3]. Second, fraud patterns change over time, so a method that is tuned on old data must be checked on newer data [3].

At the same time, transaction data is full of personal information. A single record can hold a person's name, home address, date of birth, job and full card number. Under the European Union's General Data Protection Regulation (GDPR), any information relating to an identified or identifiable person is "personal data" [7]. The US National Institute of Standards and Technology (NIST) calls the same kind of data personally identifiable information (PII) and advises organisations to minimise its use, collection and retention [8]. The card industry has its own rules: the Payment Card Industry Data Security Standard (PCI DSS) limits how much of a card number may be shown on screens and in reports [5], [6].

This creates a tension. Fraud analysts and dashboard users need to see patterns, but they do not need to know who each customer is, and every extra copy of raw data is another place where it can leak. This project shows how both needs can be met: Python processes the data, a privacy layer protects it, and only then is it analysed and shown in a Tableau dashboard.

## 1.2 Problem Statement

Card transaction data is needed to detect and explain fraud, but it also contains names, addresses, dates of birth and full card numbers. Sharing it as it is with analysts or a BI tool exposes this personal data. Removing columns without a plan can either leave people identifiable (for example, through a rare combination of age and state) or remove the information needed to find fraud.

The problem this project addresses is therefore:

> *How can a large set of credit card transactions be protected so that no individual can be identified, and still be used to detect fraud with simple, explainable rules and to present the results in an interactive Tableau dashboard, with both the privacy level and the detection quality measured rather than assumed?*

This breaks down into four smaller questions:

1. Which columns are direct identifiers, which are quasi-identifiers, and how should each be treated (masked, hashed, generalized or deleted)?
2. How can we prove that the protected data meets a stated privacy level, such as k-anonymity with k = 5?
3. Can a small set of readable rules, learned only from older data, find fraud in newer data that the rules have never seen, and how well?
4. How can the protected results be shown in a dashboard that tells a clear story without ever loading the raw data?

## 1.3 Objectives

Each objective has a target that can be checked and an output that shows whether it was met. Results are reported in Chapter 4.

1. **Load and profile the data.** Load both source files (1,296,675 + 555,719 = 1,852,394 rows), confirm the number of missing values and duplicate rows, and save the dataset facts to `outputs/data_profile.json`.
2. **Remove direct identifiers.** The file given to Tableau must contain no names, street address, city, ZIP code, coordinates, job, date of birth or full card number. Of the 23 raw columns, 13 personal or linkable columns are deleted, the row-number column is dropped, and the card number, date of birth and state are transformed.
3. **Mask and pseudonymize the card number.** Show at most the last 4 digits of any card (stricter than the PCI DSS limit of the BIN plus the last 4 digits [6]), and replace the card number with a salted SHA-256 pseudonym so that each customer can still be followed across transactions.
4. **Achieve k-anonymity with k ≥ 5** on the quasi-identifiers (age band, gender, region): every combination must contain at least 5 distinct customers. The check runs automatically on a detailed version (state, 7 age bands) and on the final version (region, 5 age bands), and both results are saved to `outputs/privacy_report.json`.
5. **Build four explainable fraud rules** (high amount, night time, risky category, above usual spend) whose limits are learned from `fraudTrain.csv` only, combine them into a risk score from 0 to 4, and pick the score threshold with the best F1 score on the training data (saved to `outputs/rule_tuning.csv`).
6. **Evaluate the rules on unseen data.** Apply the frozen rules to `fraudTest.csv` (555,719 rows) and report precision, recall, F1, accuracy and a confusion matrix for each rule and for the combined score (`outputs/metrics.json`), compared with a "flag nothing" baseline.
7. **Build an interactive Tableau dashboard** on the protected file only, with at least 6 KPIs, at least 6 charts and at least 5 filters. The planned design has 6 KPIs, 6 charts and 6 filters.
8. **Make the work reproducible.** The whole pipeline, from raw CSV files to the Tableau workbook, runs from one command and gives the same outputs every time.

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

* **Machine learning models.** Only rules are used, so every decision can be explained in plain words. Machine learning is reviewed in Section 1.5 for comparison.
* **Real customer data.** The dataset is simulated, so no real person is involved.
* **Real-time or streaming detection.** The pipeline works in batch mode on files.
* **Advanced privacy models** such as l-diversity and differential privacy. They are reviewed in Section 1.5 and noted as future work.
* **Infrastructure security** such as encryption at rest, access control and big data platforms (Hadoop, Spark, Kerberos, Ranger), which belong to other course tracks.
* **Publishing the dashboard on the Tableau Public website**, where anything published is visible to everyone [15]. The workbook is kept locally.

## 1.5 Review of Existing Systems

This section reviews the three areas the project combines: fraud detection methods, privacy techniques and business intelligence (BI) tools. It ends with a comparison, the identified gap and a feasibility analysis.

### 1.5.1 Fraud Detection Approaches

**Rule-based (expert-driven) systems.** The oldest and simplest approach is a set of "if-then" rules written by fraud experts, for example "if the amount is very large and the card is used at night, raise an alert". Le Borgne et al. describe how a real fraud detection system has several layers [4]. After basic checks at the payment terminal, *blocking rules* stop clearly fraudulent payments in real time, and *scoring rules* give each accepted transaction a fraud score. Rules are fast and easy to explain. Their weaknesses are that they only catch fraud patterns that experts already know, different experts may write different rules, and a large rule set is hard to maintain [4].

**Machine learning (data-driven) systems.** Here a model, such as a decision tree, random forest or neural network, is trained on past transactions that are labelled as fraud or genuine. The model learns the patterns by itself and gives each new transaction a fraud probability. Bolton and Hand review the statistical and machine learning tools used for fraud detection, including supervised methods (which learn from labelled examples) and unsupervised methods (which look for unusual behaviour without labels) [2]. Machine learning can find complex patterns that experts may miss, but its decisions are harder to explain and it needs careful handling of class imbalance and changing fraud patterns [3], [4].

**Hybrid systems used in industry.** In practice, banks use both. Le Borgne et al. describe a system in which expert rules and a data-driven model run side by side, and human investigators review the alerts [4]. Because investigators can check only a limited number of alerts each day, the alerts must be precise. Dal Pozzolo et al., working with real data from an industry partner, add that a fraud model must handle class imbalance and changing fraud patterns, and be measured in a way that fits the investigators' limited time [3].

**What this project takes from the review.** The project builds a small version of the *scoring rules* layer, because rules are explainable and every decision about a customer is easy to justify. Unlike hand-written expert rules, the limits (for example, what counts as a "high amount") are learned from training data, and the rules are tested on later data they have never seen [3].

### 1.5.2 Privacy Protection Techniques

**Direct identifiers and quasi-identifiers.** A *direct identifier* points to one person on its own, such as a name or a full card number. A *quasi-identifier* does not identify anyone alone, but a combination of them can. For example, age, gender and state together may match only one person in a dataset. NIST lists removing direct identifiers and transforming quasi-identifiers as two of the main de-identification methods [9].

**Masking.** Masking hides part of a value when it is displayed. PCI DSS v4.0 was published by the PCI Security Standards Council in March 2022 [5]. Its Requirement 3.4.1 says that the card number (Primary Account Number, PAN) must be masked when displayed, so that no more than the BIN (the first digits, which identify the issuer) and the last four digits are shown, unless there is a documented business need [6]. Masking is simple and familiar ("card ending 2095"), but it does not let an analyst follow one customer, because many cards share the same last four digits.

**Pseudonymization (hashing).** GDPR Article 4(5) defines pseudonymisation as processing personal data so that it "can no longer be attributed to a specific data subject without the use of additional information", where that additional information is kept separately and protected [7]. A common way to do this is to replace an identifier with its cryptographic hash, for example SHA-256. A hash is one-way: the original value cannot be calculated back from it. However, if the set of possible inputs is small or structured, as with card numbers, an attacker can hash many possible values and compare. Adding a secret value called a *salt* before hashing prevents this, because the attacker does not know the salt. The salt is the "additional information" that must be kept separately.

**Generalization and suppression.** Generalization replaces an exact value with a broader one, for example a date of birth with an age band, or a state with a region. Suppression deletes a value or a whole column. Both reduce the detail in the data so that people are harder to single out [9].

**k-anonymity.** Sweeney proposed k-anonymity as a formal privacy model [10]. A released table is k-anonymous if every person in it cannot be distinguished from at least k − 1 other people on the quasi-identifiers. For example, with k = 5, every combination of age band, gender and region must cover at least 5 people. k-anonymity is easy to understand and easy to check, which is why it is used in this project. Its known weakness is that if all people in a group share the same sensitive value, an attacker still learns that value [11].

**l-diversity.** Machanavajjhala et al. showed two attacks on k-anonymity: the *homogeneity attack*, where everyone in a group has the same sensitive value, and the *background knowledge attack*, where the attacker uses outside information [11]. They proposed l-diversity, which requires each group to contain at least l "well-represented" values of the sensitive attribute [11].

**Differential privacy.** Dwork introduced differential privacy, a mathematical guarantee that the result of an analysis changes very little whether or not any one person's data is included [12]. It is usually achieved by adding carefully measured random noise. It is the strongest guarantee reviewed here, but the noise reduces accuracy and it is harder to apply to row-level dashboard data.

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

### 1.5.3 Business Intelligence Tools

The course allows Microsoft Power BI or Tableau. Both support charts, filters, slicers and KPIs, so the choice was made on practical grounds (Table 1.2).

**Table 1.2: Comparison of BI tools for this project**

| Point | Microsoft Power BI Desktop | Tableau Desktop Public Edition |
|---|---|---|
| Cost | Free desktop app | Free desktop app |
| Operating system | Windows 10 or later only [14] | Windows and macOS |
| Saving work locally | Yes | Yes, since April 2024 [13] |
| Private data | Supported | Supported when saved locally [15] |
| Fit for this project (Apple Silicon Mac) | Not possible without a Windows machine | Runs natively |

Power BI Desktop requires Windows [14], while the project laptop is an Apple Silicon Mac. Tableau Desktop Public Edition is free and, since April 2024, can save workbooks locally and work offline [13]. Tableau's documentation notes that workbooks published to a Tableau Public profile "are not private and are freely accessible to anyone" [15]. For a privacy project this matters: the dashboard is kept local and reads only the protected file.

### 1.5.4 Comparison and Identified Gap

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

**Identified gap.** The reviewed work treats fraud detection, privacy protection and visual analytics mostly as separate problems. Fraud detection studies focus on detection quality [2]-[4], privacy models focus on how to release data safely [10]-[12], and BI tools focus on showing data. A simple, end-to-end pipeline that (a) protects the data first and *measures* the privacy level, (b) detects fraud with rules that a non-expert can read, (c) tests those rules honestly on later data, and (d) shows everything in a dashboard that never touches raw personal data, is not commonly available at a scale a student or a small team can build and explain. This project aims to fill that gap at teaching scale.

### 1.5.5 Feasibility Analysis

**Technical feasibility.** The two raw files together are about 502 MB (351 MB and 150 MB) with 1,852,394 rows. This fits in the memory of a modern laptop and can be processed with pandas without a cluster. All techniques used (SHA-256 hashing, grouping, percentiles, medians, counting) are standard features of Python and its libraries, and Tableau Desktop Public Edition runs natively on macOS. The data has no missing values or duplicate rows, so little cleaning is needed.

**Economic feasibility.** The project has no direct cost. Python, uv, pandas, NumPy and Matplotlib are free and open source. Tableau Desktop Public Edition is free [13]. The dataset is free and is released under the CC0 (public domain) licence on Kaggle [16]. The only resources used are a laptop the student already owns and student time.

**Operational feasibility.** The rules are written in plain language (for example "the amount is at least 5 times the customer's usual spend"), so anyone can understand why a transaction was flagged. Dashboard filters (date, category, region, age band, gender, dataset split) let users explore without writing code. Because the dashboard reads only the protected file, it can be shown in class without exposing personal data, and the one-command pipeline can be re-run during the demo.

**Schedule feasibility.** The course fixes two milestones. Table 1.4 shows how the work fits into them.

**Table 1.4: Project schedule**

| Phase | Dates | Work | Deliverable |
|---|---|---|---|
| M1: Research definition and planning | 1 to 10 October 2026 | Problem analysis, review, design, dataset study | Report Chapters 1 and 2 |
| Implementation | October 2026 | Pipeline code, privacy layer, rules, evaluation, charts, Tableau workbook | Source code and outputs |
| M2: Final report, demo and presentation | 15 October to 5 November 2026 | Results, screenshots, final report, presentation, live demo | Report Chapters 3 to 5, Appendix A, presentation, code and data |

The scope is kept small on purpose (rules instead of machine learning, k-anonymity instead of differential privacy) so the work can be finished and tested on time.

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
