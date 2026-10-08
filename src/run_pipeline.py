"""Run the whole project, start to finish:

    uv run python src/run_pipeline.py

Step 1 load -> 2 privacy -> 3 rules -> 4 evaluate -> 5 charts -> 6 Tableau workbook
"""

import argparse
import json
import time
from pathlib import Path

import config
import build_dashboard
import fraud_rules
import load_data
import make_charts
import privacy


def save_json(data: dict, name: str) -> None:
    path = config.OUTPUT_DIR / name
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"   saved {path.relative_to(config.ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fraud + privacy pipeline.")
    parser.add_argument("--tableau-data-dir", type=Path, default=None,
                        help="Folder path Tableau should use for the CSV (only needed if you "
                             "run this somewhere other than the computer that runs Tableau).")
    args = parser.parse_args()
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.PROCESSED_CSV.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()

    print("[1/6] Loading raw Kaggle files ...")
    raw = load_data.load_raw()
    facts = load_data.profile(raw)
    print(f"   {facts['total_rows']:,} rows, {facts['fraud_rows']:,} fraud ({facts['fraud_rate_pct']}%)")
    save_json(facts, "data_profile.json")

    print("[2/6] Privacy layer: mask, hash, generalize, suppress ...")
    df, privacy_report = privacy.protect(raw)
    del raw  # the raw data is not used after this point
    for when in ("before", "after"):
        k = privacy_report[f"k_anonymity_{when}"]
        print(f"   k-anonymity {when}: {k['result']} (smallest group {k['smallest_group']}, "
              f"{k['customers_in_groups_below_k']} customers in groups < {k['k']})")
    save_json(privacy_report, "privacy_report.json")

    print("[3/6] Learning rule limits from the TRAIN file ...")
    train_mask = df["dataset_split"] == "train"
    limits = fraud_rules.learn_limits(df[train_mask])
    df = fraud_rules.apply_rules(df, limits)
    tuning, threshold = fraud_rules.tune_threshold(df[train_mask])
    tuning.to_csv(config.OUTPUT_DIR / "rule_tuning.csv", index=False)
    print(f"   night hours {limits.night_hours}, risky categories {limits.risky_categories}")
    print(f"   best threshold on train: risk_score >= {threshold}")

    print("[4/6] Evaluating on the unseen TEST file ...")
    metrics = fraud_rules.evaluate(df[~train_mask], threshold)
    c = metrics["combined"]
    print(f"   precision {c['precision']:.1%}, recall {c['recall']:.1%}, F1 {c['f1']:.3f}")
    save_json({"threshold": threshold, "night_hours": limits.night_hours,
               "risky_categories": limits.risky_categories,
               "overall_train_fraud_rate": round(limits.overall_fraud_rate, 6),
               "test": metrics}, "metrics.json")
    df = fraud_rules.add_decision(df, threshold)

    print("[5/6] Drawing report charts ...")
    make_charts.make_all(df, limits, metrics, privacy_report)
    print(f"   saved {config.CHARTS_DIR.relative_to(config.ROOT)}/*.png")

    print("[6/6] Writing protected CSV and Tableau workbook ...")
    columns = ["transaction_time", "hour", "dataset_split", "customer_id", "card_masked",
               "merchant", "category", "amount", "gender", "age_band", "region",
               *fraud_rules.RULE_COLUMNS, "risk_score", "flagged", "is_fraud", "outcome"]
    df[columns].to_csv(config.PROCESSED_CSV, index=False, float_format="%.2f",
                       date_format="%Y-%m-%d %H:%M:%S")
    print(f"   saved {config.PROCESSED_CSV.relative_to(config.ROOT)}")
    build_dashboard.build(config.PROCESSED_CSV, config.DASHBOARD_TWB, args.tableau_data_dir)
    print(f"   saved {config.DASHBOARD_TWB.relative_to(config.ROOT)}")

    print(f"Done in {time.time() - start:.0f} seconds.")


if __name__ == "__main__":
    main()
