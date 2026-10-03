from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(Strict):
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize(cls, value):
        return value.lower()


class CreateProject(Strict):
    name: str = Field(min_length=1, max_length=120)


class GitHubImport(Strict):
    url: str = Field(min_length=20, max_length=300)


class AskQuestion(Strict):
    question: str = Field(min_length=3, max_length=2000)
    snapshot_id: str | None = None


class VivaRequest(Strict):
    difficulty: Literal[
        "BEGINNER", "FACULTY", "TECHNICAL REVIEWER", "RECRUITER", "ADVERSARIAL EXAMINER"
    ] = "FACULTY"


class DocumentRequest(Strict):
    kind: Literal["report", "presentation", "resume", "linkedin", "readme", "viva-notes"] = "report"


class DeleteRequest(Strict):
    confirmation: str


class RevisionRequest(Strict):
    revision: bool


class ModelAnswer(Strict):
    answer: str = Field(max_length=12000)
    status: Literal["INFERRED", "UNVERIFIED"]
    confidence: float = Field(ge=0, le=1)
    citation_ids: list[str] = Field(max_length=8)
    limitations: list[str] = Field(max_length=10)


class EvidenceOut(BaseModel):
    id: str
    file_id: str
    project_id: str
    snapshot_id: str
    commit_sha: str
    path: str
    start_line: int
    end_line: int
    chunk_type: str
    content: str


class AnswerOut(BaseModel):
    answer: str
    status: str
    confidence: float
    evidence: list[EvidenceOut]
    limitations: list[str]
    provider: str
