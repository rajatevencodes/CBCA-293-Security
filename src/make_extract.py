# CBCA293 Security and Privacy for Big Data Analytics, Bennett University
# Team: Rajat Sharma (S24BCAU0134), Ishan Chaudary (S24BCAU0002), Piyush Agarwal (S24BCAU0182), Suraj Tiwari (S24BCAU0136)
"""Turn the protected CSV into a Tableau extract (.hyper file).

Why: Tableau Public only opens and saves workbooks whose data is an extract,
not a live link to a CSV. This script writes the extract that
dashboard/fraud_dashboard.twb points to.

    pip install tableauhyperapi
    python src/make_extract.py

Input:  data/processed/transactions_protected.csv
Output: data/processed/transactions_protected.hyper  (schema "Extract", table "Extract",
        the same layout Tableau itself uses when it creates an extract)

The Tableau Hyper API has no build for Linux on ARM, so run this on a Mac,
Windows PC or an x86 Linux machine.
"""

import sys
from pathlib import Path

from tableauhyperapi import (Connection, CreateMode, HyperProcess, SqlType, TableDefinition,
                             TableName, Telemetry, escape_string_literal)

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "processed" / "transactions_protected.csv"
HYPER = ROOT / "data" / "processed" / "transactions_protected.hyper"

TEXT, BIG, REAL, TS = SqlType.text(), SqlType.big_int(), SqlType.double(), SqlType.timestamp()
COLUMNS = [  # same order and types as the CSV header
    ("transaction_time", TS), ("hour", BIG), ("dataset_split", TEXT), ("customer_id", TEXT),
    ("card_masked", TEXT), ("merchant", TEXT), ("category", TEXT), ("amount", REAL),
    ("gender", TEXT), ("age_band", TEXT), ("region", TEXT), ("rule_high_amount", BIG),
    ("rule_night", BIG), ("rule_risky_category", BIG), ("rule_above_usual", BIG),
    ("risk_score", BIG), ("flagged", BIG), ("is_fraud", BIG), ("outcome", TEXT),
]


def make_extract(csv_path: Path = CSV, hyper_path: Path = HYPER) -> int:
    """Write the .hyper file and return the number of rows loaded."""
    table = TableDefinition(TableName("Extract", "Extract"),
                            [TableDefinition.Column(name, sql_type) for name, sql_type in COLUMNS])
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
        with Connection(hyper.endpoint, str(hyper_path), CreateMode.CREATE_AND_REPLACE) as conn:
            conn.catalog.create_schema("Extract")
            conn.catalog.create_table(table)
            rows = conn.execute_command(
                f"COPY {table.table_name} FROM {escape_string_literal(str(csv_path))} "
                "WITH (format csv, header true, NULL '')")
    return rows


if __name__ == "__main__":
    csv_in = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV
    hyper_out = Path(sys.argv[2]) if len(sys.argv) > 2 else HYPER
    n = make_extract(csv_in, hyper_out)
    print(f"Wrote {hyper_out.name}: {n:,} rows")
