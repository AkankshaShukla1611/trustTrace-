"""
API-level tests: exercise the actual HTTP layer (app.main) through
FastAPI's TestClient, rather than only calling internal functions
directly. Uses an isolated in-memory DB per test via dependency override,
so these never touch backend/data/trusttrace.db.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
import app.models  # noqa: F401
from app.database import get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_list_projects(client):
    create_response = client.post("/projects", json={"name": "API Test Project", "description": "d"})
    assert create_response.status_code == 200
    project_id = create_response.json()["id"]

    list_response = client.get("/projects")
    assert list_response.status_code == 200
    assert any(p["id"] == project_id for p in list_response.json())


def test_create_integration_declares_real_capabilities_not_empty(client):
    project_id = client.post("/projects", json={"name": "P"}).json()["id"]
    response = client.post(
        f"/projects/{project_id}/integrations",
        json={"name": "Mock", "adapter_type": "mock", "config": {}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["capabilities"]["retrieved_passages"] is True
    assert body["status"] == "configured"


def test_validate_integration_updates_status(client):
    project_id = client.post("/projects", json={"name": "P"}).json()["id"]
    integration_id = client.post(
        f"/projects/{project_id}/integrations", json={"name": "Mock", "adapter_type": "mock", "config": {}}
    ).json()["id"]

    response = client.post(f"/integrations/{integration_id}/validate")
    assert response.status_code == 200
    assert response.json()["status"] == "connected"


def test_unknown_adapter_type_is_rejected_not_silently_accepted(client):
    project_id = client.post("/projects", json={"name": "P"}).json()["id"]
    response = client.post(
        f"/projects/{project_id}/integrations",
        json={"name": "Bogus", "adapter_type": "not_a_real_adapter", "config": {}},
    )
    assert response.status_code == 400


def test_list_runs_is_empty_then_populated_after_a_real_run(client):
    assert client.get("/runs").json() == []

    # Build a minimal project/dataset/test case/run through the API +
    # direct DB access (dataset/test-case management has no API yet).
    from app.models.dataset import Dataset, DatasetVersion
    from app.models.evaluation_pack import EvaluationPack
    from app.models.test_case import TestCase

    db = next(app.dependency_overrides[get_db]())
    project_id = client.post("/projects", json={"name": "Run listing test"}).json()["id"]
    integration_id = client.post(
        f"/projects/{project_id}/integrations", json={"name": "Mock", "adapter_type": "mock", "config": {}}
    ).json()["id"]

    pack = EvaluationPack(slug="api_test_pack", name="API test pack")
    db.add(pack)
    db.flush()
    dataset = Dataset(project_id=project_id, evaluation_pack_id=pack.id, name="ds")
    db.add(dataset)
    db.flush()
    case = TestCase(
        dataset_id=dataset.id, evaluation_pack_id=pack.id, name="trivial", category="qa",
        severity="low", behavior_type="free_text", input_payload={"mode": "qa", "query": "x", "documents": []},
    )
    db.add(case)
    db.flush()
    dataset_version = DatasetVersion(
        dataset_id=dataset.id, version_number=1,
        test_case_snapshot=[{"test_case_id": case.id, "content_hash": "x"}],
    )
    db.add(dataset_version)
    db.commit()

    run_response = client.post(
        "/runs",
        json={"project_id": project_id, "integration_id": integration_id, "dataset_version_id": dataset_version.id},
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["id"]

    listed = client.get("/runs").json()
    assert any(r["id"] == run_id for r in listed)
    assert "executions" not in listed[0]  # list view omits the heavy nested payload

    fetched = client.get(f"/runs/{run_id}").json()
    assert len(fetched["executions"]) == 1
