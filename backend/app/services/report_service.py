"""
Builds a reproducible report for one run: metadata, metrics with
coverage and accuracy kept as separate denominators, failures, evidence,
an automatic regression section (if the run has a baseline), and a
"known limitations" list that is read off the run's own real data
(each evaluator's reported limitation text, plus how many executions
ran in a mode that can't test live execution) rather than a fixed
boilerplate list -- a report should say what was actually unverifiable
about *this* run, not a generic disclaimer.
"""
from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.enums import ExecutionStatus
from app.models.dataset import Dataset, DatasetVersion
from app.models.project import Integration, Project
from app.models.run import Run
from app.models.test_case import TestCase
from app.runner.regression import compare_runs

_STATUS_KEYS = ["passed", "failed", "unevaluated", "execution_error", "cancelled", "needs_review"]


def _empty_status_counts() -> dict:
    return {key: 0 for key in _STATUS_KEYS}


def _bump(counts: dict, status: str) -> None:
    if status in counts:
        counts[status] += 1


def build_run_report(db: Session, run_id: str) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise ValueError(f"run {run_id} not found")

    project = db.get(Project, run.project_id)
    integration = db.get(Integration, run.integration_id)
    dataset_version = db.get(DatasetVersion, run.dataset_version_id)
    dataset = db.get(Dataset, dataset_version.dataset_id) if dataset_version else None

    executions = run.executions
    test_cases = {
        tc.id: tc for tc in db.query(TestCase).filter(TestCase.id.in_([e.test_case_id for e in executions])).all()
    }

    overall_counts = _empty_status_counts()
    by_category: dict[str, dict] = {}
    by_severity: dict[str, dict] = {}
    failures = []
    needs_review = []
    unavailable_evaluations = []
    limitations: set[str] = set()
    live_execution_false_count = 0
    live_execution_known_count = 0

    for execution in executions:
        test_case = test_cases.get(execution.test_case_id)
        category = test_case.category if test_case else "unknown"
        severity = test_case.severity if test_case else "unknown"

        _bump(overall_counts, execution.status)
        by_category.setdefault(category, _empty_status_counts())
        _bump(by_category[category], execution.status)
        by_severity.setdefault(severity, _empty_status_counts())
        _bump(by_severity[severity], execution.status)

        if isinstance(execution.config_metadata, dict) and "live_execution" in execution.config_metadata:
            live_execution_known_count += 1
            if execution.config_metadata["live_execution"] is False:
                live_execution_false_count += 1

        evaluator_failures = []
        evaluator_inconclusive = []
        for result in execution.evaluator_results:
            if result.limitations:
                limitations.add(result.limitations)
            if result.status == "unavailable":
                unavailable_evaluations.append(
                    {
                        "test_case_id": execution.test_case_id,
                        "test_case_name": test_case.name if test_case else None,
                        "evaluator_name": result.evaluator_name,
                        "reason": result.reason,
                    }
                )
            elif result.status in ("fail", "error"):
                evaluator_failures.append(
                    {
                        "evaluator_name": result.evaluator_name,
                        "status": result.status,
                        "reason": result.reason,
                        "severity": result.severity,
                    }
                )
            elif result.status == "inconclusive":
                evaluator_inconclusive.append(
                    {"evaluator_name": result.evaluator_name, "reason": result.reason}
                )

        if execution.status in (ExecutionStatus.FAILED, ExecutionStatus.EXECUTION_ERROR):
            failures.append(
                {
                    "test_case_id": execution.test_case_id,
                    "test_case_name": test_case.name if test_case else None,
                    "category": category,
                    "severity": severity,
                    "status": execution.status,
                    "evaluator_failures": evaluator_failures,
                    "error_category": execution.error_category,
                    "error_detail": execution.error_detail,
                }
            )
        elif execution.status == ExecutionStatus.NEEDS_REVIEW:
            needs_review.append(
                {
                    "test_case_id": execution.test_case_id,
                    "test_case_name": test_case.name if test_case else None,
                    "category": category,
                    "severity": severity,
                    "evaluator_inconclusive": evaluator_inconclusive,
                }
            )

    if live_execution_known_count > 0 and live_execution_false_count > 0:
        limitations.add(
            f"{live_execution_false_count} of {live_execution_known_count} execution(s) with known execution-mode "
            "metadata ran in file/batch mode and could not independently test live target execution."
        )

    evaluated = overall_counts["passed"] + overall_counts["failed"]
    total = len(executions)
    pass_rate = (overall_counts["passed"] / evaluated) if evaluated > 0 else None
    coverage = (evaluated / total) if total > 0 else None

    regression = None
    if run.baseline_run_id:
        try:
            summary = compare_runs(db, run.baseline_run_id, run.id)
            regression = summary
        except ValueError as exc:
            regression = {"error": str(exc)}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": {
            "id": run.id,
            "label": run.label,
            "mode": run.mode,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "project_id": project.id if project else None,
            "project_name": project.name if project else None,
            "integration_id": integration.id if integration else None,
            "integration_name": integration.name if integration else None,
            "adapter_type": integration.adapter_type if integration else None,
            "dataset_id": dataset.id if dataset else None,
            "dataset_name": dataset.name if dataset else None,
            "dataset_version_id": dataset_version.id if dataset_version else None,
            "dataset_version_number": dataset_version.version_number if dataset_version else None,
            "baseline_run_id": run.baseline_run_id,
        },
        "metrics": {
            "total_executions": total,
            "status_counts": overall_counts,
            "pass_rate_of_evaluated": pass_rate,
            "evaluation_coverage": coverage,
            "by_category": by_category,
            "by_severity": by_severity,
        },
        "failures": failures,
        "needs_review": needs_review,
        "unavailable_evaluations": unavailable_evaluations,
        "regression": regression,
        "known_limitations": sorted(limitations),
    }


def render_markdown(report: dict) -> str:
    run = report["run"]
    metrics = report["metrics"]

    lines = [f"# TrustTrace Run Report", ""]
    lines.append(f"Generated: {report['generated_at']}")
    lines.append("")
    lines.append("## Run")
    lines.append(f"- Run ID: `{run['id']}`")
    if run["label"]:
        lines.append(f"- Label: {run['label']}")
    lines.append(f"- Project: {run['project_name']} (`{run['project_id']}`)")
    lines.append(f"- Integration: {run['integration_name']} -- adapter type `{run['adapter_type']}`")
    lines.append(
        f"- Dataset: {run['dataset_name']} version {run['dataset_version_number']} (`{run['dataset_version_id']}`)"
    )
    lines.append(f"- Mode: {run['mode']} -- Status: {run['status']}")
    lines.append(f"- Started: {run['started_at']} -- Finished: {run['finished_at']}")
    if run["baseline_run_id"]:
        lines.append(f"- Baseline run for comparison: `{run['baseline_run_id']}`")
    lines.append("")

    lines.append("## Metrics")
    lines.append(f"- Total executions: {metrics['total_executions']}")
    counts = metrics["status_counts"]
    lines.append(
        f"- Passed: {counts['passed']} | Failed: {counts['failed']} | "
        f"Unevaluated: {counts['unevaluated']} | Execution errors: {counts['execution_error']} | "
        f"Needs review: {counts['needs_review']} | Cancelled: {counts['cancelled']}"
    )
    pass_rate = metrics["pass_rate_of_evaluated"]
    coverage = metrics["evaluation_coverage"]
    lines.append(
        f"- Pass rate (of evaluated only): {f'{pass_rate:.1%}' if pass_rate is not None else 'n/a'} "
        "-- excludes unevaluated cases"
    )
    lines.append(
        f"- Evaluation coverage: {f'{coverage:.1%}' if coverage is not None else 'n/a'} "
        "-- coverage, not accuracy"
    )
    lines.append("")

    if metrics["by_category"]:
        lines.append("### By category")
        lines.append("| Category | Passed | Failed | Unevaluated | Execution error |")
        lines.append("|---|---|---|---|---|")
        for category, c in metrics["by_category"].items():
            lines.append(f"| {category} | {c['passed']} | {c['failed']} | {c['unevaluated']} | {c['execution_error']} |")
        lines.append("")

    if metrics["by_severity"]:
        lines.append("### By severity")
        lines.append("| Severity | Passed | Failed | Unevaluated | Execution error |")
        lines.append("|---|---|---|---|---|")
        for severity, c in metrics["by_severity"].items():
            lines.append(f"| {severity} | {c['passed']} | {c['failed']} | {c['unevaluated']} | {c['execution_error']} |")
        lines.append("")

    lines.append(f"## Failures ({len(report['failures'])})")
    if not report["failures"]:
        lines.append("None.")
    else:
        for f in report["failures"]:
            lines.append(f"- **{f['test_case_name'] or f['test_case_id']}** ({f['category']}, severity {f['severity']}) -- {f['status']}")
            if f["error_detail"]:
                lines.append(f"  - error ({f['error_category']}): {f['error_detail']}")
            for ef in f["evaluator_failures"]:
                lines.append(f"  - {ef['evaluator_name']} [{ef['status']}]: {ef['reason']}")
    lines.append("")

    lines.append(f"## Needs human review ({len(report['needs_review'])})")
    lines.append(
        "The optional LLM judge returned an inconclusive verdict for these, with no deterministic "
        "failure either -- not counted as passed. A person should look at these."
    )
    if not report["needs_review"]:
        lines.append("None.")
    else:
        for item in report["needs_review"]:
            lines.append(f"- **{item['test_case_name'] or item['test_case_id']}** ({item['category']}, severity {item['severity']})")
            for ic in item["evaluator_inconclusive"]:
                lines.append(f"  - {ic['evaluator_name']}: {ic['reason']}")
    lines.append("")

    lines.append(f"## Unavailable evaluations ({len(report['unavailable_evaluations'])})")
    lines.append(
        "Evaluators with nothing applicable to check -- not counted toward pass or fail. "
        "Grouped by evaluator and reason (full per-case detail is in the JSON report)."
    )
    if report["unavailable_evaluations"]:
        grouped: dict[tuple[str, str], int] = {}
        for u in report["unavailable_evaluations"]:
            key = (u["evaluator_name"], u["reason"])
            grouped[key] = grouped.get(key, 0) + 1
        for (evaluator_name, reason), count in sorted(grouped.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- **{evaluator_name}** ({count}x): {reason}")
    lines.append("")

    if report["regression"]:
        reg = report["regression"]
        lines.append("## Regression vs. baseline")
        if "error" in reg:
            lines.append(f"Could not compare: {reg['error']}")
        else:
            lines.append(f"- New failures: {len(reg['new_failures'])}")
            lines.append(f"- Critical failures: {len(reg['critical_failures'])}")
            lines.append(f"- Resolved failures: {len(reg['resolved_failures'])}")
            lines.append(f"- Newly passed: {len(reg['newly_passed'])}")
            lines.append(f"- Unchanged failures: {len(reg['unchanged_failures'])}")
            lines.append(f"- Non-comparable (dataset changed): {len(reg['non_comparable'])}")
            lines.append(f"- Integration config changed: {reg['config_changed']}")
        lines.append("")

    lines.append("## Known limitations")
    if report["known_limitations"]:
        for limitation in report["known_limitations"]:
            lines.append(f"- {limitation}")
    else:
        lines.append("None reported by the evaluators that ran in this run.")

    return "\n".join(lines) + "\n"
