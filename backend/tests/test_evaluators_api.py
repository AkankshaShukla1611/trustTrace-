from fastapi.testclient import TestClient

from app.main import app


def test_list_evaluators_returns_every_registered_evaluator_with_a_real_description():
    client = TestClient(app)
    response = client.get("/evaluators")
    assert response.status_code == 200

    body = response.json()
    names = {e["name"] for e in body}
    assert names == {
        "schema_correctness", "factual_correctness", "retrieval_metrics", "citation_grounding",
        "abstention", "conflict_detection", "missing_field", "hitl_gate", "llm_judge",
    }
    for evaluator in body:
        # every description comes from a real docstring, not a placeholder
        assert len(evaluator["description"]) > 20
        assert evaluator["version"]

    by_name = {e["name"]: e for e in body}
    assert by_name["llm_judge"]["deterministic"] is False
    assert by_name["schema_correctness"]["deterministic"] is True
