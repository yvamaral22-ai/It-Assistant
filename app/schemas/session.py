from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_name: str = Field(min_length=1, max_length=120)
    department: str = Field(min_length=1, max_length=120)
    computer_name: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=120)
    asset_tag: str | None = Field(None, max_length=80)
    device_model: str | None = Field(None, max_length=120)
    category: str = Field(min_length=1, max_length=40)
    issue_type: str = Field(min_length=1, max_length=120)
    urgency: Literal["low", "medium", "high"] | None = None
    impact: Literal["individual", "team", "company"] | None = None
    initial_description: str = Field(min_length=1, max_length=1000)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_name: str | None
    department: str | None
    computer_name: str | None
    location: str | None
    asset_tag: str | None
    device_model: str | None
    category: str
    issue_type: str | None
    urgency: str | None
    impact: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    initial_description: str | None
    final_feedback: str | None
    rating: int | None
    current_node_id: str | None


SessionStatus = Literal["resolved", "unresolved", "abandoned"]
