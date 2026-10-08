# Setup Guide (Step by Step)

This guide assumes you have **never run this project before**. Follow the steps in order. Each step tells you **what to do**, **why**, and **what you should see**.

**Time needed:** about 20 minutes (most of it is downloads).
**Computer:** a Mac. On Windows the commands are the same, but run them in PowerShell.

## The big picture (read this once)

```text
data/raw/*.csv  →  Python pipeline  →  data/processed/transactions_protected.csv  →  Tableau dashboard
 (private data)    (hides + checks)     (safe data, no names or card numbers)        (charts + filters)
```

* **Python** does all the work: it hides private data, finds suspicious transactions and measures how good the rules are.
* **Tableau** only draws pictures from the safe file.
* **The dashboard is code:** `src/build_dashboard.py` writes the Tableau file for you. You never drag and drop to build it.

## Step 1: Install uv (the Python manager)

**Why:** `uv` installs the right Python version (3.13) and the right packages, so everybody gets the same results.

Open **Terminal** (press Cmd + Space, type "Terminal", press Enter) and run **one** of these:

```bash
brew install uv                                       # if you use Homebrew
curl -LsSf https://astral.sh/uv/install.sh | sh       # otherwise
```

Close Terminal, open it again, and check:

```bash
uv --version
```

**You should see:** something like `uv 0.x.x`. If you see `command not found`, close and reopen Terminal.

## Step 2: Install Tableau Desktop Public Edition (free)

**Why:** it opens and shows the dashboard file.

1. Go to https://www.tableau.com/products/public/download
2. Enter your email and download the Mac installer.
3. Open the downloaded `.dmg` file and drag Tableau into Applications.
4. Open Tableau once and sign in or create a free Tableau Public account.

## Step 3: Go to the project folder

```bash
cd ~/Desktop/cbca-293-security
ls
```

**You should see:** `README.md  setup.md  pyproject.toml  data  src  dashboard  outputs  reports  docs`

## Step 4: Check the dataset is there

```bash
ls -lh data/raw
```

**You should see:** `fraudTest.csv` (about 143 MB) and `fraudTrain.csv` (about 335 MB).

**If they are missing,** download them (about 200 MB):

```bash
mkdir -p data/raw
curl -L -o /tmp/fraud.zip https://www.kaggle.com/api/v1/datasets/download/kartik2112/fraud-detection
unzip -o /tmp/fraud.zip -d data/raw
```

## Step 5: Install Python 3.13 and the packages

```bash
uv sync
```

**Why:** this reads `pyproject.toml` and creates a private environment in a `.venv` folder, with Python 3.13, pandas, numpy and matplotlib in it. It does not touch any other Python on your Mac.

**You should see:** lines like `Installed ... packages`. The first time can take a minute.

## Step 6: Run the pipeline

```bash
uv run python src/run_pipeline.py
```

**Why:** this one command runs all 6 steps. It takes about 2 minutes.

**You should see:**

```text
[1/6] Loading raw Kaggle files ...
   1,852,394 rows, 9,651 fraud (0.52%)
[2/6] Privacy layer: mask, hash, generalize, suppress ...
   k-anonymity before: FAIL (smallest group 1, 659 customers in groups < 5)
   k-anonymity after: PASS (smallest group 5, 0 customers in groups < 5)
[3/6] Learning rule limits from the TRAIN file ...
   best threshold on train: risk_score >= 3
[4/6] Evaluating on the unseen TEST file ...
   precision 34.1%, recall 57.1%, F1 0.427
[5/6] Drawing report charts ...
[6/6] Writing protected CSV and Tableau workbook ...
Validated fraud_dashboard.twb: 12 worksheets, 6 calculated fields, 6 shared filters.
Done in ... seconds.
```

**What each step means, in one line:**

| Step | Plain English |
|---|---|
| 1 Load | Read both Kaggle files and join them into one table |
| 2 Privacy | Card number → `**** 2095`, card → secret ID `C_3298fc2482`, birth date → age band, state → region, names and addresses deleted |
| 3 Rules | Learn what "too big", "night", "risky shop" and "unusual for this person" mean, from the **train** file only |
| 4 Evaluate | Test the rules on the **test** file they never saw: how many frauds did we catch? |
| 5 Charts | Save the report pictures in `outputs/charts/` |
| 6 Dashboard | Save the safe CSV and write the Tableau file `dashboard/fraud_dashboard.twb` |

## Step 7: Look at the results

| File | What is inside |
|---|---|
| `outputs/metrics.json` | Precision, recall and F1 for each rule and for all rules together |
| `outputs/privacy_report.json` | The k-anonymity checks (FAIL then PASS) and a before/after example |
| `outputs/rule_tuning.csv` | Why the threshold is 3 (it had the best F1 on train) |
| `outputs/charts/*.png` | The 5 report charts |
| `data/processed/transactions_protected.csv` | The safe data Tableau uses (about 265 MB) |

## Step 8: Open the dashboard in Tableau

1. Open **Tableau Public**.
2. Click **File → Open** and choose `dashboard/fraud_dashboard.twb`.
3. Wait 20 to 60 seconds while Tableau reads 1.85 million rows.
4. The **Fraud & Privacy Dashboard** appears, with KPIs on top, 6 charts and filters on the right.

**If Tableau says it cannot find the data file:** click **Browse**, choose `data/processed/transactions_protected.csv`, and click **Open**.

**To match the report numbers:** in the **Dataset Split** filter, select only **test**. By default the dashboard shows train and test together.

**Try the filters:** pick a category or a region, and every chart updates.

## Step 9: Save and take screenshots

* **Save on your Mac:** File → Save As (`.twbx` packs the data inside the file).
* **Publish online (optional):** File → Save to Tableau Public. It is safe, because the file contains no names, card numbers or addresses.
* **Screenshots for the report:** press Cmd + Shift + 4, then Space, then click the Tableau window. Rename the files and move them into `dashboard/screenshots/`:
  * `01_dashboard_overview.png`: the full dashboard, no filters
  * `02_dashboard_test_filter.png`: with Dataset Split = test
  * `03_filter_panel.png`: the filter panel
  * `04_tooltip.png`: hovering over a bar

## If something goes wrong

| Problem | Fix |
|---|---|
| `uv: command not found` | Reopen Terminal, or redo Step 1 |
| `FileNotFoundError: data/raw/fraudTrain.csv` | Redo Step 4 |
| You moved the project folder and Tableau cannot find the data | Run Step 6 again. It rewrites the `.twb` with the new folder path |
| Tableau shows a red `!` next to the data source | Right-click the data source → Edit Data Source → pick the CSV again |
| A chart looks empty | Check the filters, and click "All" in each one |
| Your Mac is slow during Step 6 | Normal. It is processing 1.85 million rows. Wait about 2 minutes |

## Change a setting (optional)

All settings live in `src/config.py`. For example, to make the "above usual spend" rule stricter, change `ABOVE_USUAL_FACTOR = 5.0` to `10.0`, then run Step 6 again. The metrics, charts and dashboard all update together.
