import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

def generate_transactions(days=15):
    transactions = []
    utility_payments = []
    
    now = datetime.now(timezone.utc)
    
    # 1. Generate Daily Activity (Zanaco & Mobile Money)
    for i in range(days):
        date = now - timedelta(days=i)
        
        # Periodic Salary/Big Deposit from Zanaco
        if i == 14: # 15 days ago
            transactions.append({
                "transaction_id": f"ZAN-{uuid.uuid4().hex[:6]}",
                "amount": 4500.0,
                "type": "DEPOSIT",
                "timestamp": (date - timedelta(hours=2)).isoformat(),
                "counterparty": "Zanaco Bank - Salary"
            })
            
        # Daily Small Deposits (e.g. Sales)
        transactions.append({
            "transaction_id": f"TX-{uuid.uuid4().hex[:6]}",
            "amount": 200.0 + (i * 10),
            "type": "DEPOSIT",
            "timestamp": (date - timedelta(hours=5)).isoformat(),
            "counterparty": "Customer Payment"
        })
        
        # Daily Small Withdrawals
        transactions.append({
            "transaction_id": f"TX-{uuid.uuid4().hex[:6]}",
            "amount": 50.0 + (i * 2),
            "type": "WITHDRAWAL",
            "timestamp": (date - timedelta(hours=8)).isoformat(),
            "counterparty": "Personal Expense"
        })

    # 2. Specific ZESCO Utility Payment (Zambia Electricity)
    utility_payments.append({
        "utility_name": "ZESCO",
        "amount": 150.0,
        "timestamp": (now - timedelta(days=5, hours=10)).isoformat(),
        "status": "PAID"
    })
    
    # 3. Specific Zanaco Outgoing Payment (e.g. Rent or Supplier)
    transactions.append({
        "transaction_id": f"ZAN-{uuid.uuid4().hex[:6]}",
        "amount": 1200.0,
        "type": "PAYMENT",
        "timestamp": (now - timedelta(days=10, hours=4)).isoformat(),
        "counterparty": "Zanaco - Supplier HQ"
    })

    data = {
        "borrower_id": "BOR-TEST-001",
        "mobile_money_history": transactions,
        "utility_history": utility_payments,
        "airtime_usage_avg": 45.5
    }
    
    return data

if __name__ == "__main__":
    test_data = generate_transactions(15)
    
    filename = "synthetic_transactions.json"
    with open(filename, "w") as f:
        json.dump(test_data, f, indent=4)
        
    print(f"✅ Successfully generated 15 days of data in '{filename}'")
    print(f"   - Transactions: {len(test_data['mobile_money_history'])}")
    print(f"   - Utility (ZESCO): {len(test_data['utility_history'])}")
    print(f"   - Counterparties include Zanaco and ZESCO.")
