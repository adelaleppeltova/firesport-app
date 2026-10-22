**EN** · [CZ](README.cs.md) · [Project](../../README.md)

# Exploratory data analysis notebook

[`eda.ipynb`](eda.ipynb) explores the **versioned JSON before MongoDB import** using helpers in [`docs/analysis`](../analysis). It does not read the live database, resolve canonical athlete identities or execute the application Isolation Forest pipeline. It needs no account, Docker or secrets.

## Inputs, dependencies and order

The first cell locates the project root by looking for `docs/` and `data/` in the working directory or its parents (up to five iterations) and adds it to `sys.path`. Start from the repository root or `docs/notebooks/`. Data loading recursively reads sorted `data/**/*.json`; keep the full checkout, including the analysis helpers.

Imported packages are pandas, Matplotlib, seaborn and `IPython.display`; Python's `pathlib`, `sys` and `json` are also used. The backend requirements do not install these notebook dependencies, and there is **no dedicated notebook lockfile**. The example below adds nbformat/nbclient/ipykernel only for headless execution. Use an isolated environment; no project dependency files need to change.

Execute all cells from top to bottom in a fresh kernel: root discovery → imports/style → source loading and flattened frames → dataset and time summaries → distributions/category counts/IQR outliers → quality and identity checks → yearly/monthly coverage → narrative interpretation. Later cells reuse variables created earlier; isolated cell execution can fail or show stale state.

```bash
# From the repository root / Z kořene repozitáře
python3.12 -m venv /tmp/flamma-eda-venv
. /tmp/flamma-eda-venv/bin/activate
python -m pip install pandas matplotlib seaborn ipython nbformat nbclient ipykernel
python - <<'PYEDA'
from pathlib import Path
import nbformat
from nbclient import NotebookClient
nb = nbformat.read("docs/notebooks/eda.ipynb", as_version=4)
NotebookClient(
    nb, kernel_name="python3", timeout=120,
    resources={"metadata": {"path": str(Path.cwd())}},
).execute()
nbformat.write(nb, "/tmp/flamma-eda.executed.ipynb")
PYEDA
deactivate
```

The output copy goes to `/tmp`; do not overwrite the versioned notebook simply to refresh outputs. For interactive work, open it in a Jupyter-capable editor using the same environment/kernel. Record the Git commit, Python and installed package versions with any exported figure.

## Interpretation caveats

- `athlete_count` counts unique constructed full names, not resolved MongoDB athlete identities. Team/code/year variations only identify possible duplicates.
- EDA `suspicious_final_time` means missing final time, non-valid status, a time ≥90 s, or sentinel 999. It is **different from** backend percentile/history quality flags and from Isolation Forest labels.
- EDA missing-birth-year flags use pandas null checks; source year `0` is not considered missing by that helper. The source audit separately counts null **or zero**.
- The distribution's `valid_results` additionally excludes EDA-suspicious times; it is not literally all valid source rows.
- Category grouping includes `discipline`; pandas' default groupby drops null keys, so blocks with missing discipline may be excluded from those summaries.
- Yearly/monthly coverage uses **all `df_results` rows**, although some chart titles say “valid results”. Read them as coverage of all source rows; notebook content was preserved during this documentation task.
- A rolling mean over observed months is a three-row mean, not a calendar-complete monthly series. Missing months are not automatically zero-filled.
- The written findings are existing exploratory statements, not held-out validation or causal claims. Saved outputs are not a substitute for rerunning cells.

## Verification status

See the dated [audit](../documentation-audit.md) for the actual execution outcome and package versions. Inputs and execution order are identifiable, but the lack of an environment lock and source extraction assets prevents a promise of exact historical figures across installations. See [data provenance](../data-baseline.en.md) and [application ML](../ml-baseline.en.md) for their separate meanings.
