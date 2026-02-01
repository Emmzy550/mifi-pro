import sys
import os
from datetime import datetime
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Mocking parts of the system to test the robust logic
class MockTransaction(BaseModel):
    transaction_id: str
    amount: float
    type: str
    date: datetime
    direction: str

def test_robust_logic():
    print("Testing robust logic for tuples...")
    
    # Test case 1: Real object
    tx_obj = MockTransaction(transaction_id="TX1", amount=100.0, type="DEPOSIT", date=datetime.now(), direction="INFLOW")
    
    # Test case 2: Tuple (the suspected rogue data)
    tx_tuple = ("TX2", datetime.now(), 200.0, "DEPOSIT", "INFLOW")
    
    all_parsed = [tx_obj, tx_tuple]
    
    history_dicts = []
    for tx in all_parsed:
        if isinstance(tx, tuple):
            print(f"DEBUG: Found tuple: {tx}")
            t_id = tx[0]
            t_amount = tx[2]
            t_type = tx[3]
            t_date = tx[1]
            t_direction = tx[4]
        else:
            t_id = tx.transaction_id
            t_amount = tx.amount
            t_type = tx.type
            t_date = tx.date
            t_direction = tx.direction
            
        history_dicts.append({
            "transaction_id": t_id,
            "amount": t_amount,
            "type": t_type,
            "timestamp": t_date.isoformat(),
            "direction": t_direction
        })
    
    assert len(history_dicts) == 2
    assert history_dicts[0]["transaction_id"] == "TX1"
    assert history_dicts[1]["transaction_id"] == "TX2"
    print("✅ Robust logic passed.")

if __name__ == "__main__":
    test_robust_logic()
