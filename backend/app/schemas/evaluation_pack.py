from pydantic import BaseModel, Field


class EvaluationPackCreate(BaseModel):
    slug: str
    name: str
    description: str | None = None
    version: str = "1.0.0"
    rules_config: dict = Field(default_factory=dict)
