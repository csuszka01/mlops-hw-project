"""The model quality gate: acceptance criteria in, a GO or NO-GO verdict out.

The criteria come from the `acceptance` block of `params.yaml`. `evaluate_gate`
is a pure function over plain dicts, so the tests need no files and no services.
Check kinds: minimum, regression, slice and fairness.
"""

from __future__ import annotations

PASS, FAIL, SKIPPED = "pass", "fail", "skipped"
LOWER_IS_BETTER = ("rmse", "mae")

def _round(value):
    return None if value is None else round(float(value), 4)


def _check(**fields) -> dict:
    """One check result. `id`, `kind` and `status` are mandatory by convention."""
    return fields


def evaluate_gate(
    metrics: dict,
    slices: dict,
    baseline: dict,
    acceptance: dict,
) -> dict:
    """Apply every acceptance criterion and return the verdict.

    `metrics` is `metrics/metrics.json`, `slices` is `metrics/slices.json` (may be
    {}), `baseline` is `{"metrics": {...}}` (may be {}), and `acceptance` is the
    block from `params.yaml`. A missing input gives a `skipped` check with a
    reason, never a pass.
    """
    checks: list[dict] = []

    checks += _minimum_checks(metrics, acceptance.get("minimum") or {})
    checks += _maximum_checks(metrics, acceptance.get("maximum") or {})
    regression_checks, deltas = _regression_checks(
        metrics, baseline, acceptance.get("regression") or {}
    )
    checks += regression_checks
    checks += _slice_checks(metrics, slices, acceptance.get("slice_rules") or {})
    checks += _fairness_checks(slices, acceptance.get("fairness") or {})

    passed = sum(1 for c in checks if c["status"] == PASS)
    failed = sum(1 for c in checks if c["status"] == FAIL)
    skipped = sum(1 for c in checks if c["status"] == SKIPPED)

    return {
        "verdict": "NO-GO" if failed else "GO",
        "criteria_version": str(acceptance.get("criteria_version", "unset")),
        "primary_metric": (acceptance.get("regression") or {}).get("primary_metric"),
        "summary": {"passed": passed, "failed": failed, "skipped": skipped},
        "deltas": deltas,
        "checks": checks,
    }


def _minimum_checks(metrics: dict, minimum: dict) -> list[dict]:
    """Absolute floors: one check per metric in `acceptance.minimum`."""
    out = []
    for metric in sorted(minimum):
        required = float(minimum[metric])
        observed = metrics.get(metric)
        if observed is None:
            out.append(
                _check(
                    id=f"minimum.{metric}",
                    kind="minimum",
                    metric=metric,
                    required=_round(required),
                    observed=None,
                    status=SKIPPED,
                    reason=f"{metric} was not recorded by the evaluate stage",
                )
            )
            continue
        out.append(
            _check(
                id=f"minimum.{metric}",
                kind="minimum",
                metric=metric,
                required=_round(required),
                observed=_round(observed),
                status=PASS if float(observed) >= required else FAIL,
                reason=None
                if float(observed) >= required
                else f"{metric} {observed:.4f} is below the floor {required:.4f}",
            )
        )
    return out

# CHANGED, new function, ceilings for the metrics where lower is better
def _maximum_checks(metrics: dict, maximum: dict) -> list[dict]:
    """Absolute ceilings, one check per metric in `acceptance.maximum`."""
    out = []
    for metric in sorted(maximum):
        allowed = float(maximum[metric])
        observed = metrics.get(metric)
        if observed is None:
            out.append(
                _check(
                    id=f"maximum.{metric}",
                    kind="maximum",
                    metric=metric,
                    allowed=_round(allowed),
                    observed=None,
                    status=SKIPPED,
                    reason=f"{metric} was not recorded by the evaluate stage",
                )
            )
            continue
        within = float(observed) <= allowed
        out.append(
            _check(
                id=f"maximum.{metric}",
                kind="maximum",
                metric=metric,
                allowed=_round(allowed),
                observed=_round(observed),
                status=PASS if within else FAIL,
                reason=None
                if within
                else f"{metric} {observed:.4f} is above the ceiling {allowed:.4f}",
            )
        )
    return out


def _regression_checks(metrics: dict, baseline: dict, rules: dict) -> tuple[list, dict]:
    """Is this model worse than the recorded champion on the primary metric?"""
    primary = rules.get("primary_metric")
    max_drop = rules.get("max_drop")
    also = list(rules.get("also_report") or [])
    baseline_metrics = (baseline or {}).get("metrics") or {}

    deltas = {}
    for metric in ([primary] if primary else []) + also:
        if metric and metric in metrics and metric in baseline_metrics:
            deltas[metric] = _round(float(metrics[metric]) - float(baseline_metrics[metric]))

    if not primary or max_drop is None:
        return [
            _check(
                id="regression",
                kind="regression",
                status=SKIPPED,
                reason="acceptance.regression declares no primary_metric/max_drop",
            )
        ], deltas

    if not baseline_metrics:
        return [
            _check(
                id=f"regression.{primary}",
                kind="regression",
                metric=primary,
                observed=_round(metrics.get(primary)),
                baseline=None,
                status=SKIPPED,
                reason="no baseline recorded — run `make baseline-sync` once a "
                "champion exists (metrics/baseline.json is absent or empty)",
            )
        ], deltas

    observed, previous = metrics.get(primary), baseline_metrics.get(primary)
    if observed is None or previous is None:
        return [
            _check(
                id=f"regression.{primary}",
                kind="regression",
                metric=primary,
                observed=_round(observed),
                baseline=_round(previous),
                status=SKIPPED,
                reason=f"{primary} missing from the metrics or the baseline",
            )
        ], deltas

    delta = float(observed) - float(previous)
    # CHANGED, for rmse and mae a rise is the worsening, for r2 a fall is
    worsening = delta if primary in LOWER_IS_BETTER else -delta
    dropped = worsening > float(max_drop)
    return [
        _check(
            id=f"regression.{primary}",
            kind="regression",
            metric=primary,
            baseline=_round(previous),
            observed=_round(observed),
            delta=_round(delta),
            max_drop=_round(max_drop),
            status=FAIL if dropped else PASS,
            reason=(
                f"{primary} got worse by {worsening:.4f} against the champion's "  # CHANGED
                f"{previous:.4f}, past the tolerated {float(max_drop):.4f}"
            )
            if dropped
            else None,
        )
    ], deltas


def _slice_checks(metrics: dict, slices: dict, rules: dict) -> list[dict]:
    """One check per group in the slice report.

    A group with fewer than `min_support` rows is skipped, because its metrics
    mean nothing. Otherwise it fails when its RMSE is above `max_rmse`, or more
    than `max_rmse_gap` above the aggregate RMSE.
    """
    # CHANGED, rmse rules instead of the f1 and positives rules
    min_support = int(rules.get("min_support", 0))
    max_rmse = rules.get("max_rmse")
    max_gap = rules.get("max_rmse_gap")
    aggregate_rmse = metrics.get("rmse")

    if not slices or not slices.get("slices"):
        return [
            _check(
                id="slice",
                kind="slice",
                status=SKIPPED,
                reason="no slice report, the evaluate stage produced no "
                "metrics/slices.json",
            )
        ]

    out = []
    for axis, groups in slices["slices"].items():
        for group, m in groups.items():
            check = _check(
                id=f"slice.{axis}.{group}",
                kind="slice",
                axis=axis,
                group=group,
                n=m["n"],
                rmse=m["rmse"],
            )

            too_small = None
            if m["n"] < min_support:
                too_small = f"support {m['n']} < min_support {min_support}"
            if too_small:
                out.append(dict(check, status=SKIPPED, reason=too_small))
                continue

            gap = None
            if aggregate_rmse is not None and m["rmse"] is not None:
                gap = round(float(m["rmse"]) - float(aggregate_rmse), 4)

            violations: list[str] = []
            if max_rmse is not None and m["rmse"] is not None and float(m["rmse"]) > float(max_rmse):
                violations.append(
                    f"RMSE {float(m['rmse']):.4f} is above max_rmse {float(max_rmse):.4f}"
                )
            if max_gap is not None and gap is not None and gap > float(max_gap):
                violations.append(
                    f"RMSE {float(m['rmse']):.4f} is {gap:.4f} above the aggregate, "
                    f"past max_rmse_gap {float(max_gap):.4f}"
                )

            out.append(
                dict(
                    check,
                    gap_to_aggregate=gap,
                    max_rmse=_round(max_rmse),
                    max_rmse_gap=_round(max_gap),
                    status=FAIL if violations else PASS,
                    reason="; ".join(violations) or None,
                )
            )
    return out


def _fairness_checks(slices: dict, rules: dict) -> list[dict]:
    """Gate each axis named in `rules` with its own limits; the other axes are only reported."""
    out = []
    for axis in sorted(rules):
        if not slices or axis not in (slices.get("fairness") or {}):
            out.append(
                _check(
                    id=f"fairness.{axis}",
                    kind="fairness",
                    axis=axis,
                    status=SKIPPED,
                    reason=f"no fairness report for axis {axis!r}",
                )
            )
            continue

        block = slices["fairness"][axis]
        axis_rules = rules[axis] or {}
        limits = {
            "rmse_gap": axis_rules.get("max_rmse_gap"),
            "mae_gap": axis_rules.get("max_mae_gap"),
        }
        for key, limit in limits.items():
            if limit is None:
                continue
            observed = block.get(key)
            if observed is None:
                out.append(
                    _check(
                        id=f"fairness.{axis}.{key}",
                        kind="fairness",
                        axis=axis,
                        metric=key,
                        limit=_round(limit),
                        observed=None,
                        status=SKIPPED,
                        reason=f"{key} is undefined for this axis (fewer than two "
                        f"groups have at least {block.get('min_group_for_gap')} rows)",
                    )
                )
                continue
            # TODO(student) Exercise 5: set `exceeded` to True when the observed gap
            # is above the limit this axis configures, and to False otherwise.
            exceeded = float(observed) > float(limit)
            out.append(
                _check(
                    id=f"fairness.{axis}.{key}",
                    kind="fairness",
                    axis=axis,
                    metric=key,
                    limit=_round(limit),
                    observed=_round(observed),
                    status=FAIL if exceeded else PASS,
                    reason=f"{key} {observed:.4f} exceeds the limit {float(limit):.4f}"
                    if exceeded
                    else None,
                )
            )
    return out


def format_gate(report: dict) -> str:
    """The verdict as text: headline with the SKIPPED count, failures, skips, then every check."""
    if not report:
        return "No gate report."

    summary = report["summary"]
    lines = [
        f"{report['verdict']} — {summary['passed']} passed, "
        f"{summary['failed']} failed, {summary['skipped']} SKIPPED "
        f"(criteria v{report['criteria_version']})"
    ]

    failures = [c for c in report["checks"] if c["status"] == FAIL]
    if failures:
        lines.append("")
        lines.append("  FAILED:")
        for c in failures:
            lines.append(f"    {c['id']:<40} {c.get('reason')}")

    skips = [c for c in report["checks"] if c["status"] == SKIPPED]
    if skips:
        lines.append("")
        lines.append("  SKIPPED (not checked — read these before you trust the verdict):")
        for c in skips:
            lines.append(f"    {c['id']:<40} {c.get('reason')}")

    lines.append("")
    lines.append(f"  {'check':<40} {'status':<8} detail")
    lines.append(f"  {'-' * 40} {'-' * 8} {'-' * 40}")
    for c in report["checks"]:
        lines.append(f"  {c['id']:<40} {c['status']:<8} {_detail(c)}")

    if report.get("deltas"):
        lines.append("")
        lines.append("  versus the recorded champion:")
        for metric, delta in report["deltas"].items():
            arrow = "+" if delta >= 0 else ""
            lines.append(f"    {metric:<12} {arrow}{delta:.4f}")
    return "\n".join(lines)


def _detail(check: dict) -> str:
    kind = check.get("kind")
    if kind == "minimum":
        return f"observed {check.get('observed')} vs floor {check.get('required')}"
    if kind == "maximum":
        return f"observed {check.get('observed')} vs ceiling {check.get('allowed')}"
    if kind == "regression":
        if check.get("delta") is None:
            return check.get("reason") or ""
        return (
            f"{check.get('observed')} vs champion {check.get('baseline')} "
            f"(delta {check['delta']:+.4f}, tolerated {check.get('max_drop')})"  # CHANGED, was tolerated -
        )
    if kind == "slice":
        if check["status"] == SKIPPED:
            return check.get("reason") or ""
        return (
            f"n={check.get('n')} rmse={check.get('rmse')} "  # CHANGED, was pos and f1
            f"gap={check.get('gap_to_aggregate')}"
        )
    if kind == "fairness":
        return f"observed {check.get('observed')} vs limit {check.get('limit')}"
    return check.get("reason") or ""

def format_gate_markdown(report: dict) -> str:
    """The gate verdict as GitHub-flavoured markdown, for a job summary.

    Why this lives here rather than as a shell heredoc inside the workflow:
    a `run:` block is the one place in a project that nothing tests. Logic that
    ends up there is invisible to the linter, invisible to pytest, and only
    runs on a machine you have to push to in order to observe. Keep workflows
    thin -- checkout, install, invoke -- and put anything with a branch in it
    somewhere a test can reach.
    """
    if not report:
        return "### Gate\n\nNo verdict recorded — the gate never ran.\n"

    verdict = report["verdict"]
    summary = report.get("summary", {})
    mark = "PASS" if verdict == "GO" else "FAIL"

    lines = [
        f"### {mark} — gate verdict: `{verdict}`",
        "",
        f"criteria `{report.get('criteria_version', 'unset')}` · "
        f"**{summary.get('passed', 0)} passed** · "
        f"**{summary.get('failed', 0)} failed** · "
        f"**{summary.get('skipped', 0)} skipped**",
        "",
    ]

    failed = [c for c in report.get("checks", []) if c.get("status") == "fail"]
    if failed:
        lines += ["| failed check | detail |", "| --- | --- |"]
        for check in failed:
            lines.append(f"| `{check['id']}` | {check.get('reason', '')} |")
        lines.append("")

    skipped = [c for c in report.get("checks", []) if c.get("status") == "skipped"]
    if skipped:
        lines.append(f"<details><summary>{len(skipped)} criteria were NOT evaluated</summary>")
        lines.append("")
        lines += ["| skipped check | why |", "| --- | --- |"]
        for check in skipped:
            lines.append(f"| `{check['id']}` | {check.get('reason', '')} |")
        lines += ["", "</details>", ""]

    deltas = report.get("deltas") or {}
    if deltas:
        lines += ["| metric | delta vs champion |", "| --- | ---: |"]
        for name, value in deltas.items():
            lines.append(f"| {name} | {value:+.4f} |")
        lines.append("")

    return "\n".join(lines)