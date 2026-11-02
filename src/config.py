# CBCA293 Security and Privacy for Big Data Analytics, Bennett University
# Team: Rajat Sharma (S24BCAU0134), Ishan Chaudary (S24BCAU0002), Piyush Agarwal (S24BCAU0182), Suraj Tiwari (S24BCAU0136)
"""All settings in one place.

If you want to change a path, the salt or a rule setting, change it HERE.
Every other file imports its settings from this module.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Folders and files
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent  # the project folder

RAW_FILES = {  # dataset_split name -> raw Kaggle file
    "train": ROOT / "data" / "raw" / "fraudTrain.csv",
    "test": ROOT / "data" / "raw" / "fraudTest.csv",
}
PROCESSED_CSV = ROOT / "data" / "processed" / "transactions_protected.csv"
OUTPUT_DIR = ROOT / "outputs"
CHARTS_DIR = OUTPUT_DIR / "charts"
DASHBOARD_TWB = ROOT / "dashboard" / "fraud_dashboard.twb"

# ---------------------------------------------------------------------------
# Privacy settings
# ---------------------------------------------------------------------------
# Secret "salt" added before hashing a card number. Without it, an attacker could
# hash every possible card number and match the results. In a real company this
# would live in a secrets vault, never in code. It is here so results repeat.
SALT = "cbca293-demo-salt"

K_ANONYMITY = 5  # every (age_band, gender, region) group needs >= 5 customers

# Final (safe) age bands. Bin edges are inclusive on the right: 0-24 -> "<25".
AGE_BINS = [0, 24, 39, 54, 69, 200]
AGE_LABELS = ["<25", "25-39", "40-54", "55-69", "70+"]

# Narrow age bands, used ONLY for the "before" k-anonymity check (it fails).
NARROW_AGE_BINS = [0, 17, 25, 35, 45, 55, 65, 200]
NARROW_AGE_LABELS = ["<18", "18-25", "26-35", "36-45", "46-55", "56-65", "66+"]

# US Census Bureau regions: state code -> region.
REGIONS = {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}
STATE_TO_REGION = {s: region for region, states in REGIONS.items() for s in states.split()}

# ---------------------------------------------------------------------------
# Fraud rule settings (the limits themselves are LEARNED from the train file)
# ---------------------------------------------------------------------------
HIGH_AMOUNT_PERCENTILE = 0.99  # R1: above the 99th percentile of the category
RISK_FACTOR = 2.0              # R2/R3: an hour or category is "risky" if its fraud rate >= 2x overall
ABOVE_USUAL_FACTOR = 5.0       # R4: amount >= 5x the customer's median spend
SCORE_THRESHOLDS = [1, 2, 3, 4]  # flagged if risk_score >= threshold (best one picked on train)
