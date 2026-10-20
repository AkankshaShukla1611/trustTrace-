"""
Tests the dataset/test-case management API: CRUD, search/filter,
JSON/CSV import-export, duplicate detection, validation errors, and
dataset version snapshotting. This is the layer that previously only
existed via hand-written seed scripts.
"""
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
import app.models  # noqa: F401
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


@pytest.fixture()
def dataset(client):
    project_id = client.post("/projects", json={"name": "DS test project"}).json()["id"]
    pack = client.post("/evaluation-packs", json={"slug": "ds_test_pack", "name": "DS Test Pack"}).json()
    dataset = client.post(
        f"/projects/{project_id}/datasets",
        json={"name": "DS test dataset", "evaluation_pack_id": pack["id"]},
    ).json()
    return {"project_id": project_id, "pack_id": pack["id"], "dataset_id": dataset["id"]}


def _case_payload(name="A test case", **overrides):
    payload = {
        "name": name,
        "category": "extraction",
        "severity": "medium",
        "behavior_type": "free_text",
        "input_payload": {"query": "x"},
    }
    payload.update(overrides)
    return payload


def test_create_evaluation_pack_rejects_duplicate_slug(client):
    first = client.post("/evaluation-packs", json={"slug": "dup_pack", "name": "First"})
    assert first.status_code == 200
    second = client.post("/evaluation-packs", json={"slug": "dup_pack", "name": "Second"})
    assert second.status_code == 409


def test_create_test_case_then_fetch_and_list(client, dataset):
    create_response = client.post(f"/datasets/{dataset['dataset_id']}/test-cases", json=_case_payload())
    assert create_response.status_code == 200
    test_case_id = create_response.json()["id"]

    fetched = client.get(f"/test-cases/{test_case_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "A test case"

    listed = client.get(f"/datasets/{dataset['dataset_id']}/test-cases")
    assert len(listed.json()) == 1


def test_create_test_case_validates_exact_fields_requires_expected_output(client, dataset):
    response = client.post(
        f"/datasets/{dataset['dataset_id']}/test-cases",
        json=_case_payload(behavior_type="exact_fields"),
    )
    assert response.status_code == 422
    assert "expected_output" in str(response.json())


def test_create_test_case_rejects_identical_duplicate(client, dataset):
    payload = _case_payload()
    first = client.post(f"/datasets/{dataset['dataset_id']}/test-cases", json=payload)
    assert first.status_code == 200
    second = client.post(f"/datasets/{dataset['dataset_id']}/test-cases", json=payload)
    assert second.status_code == 409


def test_search_and_filter_by_category_severity_and_tag(client, dataset):
    client.post(
        f"/datasets/{dataset['dataset_id']}/test-cases",
        json=_case_payload("Alpha case", category="citation", severity="high", tags=["prod"]),
    )
    client.post(
        f"/datasets/{dataset['dataset_id']}/test-cases",
        json=_case_payload("Beta case", category="extraction", severity="low", tags=["staging"]),
    )

    by_category = client.get(f"/datasets/{dataset['dataset_id']}/test-cases", params={"category": "citation"}).json()
    assert len(by_category) == 1 and by_category[0]["name"] == "Alpha case"

    by_severity = client.get(f"/datasets/{dataset['dataset_id']}/test-cases", params={"severity": "low"}).json()
    assert len(by_severity) == 1 and by_severity[0]["name"] == "Beta case"

    by_tag = client.get(f"/datasets/{dataset['dataset_id']}/test-cases", params={"tag": "prod"}).json()
    assert len(by_tag) == 1 and by_tag[0]["name"] == "Alpha case"

    by_search = client.get(f"/datasets/{dataset['dataset_id']}/test-cases", params={"q": "beta"}).json()
    assert len(by_search) == 1 and by_search[0]["name"] == "Beta case"


def test_update_test_case_bumps_version_and_content_hash(client, dataset):
    created = client.post(f"/datasets/{dataset['dataset_id']}/test-cases", json=_case_payload()).json()
    assert created["version"] == 1
    original_hash = created["content_hash"]

    updated = client.put(
        f"/test-cases/{created['id']}", json=_case_payload(category="citation")
    ).json()
    assert updated["version"] == 2
    assert updated["content_hash"] != original_hash
    assert updated["category"] == "citation"


def test_archive_is_soft_delete_not_removal(client, dataset):
    created = client.post(f"/datasets/{dataset['dataset_id']}/test-cases", json=_case_payload()).json()
    archive_response = client.delete(f"/test-cases/{created['id']}")
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    # dropped from the default (active-only) listing...
    assert client.get(f"/datasets/{dataset['dataset_id']}/test-cases").json() == []
    # ...but still fetchable directly and visible with status=all
    assert client.get(f"/test-cases/{created['id']}").json()["status"] == "archived"
    all_listed = client.get(f"/datasets/{dataset['dataset_id']}/test-cases", params={"status": "all"}).json()
    assert len(all_listed) == 1


def test_json_import_reports_created_skipped_and_errors_separately(client, dataset):
    good = _case_payload("Good case")
    bad = {"name": "Bad case", "behavior_type": "not_a_real_behavior"}  # missing category too

    response = client.post(
        f"/datasets/{dataset['dataset_id']}/test-cases/import",
        json={"test_cases": [good, bad]},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["created"]) == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["name"] == "Bad case"

    # importing the exact same good case again is a reported duplicate, not a silent re-create
    dup_response = client.post(
        f"/datasets/{dataset['dataset_id']}/test-cases/import", json={"test_cases": [good]}
    ).json()
    assert dup_response["created"] == []
    assert len(dup_response["skipped_duplicates"]) == 1


def test_export_json_then_reimport_round_trips(client, dataset):
    client.post(f"/datasets/{dataset['dataset_id']}/test-cases", json=_case_payload("Round trip case"))
    exported = client.get(f"/datasets/{dataset['dataset_id']}/test-cases/export", params={"format": "json"}).json()
    assert len(exported) == 1

    other_dataset_id = client.post(
        f"/projects/{dataset['project_id']}/datasets",
        json={"name": "second dataset", "evaluation_pack_id": dataset["pack_id"]},
    ).json()["id"]

    reimport = client.post(
        f"/datasets/{other_dataset_id}/test-cases/import", json={"test_cases": exported}
    ).json()
    assert len(reimport["created"]) == 1


def test_csv_export_then_csv_reimport_round_trips(client, dataset):
    client.post(
        f"/datasets/{dataset['dataset_id']}/test-cases",
        json=_case_payload("CSV case", tags=["a", "b"], expected_evidence=[{"document_id": "d1", "page": 1}]),
    )
    csv_response = client.get(f"/datasets/{dataset['dataset_id']}/test-cases/export", params={"format": "csv"})
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    csv_bytes = csv_response.content

    other_dataset_id = client.post(
        f"/projects/{dataset['project_id']}/datasets",
        json={"name": "csv target dataset", "evaluation_pack_id": dataset["pack_id"]},
    ).json()["id"]

    reimport = client.post(
        f"/datasets/{other_dataset_id}/test-cases/import-csv",
        files={"file": ("cases.csv", io.BytesIO(csv_bytes), "text/csv")},
    ).json()
    assert len(reimport["created"]) == 1

    reimported_case = client.get(f"/datasets/{other_dataset_id}/test-cases").json()[0]
    assert reimported_case["tags"] == ["a", "b"]
    assert reimported_case["expected_evidence"] == [{"document_id": "d1", "page": 1}]


def test_dataset_version_snapshots_only_active_cases(client, dataset):
    keep = client.post(f"/datasets/{dataset['dataset_id']}/test-cases", json=_case_payload("Keep")).json()
    # different input_payload so this doesn't collide with "Keep" on content-hash duplicate detection
    archived = client.post(
        f"/datasets/{dataset['dataset_id']}/test-cases",
        json=_case_payload("Archive me", input_payload={"query": "something else"}),
    ).json()
    client.delete(f"/test-cases/{archived['id']}")

    version = client.post(f"/datasets/{dataset['dataset_id']}/versions").json()
    assert version["test_case_count"] == 1
    assert version["test_case_snapshot"][0]["test_case_id"] == keep["id"]

    listed_versions = client.get(f"/datasets/{dataset['dataset_id']}/versions").json()
    assert len(listed_versions) == 1
    assert listed_versions[0]["version_number"] == 1
