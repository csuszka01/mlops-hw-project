"""Group-fairness metrics with fairlearn: rates per group, and the gaps between groups.

Rates per group: selection rate, TPR and FPR. Gaps (the largest rate minus the
smallest): demographic parity (selection rate), equal opportunity (TPR) and
equalized odds (the larger of the TPR and FPR gaps).
Reference: https://fairlearn.org/main/user_guide/assessment/common_fairness_metrics.html
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from fairlearn.metrics import MetricFrame
from sklearn.metrics import mean_absolute_error, root_mean_squared_error


# Smaller groups are reported, but left out of the gaps. fairlearn has no such rule.
MIN_GROUP_FOR_GAP = 5


def rates_by_group(y_true, y_pred, groups) -> pd.DataFrame:
    """One row per group, with the columns rmse and mae."""
    # CHANGED, error per group instead of selection rate, tpr and fpr
    frame = MetricFrame(
        metrics={
            "rmse": root_mean_squared_error,
            "mae": mean_absolute_error,
        },
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=groups,
    )

    return frame.by_group



def gaps(y_true, y_pred, groups) -> dict:
    """The gaps between the groups, as a dict of floats in minutes."""
    # CHANGED, the largest error minus the smallest, instead of the classification gaps
    table = rates_by_group(y_true, y_pred, groups)
    return {
        "rmse_gap": float(table["rmse"].max() - table["rmse"].min()),
        "mae_gap": float(table["mae"].max() - table["mae"].min()),
    }


def _r(value):
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def fairness_report(y_true, y_pred, groups) -> dict:
    """Errors and gaps for one axis, as plain JSON-able values rounded to 4 decimals.

    Only groups with at least MIN_GROUP_FOR_GAP rows enter the gaps; with fewer
    than two such groups the gaps are None.
    """
    # CHANGED, floats instead of ints, and no positives or negatives
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    groups = pd.Series(groups).astype(str).to_numpy()

    errors = rates_by_group(y_true, y_pred, groups)
    report_groups = {}
    for group in sorted(set(groups)):
        n = int((groups == group).sum())
        row = errors.loc[group] if group in errors.index else {}
        report_groups[group] = {
            "n": n,
            "rmse": _r(row.get("rmse")),
            "mae": _r(row.get("mae")),
        }

    comparable = [g for g, r in report_groups.items() if r["n"] >= MIN_GROUP_FOR_GAP]
    rows = np.isin(groups, comparable)
    measured = (
        gaps(y_true[rows], y_pred[rows], groups[rows]) if len(comparable) >= 2 else {}
    )
    return {
        "groups": report_groups,
        "rmse_gap": _r(measured.get("rmse_gap")),
        "mae_gap": _r(measured.get("mae_gap")),
        "min_group_for_gap": MIN_GROUP_FOR_GAP,
    }


def format_fairness(report: dict, gated_axes=()) -> str:
    """The fairness tables, for the CLI."""
    if not report:
        return "No fairness report."

    def cell(value) -> str:
        return "    —  " if value is None else f"{value:7.4f}"

    lines = []
    for axis, block in report.items():
        marker = "  [GATED]" if axis in gated_axes else "  (report only)"
        lines.append("")
        lines.append(f"  axis: {axis}{marker}")
        # CHANGED, rmse and mae columns instead of the classification rates
        lines.append(f"  {'group':<18} {'n':>5} {'rmse':>7} {'mae':>7}")
        lines.append(f"  {'-' * 18} {'-' * 5} {'-' * 7} {'-' * 7}")
        for group, r in block["groups"].items():
            lines.append(
                f"  {group:<18} {r['n']:>5} {cell(r['rmse'])} {cell(r['mae'])}"
            )
        lines.append(
            f"    rmse gap (worst group minus best, minutes): "
            f"{cell(block['rmse_gap']).strip()}"
        )
        lines.append(
            f"    mae gap  (worst group minus best, minutes): "
            f"{cell(block['mae_gap']).strip()}"
        )
    return "\n".join(lines)
