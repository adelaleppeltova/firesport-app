**EN** · [CZ](ml-baseline.md) · [Project](../README.md)

# Machine learning baseline

This documents the implemented baseline, without new experiments, benchmark claims or scientific conclusions. An unusual performance is a final time that Isolation Forest classifies as an outlier within one athlete's eligible history, category group and window. It is not automatically a data error or evidence of exceptional ability.

## Inputs and category grouping

The sole feature is `results.final_time`. [`recompute_for_window`](../backend/app/services/anomaly_service.py) selects `final_time_status="valid"`, non-null final times and dates within both inclusive window boundaries. It groups by `(athlete_id, category_group)` and fits each group separately. Neither competition context nor the temporal order of times is a model feature.

The [fixed category mapping](../backend/app/ml/anomaly_config.py) trims and lowercases names:

| Group | Category names mapped together |
| --- | --- |
| `muz` | Muži, Dorostenci, Starší dorostenci, Muži a starší dorostenci, Muži HZS |
| `zena` | Ženy, Dorostenky, Mladší dorostenky, Střední dorostenky, Starší dorostenky, Ženy a starší dorostenky |
| `mladsi_dorostenci` | Mladší dorostenci, Střední dorostenci, Dorostenci střední |

An unknown normalized category name forms its own group. An unresolved category ID becomes its own identifier; an absent category uses `unknown`. These are manually defined comparability assumptions, not learned age adjustments. `quality_flag="suspicious"` does not exclude an otherwise eligible time.

## Rolling windows and recomputation

The default `yearly_3y` anchor is December 31 at midnight UTC. [`windows.py`](../backend/app/services/windows.py) computes:

```text
window_end   = anchor
window_start = anchor - 3 years + 1 day
```

For `2025-12-31`, the inclusive window is `2023-01-01` through `2025-12-31`; adjacent windows overlap by two years. The final year's year-end anchor is generated even when the latest data is earlier in that year. Date bounds therefore select years with data, not strictly only anchors before the supplied upper date. Bounds are midnight timestamps, not an end-of-day expansion.

`POST /v1/ml/recompute-yearly` accepts query parameters `from`, `to` and `force`. Omitted bounds come from minimum/maximum `results.date`. With `force=false`, an existing active anchor is skipped. Recomputing supersedes the previous run (`is_superseded=true`), deletes its scores and creates a new run ID. Old run metadata remains, but historical scores are not a permanent archive. There is no automatic recomputation after ordinary JSON import.

## Eligibility guards and parameters

The service skips groups below 10 results (`not_enough_data`). The [numerical helper](../backend/app/ml/isolation_forest.py) converts to float64 and removes NaN and positive/negative infinity. Fewer than 10 remaining values yields `not_enough_data_after_cleaning` (or `not_enough_data` if nothing was removed). Standard deviation `numpy.std(times) < 0.01` seconds yields `low_variance`.

| Parameter | Effective default |
| --- | --- |
| feature | `final_time` (seconds), one column |
| `min_results` | `10` |
| `eps_std` | `0.01` s |
| `n_estimators` | `200` |
| `contamination` | `"auto"` |
| `random_state` | `42` |
| `n_jobs` | `-1` |
| `max_samples` | scikit-learn default `"auto"` |

[AnomalyConfig](../backend/app/ml/anomaly_config.py) is immutable. The pipeline does not specify a target percentage of outliers or its own quantile threshold. A fixed seed supports repeatability for the same ordered data and software environment; Python dependencies are not pinned, so it does not guarantee identical results across installations.

## Scores, labels and direction

```python
X = times.reshape(-1, 1)
model.fit(X)
score = -model.decision_function(X)
is_anomaly = model.predict(X) == -1
```

Higher scores mean greater outlierness within that fitted model. They are not calibrated probabilities or directly comparable across athletes/windows. For flagged results only, times below the cleaned group median are `fast`, above it `slow`; equal-to-median and all non-anomalous times are `none`. The median describes direction, not the classification threshold. Training and scoring use the same historical observations; this is retrospective detection, not held-out prediction.

## Persistence and application delivery

One window run stores `run_id`, creation time, window type/bounds/years, minimum count, model parameters, feature and score definition, status and counters (`processed`, `skipped`, `failed`, `scores_inserted`, skip reasons) in `anomaly_runs`. Counters for processed/skipped refer to athlete/category groups, not individual results.

`anomaly_scores` stores **every scored result** in successful groups: run, athlete and result references, date/time, score, median, anomaly label, direction, contamination mode and category group. Fitted estimator objects are not serialized. The [anomaly router](../backend/app/api/v1/athlete_anomalies_router.py) joins competition and `quality_flag` information from source results.

`GET /v1/ml/windows` lists stored windows and optionally filters by athlete. `GET /v1/athletes/{athlete_id}/anomalies` chooses a run by `run_id`, `anchor_date`, or latest active yearly run, with optional `category_group`. The default run is global, so an athlete may have no scores in it. The [statistics screen](../frontend/src/pages/StatisticsPage.jsx) consumes these stored outputs.

## Quality flags are a separate layer

[Deterministic rules](../backend/app/services/quality_flag_service.py) store `ok`/`suspicious` directly on results:

1. For the same exact category, `low=max(11, Q01)` and `high=min(45, Q99)` from valid final times. A valid time outside these bounds is suspicious; without times the fallback is 11–45 s.
2. With five previous valid times for the same athlete and exact category, a time greater than 125% of their median is suspicious. History is restricted to earlier dates.
3. Invalid or missing times receive `ok`, which does not mean the performance was valid.

Import-time flags use the database available at that point and a per-importer bounds cache; unpaired results receive `ok`. Errors computing a flag also fall back to `ok`. A full quality recomputation can differ from import-time flags. These rules are not Isolation Forest, and notebook EDA flags use yet another definition.

## Running and interpreting the baseline

After importing data, resolve eligible results without an athlete reference before requesting recomputation. Use the [full procedure](reproducibility.md) for inspection and commands. On an isolated local stack the request is:

```bash
curl --fail-with-body -X POST 'http://localhost:8000/v1/ml/recompute-yearly?force=false'
curl --fail-with-body 'http://localhost:8000/v1/ml/windows'
```

Inspect per-anchor and per-group failures even if the HTTP request succeeds. Re-run with `force=true` after data or identity changes to replace stale scores. These mutation routes currently have no authentication dependency.

## Methodological and implementation limitations

- No labelled ground truth, precision/recall/F1, cross-validation, score calibration or benchmark evaluation is implemented. Anomaly percentages are not accuracy metrics.
- Missing weather, track, equipment, competition context and age-adjusted development limit interpretation. This is not a context-aware hierarchical model.
- Small and incomplete histories are excluded; different category mappings or identity decisions change eligible groups. Overlapping windows are dependent views of history.
- The selection query does not require an `athlete` field, but grouping uses `r["athlete"]`. A valid unresolved result can therefore fail a whole window before group-level handling. The batch can return HTTP success containing failed anchors.
- Numerical cleaning drops non-finite values, while persistence aligns the outputs with original results by position. Non-finite database values are not safely handled by the complete pipeline.
- Scores and runs are written separately without a transaction. Superseding deletes prior scores before a new run completes; concurrent recomputation and partial failure are not robustly isolated.
- Data/version changes, import ordering and unpinned dependencies prevent a promise of byte-identical outputs.

[Unit tests](../backend/app/tests/test_isolation_forest.py) cover minimum sample size, non-finite cleaning, low variance, deterministic repetition, negated decision scores and prediction labels. [Window tests](../backend/app/tests/test_windows.py) cover rolling boundaries; they do not provide scientific model validation.
