from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActivityEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    kind: str
    occurred_at: datetime = Field(serialization_alias="occurredAt")
    actor_user_id: UUID | None = Field(serialization_alias="actorUserId")
    aggregate_type: str = Field(serialization_alias="aggregateType")
    aggregate_id: UUID | None = Field(serialization_alias="aggregateId")
    payload: dict[str, Any]


class OutboxSummary(BaseModel):
    pending: int = 0
    sent: int = 0
    failed: int = 0
    suppressed: int = 0


class ActivityFeedResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entries: list[ActivityEntry]
    page: int
    page_size: int = Field(serialization_alias="pageSize")
    has_more: bool = Field(serialization_alias="hasMore")
    outbox: OutboxSummary
