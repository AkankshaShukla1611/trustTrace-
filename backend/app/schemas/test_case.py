from pydantic import BaseModel, Field


class TestCaseCreate(BaseModel):
    name: str
    description: str | None = None
    category: str
    tags: list[str] = Field(default_factory=list)
    severity: str = "medium"
    input_payload: dict = Field(default_factory=dict)
    behavior_type: str = "free_text"
    expected_output: dict | None = None
    expected_evidence: list[dict] = Field(default_factory=list)
    relevant_passage_ids: list[str] = Field(default_factory=list)
    expected_tool_calls: list[dict] = Field(default_factory=list)
    prohibited_tool_calls: list[dict] = Field(default_factory=list)
    evaluator_config: dict = Field(default_factory=dict)
    preconditions: str | None = None


class TestCaseUpdate(TestCaseCreate):
    pass


class TestCaseImportRequest(BaseModel):
    test_cases: list[dict]
    allow_duplicates: bool = False
