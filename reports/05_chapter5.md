# Chapter 5. Conclusion

## 5.1 Conclusion

The Python pipeline processed 1,852,394 simulated card transactions. It masked and pseudonymized card numbers, generalized dates of birth and states, and removed the remaining personal fields. The released data passed a k-anonymity check with k = 5. Four readable rules scored suspicious transactions, and the generated Tableau workbook reads only the protected file.

The detailed privacy design did not pass. With exact states and narrow age bands, 659 of 999 customers were in groups smaller than 5. After generalization to 4 regions and 5 age bands, every group contained at least 5 customers.

The combined rules were learned from the training file only. On the later test file they caught 57.1% of fraud at 34.1% precision, with F1 0.427. The best single rule reached F1 0.179.

Accuracy hid the failure of the baseline. Flagging nothing scored 99.61% accuracy and caught no fraud.

None of the four rules uses names, addresses, exact ages or states. Generalizing or removing those fields did not change the rule inputs.

Table 5.1 checks each objective from Section 1.3 against the measured result.

**Table 5.1: Objectives and results**

| No. | Objective (Section 1.3) | Measured result | Status |
|---|---|---|---|
| 1 | Load and profile both files (1,852,394 rows), confirm missing values and duplicates, save `data_profile.json` | 1,852,394 rows loaded; 0 missing values; 0 duplicate rows; 0 duplicate transaction IDs; profile saved | Met |
| 2 | No direct identifiers in the file given to Tableau | Protected CSV has 19 columns with no name, address, coordinates, job, date of birth or full card number; 13 columns suppressed, 3 transformed | Met |
| 3 | Show at most the last 4 digits; replace the card number with a salted SHA-256 pseudonym | `**** **** **** 2095` and `C_3298fc2482` for the first record; 999 cards each mapped to one pseudonym | Met |
| 4 | k-anonymity with k ≥ 5 on (age band, gender, region), before and after checks saved | Before: FAIL, smallest group 1, 659 customers exposed. After: PASS, smallest group 5, 0 customers exposed | Met |
| 5 | Four rules learned from train only; threshold with best train F1 saved | 4 rules implemented; best threshold risk_score ≥ 3 (train F1 0.4666); `rule_tuning.csv` saved | Met |
| 6 | Evaluate on the 555,719 unseen test rows with precision, recall, F1, accuracy, confusion matrix, and a flag-nothing baseline | Combined: precision 34.08%, recall 57.06%, F1 0.4267, accuracy 99.41%; TP 1,224, FP 2,368, FN 921, TN 551,206; baseline accuracy 99.61% with 0% recall | Met |
| 7 | Tableau dashboard on the protected file with ≥ 6 KPIs, ≥ 6 charts, ≥ 5 filters | 6 KPIs, 6 charts, 6 shared filters; workbook passed `validate()` (12 worksheets, 6 calculated fields) | Met in code; <!-- VERIFY: change to "Met" after the workbook is opened in Tableau and screenshots 3.7 and 3.8 are captured --> pending a visual check in Tableau |
| 8 | Whole pipeline runs from one command and repeats its outputs | `uv run python src/run_pipeline.py` runs all 6 steps in about 2 minutes; no step uses random numbers and the salt is fixed | Met |

Seven of the eight objectives are fully met and measured. The dashboard meets its structural target in code, but its visual check in Tableau and the screenshots in Figures 3.7 and 3.8 are still pending.

## 5.2 Limitations

1. Sparkov generated the dataset [16], [23]. Real fraud is more varied and changes over time [3], so the measured precision and recall do not predict performance at a bank.
2. The four rules catch patterns like the ones learned. They miss 921 test frauds that do not combine three warning signs. Machine learning models may find more complex patterns [2], [4], though their decisions are harder to explain.
3. The test run raises about 2 false alarms for every fraud caught, 2,368 against 1,224. Each alert would use investigator time in a bank [4].
4. k-anonymity guarantees group size, not protection from attribute disclosure. If all 5 customers in a group share a sensitive value, an attacker learns it. Outside knowledge may also narrow the group [11]. The pipeline does not test l-diversity.
5. The selected quasi-identifiers are age band, gender and region. Merchant, exact transaction time and amount remain in the file. An attacker who knows some purchases could use those fields too.
6. `src/config.py` contains the salt so repeated runs produce the same output. Anyone with the code and card numbers can rebuild the pseudonyms. A real deployment would store the salt in a secrets vault and keep it apart from the data [7].
7. A workbook published to a Tableau Public profile is available to anyone [15]. This workbook must use only the protected CSV and remain local or move through a private channel.
8. The pipeline processes files rather than a live payment stream, and it learns the rule limits once. A deployed system would need to update them as fraud patterns change [3].
9. The `.twb` file stores the CSV folder as an absolute path. Another computer must rebuild it with `--tableau-data-dir`.

## 5.3 Further work

1. Check l-diversity [11] for the fraud label within each group, and test differential privacy [12] for aggregate dashboard KPIs.
2. Train a decision tree or random forest on the protected features and compare it with the rules. Industry systems often combine rules and models [4].
3. Choose the threshold from the estimated money saved and the cost of reviewing alerts, not F1 alone [3].
4. Read the salt from an environment variable or secrets manager instead of source code.
5. Test frequency rules, such as several payments from one card within a short period.
6. Apply the rules to a transaction stream with a tool such as Apache Spark.
7. Add unit tests for functions including `mask_card()`, `pseudonymize()` and `k_anonymity()`.

## 5.4 References

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

[17] National Institute of Standards and Technology, "Secure Hash Standard (SHS)," FIPS PUB 180-4, Aug. 2015, doi: 10.6028/NIST.FIPS.180-4.

[18] Python Software Foundation, "hashlib: Secure hashes and message digests," Python Documentation. [Online]. Available: https://docs.python.org/3/library/hashlib.html (accessed Oct. 8, 2026).

[19] National Center for Health Statistics, "Geographic division or region," Health, United States, Centers for Disease Control and Prevention. [Online]. Available: https://www.cdc.gov/nchs/hus/sources-definitions/geographic-region.htm (accessed Oct. 8, 2026).

[20] T. Saito and M. Rehmsmeier, "The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets," *PLOS ONE*, vol. 10, no. 3, Art. e0118432, 2015, doi: 10.1371/journal.pone.0118432.

[21] Astral, "uv: An extremely fast Python package and project manager," Documentation. [Online]. Available: https://docs.astral.sh/uv/ (accessed Oct. 8, 2026).

[22] pandas development team, "pandas documentation." [Online]. Available: https://pandas.pydata.org/docs/ (accessed Oct. 8, 2026).

[23] B. Harris, "Sparkov_Data_Generation," GitHub repository. [Online]. Available: https://github.com/namebrandon/Sparkov_Data_Generation (accessed Oct. 8, 2026).

[24] Python Software Foundation, "xml.etree.ElementTree: The ElementTree XML API," Python Documentation. [Online]. Available: https://docs.python.org/3/library/xml.etree.elementtree.html (accessed Oct. 8, 2026).

[25] Matplotlib development team, "Matplotlib documentation." [Online]. Available: https://matplotlib.org/stable/ (accessed Oct. 8, 2026).

[26] NumPy developers, "NumPy documentation." [Online]. Available: https://numpy.org/doc/stable/ (accessed Oct. 8, 2026).
