# CBCA293 Security and Privacy for Big Data Analytics, Bennett University
# Team: Rajat Sharma (S24BCAU0134), Ishan Chaudary (S24BCAU0002), Piyush Agarwal (S24BCAU0182), Suraj Tiwari (S24BCAU0136)
"""Step 2: the privacy layer.

Turns raw rows into protected rows. After this step there is no card number,
name, address, birth date or exact location left in the data.

Techniques used (see docs/01_project_understanding.md, section 2):
  * masking            card number -> "**** **** **** 2095"
  * pseudonymization   card number -> salted SHA-256 -> "C_3298fc2482"
  * generalization     birth date -> age band, state -> US region
  * suppression        name, street, city, zip, coordinates, job ... are deleted
  * k-anonymity check  every (age_band, gender, region) group has >= k customers
"""

import hashlib

import pandas as pd

import config


def mask_card(card_number: int) -> str:
    """Keep only the last 4 digits, like a printed receipt."""
    return "**** **** **** " + str(card_number)[-4:]


def pseudonymize(card_number: int, salt: str = config.SALT) -> str:
    """One-way, salted SHA-256 fingerprint of the card number.

    The same card always gives the same ID (so we can still group a customer's
    transactions), but the ID cannot be turned back into the card number.
    """
    digest = hashlib.sha256((salt + str(card_number)).encode("utf-8")).hexdigest()
    return "C_" + digest[:10]


def age_at_transaction(df: pd.DataFrame) -> pd.Series:
    """Whole years between birth date and transaction date."""
    return ((df["transaction_time"] - df["dob"]).dt.days // 365.25).astype(int)


def k_anonymity(df: pd.DataFrame, quasi_identifiers: list[str], k: int = config.K_ANONYMITY) -> dict:
    """Check k-anonymity: count distinct customers in every quasi-identifier group.

    A group smaller than k means the people in it are easy to single out.
    """
    sizes = df.groupby(quasi_identifiers, observed=True)["customer_id"].nunique()
    small = sizes[sizes < k]
    exposed = df.loc[df.set_index(quasi_identifiers).index.isin(small.index), "customer_id"].nunique()
    return {
        "quasi_identifiers": quasi_identifiers,
        "k": k,
        "groups": int(len(sizes)),
        "smallest_group": int(sizes.min()),
        "groups_below_k": int(len(small)),
        "customers_in_groups_below_k": int(exposed),
        "total_customers": int(df["customer_id"].nunique()),
        "result": "PASS" if sizes.min() >= k else "FAIL",
    }


def protect(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Apply every privacy technique. Returns (protected table, privacy report)."""
    df = pd.DataFrame(index=raw.index)
    df["transaction_time"] = raw["transaction_time"]
    df["hour"] = raw["transaction_time"].dt.hour
    df["dataset_split"] = raw["dataset_split"]

    # Hash/mask each of the ~1,000 distinct cards once, then map to all rows (fast).
    cards = pd.Series(raw["cc_num"].unique())
    customer_ids = dict(zip(cards, cards.map(pseudonymize)))
    masked = dict(zip(cards, cards.map(mask_card)))
    df["customer_id"] = raw["cc_num"].map(customer_ids)
    df["card_masked"] = raw["cc_num"].map(masked)

    df["merchant"] = raw["merchant"]
    df["category"] = raw["category"]
    df["amount"] = raw["amt"]
    df["gender"] = raw["gender"]

    age = age_at_transaction(raw)
    df["age_band"] = pd.cut(age, config.AGE_BINS, labels=config.AGE_LABELS)
    df["region"] = raw["state"].astype(str).map(config.STATE_TO_REGION)
    df["is_fraud"] = raw["is_fraud"]

    # Privacy report: k-anonymity BEFORE generalization (narrow ages + state)
    # and AFTER (wide age bands + region).
    before = pd.DataFrame({
        "customer_id": df["customer_id"],
        "age_band": pd.cut(age, config.NARROW_AGE_BINS, labels=config.NARROW_AGE_LABELS),
        "gender": df["gender"],
        "state": raw["state"],
    })
    first = raw.iloc[0]
    report = {
        "k_anonymity_before": k_anonymity(before, ["age_band", "gender", "state"]),
        "k_anonymity_after": k_anonymity(df, ["age_band", "gender", "region"]),
        "example_before": {
            "cc_num": str(first["cc_num"]), "name": f"{first['first']} {first['last']}",
            "dob": str(first["dob"].date()), "street": str(first["street"]),
            "city": str(first["city"]), "state": str(first["state"]), "zip": str(first["zip"]),
        },
        "example_after": {
            "card_masked": df.at[0, "card_masked"], "customer_id": df.at[0, "customer_id"],
            "age_band": str(df.at[0, "age_band"]), "region": df.at[0, "region"],
            "name / street / city / zip": "removed",
        },
        "columns_removed": ["cc_num", "first", "last", "dob", "street", "city", "state", "zip",
                            "lat", "long", "city_pop", "job", "merch_lat", "merch_long",
                            "trans_num", "unix_time"],
    }
    return df, report
