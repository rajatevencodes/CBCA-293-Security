# CBCA293 Security and Privacy for Big Data Analytics, Bennett University
# Team: Rajat Sharma (S24BCAU0134), Ishan Chaudary (S24BCAU0002), Piyush Agarwal (S24BCAU0182), Suraj Tiwari (S24BCAU0136)
"""Step 1: load the two Kaggle files, combine them, clean them, and profile them."""

import pandas as pd

import config

# Columns we read from the raw files (the unnamed row-number column is skipped).
RAW_COLUMNS = [
    "trans_date_trans_time", "cc_num", "merchant", "category", "amt", "first", "last",
    "gender", "street", "city", "state", "zip", "lat", "long", "city_pop", "job", "dob",
    "trans_num", "unix_time", "merch_lat", "merch_long", "is_fraud",
]
# Text columns with few distinct values are stored as "category" to save memory.
CATEGORY_COLUMNS = ["merchant", "category", "first", "last", "gender", "street",
                    "city", "state", "job", "dob"]


def load_raw() -> pd.DataFrame:
    """Read fraudTrain.csv and fraudTest.csv and stack them into one table.

    A new column `dataset_split` remembers which file each row came from.
    """
    parts = []
    for split, path in config.RAW_FILES.items():
        df = pd.read_csv(path, usecols=RAW_COLUMNS,
                         dtype={c: "category" for c in CATEGORY_COLUMNS})
        df["dataset_split"] = split
        parts.append(df)
    df = pd.concat(parts, ignore_index=True)

    # Clean-up: parse dates, and strip the simulator's "fraud_" merchant prefix
    # (every merchant has it, so it does NOT mean fraud).
    df["transaction_time"] = pd.to_datetime(df["trans_date_trans_time"])
    df["dob"] = pd.to_datetime(df["dob"].astype(str))
    df["merchant"] = df["merchant"].astype(str).str.removeprefix("fraud_")
    df["dataset_split"] = df["dataset_split"].astype("category")
    return df.drop(columns=["trans_date_trans_time"])


def profile(df: pd.DataFrame) -> dict:
    """Return the basic facts about the dataset (saved to outputs/data_profile.json)."""
    age = (df["transaction_time"] - df["dob"]).dt.days // 365.25
    facts = {
        "total_rows": len(df),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.drop(columns="dataset_split").duplicated().sum()),
        "duplicate_transaction_ids": int(df["trans_num"].duplicated().sum()),
        "fraud_rows": int(df["is_fraud"].sum()),
        "fraud_rate_pct": round(df["is_fraud"].mean() * 100, 2),
        "customers_cards": int(df["cc_num"].nunique()),
        "states": int(df["state"].nunique()),
        "categories": int(df["category"].nunique()),
        "merchants": int(df["merchant"].nunique()),
        "customer_age_min": int(age.min()),
        "customer_age_max": int(age.max()),
        "splits": {},
    }
    for split, part in df.groupby("dataset_split", observed=True):
        facts["splits"][split] = {
            "rows": len(part),
            "fraud_rows": int(part["is_fraud"].sum()),
            "fraud_rate_pct": round(part["is_fraud"].mean() * 100, 2),
            "first_transaction": str(part["transaction_time"].min()),
            "last_transaction": str(part["transaction_time"].max()),
        }
    return facts
