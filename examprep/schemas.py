"""CLI giriş/çıkış şemaları. Skill'ler CLI'ye bu şemalara uyan JSON gönderir ve alır."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from examprep.models import DocStatus, DocType


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CourseIn(_In):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    exam_date: date | None = None

    @field_validator("code")
    @classmethod
    def _empty_code_is_none(cls, v: str | None) -> str | None:
        return v or None


class CourseOut(_Out):
    id: int
    name: str
    code: str | None
    exam_date: date | None
    document_count: int = 0


class DocumentOut(_Out):
    id: int
    course_id: int
    filename: str
    doc_type: DocType
    sha256: str
    page_count: int
    status: DocStatus
    uploaded_at: datetime


class IngestResult(BaseModel):
    document: DocumentOut
    created: bool


class PageOut(BaseModel):
    page_no: int
    text: str
    image_path: str = Field(description="Sayfa görüntüsünün mutlak yolu")
    char_count: int
    is_scanned: bool
