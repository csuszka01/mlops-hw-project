"""Slice-based evaluation, score the same test set group by group.

Every function takes the raw frame, before imputation, so a missing value stays a slice of its own.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from fairlearn.metrics import MetricFrame
from sklearn.exceptions import UndefinedMetricWarning
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

from .fairness import fairness_report
from .schemas import SENTINEL_COLUMNS

# Bands are left-closed, [21, 30) is 21 to 29.
BIN_CLOSED_LEFT = True

# Label for a value that falls in no declared band.
OUT_OF_RANGE = "out_of_range"


def _as_float(frame: pd.DataFrame, column: str) -> pd.Series:
    """The raw column as numbers, with unparseable cells becoming NaN."""
    if column not in frame.columns:
        raise KeyError(
            f"Slice column {column!r} is not in the frame. Available: "
            f"{list(frame.columns)}"
        )
    return pd.to_numeric(frame[column], errors="coerce")


def slice_labels(frame: pd.DataFrame, spec: dict) -> pd.Series:
    """Turn one slice specification from `params.yaml` into a column of labels.

    `frame` must be the raw frame. The kinds are `bins` (cut a numeric column),
    `category` (one group per value) and `missing_flag` (recorded or not).
    """
    kind = spec.get("kind", "bins")
    column = spec["column"]

    # CHANGED, new kind, one group per value of the column
    if kind == "category":
        if column not in frame.columns:
            raise KeyError(f"Slice column {column!r} is not in the frame.")
        return frame[column].astype("string").str.strip().str.lower().astype("object")

    values = _as_float(frame, column)
    sentinel = column in SENTINEL_COLUMNS
    is_missing = (values == 0) | values.isna() if sentinel else values.isna()

    if kind == "missing_flag":
        present, absent = spec.get("labels", [f"{column}_present", f"{column}_missing"])
        return pd.Series(
            np.where(is_missing, absent, present), index=frame.index, dtype="object"
        )

    if kind != "bins":
        raise ValueError(
            f"Unknown slice kind {kind!r} for column {column!r}; "
            "expected 'bins', 'category' or 'missing_flag'."
        )

    edges = [float(edge) for edge in spec["bins"]]
    labels = list(spec["labels"])
    if len(labels) != len(edges) - 1:
        raise ValueError(
            f"Slice on {column!r} declares {len(edges) - 1} bin(s) but "
            f"{len(labels)} label(s); they must match."
        )

    banded = pd.cut(
        values, bins=edges, labels=labels, right=not BIN_CLOSED_LEFT, include_lowest=False
    )
    out = pd.Series(banded.astype("object"), index=frame.index)
    out = out.where(~out.isna(), OUT_OF_RANGE)
    missing_label = spec.get("missing_label")
    if missing_label:
        out = out.mask(is_missing, missing_label)
    return out


# CHANGED, regression metrics, the y_prob argument is gone
def group_scores(y_true, y_pred, groups) -> pd.DataFrame:
    """One row per group, one column per metric, from fairlearn's MetricFrame."""
    frame = MetricFrame(
        metrics={
            "rmse": root_mean_squared_error,
            "mae": mean_absolute_error,
            "r2": r2_score,
        },
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=groups,
    )
    return frame.by_group


METRIC_KEYS = ("rmse", "mae", "r2")  # CHANGED


def _r(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


# CHANGED, regression version, no positives and no y_prob
def group_metrics(y_true, y_pred, groups) -> dict:
    """Metrics for every group, as {group: {metric: value}} with plain values.

    `r2` is None when it is undefined for the group. Read every metric together with `n`.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    groups = pd.Series(groups).astype(str).to_numpy()
    # A group with a single row has no R2, the records below say None instead.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UndefinedMetricWarning)
        table = group_scores(y_true, y_pred, groups)

    records = {}
    for group in sorted(set(groups)):
        row = table.loc[group] if group in table.index else {}
        record = {"n": int((groups == group).sum())}
        record.update({key: _r(row.get(key)) for key in METRIC_KEYS})
        records[group] = record
    return records


# CHANGED, the signature has no y_prob
def slice_report(
    raw_frame: pd.DataFrame,
    y_true,
    y_pred,
    slice_specs: dict,
) -> dict:
    """Score every declared slice and every group inside it.

    Returns a plain dict (no pandas), so it can go into JSON, MLflow and tests.
    It only measures, `gates.py` decides.
    """
    if not slice_specs:
        return {}

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    report: dict = {
        "n_rows": int(len(raw_frame)),
        "slices": {},
        "fairness": {},
    }

    for name, spec in slice_specs.items():
        labels = slice_labels(raw_frame, spec)
        groups = group_metrics(y_true, y_pred, labels)
        report["slices"][name] = {group: groups[group] for group in _group_order(spec, labels)}
        # Fairness is measured for every axis, `acceptance` picks the gated ones.
        report["fairness"][name] = fairness_report(y_true, y_pred, labels)

    return report


def _group_order(spec: dict, labels: pd.Series) -> list:
    """Group labels in declaration order, then any unexpected label, sorted."""
    declared = list(spec.get("labels", []))
    if spec.get("missing_label"):
        declared.append(spec["missing_label"])
    present = set(labels.unique())
    ordered = [label for label in declared if label in present]
    ordered += sorted(str(label) for label in present if label not in declared)
    return ordered


def format_slices(report: dict, aggregate: dict | None = None) -> str:
    """The slice table, for the CLI. One row per group, `n` always visible."""
    if not report or not report.get("slices"):
        return (
            "No slice report, `evaluation.slice_report` returned nothing.\n"
            "  Check the evaluation block in params.yaml."
        )

    lines = [f"{report['n_rows']} rows"]
    if aggregate:
        lines.append(
            "  aggregate      "
            + "  ".join(f"{k} {v:.4f}" for k, v in aggregate.items() if v is not None)
        )

    def cell(value) -> str:
        return "    —  " if value is None else f"{value:7.4f}"

    for name, groups in report["slices"].items():
        lines.append("")
        lines.append(f"  slice  {name}")
        lines.append(f"  {'group':<18} {'n':>5} {'rmse':>7} {'mae':>7} {'r2':>7}")
        lines.append(f"  {'-' * 18} {'-' * 5} " + " ".join(["-" * 7] * 3))
        for group, m in groups.items():
            lines.append(
                f"  {group:<18} {m['n']:>5} "
                f"{cell(m['rmse'])} {cell(m['mae'])} {cell(m['r2'])}"
            )
    return "\n".join(lines)