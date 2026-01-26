from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class CounterfactualOutcome(str, Enum):
    APPROVE = "APPROVE"
    REFER = "REFER"


class DecisionCounterfactual(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(..., description="Unique counterfactual ID")
    decision_id: str = Field(..., description="Decision/assessment ID this counterfactual belongs to")
    factor_name: str = Field(..., description="Policy factor name")
    current_value: str = Field(..., description="Current observed value")
    required_value: str = Field(..., description="Threshold required to alter outcome")
    policy_rule_id: str = Field(..., description="Policy rule reference")
    impact_description: str = Field(..., description="Neutral description of potential impact")
    outcome_if_met: CounterfactualOutcome = Field(..., description="Expected outcome if threshold is met")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_version: Optional[str] = Field(None, description="Model version used")
    policy_version: Optional[str] = Field(None, description="Policy version used")
