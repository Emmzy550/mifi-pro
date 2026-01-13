from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

class MobileMoneyTransaction(BaseModel):
    transaction_id: str
    amount: float
    type: str  # DEPOSIT, WITHDRAWAL, PAYMENT, TRANSFER
    timestamp: datetime
    counterparty: Optional[str] = None

class UtilityPayment(BaseModel):
    utility_name: str
    amount: float
    timestamp: datetime
    status: str  # PAID, LATE, MISSED

class AlternativeData(BaseModel):
    borrower_id: str
    mobile_money_history: List[MobileMoneyTransaction] = []
    utility_history: List[UtilityPayment] = []
    airtime_usage_avg: float = 0.0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_schema_extra = {
            "example": {
                "borrower_id": "BOR-12345",
                "mobile_money_history": [
                    {"transaction_id": "TXN001", "amount": 500.0, "type": "DEPOSIT", "timestamp": "2024-01-01T10:00:00"}
                ],
                "utility_history": [
                    {"utility_name": "Electricity", "amount": 50.0, "timestamp": "2024-01-01T12:00:00", "status": "PAID"}
                ],
                "airtime_usage_avg": 25.0
            }
        }
