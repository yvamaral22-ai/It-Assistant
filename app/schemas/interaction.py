from typing import Literal

from pydantic import BaseModel, Field


class AnswerRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=500)


class FinishRequest(BaseModel):
    status: Literal["resolved", "unresolved", "abandoned", "not_tested"]
    feedback: str | None = Field(None, max_length=1000)


class SolutionResultRequest(BaseModel):
    result: Literal["resolved", "unresolved", "not_tested"]
    feedback: str | None = Field(None, max_length=1000)
