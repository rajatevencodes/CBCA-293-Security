# CBCA293 Security and Privacy for Big Data Analytics, Bennett University
# Team: Rajat Sharma (S24BCAU0134), Ishan Chaudary (S24BCAU0002), Piyush Agarwal (S24BCAU0182), Suraj Tiwari (S24BCAU0136)
"""Steps 3 and 4: the fraud rule engine and its evaluation.

Every limit is LEARNED from the train file only. The rules are then judged on
the test file, which they never saw. This is an honest test.

  R1 High amount      amount > 99th percentile of its category
  R2 Night time       the hour has a fraud rate >= 2x the overall rate
  R3 Risky category   the category has a fraud rate >= 2x the overall rate
  R4 Above usual      amount >= 5x this customer's median spend

risk_score = number of rules fired (0 to 4). flagged = 1 if risk_score >= threshold,
where threshold is the value with the best F1 score on the train file.
"""

from dataclasses import dataclass

import pandas as pd

import config

RULE_COLUMNS = ["rule_high_amount", "rule_night", "rule_risky_category", "rule_above_usual"]


@dataclass
class RuleLimits:
    """Everything the rules learned from the train file."""
    overall_fraud_rate: float
    category_p99: dict          # category -> 99th percentile amount
    night_hours: list           # hours with high fraud rate
    risky_categories: list      # categories with high fraud rate
    customer_median: dict       # customer_id -> median amount
    category_median: dict       # category -> median amount (for unseen customers)


def learn_limits(train: pd.DataFrame) -> RuleLimits:
    """Learn the rule limits from the train rows."""
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


def apply_rules(df: pd.DataFrame, limits: RuleLimits) -> pd.DataFrame:
    """Add the 4 rule columns (0/1) and risk_score to the table."""
    category = df["category"].astype(str)
    usual = df["customer_id"].map(limits.customer_median).fillna(category.map(limits.category_median))
    df["rule_high_amount"] = (df["amount"] > category.map(limits.category_p99)).astype(int)
    df["rule_night"] = df["hour"].isin(limits.night_hours).astype(int)
    df["rule_risky_category"] = category.isin(limits.risky_categories).astype(int)
    df["rule_above_usual"] = (df["amount"] >= config.ABOVE_USUAL_FACTOR * usual).astype(int)
    df["risk_score"] = df[RULE_COLUMNS].sum(axis=1)
    return df


def score(predicted: pd.Series, actual: pd.Series) -> dict:
    """Confusion matrix + precision, recall, F1 and accuracy."""
    p, a = predicted.astype(bool), actual.astype(bool)
    tp, fp = int((p & a).sum()), int((p & ~a).sum())
    fn, tn = int((~p & a).sum()), int((~p & ~a).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "flagged": tp + fp, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(f1, 4), "accuracy": round((tp + tn) / len(a), 4),
    }


def tune_threshold(train: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Try each risk_score threshold on train; return the table and the best (highest F1)."""
    rows = [{"threshold": t, **score(train["risk_score"] >= t, train["is_fraud"])}
            for t in config.SCORE_THRESHOLDS]
    table = pd.DataFrame(rows)
    best = int(table.loc[table["f1"].idxmax(), "threshold"])
    return table, best


def evaluate(test: pd.DataFrame, threshold: int) -> dict:
    """Score every rule alone and the combined decision on the test rows."""
    results = {rule: score(test[rule], test["is_fraud"]) for rule in RULE_COLUMNS}
    results["combined"] = score(test["risk_score"] >= threshold, test["is_fraud"])
    results["flag_nothing_baseline"] = score(test["risk_score"] > 99, test["is_fraud"])
    return results


def add_decision(df: pd.DataFrame, threshold: int) -> pd.DataFrame:
    """Add `flagged` (0/1) and a readable `outcome` label for the dashboard."""
    df["flagged"] = (df["risk_score"] >= threshold).astype(int)
    fraud, flag = df["is_fraud"] == 1, df["flagged"] == 1
    df["outcome"] = "Correctly passed"
    df.loc[flag & fraud, "outcome"] = "Caught"
    df.loc[~flag & fraud, "outcome"] = "Missed"
    df.loc[flag & ~fraud, "outcome"] = "False alarm"
    return df
