import sys
import os
from datetime import datetime

# Add current dir to path
sys.path.append(os.getcwd())

from utils.transaction_parser import TransactionParser

def reproduce():
    parser = TransactionParser()
    
    # Text provided by user
    text = """
Kansas City MO 64106-3686
Jane Customer
1234 Anywhere Dr.
Small Town, MO 12345-6789
Bank Statement
Primary Account Number:
000009752
If you have any questions about your statement, 
please call us at 816-234-2265
Statement Date:
Page Number:
              J une 5, 2003
                                         1
CONNECTIONS CHECKING Account # 000009752
 Account Summary Account # 000009752
Beginning Balance on May 3, 2003                      
Deposits & Other Credits
ATM Withdrawals & Debits
VISA Check Card Purchases & Debits                 
Withdrawals & Other Debits
Checks Paid
          Ending Balance on June 5, 2003
$7,126.11
         +3,615.08
               -20.00-0.00
      -0.00
             -200.00
$10,521.19
Deposits & Other Credits Account # 000009752
Description
Deposit
Total Deposits & Other Credits
Ref Nbr:     130012345
ATM Withdrawals & Debits Account # 000009752
Description                                                    
ATM Withdrawal
1000 Walnut St      M119
Kansas City MO    00005678                
Total ATM Withdrawals & Debits
Checks Paid Account # 000009752
Date Paid
05-12
Check Number
1001
Amount Reference Number
75.00 00012576589
05-18
1002
30.00 00036547854
05-24
1003
200.00 00094613547
Total Checks Paid
Date Credited
                    Amount
                           05-15                                      $3,615.08
                      $3,615.08
                         Tran 
Date
Date Paid                     
05-18                 05-19  
   Amount
                                      $20.00
 $20.00
            $305.0
"""
    
    print("--- Testing TransactionParser with Full Logic ---")
    result = parser.parse(text.encode(), "statement.pdf")
    
    print(f"Document Type: {result.document_type}")
    print(f"Transactions found: {len(result.transactions)}")
    
    if result.transactions:
        print(f"Extraction Results (Count: {len(result.transactions)}):")
        for i, tx in enumerate(result.transactions):
            print(f" {i}: {tx.date.strftime('%Y-%m-%d')} | {tx.amount:8.2f} | {tx.direction:7} | {tx.description[:30]}")
        
        # Check specific bug: Check 1001 should NOT be a year
        years = {tx.date.year for tx in result.transactions}
        print(f"\nUnique Years Extracted: {years}")
        
        # Behavioral Check
        from agents.behavioral_agent_v2 import BehavioralAgentV2
        metrics = BehavioralAgentV2.analyze_transactions(result.transactions)
        print(f"\nBehavioral Metrics:")
        print(f" - Window: {metrics.get('observation_window_days')} days")
        print(f" - Status: {metrics.get('behavioral_status')}")
        print(f" - Income Consistency: {metrics.get('income_consistency_score'):.4f}")
        
        total_in = sum(tx.amount for tx in result.transactions if tx.direction == "INFLOW")
        print(f" - Raw Total Inflow: ${total_in:.2f}")
    else:
        print("\n[!] No transactions found in the provided text sample.")

if __name__ == "__main__":
    reproduce()
