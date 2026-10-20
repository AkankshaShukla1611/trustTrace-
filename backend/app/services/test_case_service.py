from __future__ import annotations
import hashlib
import json

from app.enums import BehaviorType, Severity

# Fields that define a test case's actual testing semantics -- used for
# content hashing (dataset version reproducibility) and duplicate
# detection. Cosmetic fields (name, description, tags, preconditions)
# deliberately excluded so renaming a test case doesn't count as a new one.
CONTENT_FIELDS = [
    "category",
    "severity",
    "behavior_type",
    "input_payload",
    "expected_output",
    "expected_evidence",
    "relevant_passage_ids",
    "expected_tool_calls",
    "prohibited_tool_calls",
    "evaluator_config",
]


def content_fields(data: dict) -> dict:
    return {field: data.get(field) for field in CONTENT_FIELDS}


def compute_content_hash(data: dict) -> str:
    canonical = json.dumps(content_fields(data), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_test_case_fields(data: dict) -> list[str]:
    """Returns a list of actionable error strings; empty means valid."""
    errors: list[str] = []

    if not data.get("name"):
        errors.append("name is required")
    if not data.get("category"):
        errors.append("category is required")

    severity = data.get("severity")
    valid_severities = {s.value for s in Severity}
    if severity and severity not in valid_severities:
        errors.append(f"severity '{severity}' is not one of {sorted(valid_severities)}")

    behavior_type = data.get("behavior_type")
    valid_behaviors = {b.value for b in BehaviorType}
    if behavior_type and behavior_type not in valid_behaviors:
        errors.append(f"behavior_type '{behavior_type}' is not one of {sorted(valid_behaviors)}")

    if behavior_type == BehaviorType.EXACT_FIELDS.value and not data.get("expected_output"):
        errors.append("behavior_type 'exact_fields' requires a non-empty expected_output")

    input_payload = data.get("input_payload")
    if input_payload is not None and not isinstance(input_payload, dict):
        errors.append("input_payload must be an object")

    tags = data.get("tags")
    if tags is not None and not isinstance(tags, list):
        errors.append("tags must be a list")

    return errors
