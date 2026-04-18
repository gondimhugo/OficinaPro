from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TransitionRequest(BaseModel):
    target_state: str = Field(min_length=2, max_length=40)
    event: str = Field(min_length=2, max_length=60)
    profile: str = Field(min_length=2, max_length=40)
    context: dict = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=64)


class TransitionResponse(BaseModel):
    entity_type: str
    entity_id: int
    from_state: str
    to_state: str
    event: str
    auto_follow_up: list[str] = Field(default_factory=list)


class StateEventItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    from_state: str | None
    to_state: str
    event: str
    actor_user_id: int | None
    actor_role: str | None
    correlation_id: str | None
    created_at: datetime
