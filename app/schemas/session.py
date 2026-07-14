from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    user_name: str | None = Field(None, max_length=120)
    department: str | None = Field(None, max_length=120)
    computer_name: str | None = Field(None, max_length=120)
    category: str = Field(min_length=1, max_length=40)
    initial_description: str | None = Field(None, max_length=1000)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_name: str | None
    department: str | None
    computer_name: str | None
    category: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    initial_description: str | None
    final_feedback: str | None
    current_node_id: str | None


SessionStatus = Literal["resolved", "unresolved", "abandoned"]

