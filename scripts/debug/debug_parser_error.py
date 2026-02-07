import sys
import os
from datetime import datetime

# Add current dir to path
sys.path.append(os.getcwd())

from utils.transaction_parser import TransactionParser, ExtractionResult

def debug_parser():
    parser = TransactionParser()
    
    # Mock content based on user log: [SAVE] WITHDRAWAL 200.0 (05-24 1003  00094613)
    content = b"05-24 1003 WITHDRAWAL 200.00 00094613\n"
    filename = "statement.pdf"
    
    try:
        print(f"Calling parser.parse with content: {content}")
        result = parser.parse(content, filename)
        print(f"Result document_type: {result.document_type}")
        print(f"Transactions found: {len(result.transactions)}")
        
        for i, tx in enumerate(result.transactions):
            print(f"Transaction {i} type: {type(tx)}")
            print(f"Transaction {i} item: {tx}")
            # This is where it fails in api.py if tx is a tuple
            t_id = tx.transaction_id
            print(f"Transaction {i} ID: {t_id}")
            
    except Exception as e:
        import traceback
        print(f"CAUGHT ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_parser()
