# HW2 Documentation

## R1 Two Pandera Contracts

### Dataset Integrity and Impossible Values

The filtered dataset (`8,231` accident records) **contains no physically impossible or sentinel-encoded values** in any of the 11 retained columns:

- **No zero-as-missing sentinels (`SENTINEL_COLUMNS = ()`):** Unlike datasets that encode unmeasured readings as `0`, every numerical feature (`Visibility_m`, `Congestion_Index`, `Actual_Response_Time_min`) is strictly positive (`> 0`), and `Hour = 0` validly represents midnight. Genuine missing values in `Visibility_m` (`264` rows, ~3.2%) are already represented as `NaN` in the source file.
- **Note on upstream data quirks (not impossible values):**
  - `Weather` contains inconsistent casing and leading/trailing whitespace (`"Rain"`, `"rain"`, `"Rain "`, `" RAIN"`). A Pandera `@pa.parser` normalizes these (`str.strip().str.lower()`) before checking membership in `{"clear", "rain", "snow", "fog"}`.
  - `Intersection_Type` uses the literal string `"None"` (3,596 rows) to mean *no intersection*, which must be preserved via `keep_default_na=False` at load time rather than treated as `NaN`.
  - Columns with known corruption in the raw Kaggle table (such as `Recorded_Speed_kmh` containing `999 km/h` placeholders and `Record_ID` containing duplicate IDs) were excluded during feature selection.

---

### Declared Schema Contracts (`SCHEMA_VERSION = "1.0.0"`)

Even though no current record violates domain bounds, explicit upper and lower bounds act as a **data contract** to catch upstream pipeline corruption, unit mismatches (e.g., visibility reported in millimeters instead of meters, or response times in seconds instead of minutes), or accidental inclusion of non-accident rows (`Actual_Response_Time_min == 0`).

### Boundary & Domain Constraints

| Column | Type | Nullable | Constraint | Rationale / Corruption Caught |
| :--- | :--- | :--- | :--- | :--- |
| `Hour` | `int` | No | `0 <= x <= 23` | Standard 24-hour clock bounds. |
| `Month` | `int` | No | `1 <= x <= 12` | Calendar month bounds. |
| `Area_Type` | `str` | No | `isin(["Urban", "Suburban", "Rural"])` | Rejects unknown or mistyped area categories. |
| `Road_Type` | `str` | No | `isin(["Interstate", "Arterial", "Collector", "Local"])` | Rejects invalid road classifications. |
| `Intersection_Type` | `str` | No | `isin(["4-Way", "T-Junction", "Roundabout", "None"])` | Ensures literal `"None"` was not parsed as `NaN`. |
| `Road_Condition` | `str` | No | `isin(["Dry", "Wet", "Snowy", "Icy", "Standing Water"])` | Rejects unrecognized surface states. |
| `Weather` | `str` | No | `isin(["clear", "rain", "snow", "fog"])` *(after strip + lowercase)* | Normalizes formatting noise; rejects unknown weather labels. |
| `Visibility_m` | `float` | Yes | `0 < x <= 15000.0` | Rejects `0` or negative distances and sensor/unit overflows (`MAX_VISIBILITY = 15000.0`). Allows `NaN`. |
| `Congestion_Index` | `float` | No | `0 < x <= 100.0` | Enforces the `[0, 100]` index scale (`MAX_CONGESTION = 100.0`) and catches zero-corrupted rows. |
| `Dispatch_Priority` | `str` | No | `isin(["Standard", "Medium", "High"])` | Rejects invalid priority tiers. |
| `Actual_Response_Time_min` | `float` | No* | `0 < x <= 1000.0` | `gt=0` blocks unfiltered non-accident rows (`0.0`); `le=1000.0` (`MAX_RESPONSE_TIME`) catches sentinel placeholders (like `9999`) or seconds-to-minutes unit errors, even though real data peaks at `56.6` min. |

*\*In `PredictionInput`, `Actual_Response_Time_min` is `Optional` and `nullable=True` because serving payloads omit the target label.*

### Structural & Table-Level Checks

- **`RawMeasurements` (Ingestion Gate):**
  - `strict = True` and `unique_column_names = True` prevent unexpected or duplicate columns from entering ingestion.
  - `no_duplicate_rows` dataframe check rejects exact duplicate records that would distort train/test splits and inflate evaluation metrics.
- **`ModelInput` (Training & Pipeline Gate):**
  - `strict = True` and `ordered = True` enforce exact column order matching `FEATURE_COLUMNS + [TARGET_COLUMN]`, verified at module import time.
- **`PredictionInput` (Serving Gate):**
  - Inherits all feature constraints from `ModelInput`, makes `Actual_Response_Time_min` optional, and sets `ordered = False` to accept unordered JSON payloads before column alignment.


## R2 Validation gate

### Validation Failure Demonstration

To demonstrate the data contract rejecting corrupted input, the `make validate-broken` target runs the validation pipeline against a deliberately malformed batch (`data/broken/broken-batch.csv`) without modifying the tracked dataset. As shown below, the Pandera schema catches the contract violations and aborts execution before any downstream pipeline stages can run.

```
mlops-project ❯ make validate-broken
uv run python src/main.py check-file
[FAIL] RawMeasurements v1.0.0 on broken_batch.csv — 8209 rows
  3 failure case(s)

    row  column             check                            failure_case
  -----  ------------------ -------------------------------- ------------------------
     37  Hour               less_than_or_equal_to(23)        122
     52  Weather            isin(['clear', 'rain', 'snow', 'fog']) tornado
     23  Actual_Response_Time_min greater_than(0)                  -15.9

  by check : {"less_than_or_equal_to(23)": 1, "isin(['clear', 'rain', 'snow', 'fog'])": 1, "greater_than(0)": 1}
  by column: {"Hour": 1, "Weather": 1, "Actual_Response_Time_min": 1}

  Two summaries because they answer different questions:
  'what rule broke' tells you how to fix the data;
  'which column'    tells you who to talk to.
```

## R3 Slice Evaluation

### Imputation Impact

Slices are evaluated on **raw values** prior to the `ColumnTransformer` preprocessing steps (`SimpleImputer(strategy="median")` and `StandardScaler` for numeric features; `SimpleImputer(strategy="most_frequent")` and `OneHotEncoder` for categorical features).

Had slices been computed after imputation and scaling instead:
- **Numeric imputation and scaling:** Missing `Visibility_m` values (`264` rows) would be replaced by the imputed median before grouping, shifting those records into the median's slice bucket and changing slice sample counts (`n`), target spread (`Actual_Response_Time_min`), and per-slice error metrics. Scaling first would shift features to standardized units rather than raw physical measurements.
- **Categorical imputation:** Any missing categorical values would be folded into the most frequent category (`strategy="most_frequent"`), increasing that category's `n` and mixing imputed rows into its target spread and error metrics.

## R4 Model Acceptance Criteria and Threshold Derivation

- **Criteria version:** `1.1.0` (bumped from `1.0.0` when `slice_rules.min_support` was raised from `30` to `50`).
- **Champion baseline:** `mlflow://ambulance-response-regressor@champion` (version `2`, run `7242d0667b344e55ad4b1d95fdacbc2b`), achieving `RMSE = 3.6521` min, `MAE = 2.8967` min, and `R² = 0.7859`.
- **Latest gate verdict:** `GO` (`21` passed, `0` failed, `1` skipped).

### Trivial Baseline Comparison

A constant mean predictor on `Actual_Response_Time_min` has an error scale bounded by the target's dispersion (`8.11` min standard deviation across the `8,231` records, spanning `4.8` to `56.6` min) and yields `R² ≈ 0.0` on held-out data.

- **RMSE ceiling vs. trivial baseline:** The maximum allowed `RMSE` of `4.5` min sits well below the `~8.11` min constant-mean error scale while leaving margin above the champion's `3.6521` min.
- **R² floor vs. trivial baseline:** The minimum allowed `R²` of `0.70` sits well above a constant predictor's `~0.0` baseline while allowing a `~0.086` drop below the champion's `0.7859`.

### Threshold Justifications

| Criterion / Parameter | Configured Value | Measured Project Reference & Derivation |
| :--- | :--- | :--- |
| `minimum.r2` | `0.70` | Champion `R²` is `0.7859` versus `~0.0` for a constant predictor. Set to `0.70` to catch weak models while allowing moderate split variance. |
| `maximum.rmse` | `4.5` | Champion `RMSE` is `3.6521` min versus `~8.11` min target standard deviation for a constant predictor. Set to `4.5` min (`+0.8479` min above champion) to catch severe regressions while staying far below the trivial baseline. |
| `maximum.mae` | `3.5` | Champion `MAE` is `2.8967` min. Set to `3.5` min (`+0.6033` min above champion) to block major absolute-error degradation. |
| `regression.primary_metric` & `max_drop` | `rmse`, `0.3` | `rmse` is the primary metric against champion `3.6521` min (`delta = 0.0` in the latest run). A `0.3` min tolerance catches meaningful 

## R6 - Demonstrating the gate refuses a model with NO-GO

```
// changed max_iter from 300 to 1 in params.yaml
> make repro

...

Running stage 'evaluate':                                                                                                                                                                                             
> uv run python src/main.py evaluate
evaluate:
{
  "rmse": 7.5917,
  "mae": 5.9252,
  "r2": 0.0748
}
  12 slice group(s) across 4 axes -> metrics/slices.json
  metrics also logged to MLflow run d91e6c03486e46bf8ab03685e8568ee2

Updating lock file 'dvc.lock'                                                                                                                                                                                         

Running stage 'gate':                                                                                                                                                                                                 
> uv run python src/main.py gate

Cannot run `gate` yet:
  NO-GO. 16 acceptance criteria failed: minimum.r2, maximum.mae, maximum.rmse, regression.rmse, slice.weather.clear, slice.weather.fog, slice.weather.rain, slice.weather.snow, slice.area_type.rural, slice.area_type.urban, slice.dispatch_priority.high, slice.dispatch_priority.medium, slice.dispatch_priority.standard, slice.visibility_missing.visibility_present, fairness.area_type.rmse_gap, fairness.area_type.mae_gap. See reports/gate.json for the numbers, or run `make gate` to print them. The model is still on disk — a failing gate stops a release, not an investigation.

ERROR: failed to reproduce 'gate': failed to run: uv run python src/main.py gate, exited with 1 
make: *** [Makefile:110: repro] Error 255

> make register
uv run python src/main.py register

Cannot run `register` yet:
  The recorded verdict is NO-GO (criteria v1.1.0): minimum.r2, maximum.mae, maximum.rmse, regression.rmse, slice.weather.clear, slice.weather.fog, slice.weather.rain, slice.weather.snow, slice.area_type.rural, slice.area_type.urban, slice.dispatch_priority.high, slice.dispatch_priority.medium, slice.dispatch_priority.standard, slice.visibility_missing.visibility_present, fairness.area_type.rmse_gap, fairness.area_type.mae_gap. Refusing to release.

make: *** [Makefile:232: register] Error 1

```

## R8 fairness checks accross groups

### Chosen Axis, Rationale, and Gating Decision

- **Chosen axis:** `area_type` (`Urban`, `Suburban`, `Rural`).
- **Observed gaps:** Across the test set (`n = 725` Urban, `n = 632` Suburban, `n = 285` Rural), the within-axis `RMSE` gap is `0.1474` min (`rural` `3.7439` vs. `urban` `3.5966`) and the `MAE` gap is `0.1739` min.
- **Why `area_type` instead of another axis:** `area_type` captures structural geography and regional service coverage. Emergency dispatch stakeholders care directly whether rural or suburban communities experience systematically worse response-time accuracy than urban centers. By contrast, `weather` reflects transient meteorological conditions (`fog` has higher error at `4.0128` min, `n = 129`), `dispatch_priority` may reflect synthetic generator coupling with the target, and `visibility_missing` has insufficient support (`n = 33`, skipped below `min_support: 50`).
- **Gated vs. report-only:** `area_type` should be **gated** (`max_rmse_gap: 2.0`, `max_mae_gap: 1.5` in `params.yaml`) rather than report-only. Because `area_type` has strong support across all three groups (`n >= 285`) and represents persistent geographic equity rather than temporary weather noise, a large disparity here indicates a structural model failure that should block promotion.

### Unaudited Group and What Would Have Had to Happen

- **Group we cannot audit:** Less-developed or lower-income areas (or specific local neighborhoods/districts) where emergency response may be uneven.
- **Why it is not possible:** Our dataset has no neighborhood, district, or income/development labels.
- **What would have had to happen, and when:** Labels showing local areas or development/income levels would have needed to be recorded when the data was first collected or generated.