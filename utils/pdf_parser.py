"""
PDF Transaction Parser
======================

Parses transaction data from PDF bank statements and converts them
into AlternativeData format for behavioral analysis.

Supports common formats:
- Mobile money statements (M-Pesa, Airtel Money)
- Bank statements
- Utility payment records
"""

import re
from datetime import datetime
from typing import List, Dict, Any
from models.alternative_data import AlternativeData, MobileMoneyTransaction, UtilityPayment


class PDFTransactionParser:
    """
    Parses transaction data from PDF text content.
    """
    
    @staticmethod
    def parse_pdf_text(pdf_text: str, borrower_id: str) -> AlternativeData:
        transactions = []
        utilities = []
        
        # Zanaco/Bank Statement Parsing Logic
        # Pattern: Ends with D or C, followed by Amount, then Balance
        # Example: ... D 10.00 1,803.18
        tx_pattern = re.compile(r'(.*?)\s([DC])\s+([0-9,]+\.[0-9]{2})\s+[0-9,]+\.[0-9]{2}.*?$')
        
        # Date Pattern: Dec 02, 2025
        date_pattern = re.compile(r'([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})')
        
        lines = pdf_text.split('\n')
        current_date = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 1. Try to find a date (Context)
            # Lines often look like: "Dec 02, " then next line "2025"
            # Or "Dec 02, 2025"
            date_match = date_pattern.search(line)
            if date_match:
                try:
                    month, day, year = date_match.groups()
                    current_date = datetime.strptime(f"{year}-{month}-{day}", "%Y-%b-%d")
                except:
                    pass
            
            # 2. Try to find a transaction
            tx_match = tx_pattern.search(line)
            if tx_match and current_date:
                description, dc_type, amount_str = tx_match.groups()
                amount = float(amount_str.replace(',', ''))
                
                # Refine Description (remove common prefixes)
                description = description.replace('DIGITAL NFS TRANSACTIONS', '')
                description = description.replace('COMMISSION ON', '')
                description = description.strip()
                
                # Determine Transaction Type
                tx_type = 'PAYMENT' # Default
                
                if dc_type == 'C':
                    tx_type = 'DEPOSIT'
                    if 'SALARY' in description.upper():
                        tx_type = 'SALARY'
                else:
                    if 'AIRTEL' in description.upper() or 'MTN' in description.upper():
                        tx_type = 'UTILITY_PAYMENT'
                        # Add to Utility History
                        utility_provider = "Airtel" if "AIRTEL" in description.upper() else "MTN"
                        utilities.append(UtilityPayment(
                            utility_name=utility_provider,
                            amount=amount,
                            timestamp=current_date,
                            status="PAID"
                        ))
                    elif 'WITHDRAWAL' in description.upper() or 'CASH' in description.upper():
                        tx_type = 'WITHDRAWAL'
                    else:
                        tx_type = 'TRANSFER'

                # Add to Mobile Money / Bank History
                transactions.append(MobileMoneyTransaction(
                    transaction_id=f"TX-{hash(line+str(amount)) % 1000000}",
                    amount=amount,
                    type=tx_type,
                    timestamp=current_date,
                    counterparty=description[:30] # Truncate for display
                ))

        # Calculate average airtime usage
        airtime_txs = [t for t in transactions if 'TOP UP' in t.counterparty.upper() or t.type == 'UTILITY_PAYMENT']
        airtime_avg = sum(t.amount for t in airtime_txs) / len(airtime_txs) if airtime_txs else 0
        
        # Identify Top 5 High Value Transactions for "Evidence"
        # This proves to the user we read the line items individually
        sorted_txs = sorted(transactions, key=lambda x: x.amount, reverse=True)[:5]
        
        # We attach this to early_warnings temporarily or return as extras if we modify the model
        # For now, we'll let the main endpoint handle the extraction from mobile_money_history
        
        return AlternativeData(
            borrower_id=borrower_id,
            mobile_money_history=transactions,
            utility_history=utilities,
            airtime_usage_avg=airtime_avg
        )

    @staticmethod
    def _parse_mobile_money_line(line: str):
        # Deprecated in favor of main logic above
        return None
    
    @staticmethod
    def _parse_utility_line(line: str):
        # Deprecated in favor of main logic above
        return None
    
    @staticmethod
    def _map_transaction_type(raw_type: str) -> str:
        """Maps various transaction type names to standard types."""
        raw_type = raw_type.lower()
        
        if any(word in raw_type for word in ['deposit', 'credit', 'received', 'salary']):
            return 'DEPOSIT'
        elif any(word in raw_type for word in ['withdrawal', 'withdraw', 'cash']):
            return 'WITHDRAWAL'
        elif any(word in raw_type for word in ['transfer', 'sent', 'send']):
            return 'TRANSFER_OUT'
        elif any(word in raw_type for word in ['payment', 'bill', 'purchase']):
            return 'PAYMENT'
        else:
            return 'TRANSFER'


def parse_simple_csv_format(csv_text: str, borrower_id: str) -> AlternativeData:
    """
    Alternative parser for CSV-like format.
    
    Expected format:
    Date,Type,Amount,Description
    2024-01-15,DEPOSIT,5000,Salary
    2024-01-16,WITHDRAWAL,2000,ATM
    """
    transactions = []
    lines = csv_text.strip().split('\n')
    
    # Skip header if present
    start_idx = 1 if 'date' in lines[0].lower() else 0
    
    for line in lines[start_idx:]:
        parts = line.split(',')
        if len(parts) >= 3:
            try:
                date_str = parts[0].strip()
                tx_type = parts[1].strip().upper()
                amount = float(parts[2].strip())
                description = parts[3].strip() if len(parts) > 3 else ""
                
                # Parse date (try multiple formats)
                timestamp = None
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                    try:
                        timestamp = datetime.strptime(date_str, fmt)
                        break
                    except:
                        continue
                
                if timestamp:
                    transactions.append(MobileMoneyTransaction(
                        transaction_id=f"TX-{hash(line) % 1000000}",
                        amount=amount,
                        type=tx_type,
                        timestamp=timestamp,
                        counterparty=description or None
                    ))
            except:
                continue
    
    return AlternativeData(
        borrower_id=borrower_id,
        mobile_money_history=transactions,
        utility_history=[],
        airtime_usage_avg=0
    )
