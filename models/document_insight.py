from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    PARSED = "parsed"
    PARTIAL = "partial"
    MISSING = "missing"
    ERROR = "error"


class DocumentFlagSeverity(str, Enum):
    LOW = "low"
    MED = "med"
    HIGH = "high"


class DecisionDocumentSummary(BaseModel):
    docId: str
    type: str
    provider: Optional[str] = None
    period: Optional[Union[str, Dict[str, Optional[str]]]] = None
    status: DocumentStatus
    oneLiner: str
    confidence: Optional[float] = None
    createdAt: str


class DocumentInsightFlag(BaseModel):
    label: str
    severity: DocumentFlagSeverity
    detail: Optional[str] = None


class DocumentInsight(BaseModel):
    docId: str
    type: str
    provider: Optional[str] = None
    period: Optional[Union[str, Dict[str, Optional[str]]]] = None
    status: DocumentStatus
    confidence: Optional[float] = None
    keyTakeaway: str
    summaryBullets: List[str] = Field(default_factory=list)
    extractedMetrics: Dict[str, Union[str, float, int, bool]] = Field(default_factory=dict)
    flags: List[DocumentInsightFlag] = Field(default_factory=list)
    provenance: Optional[Dict[str, Any]] = None
    secureFileUrl: Optional[str] = None


class DocumentInsightRecord(DocumentInsight):
    decisionId: str
    organizationId: str
    sourceIndex: Optional[int] = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
