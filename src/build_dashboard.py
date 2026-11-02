# CBCA293 Security and Privacy for Big Data Analytics, Bennett University
# Team: Rajat Sharma (S24BCAU0134), Ishan Chaudary (S24BCAU0002), Piyush Agarwal (S24BCAU0182), Suraj Tiwari (S24BCAU0136)
"""Step 6: write the Tableau workbook (``.twb`` and packaged ``.twbx``) as code.

What this script does
---------------------
A Tableau workbook (``.twb``) is just an XML text file. Tableau Desktop reads
it and draws the worksheets and dashboards it describes. This script builds that
XML with Python's standard library (``xml.etree.ElementTree``) so the whole
"Fraud & Privacy Dashboard" can be rebuilt at any time with one command::

    uv run python src/build_dashboard.py

The workbook connects to ``data/processed/transactions_protected.csv`` (the
privacy-protected file written by the pipeline) through its Tableau extract
``transactions_protected.hyper`` (written by ``make_extract.py``), because
Tableau Public only opens workbooks that use an extract. It also writes
``dashboard/fraud_dashboard.twbx``: one packaged file with the dashboard and the
extract inside. Tableau never sees the raw data.

How a .twb is organised (top to bottom)
---------------------------------------
``<workbook>``
    ``<document-format-change-manifest>``  which XML "dialect" features we use
    ``<datasources>``     the CSV connection, its columns and our calculated fields
    ``<shared-views>``    filters that apply to ALL worksheets using the data source
    ``<worksheets>``      one ``<worksheet>`` per KPI tile or chart
    ``<dashboards>``      the dashboard layout (zones = boxes on the page)
    ``<windows>``         which tabs exist in Tableau and which one is open

Field references look like ``[federated.xxx].[sum:is_fraud:qk]``:
``federated.xxx`` is the data source name, ``sum`` is the aggregation
(derivation), ``is_fraud`` the column and ``qk`` means "quantitative"
(continuous). ``nk`` means nominal (discrete) and ``ok`` ordinal (discrete,
ordered). These references are called *column instances*.

The XML structure mirrors real workbooks saved by Tableau 2023 to 2025
(single CSV text connection, ``textscan`` class).
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = PROJECT_ROOT / "data" / "processed" / "transactions_protected.csv"
DEFAULT_TWB = PROJECT_ROOT / "dashboard" / "fraud_dashboard.twb"

DASHBOARD_NAME = "Fraud & Privacy Dashboard"
DASHBOARD_WIDTH = 1265   # pixels (fixed size): fits a 13-inch MacBook screen in
DASHBOARD_HEIGHT = 760   # Tableau's Presentation Mode without scrolling

# Namespace Tableau uses for "user interface" attributes such as user:ui-marker.
USER_NS = "http://www.tableausoftware.com/xml/user"
ET.register_namespace("user", USER_NS)

# The workbook says which Tableau build wrote it. We claim an older 2023.2
# build so that any newer Tableau (2024/2025) opens it without complaint.
SOURCE_BUILD = "2023.2.0 (20232.23.0611.2007)"
BUILD_COMMENT = "<!-- build 20232.23.0611.2007                               -->"
XML_VERSION = "18.1"

# Internal names. Tableau generates random ones like these; any stable string
# of the same shape works. 'federated.' + 28 characters is the data source,
# 'textscan.' + 28 characters is the CSV connection inside it.
DS = "federated.0cbca293fraud0privacy0dash01"
CONNECTION = "textscan.1cbca293protected0csv0conn01"
# Tableau 2020.2+ gives every table an object id: '<file name>_<32 hex digits>'.
OBJECT_ID_SUFFIX = "5F1C0A2E9B8D4C3AA6E7B1D2C3F4A5B6"

# The CSV schema (docs/01_project_understanding.md, section 4), in file order.
# (column name, Tableau datatype, role, type, caption, default number format)
#   role: 'dimension' (things you group by) or 'measure' (things you add up)
#   type: 'nominal' (unordered labels), 'ordinal' (ordered), 'quantitative'
CSV_COLUMNS: list[tuple[str, str, str, str, str, str | None]] = [
    ("transaction_time", "datetime", "dimension", "ordinal", "Transaction Time", None),
    ("hour", "integer", "dimension", "ordinal", "Hour", None),
    ("dataset_split", "string", "dimension", "nominal", "Dataset Split", None),
    ("customer_id", "string", "dimension", "nominal", "Customer ID", None),
    ("card_masked", "string", "dimension", "nominal", "Card (masked)", None),
    ("merchant", "string", "dimension", "nominal", "Merchant", None),
    ("category", "string", "dimension", "nominal", "Category", None),
    ("amount", "real", "measure", "quantitative", "Amount", 'c"$"#,##0.00;-"$"#,##0.00'),
    ("gender", "string", "dimension", "nominal", "Gender", None),
    ("age_band", "string", "dimension", "nominal", "Age Band", None),
    ("region", "string", "dimension", "nominal", "Region", None),
    ("rule_high_amount", "integer", "measure", "quantitative", "Rule: High Amount", None),
    ("rule_night", "integer", "measure", "quantitative", "Rule: Night Time", None),
    ("rule_risky_category", "integer", "measure", "quantitative", "Rule: Risky Category", None),
    ("rule_above_usual", "integer", "measure", "quantitative", "Rule: Above Usual Spend", None),
    ("risk_score", "integer", "measure", "quantitative", "Risk Score", None),
    ("flagged", "integer", "measure", "quantitative", "Flagged", None),
    ("is_fraud", "integer", "measure", "quantitative", "Is Fraud", None),
    ("outcome", "string", "dimension", "nominal", "Outcome", None),
]
CSV_COLUMN_NAMES = [c[0] for c in CSV_COLUMNS]

# How Tableau's text driver describes each datatype in <metadata-records>.
# remote-type numbers are OLE DB type codes; values copied from real files.
REMOTE_TYPE = {"string": 129, "integer": 20, "real": 5, "datetime": 135}
DEFAULT_AGGREGATION = {"string": "Count", "integer": "Sum", "real": "Sum", "datetime": "Year"}

# Age bands in their natural order (alphabetical order would put "<25" last).
AGE_BAND_ORDER = ["<25", "25-39", "40-54", "55-69", "70+"]

# Number formats (Tableau format strings: n = number, p = percent, c = currency).
FMT_INT = "n#,##0;-#,##0"
FMT_PCT2 = "p0.00%"
FMT_PCT1 = "p0.0%"
FMT_USD = 'c"$"#,##0;-"$"#,##0'


@dataclass(frozen=True)
class Calc:
    """A calculated field. ``name`` is the internal id, ``caption`` what users see."""

    name: str
    caption: str
    datatype: str
    formula: str
    default_format: str


# KPI calculated fields. Formulas are written in Tableau's calculation language
# and must reference columns by their internal names (e.g. [is_fraud]).
# Tableau names user calculations 'Calculation_<number>'; we follow that style.
CALCS: dict[str, Calc] = {
    "total_tx": Calc("Calculation_7310000000000000001", "Total Transactions", "integer",
                     "COUNT([customer_id])", FMT_INT),
    "fraud_tx": Calc("Calculation_7310000000000000002", "Fraud Transactions", "integer",
                     "SUM([is_fraud])", FMT_INT),
    "fraud_rate": Calc("Calculation_7310000000000000003", "Fraud Rate %", "real",
                       "SUM([is_fraud]) / COUNT([customer_id])", FMT_PCT2),
    "fraud_amount": Calc("Calculation_7310000000000000004", "Fraud Amount $", "real",
                         "SUM(IF [is_fraud] = 1 THEN [amount] ELSE 0 END)", FMT_USD),
    "recall": Calc("Calculation_7310000000000000005", "Rule Recall %", "real",
                   "SUM([flagged] * [is_fraud]) / SUM([is_fraud])", FMT_PCT1),
    "precision": Calc("Calculation_7310000000000000006", "Rule Precision %", "real",
                      "SUM([flagged] * [is_fraud]) / SUM([flagged])", FMT_PCT1),
}
CALC_BY_NAME = {c.name: c for c in CALCS.values()}


# ---------------------------------------------------------------------------
# Column instances ("pills" on shelves)
# ---------------------------------------------------------------------------

DERIVATION = {"none": "None", "sum": "Sum", "usr": "User", "tmn": "Month-Trunc"}
PILL_TYPE = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}


@dataclass(frozen=True)
class Pill:
    """One use of a column, e.g. SUM(is_fraud) or the discrete Category.

    deriv: 'none' (as is), 'sum' (SUM), 'usr' (a calculated field that
           aggregates itself) or 'tmn' (date truncated to the month).
    column: the internal column name (CSV column or Calculation_...).
    kind: 'nk' nominal, 'ok' ordinal, 'qk' quantitative (continuous).
    """

    deriv: str
    column: str
    kind: str

    @property
    def instance(self) -> str:
        """Name inside the data source, e.g. [sum:is_fraud:qk]."""
        return f"[{self.deriv}:{self.column}:{self.kind}]"

    @property
    def ref(self) -> str:
        """Fully qualified name used on shelves, e.g. [federated.x].[sum:is_fraud:qk]."""
        return f"[{DS}].{self.instance}"


def dim(column: str) -> Pill:
    """A discrete text dimension (blue pill), e.g. Category."""
    return Pill("none", column, "nk")


def calc(key: str) -> Pill:
    """A pill for one of our aggregate calculated fields."""
    return Pill("usr", CALCS[key].name, "qk")


SUM_IS_FRAUD = Pill("sum", "is_fraud", "qk")
HOUR = Pill("none", "hour", "ok")
MONTH = Pill("tmn", "transaction_time", "qk")          # continuous month
DATE_RANGE = Pill("none", "transaction_time", "qk")    # exact date, for the range filter
OUTCOME = dim("outcome")

# The six dashboard filters. They live in <shared-views>, which is how Tableau
# stores "Apply to Worksheets > All Using This Data Source".
SHARED_FILTERS: list[Pill] = [
    DATE_RANGE,
    dim("category"),
    dim("region"),
    dim("age_band"),
    dim("gender"),
    dim("dataset_split"),
]


# ---------------------------------------------------------------------------
# Worksheet specifications
# ---------------------------------------------------------------------------


@dataclass
class Sheet:
    """Everything needed to draw one worksheet."""

    name: str
    mark: str                       # 'Text', 'Bar' or 'Line'
    rows: list[Pill] = field(default_factory=list)
    cols: list[Pill] = field(default_factory=list)
    text: Pill | None = None        # big-number label (KPI tiles)
    color: Pill | None = None       # colour by this field
    label_bars: bool = False        # show the value on each mark
    sort_desc_by: tuple[Pill, Pill] | None = None   # (dimension, measure)
    manual_order: tuple[Pill, list[str]] | None = None
    exclude: tuple[Pill, str] | None = None         # (dimension, value to hide)


KPI_SHEETS = [
    Sheet("Total Transactions", "Text", text=calc("total_tx")),
    Sheet("Fraud Transactions", "Text", text=calc("fraud_tx")),
    Sheet("Fraud Rate %", "Text", text=calc("fraud_rate")),
    Sheet("Fraud Amount $", "Text", text=calc("fraud_amount")),
    Sheet("Rule Recall %", "Text", text=calc("recall")),
    Sheet("Rule Precision %", "Text", text=calc("precision")),
]

CHART_SHEETS = [
    Sheet("Fraud Rate by Hour", "Bar", rows=[calc("fraud_rate")], cols=[HOUR]),
    Sheet("Fraud Count by Category", "Bar", rows=[dim("category")], cols=[SUM_IS_FRAUD],
          label_bars=True, sort_desc_by=(dim("category"), SUM_IS_FRAUD)),
    Sheet("Fraud by Age Band", "Bar", rows=[SUM_IS_FRAUD], cols=[dim("age_band")],
          label_bars=True, manual_order=(dim("age_band"), AGE_BAND_ORDER)),
    Sheet("Fraud by Region", "Bar", rows=[SUM_IS_FRAUD], cols=[dim("region")], label_bars=True),
    Sheet("Monthly Fraud Trend", "Line", rows=[SUM_IS_FRAUD], cols=[MONTH]),
    Sheet("Rule Outcomes", "Bar", rows=[calc("total_tx")], cols=[OUTCOME], color=OUTCOME,
          label_bars=True, exclude=(OUTCOME, "Correctly passed")),
]

ALL_SHEETS = KPI_SHEETS + CHART_SHEETS

# The worksheet that "owns" the filter controls on the dashboard. Because the
# filters are shared by all sheets, any sheet would do.
FILTER_OWNER_SHEET = "Monthly Fraud Trend"


# ---------------------------------------------------------------------------
# Small XML helpers
# ---------------------------------------------------------------------------


def sub(parent: ET.Element, tag: str, attrs: dict | None = None, text: str | None = None) -> ET.Element:
    """Add a child element (attribute order is kept as given)."""
    el = ET.SubElement(parent, tag, {k: str(v) for k, v in (attrs or {}).items()})
    if text is not None:
        el.text = text
    return el


def user(attr: str) -> str:
    """Attribute name in the user: namespace, e.g. user('ui-marker')."""
    return f"{{{USER_NS}}}{attr}"


def referenced_columns(formula: str) -> list[str]:
    """Column names a formula uses, e.g. 'SUM([is_fraud])' -> ['is_fraud']."""
    return re.findall(r"\[([^\[\]]+)\]", formula)


def column_element(parent: ET.Element, column: str) -> ET.Element:
    """Write the <column> definition of a CSV column or a calculated field."""
    if column in CALC_BY_NAME:
        c = CALC_BY_NAME[column]
        el = sub(parent, "column", {
            "caption": c.caption, "datatype": c.datatype, "default-format": c.default_format,
            "name": f"[{c.name}]", "role": "measure", "type": "quantitative",
        })
        sub(el, "calculation", {"class": "tableau", "formula": c.formula})
        return el
    name, datatype, role, typ, caption, fmt = next(c for c in CSV_COLUMNS if c[0] == column)
    attrs = {"caption": caption, "datatype": datatype}
    if fmt:
        attrs["default-format"] = fmt
    attrs.update({"name": f"[{name}]", "role": role, "type": typ})
    return sub(parent, "column", attrs)


def column_instance_element(parent: ET.Element, pill: Pill) -> ET.Element:
    """Write a <column-instance>: how a column is used (aggregation + discrete/continuous)."""
    return sub(parent, "column-instance", {
        "column": f"[{pill.column}]", "derivation": DERIVATION[pill.deriv],
        "name": pill.instance, "pivot": "key", "type": PILL_TYPE[pill.kind],
    })


def dependencies(parent: ET.Element, pills: list[Pill]) -> ET.Element:
    """Write <datasource-dependencies>: every column and pill a sheet uses.

    Tableau lists the plain columns first (including columns that calculated
    fields read), then the column instances.
    """
    deps = sub(parent, "datasource-dependencies", {"datasource": DS})
    columns: set[str] = set()
    for p in pills:
        columns.add(p.column)
        if p.column in CALC_BY_NAME:
            columns.update(referenced_columns(CALC_BY_NAME[p.column].formula))
    for col in sorted(columns):
        column_element(deps, col)
    seen: set[str] = set()
    for p in sorted(pills, key=lambda p: (p.deriv, p.column, p.kind)):
        if p.instance not in seen:
            seen.add(p.instance)
            column_instance_element(deps, p)
    return deps


# ---------------------------------------------------------------------------
# 1. Data source (CSV connection + columns + calculated fields)
# ---------------------------------------------------------------------------


def csv_relation(parent: ET.Element, csv_name: str) -> ET.Element:
    """The table inside the connection: the CSV file and its column types.

    Tableau names a CSV table after the file: 'x.csv' becomes table '[x#csv]'.
    Giving every column a datatype here stops Tableau from guessing types.
    """
    rel = sub(parent, "relation", {
        "connection": CONNECTION, "name": csv_name,
        "table": f"[{csv_name.replace('.', '#')}]", "type": "table",
    })
    cols = sub(rel, "columns", {"character-set": "UTF-8", "header": "yes",
                                "locale": "en_US", "separator": ","})
    for i, (name, datatype, *_rest) in enumerate(CSV_COLUMNS):
        sub(cols, "column", {"datatype": datatype, "name": name, "ordinal": i})
    return rel


def build_datasource(parent: ET.Element, csv_path: Path, connection_dir: Path,
                     extract_dbname: str | None = None) -> ET.Element:
    """Write the <datasource>: where the CSV is, its columns and our calculations.

    ``connection_dir`` is the folder Tableau will look in for the CSV.
    ``extract_dbname`` is the path of the .hyper extract Tableau should read
    (Tableau Public refuses workbooks without an extract).
    """
    csv_name = csv_path.name                      # e.g. transactions_protected.csv
    object_id = f"{csv_name}_{OBJECT_ID_SUFFIX}"
    ds = sub(parent, "datasource", {"caption": "transactions_protected", "inline": "true",
                                    "name": DS, "version": XML_VERSION})

    # A 'federated' connection wraps one or more named connections. Ours is a
    # single text-file (textscan) connection. 'directory' is the ABSOLUTE folder
    # of the CSV, filled in when the script runs.
    conn = sub(ds, "connection", {"class": "federated"})
    named = sub(sub(conn, "named-connections"), "named-connection",
                {"caption": "transactions_protected", "name": CONNECTION})
    sub(named, "connection", {
        "class": "textscan", "directory": connection_dir.as_posix(),
        "filename": csv_path.name, "password": "", "server": "",
        "workgroup-auth-mode": "as-is",
    })
    csv_relation(conn, csv_name)

    # <metadata-records> cache what Tableau learned about the file, so it does
    # not have to re-read the whole CSV just to know the column types.
    records = sub(conn, "metadata-records")
    cap = sub(records, "metadata-record", {"class": "capability"})
    sub(cap, "remote-name")
    sub(cap, "remote-type", text="0")
    sub(cap, "parent-name", text=f"[{csv_name}]")
    sub(cap, "remote-alias")
    sub(cap, "aggregation", text="Count")
    sub(cap, "contains-null", text="true")
    attrs = sub(cap, "attributes")
    for key, value in [("character-set", '"UTF-8"'), ("collation", '"en_US"'),
                       ("field-delimiter", '","'), ("header-row", '"true"'),
                       ("locale", '"en_US"'), ("single-char", '""')]:
        sub(attrs, "attribute", {"datatype": "string", "name": key}, value)
    for i, (name, datatype, *_rest) in enumerate(CSV_COLUMNS):
        rec = sub(records, "metadata-record", {"class": "column"})
        sub(rec, "remote-name", text=name)
        sub(rec, "remote-type", text=str(REMOTE_TYPE[datatype]))
        sub(rec, "local-name", text=f"[{name}]")
        sub(rec, "parent-name", text=f"[{csv_name}]")
        sub(rec, "remote-alias", text=name)
        sub(rec, "ordinal", text=str(i))
        sub(rec, "local-type", text=datatype)
        sub(rec, "aggregation", text=DEFAULT_AGGREGATION[datatype])
        if datatype == "string":
            sub(rec, "scale", text="1")
            sub(rec, "width", text="1073741823")
        sub(rec, "contains-null", text="true")
        if datatype == "string":
            sub(rec, "collation", {"flag": "0", "name": "LEN_RUS"})
        sub(rec, "object-id", text=f"[{object_id}]")

    sub(ds, "aliases", {"enabled": "yes"})

    # Column definitions: friendly captions, roles and number formats, then
    # our calculated fields (a <column> with a <calculation> child).
    for c in CALCS.values():
        column_element(ds, c.name)
    for name in CSV_COLUMN_NAMES:
        column_element(ds, name)
    # Since Tableau 2020.2 every table is also a hidden 'table' column.
    sub(ds, "column", {"caption": csv_name, "datatype": "table",
                       "name": f"[__tableau_internal_object_id__].[{object_id}]",
                       "role": "measure", "type": "quantitative"})
    if extract_dbname:
        build_extract(ds, csv_name, extract_dbname)
    sub(ds, "layout", {"dim-ordering": "alphabetic", "measure-ordering": "alphabetic",
                       "show-structure": "true"})
    sem = sub(ds, "semantic-values")
    sub(sem, "semantic-value", {"key": "[Country].[Name]", "value": '"United States"'})

    # The object graph (Tableau 2020.2+ data model): one logical table.
    objects = sub(sub(ds, "object-graph"), "objects")
    obj = sub(objects, "object", {"caption": csv_name, "id": object_id})
    csv_relation(sub(obj, "properties", {"context": ""}), csv_name)
    if extract_dbname:
        sub(sub(obj, "properties", {"context": "extract"}), "relation",
            {"name": "Extract", "table": "[Extract].[Extract]", "type": "table"})
    return ds


def build_extract(ds: ET.Element, csv_name: str, dbname: str) -> ET.Element:
    """Write <extract>: the .hyper copy of the CSV that Tableau reads instead.

    The .hyper file itself is made by src/make_extract.py (schema "Extract",
    table "Extract", the layout Tableau uses for its own extracts).
    """
    ext = sub(ds, "extract", {"count": "-1", "enabled": "true", "object-id": "", "units": "records"})
    conn = sub(ext, "connection", {
        "access_mode": "readonly", "authentication": "auth-none", "author-locale": "en_US",
        "class": "hyper", "dbname": dbname, "default-settings": "yes", "schema": "Extract",
        "sslmode": "", "tablename": "Extract", "update-time": "11/02/2026 12:00:00 PM",
        "username": "tableau_internal_user",
    })
    sub(conn, "relation", {"name": "Extract", "table": "[Extract].[Extract]", "type": "table"})
    records = sub(conn, "metadata-records")
    for i, (name, datatype, *_rest) in enumerate(CSV_COLUMNS):
        rec = sub(records, "metadata-record", {"class": "column"})
        sub(rec, "remote-name", text=name)
        sub(rec, "remote-type", text=str(REMOTE_TYPE[datatype]))
        sub(rec, "local-name", text=f"[{name}]")
        sub(rec, "parent-name", text="[Extract]")
        sub(rec, "remote-alias", text=name)
        sub(rec, "ordinal", text=str(i))
        sub(rec, "family", text=csv_name)
        sub(rec, "local-type", text=datatype)
        sub(rec, "aggregation", text=DEFAULT_AGGREGATION[datatype])
        sub(rec, "contains-null", text="true")
    return ext


# ---------------------------------------------------------------------------
# 2. Shared filters (apply to all worksheets using the data source)
# ---------------------------------------------------------------------------


def all_values_filter(parent: ET.Element, pill: Pill) -> ET.Element:
    """A filter that starts with every value selected (the user narrows it)."""
    if pill.kind == "qk":
        # Continuous date: a range filter, initially covering all dates.
        return sub(parent, "filter", {"class": "quantitative", "column": pill.ref,
                                      "included-values": "all"})
    flt = sub(parent, "filter", {"class": "categorical", "column": pill.ref})
    sub(flt, "groupfilter", {"function": "level-members", "level": pill.instance,
                             user("ui-enumeration"): "all", user("ui-marker"): "enumerate"})
    return flt


def build_shared_views(parent: ET.Element) -> ET.Element:
    """Write <shared-views>: the six dashboard filters, shared by all sheets."""
    sv = sub(sub(parent, "shared-views"), "shared-view", {"name": DS})
    sub(sub(sv, "datasources"), "datasource", {"caption": "transactions_protected", "name": DS})
    dependencies(sv, SHARED_FILTERS)
    for pill in SHARED_FILTERS:
        all_values_filter(sv, pill)
    return sv


# ---------------------------------------------------------------------------
# 3. Worksheets
# ---------------------------------------------------------------------------


def sheet_pills(sheet: Sheet) -> list[Pill]:
    """Every pill a worksheet uses (shelves, marks card, sorts, filters)."""
    pills = list(sheet.rows) + list(sheet.cols)
    for p in (sheet.text, sheet.color):
        if p is not None:
            pills.append(p)
    if sheet.sort_desc_by:
        pills.extend(sheet.sort_desc_by)
    if sheet.manual_order:
        pills.append(sheet.manual_order[0])
    if sheet.exclude:
        pills.append(sheet.exclude[0])
    return pills + SHARED_FILTERS


def shelf_text(pills: list[Pill]) -> str | None:
    """Text for <rows>/<cols>. Several pills are joined with ' / ' (nesting)."""
    if not pills:
        return None
    if len(pills) == 1:
        return pills[0].ref
    return "(" + " / ".join(p.ref for p in pills) + ")"


def build_worksheet(parent: ET.Element, sheet: Sheet) -> ET.Element:
    """Write one <worksheet>: data used, filters, sorts, marks and shelves."""
    ws = sub(parent, "worksheet", {"name": sheet.name})
    if sheet.text:
        # KPI tile: a small one-line title so the big number fits in the tile.
        title = sub(sub(sub(ws, "layout-options"), "title"), "formatted-text")
        sub(title, "run", {"fontcolor": "#555555", "fontsize": "11"}, sheet.name)
    table = sub(ws, "table")

    # <view>: which data source and fields the sheet uses, plus filters/sorts.
    view = sub(table, "view")
    sub(sub(view, "datasources"), "datasource", {"caption": "transactions_protected", "name": DS})
    dependencies(view, sheet_pills(sheet))

    if sheet.exclude:
        # "Exclude" filter: all values EXCEPT the given one.
        pill, value = sheet.exclude
        flt = sub(view, "filter", {"class": "categorical", "column": pill.ref})
        exc = sub(flt, "groupfilter", {"function": "except", user("ui-domain"): "database",
                                       user("ui-enumeration"): "exclusive",
                                       user("ui-marker"): "enumerate"})
        sub(exc, "groupfilter", {"function": "level-members", "level": pill.instance})
        sub(exc, "groupfilter", {"function": "member", "level": pill.instance,
                                 "member": f'"{value}"'})
    if sheet.sort_desc_by:
        dim_pill, measure = sheet.sort_desc_by
        sub(view, "computed-sort", {"column": dim_pill.ref, "direction": "DESC",
                                    "using": measure.ref})
    if sheet.manual_order:
        dim_pill, values = sheet.manual_order
        ms = sub(view, "manual-sort", {"column": dim_pill.ref, "direction": "ASC"})
        dictionary = sub(ms, "dictionary")
        for v in values:
            sub(dictionary, "bucket", text=f'"{v}"')

    # <slices> lists the fields that filter this sheet (ours + the shared ones).
    slices = sub(view, "slices")
    slice_pills = ([sheet.exclude[0]] if sheet.exclude else []) + SHARED_FILTERS
    for p in slice_pills:
        sub(slices, "column", text=p.ref)
    sub(view, "aggregation", {"value": "true"})

    sub(table, "style")

    # <panes>: the Marks card (mark type, Text/Color encodings, labels).
    pane = sub(sub(table, "panes"), "pane",
               {"selection-relaxation-option": "selection-relaxation-allow"})
    sub(sub(pane, "view"), "breakdown", {"value": "auto"})
    sub(pane, "mark", {"class": sheet.mark})
    if sheet.text or sheet.color:
        enc = sub(pane, "encodings")
        if sheet.color:
            sub(enc, "color", {"column": sheet.color.ref})
        if sheet.text:
            sub(enc, "text", {"column": sheet.text.ref})
    if sheet.text:
        # KPI tile: show the number in a big bold font.
        label = sub(sub(pane, "customized-label"), "formatted-text")
        sub(label, "run", {"bold": "true", "fontcolor": "#1f4e79", "fontsize": "22"},
            f"<{sheet.text.ref}>")
    if sheet.text or sheet.label_bars:
        rule = sub(sub(pane, "style"), "style-rule", {"element": "mark"})
        sub(rule, "format", {"attr": "mark-labels-show", "value": "true"})
        sub(rule, "format", {"attr": "mark-labels-cull", "value": "true"})

    # <rows> and <cols> are the Rows and Columns shelves (empty for KPI tiles).
    sub(table, "rows", text=shelf_text(sheet.rows))
    sub(table, "cols", text=shelf_text(sheet.cols))
    return ws


# ---------------------------------------------------------------------------
# 4. Dashboard layout
# ---------------------------------------------------------------------------


class ZoneIds:
    """Hands out unique zone ids (every box on a dashboard needs one)."""

    def __init__(self) -> None:
        self.next_id = 1

    def __call__(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value


def split(start: int, length: int, sizes_px: list[float], total_px: float) -> list[tuple[int, int]]:
    """Split a span (in Tableau's 0-100000 units) into parts proportional to pixel sizes.

    Returns (start, length) pairs that add up exactly to the parent span.
    """
    out, pos, used_px = [], start, 0.0
    for i, px in enumerate(sizes_px):
        used_px += px
        end = start + length if i == len(sizes_px) - 1 else start + round(length * used_px / total_px)
        out.append((pos, end - pos))
        pos = end
    return out


def zone(parent: ET.Element, zid: int, x: int, y: int, w: int, h: int, **attrs) -> ET.Element:
    """Write a <zone> (a box on the dashboard). Coordinates are 0..100000."""
    a = {"h": h, "id": zid}
    a.update({k.replace("_", "-"): v for k, v in attrs.items()})
    a.update({"w": w, "x": x, "y": y})
    return sub(parent, "zone", a)


def build_dashboard(parent: ET.Element) -> ET.Element:
    """Write the <dashboard>: title, KPI row, 2x3 chart grid and a filter panel.

    Layout (pixels, fixed 1265 x 760):
        +------------------------------------------------------+---------+
        | Title (50 px)                                                  |
        +------------------------------------------------------+---------+
        | KPI | KPI | KPI | KPI | KPI | KPI     (110 px)       | Filters |
        | chart        | chart        | chart                  | (230 px |
        | chart        | chart        | chart                  |  wide)  |
        +------------------------------------------------------+---------+
    Containers ('layout-flow') stack their children vertically ('vert') or
    horizontally ('horz'); 'fixed-size' pins a child's size in pixels.
    """
    W, H = DASHBOARD_WIDTH, DASHBOARD_HEIGHT
    TITLE_PX, KPI_PX, FILTER_PX = 50, 110, 230
    FULL = 100000
    new_id = ZoneIds()

    db = sub(parent, "dashboard", {"name": DASHBOARD_NAME})
    sub(db, "style")
    sub(db, "size", {"maxheight": H, "maxwidth": W, "minheight": H, "minwidth": W,
                     "sizing-mode": "fixed"})
    # The filter controls need to know the fields they show.
    sub(sub(db, "datasources"), "datasource", {"caption": "transactions_protected", "name": DS})
    dependencies(db, SHARED_FILTERS)

    zones = sub(db, "zones")
    root = zone(zones, new_id(), 0, 0, FULL, FULL, type_v2="layout-basic")
    page = zone(root, new_id(), 0, 0, FULL, FULL, param="vert", type_v2="layout-flow")

    # Title row.
    (ty, th), (by, bh) = split(0, FULL, [TITLE_PX, H - TITLE_PX], H)
    title = zone(page, new_id(), 0, ty, FULL, th, fixed_size=TITLE_PX, forceUpdate="true",
                 is_fixed="true", type_v2="text")
    text = sub(title, "formatted-text")
    sub(text, "run", {"bold": "true", "fontsize": "20"}, DASHBOARD_NAME)
    # Team names shown next to the title (one line, fits the dashboard width).
    sub(text, "run", {"fontcolor": "#6b6b6b", "fontsize": "10"},
        "   Rajat Sharma (S24BCAU0134) · Ishan Chaudary (S24BCAU0002) · "
        "Piyush Agarwal (S24BCAU0182) · Suraj Tiwari (S24BCAU0136)")

    # Body: main area (left) + filter panel (right).
    body = zone(page, new_id(), 0, by, FULL, bh, param="horz", type_v2="layout-flow")
    (mx, mw), (fx, fw) = split(0, FULL, [W - FILTER_PX, FILTER_PX], W)
    main = zone(body, new_id(), mx, by, mw, bh, param="vert", type_v2="layout-flow")

    body_px = H - TITLE_PX
    chart_px = (body_px - KPI_PX) / 2
    (ky, kh), (r1y, r1h), (r2y, r2h) = split(by, bh, [KPI_PX, chart_px, chart_px], body_px)

    # KPI row: six tiles side by side.
    kpi_row = zone(main, new_id(), mx, ky, mw, kh, fixed_size=KPI_PX, is_fixed="true",
                   param="horz", type_v2="layout-flow")
    main_px = W - FILTER_PX            # width of the area left of the filter panel
    for sheet, (x, w) in zip(KPI_SHEETS, split(mx, mw, [1] * 6, 6)):
        # fixed-size keeps all six tiles the same width
        zone(kpi_row, new_id(), x, ky, w, kh, fixed_size=main_px // 6, is_fixed="true",
             name=sheet.name)

    # Two rows of three charts.
    for (y, h), sheets in [((r1y, r1h), CHART_SHEETS[:3]), ((r2y, r2h), CHART_SHEETS[3:])]:
        row = zone(main, new_id(), mx, y, mw, h, param="horz", type_v2="layout-flow")
        for sheet, (x, w) in zip(sheets, split(mx, mw, [1] * 3, 3)):
            zone(row, new_id(), x, y, w, h, fixed_size=main_px // 3, is_fixed="true",
                 name=sheet.name)

    # Filter panel: one control per shared filter, stacked vertically.
    panel = zone(body, new_id(), fx, by, fw, bh, fixed_size=FILTER_PX, is_fixed="true",
                 param="vert", type_v2="layout-flow")
    heights = [100] + [70] * (len(SHARED_FILTERS) - 1)        # date slider is taller
    heights.append(body_px - sum(heights))                    # blank space at the bottom
    parts = split(by, bh, heights, body_px)
    for pill, (y, h) in zip(SHARED_FILTERS, parts):
        attrs = {"name": FILTER_OWNER_SHEET, "param": pill.ref, "type_v2": "filter"}
        if pill.kind == "nk":
            # Drop-down list with check boxes, values taken from the database.
            attrs = {"mode": "checkdropdown", **attrs, "values": "database"}
        zone(panel, new_id(), fx, y, fw, h, **attrs)
    blank_y, blank_h = parts[-1]
    zone(panel, new_id(), fx, blank_y, fw, blank_h, type_v2="empty")
    return db


# ---------------------------------------------------------------------------
# 5. Windows (the tabs along the bottom of Tableau)
# ---------------------------------------------------------------------------


def build_windows(parent: ET.Element) -> ET.Element:
    """Write <windows>: one tab per worksheet plus the dashboard (opened first)."""
    windows = sub(parent, "windows", {"source-height": "30"})
    for sheet in ALL_SHEETS:
        win = sub(windows, "window", {"class": "worksheet", "name": sheet.name})
        cards = sub(win, "cards")
        left = sub(sub(cards, "edge", {"name": "left"}), "strip", {"size": "160"})
        for card in ("pages", "filters", "marks"):
            sub(left, "card", {"type": card})
        top = sub(cards, "edge", {"name": "top"})
        for card, size in (("columns", "2147483647"), ("rows", "2147483647"), ("title", "31")):
            sub(sub(top, "strip", {"size": size}), "card", {"type": card})
    win = sub(windows, "window", {"class": "dashboard", "maximized": "true", "name": DASHBOARD_NAME})
    viewpoints = sub(win, "viewpoints")
    for sheet in ALL_SHEETS:
        # Fit each chart to its box ("Entire View"), so no chart needs scrollbars.
        sub(sub(viewpoints, "viewpoint", {"name": sheet.name}), "zoom", {"type": "entire-view"})
    # Tableau requires these two after <viewpoints> in a dashboard window.
    sub(win, "active", {"id": "-1"})
    sub(win, "device-preview", {"visible": "true"})
    return windows


# ---------------------------------------------------------------------------
# Whole workbook
# ---------------------------------------------------------------------------


def build_workbook(csv_path: Path, connection_dir: Path, extract_dbname: str | None = None) -> ET.Element:
    """Assemble the complete <workbook> element."""
    wb = ET.Element("workbook", {
        "original-version": XML_VERSION, "source-build": SOURCE_BUILD,
        "source-platform": "mac", "version": XML_VERSION,
    })
    # Feature flags: tell Tableau which newer XML forms this file uses
    # (object-graph data model, 'type-v2' on dashboard zones, ...).
    manifest = sub(wb, "document-format-change-manifest")
    # SortTagCleanup enables the <computed-sort> / <manual-sort> tags used in
    # the worksheets; without it newer Tableau versions refuse to open the file.
    flags = ["ObjectModelEncapsulateLegacy", "ObjectModelTableType",
             "SchemaViewerObjectModel", "SetMembershipControl", "SortTagCleanup"]
    if extract_dbname:
        flags.insert(1, "ObjectModelExtractV2")   # extract inside the object-graph model
    for flag in flags:
        sub(manifest, flag)
    prefs = sub(wb, "preferences")
    sub(prefs, "preference", {"name": "ui.encoding.shelf.height", "value": "24"})
    sub(prefs, "preference", {"name": "ui.shelf.height", "value": "26"})

    build_datasource(sub(wb, "datasources"), csv_path, connection_dir, extract_dbname)
    build_shared_views(wb)
    worksheets = sub(wb, "worksheets")
    for sheet in ALL_SHEETS:
        build_worksheet(worksheets, sheet)
    build_dashboard(sub(wb, "dashboards"))
    build_windows(wb)
    return wb


def check_csv_header(csv_path: Path) -> None:
    """If the CSV already exists, warn when its header differs from the schema."""
    if not csv_path.exists():
        print(f"Note: {csv_path} does not exist yet. Run the pipeline before opening Tableau.")
        return
    with csv_path.open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh), [])
    if header != CSV_COLUMN_NAMES:
        print("WARNING: CSV header does not match the dashboard schema.\n"
              f"  expected: {CSV_COLUMN_NAMES}\n  found:    {header}", file=sys.stderr)


def build(csv_path: Path, out_path: Path, connection_dir: Path | None = None) -> Path:
    """Write the Tableau workbook for ``csv_path`` to ``out_path`` and return it.

    The CSV's absolute folder is written into the connection, so the workbook
    works on the computer where this function runs. If Tableau runs on a
    different computer (or the project folder is mounted under another path),
    pass that computer's folder as ``connection_dir`` instead.
    """
    csv_path = Path(csv_path).expanduser().resolve()
    out_path = Path(out_path).expanduser().resolve()
    connection_dir = Path(connection_dir).expanduser() if connection_dir else csv_path.parent
    check_csv_header(csv_path)

    # Tableau Public only accepts workbooks that read an extract (.hyper).
    # src/make_extract.py writes it next to the CSV.
    hyper = csv_path.with_suffix(".hyper")
    has_extract = hyper.exists()
    if not has_extract:
        print(f"Note: {hyper.name} not found; run src/make_extract.py, "
              "otherwise Tableau Public will refuse the workbook.")

    def write(path: Path, dbname: str | None) -> str:
        workbook = build_workbook(csv_path, connection_dir, dbname)
        ET.indent(workbook, space="  ")
        text = ("<?xml version='1.0' encoding='utf-8' ?>\n\n" + BUILD_COMMENT + "\n"
                + ET.tostring(workbook, encoding="unicode") + "\n")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        validate(path)
        return text

    # 1) .twb: reads the extract from data/processed on this computer.
    write(out_path, (connection_dir / hyper.name).as_posix() if has_extract else None)
    # 2) .twbx: one packaged file (workbook + extract inside), the easiest to open.
    if has_extract:
        inner = f"Data/Extracts/{hyper.name}"
        with tempfile.TemporaryDirectory() as tmp_dir:      # checked copy, kept out of the project
            with contextlib.redirect_stdout(io.StringIO()):  # same checks, printed once above
                text = write(Path(tmp_dir) / out_path.name, inner)
        twbx = out_path.with_suffix(".twbx")
        with zipfile.ZipFile(twbx, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(out_path.name, text)
            z.write(hyper, inner)
        print(f"Wrote {twbx.name} (workbook + extract in one file)")
    return out_path


# ---------------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------------

PILL_RE = re.compile(r"\[(federated\.[^\]]+)\]\.\[(\w+):([^:\]]+):(\w+)\]")


def validate(twb_path: Path) -> None:
    """Structural checks on the written file. Raises ValueError on any problem.

    Checks: the XML parses; every worksheet the dashboard shows exists; every
    field used on shelves, marks, sorts, filters and filter controls is a
    defined column or calculated field; each worksheet declares the column
    instances it uses; calculated fields only use defined columns; zone ids
    are unique and every child zone sits inside its parent; and there is a
    window (tab) for every sheet.
    """
    problems: list[str] = []
    root = ET.parse(twb_path).getroot()

    datasource = next((d for d in root.iter("datasource")
                       if d.get("name") == DS and d.find("connection") is not None), None)
    if datasource is None:
        raise ValueError(f"{twb_path}: data source {DS} not found")
    defined = {c.get("name", "").strip("[]") for c in datasource.findall("column")}
    calc_columns = [c for c in datasource.findall("column") if c.find("calculation") is not None]

    for c in calc_columns:
        for ref in referenced_columns(c.find("calculation").get("formula", "")):
            if ref not in defined:
                problems.append(f"calculation {c.get('caption')} uses unknown column [{ref}]")

    relation_cols = [c.get("name") for c in datasource.find("connection/relation/columns")]
    if relation_cols != CSV_COLUMN_NAMES:
        problems.append("CSV relation columns differ from the schema")

    def check_refs(text: str, where: str, declared: set[str] | None) -> None:
        for ds_name, deriv, column, kind in PILL_RE.findall(text or ""):
            if ds_name != DS:
                problems.append(f"{where}: unknown data source {ds_name}")
            if column not in defined:
                problems.append(f"{where}: field [{column}] is not defined in the data source")
            if deriv not in DERIVATION or kind not in PILL_TYPE:
                problems.append(f"{where}: unexpected pill [{deriv}:{column}:{kind}]")
            if declared is not None and f"[{deriv}:{column}:{kind}]" not in declared:
                problems.append(f"{where}: [{deriv}:{column}:{kind}] missing from datasource-dependencies")

    def declared_instances(scope: ET.Element) -> set[str]:
        deps = scope.find("datasource-dependencies")
        return set() if deps is None else {ci.get("name") for ci in deps.findall("column-instance")}

    # Shared filters.
    for sv in root.iter("shared-view"):
        declared = declared_instances(sv)
        for flt in sv.findall("filter"):
            check_refs(flt.get("column"), "shared filter", declared)

    # Worksheets.
    worksheet_names = []
    for ws in root.iter("worksheet"):
        name = ws.get("name")
        worksheet_names.append(name)
        view = ws.find("table/view")
        declared = declared_instances(view)
        for deps in view.findall("datasource-dependencies"):
            for col in deps.findall("column"):
                if col.get("name", "").strip("[]") not in defined:
                    problems.append(f"{name}: dependency column {col.get('name')} not defined")
        texts = [ws.findtext("table/rows") or "", ws.findtext("table/cols") or ""]
        texts += [e.get("column", "") + " " + e.get("using", "")
                  for e in view.iter() if e.tag in ("filter", "computed-sort", "manual-sort")]
        texts += [e.get("column", "") for e in ws.iter() if e.tag in ("text", "color")]
        texts += [r.text or "" for r in ws.iter("run")]
        texts += [c.text or "" for c in view.findall("slices/column")]
        for t in texts:
            check_refs(t, f"worksheet '{name}'", declared)
        if ws.find("table/panes/pane/mark") is None:
            problems.append(f"{name}: no mark type")
    if len(set(worksheet_names)) != len(worksheet_names):
        problems.append("duplicate worksheet names")

    # Dashboards.
    for db in root.iter("dashboard"):
        declared = declared_instances(db)
        ids = [z.get("id") for z in db.iter("zone")]
        if len(ids) != len(set(ids)):
            problems.append(f"dashboard '{db.get('name')}': duplicate zone ids")
        for z in db.iter("zone"):
            if z.get("name") and z.get("name") not in worksheet_names:
                problems.append(f"dashboard zone shows missing worksheet '{z.get('name')}'")
            if z.get("type-v2") == "filter":
                check_refs(z.get("param", ""), "dashboard filter control", declared)
            for child in z.findall("zone"):
                px, py, pw, ph = (int(z.get(k)) for k in "xywh")
                cx, cy, cw, ch = (int(child.get(k)) for k in "xywh")
                if cx < px or cy < py or cx + cw > px + pw or cy + ch > py + ph:
                    problems.append(f"zone {child.get('id')} lies outside its parent {z.get('id')}")
        shown = {z.get("name") for z in db.iter("zone") if z.get("name") and not z.get("type-v2")}
        missing = {s.name for s in ALL_SHEETS} - shown
        if missing:
            problems.append(f"sheets not placed on the dashboard: {sorted(missing)}")

    # Windows.
    window_names = {w.get("name") for w in root.iter("window")}
    for name in worksheet_names + [db.get("name") for db in root.iter("dashboard")]:
        if name not in window_names:
            problems.append(f"no window (tab) for '{name}'")

    if problems:
        raise ValueError(f"{twb_path} failed validation:\n  - " + "\n  - ".join(problems))
    print(f"Validated {twb_path.name}: {len(worksheet_names)} worksheets, "
          f"{len(calc_columns)} calculated fields, {len(SHARED_FILTERS)} shared filters.")


def main() -> None:
    """Build dashboard/fraud_dashboard.twb from data/processed/transactions_protected.csv."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tableau-data-dir", type=Path, default=None,
                        help="folder Tableau should read the CSV from, if it differs from "
                             "this computer's data/processed folder")
    args = parser.parse_args()
    out = build(DEFAULT_CSV, DEFAULT_TWB, args.tableau_data_dir)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
