import json
import random
from datetime import datetime, timedelta, timezone

def generate_data(borrower_id="BOR-REPLACE-THIS", days=50):
    data = {
        "borrower_id": borrower_id,
        "mobile_money_history": [],
        "utility_history": [],
        "airtime_usage_avg": 0.0
    }

    base_time = datetime.now(timezone.utc)
    
    # Generate transactions
    transaction_types = ["DEPOSIT", "WITHDRAWAL", "PAYMENT", "TRANSFER"]
    
    total_airtime = 0
    airtime_count = 0
    
    for day in range(days):
        current_date = base_time - timedelta(days=day)
        
        # EXACTLY 1 transaction per day
        tx_type = random.choice(transaction_types)
        
        # Amounts relative to type
        if tx_type == "DEPOSIT":
            amount = random.uniform(500, 5000)
        elif tx_type == "WITHDRAWAL":
            amount = random.uniform(100, 2000)
        else:
            amount = random.uniform(50, 1000)
            
        data["mobile_money_history"].append({
            "transaction_id": f"TXN-{random.randint(100000, 999999)}",
            "amount": round(amount, 2),
            "type": tx_type,
            "timestamp": (current_date - timedelta(hours=random.randint(8, 18))).isoformat(), # Business hours
            "counterparty": "Test Party"
        })

        # Simulate airtime occasionally
        if random.random() < 0.3:
            airtime_amt = random.choice([50, 100, 200])
            total_airtime += airtime_amt
            airtime_count += 1
    
    # Generate utility payments (approx 1 per month)
    months_covered = (days // 30) + 1
    for i in range(months_covered):
        pay_date = base_time - timedelta(days=i*30 + random.randint(1,5))
        data["utility_history"].append({
            "utility_name": "ZESCO Power",
            "amount": round(random.uniform(300, 800), 2),
            "timestamp": pay_date.isoformat(),
            "status": "PAID"
        })

    if airtime_count > 0:
        data["airtime_usage_avg"] = round(total_airtime / months_covered, 2)
    else:
        data["airtime_usage_avg"] = 150.00

    return data

if __name__ == "__main__":
    # Generate and print
    test_data = generate_data(days=180)
    print(json.dumps(test_data, indent=2))
