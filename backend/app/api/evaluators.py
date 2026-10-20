from __future__ import annotations

from fastapi import APIRouter

from app.evaluators import DETERMINISTIC_EVALUATORS

router = APIRouter(tags=["evaluators"])


@router.get("/evaluators")
def list_evaluators():
    """
    Describes every deterministic evaluator the runner actually applies,
    pulled straight from each evaluator class's own docstring -- so this
    endpoint can't drift out of sync with what the engine really does.
    """
    return [
        {
            "name": evaluator.name,
            "version": evaluator.version,
            "description": (type(evaluator).__doc__ or "").strip(),
        }
        for evaluator in DETERMINISTIC_EVALUATORS
    ]
