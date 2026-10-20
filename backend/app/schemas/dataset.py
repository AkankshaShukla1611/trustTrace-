from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    evaluation_pack_id: str
