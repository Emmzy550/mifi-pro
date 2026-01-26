from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ExportType(str, Enum):
    PDF = "PDF"
    XLSX = "XLSX"


class ExportStatus(str, Enum):
    READY = "READY"
    FAILED = "FAILED"


class DecisionExport(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: str = Field(..., description="Unique export ID")
    decision_id: str = Field(..., description="Decision/assessment ID this export belongs to")
    assessment_id: str = Field(..., description="Assessment ID for traceability")
    organization_id: str = Field(..., description="Organization ID")
    applicant_name: str = Field(..., description="Borrower/applicant name")
    export_type: ExportType = Field(..., description="Export format")
    file_path: str = Field(..., description="Local file path or storage URL")
    file_hash: str = Field(..., description="SHA-256 hash of file content")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generated_by: Optional[str] = Field(None, description="Actor email or system")
    model_version: str = Field(..., description="Model version used")
    policy_version: str = Field(..., description="Policy version used")
    export_version: int = Field(1, description="Incremented on regeneration")
    status: ExportStatus = Field(ExportStatus.READY, description="Export status")
    error: Optional[str] = Field(None, description="Failure diagnostic if generation failed")
