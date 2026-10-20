from app.models.dataset import Dataset, DatasetVersion
from app.models.evaluation_pack import EvaluationPack
from app.models.project import Integration, Project
from app.models.run import EvaluatorResult, Run, TestExecution, TraceEvent
from app.models.test_case import TestCase


def evaluation_pack_dict(pack: EvaluationPack) -> dict:
    return {
        "id": pack.id,
        "slug": pack.slug,
        "name": pack.name,
        "description": pack.description,
        "version": pack.version,
    }


def dataset_dict(dataset: Dataset) -> dict:
    return {
        "id": dataset.id,
        "project_id": dataset.project_id,
        "evaluation_pack_id": dataset.evaluation_pack_id,
        "name": dataset.name,
        "description": dataset.description,
    }


def dataset_version_dict(version: DatasetVersion) -> dict:
    return {
        "id": version.id,
        "dataset_id": version.dataset_id,
        "version_number": version.version_number,
        "test_case_count": len(version.test_case_snapshot),
        "test_case_snapshot": version.test_case_snapshot,
        "created_at": version.created_at,
    }


def test_case_dict(tc: TestCase) -> dict:
    return {
        "id": tc.id,
        "dataset_id": tc.dataset_id,
        "evaluation_pack_id": tc.evaluation_pack_id,
        "name": tc.name,
        "description": tc.description,
        "category": tc.category,
        "tags": tc.tags,
        "severity": tc.severity,
        "input_payload": tc.input_payload,
        "behavior_type": tc.behavior_type,
        "expected_output": tc.expected_output,
        "expected_evidence": tc.expected_evidence,
        "relevant_passage_ids": tc.relevant_passage_ids,
        "expected_tool_calls": tc.expected_tool_calls,
        "prohibited_tool_calls": tc.prohibited_tool_calls,
        "evaluator_config": tc.evaluator_config,
        "preconditions": tc.preconditions,
        "version": tc.version,
        "status": tc.status,
        "content_hash": tc.content_hash,
    }


def project_dict(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "evaluation_pack_id": project.evaluation_pack_id,
        "created_at": project.created_at,
        "integrations": [integration_dict(i) for i in project.integrations],
    }


def integration_dict(integration: Integration) -> dict:
    return {
        "id": integration.id,
        "project_id": integration.project_id,
        "name": integration.name,
        "adapter_type": integration.adapter_type,
        "capabilities": integration.capabilities,
        "status": integration.status,
        "last_validation_message": integration.last_validation_message,
        "enabled": integration.enabled,
        # config is intentionally omitted from ordinary API responses to
        # avoid echoing back anything sensitive; secrets are never stored
        # in it anyway (see adapters/http_adapter.py), but we still don't
        # expose arbitrary integration config by default.
    }


def evaluator_result_dict(result: EvaluatorResult) -> dict:
    return {
        "id": result.id,
        "evaluator_name": result.evaluator_name,
        "evaluator_version": result.evaluator_version,
        "status": result.status,
        "score": result.score,
        "expected_value": result.expected_value,
        "actual_value": result.actual_value,
        "reason": result.reason,
        "limitations": result.limitations,
        "severity": result.severity,
    }


def trace_event_dict(event: TraceEvent) -> dict:
    return {
        "sequence_index": event.sequence_index,
        "stage_name": event.stage_name,
        "status": event.status,
        "payload": event.payload,
        "occurred_at": event.occurred_at,
    }


def execution_dict(execution: TestExecution) -> dict:
    return {
        "id": execution.id,
        "test_case_id": execution.test_case_id,
        "status": execution.status,
        "actual_input": execution.actual_input,
        "actual_output": execution.actual_output,
        "started_at": execution.started_at,
        "duration_ms": execution.duration_ms,
        "config_metadata": execution.config_metadata,
        "retrieved_passages": execution.retrieved_passages,
        "tool_calls": execution.tool_calls,
        "error_category": execution.error_category,
        "error_detail": execution.error_detail,
        "trace_events": [trace_event_dict(t) for t in execution.trace_events],
        "evaluator_results": [evaluator_result_dict(r) for r in execution.evaluator_results],
    }


def run_dict(run: Run, *, include_executions: bool = True) -> dict:
    data = {
        "id": run.id,
        "project_id": run.project_id,
        "integration_id": run.integration_id,
        "dataset_version_id": run.dataset_version_id,
        "label": run.label,
        "mode": run.mode,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }
    if include_executions:
        data["executions"] = [execution_dict(e) for e in run.executions]
    return data
