from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class IntegrationCreate(BaseModel):
    name: str
    adapter_type: str
    config: dict = {}


class RunCreate(BaseModel):
    project_id: str
    integration_id: str
    dataset_version_id: str
    mode: str = "full_dataset"
    test_case_ids: list[str] | None = None
    label: str | None = None
    baseline_run_id: str | None = None


class RegressionCompareRequest(BaseModel):
    baseline_run_id: str
    candidate_run_id: str
