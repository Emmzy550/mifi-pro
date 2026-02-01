import sys
import os
from datetime import datetime

# Add current dir to path
sys.path.append(os.getcwd())

from utils.transaction_parser import TransactionParser

def reproduce():
    parser = TransactionParser()
    
    # Text provided by user (disorganized)
    text = """
Balance at 1 February:   £40,000,00
T otal money in: 
  £5,474.00 
Total money out:    £1,395.17 
Balance at 1 March: £44.079.83 
Date
Description
Balance brought forward 
1 February 
3 February 
4 February 
Card payment - High St Petrol Station
Direct debit - Green Mobile Phone Bill
Cash Withdrawal - YourBank, Anytown 
High Street, timed 17:30 31 Jan
YourJob BiWeekly Payment
11 February Direct Deposit - YourBank, Anytown High 
Street, timed 17:30 31 Jan
16 February
Cash Withdrawal - RandomBank, Randomford, 
timed 9.52 14 Feb
17 February Card payment - High St Petrol Station 
Direct Debit - Home Insurance
18 February YourJob BiWeekly Payment
18 February Randomford's Deli
Page 1 of 1
Money Money Balance
out
24.50
20.00
30.00
50.00 
40.00
78.34
15.00
24 February Anytown's Jewelers
Direct Deposit
28 February Monthly Apartment Rent
150.00
987.33
In
2,575.00
300.00
40,000.00
39,975.50
39,955.50
39,925.50
42,500.50
42,800.50
42,750.50
42,710.50
42,632.16 
2,575.00 45,207.16
45,195.16
45,042.16
25.00 
45,067.16
44.079.83
£44.079.8
"""
    
    print("--- Testing TransactionParser with MANGLED Logic ---")
    result = parser.parse(text.encode(), "statement.txt")
    
    print(f"Document Type: {result.document_type}")
    print(f"Transactions found: {len(result.transactions)}")
    
    if result.transactions:
        print(f"Extraction Results (Count: {len(result.transactions)}):")
        for i, tx in enumerate(result.transactions):
            print(f" {i}: {tx.date} | Cr: {tx.credit or 0:8.2f} | Db: {tx.debit or 0:8.2f} | Bal: {tx.balance or 0:10.2f} | {tx.description[:30]}")
        
        # Risk indicators
        print(f"\nDocument Confidence: {result.document_confidence:.2f}")
        print(f"Risk Indicators: {result.risk_indicators.model_dump()}")
    else:
        print("\n[!] No transactions found.")

if __name__ == "__main__":
    reproduce()
