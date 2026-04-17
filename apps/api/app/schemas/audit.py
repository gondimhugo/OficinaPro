from pydantic import BaseModel, Field


class CriticalActionRequest(BaseModel):
    entity_type: str = Field(min_length=2, max_length=60)
    entity_id: int = Field(gt=0)
    payload: dict | None = None


class ChangeStatusRequest(CriticalActionRequest):
    new_status: str = Field(min_length=2, max_length=40)


class AttachmentAuditRequest(CriticalActionRequest):
    operation: str = Field(pattern=r"^(upload|remove)$")
