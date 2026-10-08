"""Step 5: draw the report charts (PNG files in outputs/charts/)."""

import matplotlib

matplotlib.use("Agg")  # draw to files, no window needed
import matplotlib.pyplot as plt
import pandas as pd

import config

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
LABELS = {"rule_high_amount": "R1 High amount", "rule_night": "R2 Night time",
          "rule_risky_category": "R3 Risky category", "rule_above_usual": "R4 Above usual",
          "combined": "Combined (score)"}


def _style(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    """Shared clean look: title, thin grid, no box."""
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.tick_params(colors=MUTED, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_axisbelow(True)
    ax.set_facecolor(SURFACE)


def _save(fig, name: str) -> None:
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(config.CHARTS_DIR / name, dpi=150)
    plt.close(fig)


def fraud_by_hour(df: pd.DataFrame, night_hours: list) -> None:
    rate = df.groupby("hour")["is_fraud"].mean() * 100
    fig, ax = plt.subplots(figsize=(9, 4))
    colors = [ORANGE if h in night_hours else BLUE for h in rate.index]
    ax.bar(rate.index, rate.values, color=colors, width=0.8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_xticks(range(24))
    ax.bar(0, 0, color=ORANGE, label="Night hours (rule R2)")
    ax.bar(0, 0, color=BLUE, label="Other hours")
    ax.legend(frameon=False, labelcolor=MUTED)
    _style(ax, "Fraud rate by hour of day (all data)", "Hour", "Fraud rate (%)")
    _save(fig, "fraud_rate_by_hour.png")


def fraud_by_category(df: pd.DataFrame, risky: list) -> None:
    rate = (df.groupby("category", observed=True)["is_fraud"].mean() * 100).sort_values()
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = [ORANGE if c in risky else BLUE for c in rate.index.astype(str)]
    ax.barh(rate.index.astype(str), rate.values, color=colors, height=0.7)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    for y, v in enumerate(rate.values):
        ax.text(v + 0.02, y, f"{v:.2f}%", va="center", fontsize=8, color=MUTED)
    ax.barh(0, 0, color=ORANGE, label="Risky category (rule R3)")
    ax.barh(0, 0, color=BLUE, label="Other categories")
    ax.legend(frameon=False, labelcolor=MUTED, loc="lower right")
    _style(ax, "Fraud rate by merchant category (all data)", "Fraud rate (%)")
    _save(fig, "fraud_rate_by_category.png")


def rule_comparison(metrics: dict) -> None:
    keys = list(LABELS)
    names = [LABELS[k] for k in keys]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    width = 0.26
    for i, (metric, color) in enumerate([("precision", BLUE), ("recall", ORANGE), ("f1", AQUA)]):
        values = [metrics[k][metric] for k in keys]
        xs = [x + (i - 1) * width for x in range(len(keys))]
        ax.bar(xs, values, width=width - 0.02, color=color, label=metric.capitalize() if metric != "f1" else "F1")
        if metric == "f1":
            for x, v in zip(xs, values):
                ax.text(x, v + 0.02, f"{v:.2f}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(range(len(keys)), names)
    ax.set_ylim(0, 1.05)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.legend(frameon=False, labelcolor=MUTED, ncol=3, loc="upper left")
    _style(ax, "Rule performance on the unseen test file", "", "Score (0 to 1)")
    _save(fig, "rule_comparison.png")


def confusion_matrix(m: dict) -> None:
    cells = [[m["tn"], m["fp"]], [m["fn"], m["tp"]]]
    names = [["Correctly passed", "False alarm"], ["Missed", "Caught"]]
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    shades = [["#cde2fb", "#86b6ef"], ["#86b6ef", "#2a78d6"]]
    for r in range(2):
        for c in range(2):
            ax.add_patch(plt.Rectangle((c, 1 - r), 0.98, 0.98, color=shades[r][c]))
            ink = "white" if shades[r][c] == BLUE else INK
            ax.text(c + 0.49, 1.6 - r, f"{cells[r][c]:,}", ha="center", fontsize=14, color=ink)
            ax.text(c + 0.49, 1.35 - r, names[r][c], ha="center", fontsize=9, color=ink)
    ax.set_xlim(0, 2); ax.set_ylim(0, 2)
    ax.set_xticks([0.49, 1.49], ["Predicted normal", "Predicted fraud"])
    ax.set_yticks([1.49, 0.49], ["Actual normal", "Actual fraud"])
    _style(ax, "Confusion matrix: combined rules on test file")
    ax.spines["bottom"].set_visible(False)
    _save(fig, "confusion_matrix.png")


def k_anonymity(report: dict) -> None:
    before, after = report["k_anonymity_before"], report["k_anonymity_after"]
    labels = ["Before\n(narrow age, gender, state)", "After\n(age band, gender, region)"]
    values = [before["customers_in_groups_below_k"], after["customers_in_groups_below_k"]]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, values, color=[ORANGE, BLUE], width=0.5)
    for x, v, r in zip(range(2), values, [before["result"], after["result"]]):
        ax.text(x, v + 10, f"{v} customers · {r}", ha="center", fontsize=10, color=INK)
    ax.set_ylim(0, max(values) * 1.2 + 10)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    _style(ax, f"Customers in groups smaller than k = {before['k']} (out of {before['total_customers']})",
           "", "Customers at risk")
    _save(fig, "k_anonymity_before_after.png")


def make_all(df: pd.DataFrame, limits, metrics: dict, privacy_report: dict) -> None:
    config.CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fraud_by_hour(df, limits.night_hours)
    fraud_by_category(df, limits.risky_categories)
    rule_comparison(metrics)
    confusion_matrix(metrics["combined"])
    k_anonymity(privacy_report)
