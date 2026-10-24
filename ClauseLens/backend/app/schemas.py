from pydantic import BaseModel, Field
from typing import Optional

class AnalysisStart(BaseModel):
    document_id: int
    requirements: list[str] = Field(default_factory=list, max_length=50)

class GuidanceRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    language: str = Field(default="English", max_length=40)
    contract_type: Optional[str] = Field(default=None, max_length=100)
    jurisdiction: str = Field(default="India", max_length=100)

class NegotiationRequest(BaseModel):
    clause_text: str = Field(min_length=3, max_length=8000)
    goal: str = Field(min_length=3, max_length=1000)
    tone: str = Field(default="Professional", max_length=40)
