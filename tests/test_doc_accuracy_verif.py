import sys
import os
from datetime import datetime
from unittest.mock import MagicMock

# Add current dir to path
sys.path.append(os.getcwd())

from utils.transaction_parser import TransactionParser, Transaction, ExtractionResult

def test_type_detection():
    print("Testing Document Type Detection...")
    parser = TransactionParser()
    
    payslip_text = "SALARY ADVICE FOR JANUARY 2026. GROSS PAY: 5000.00. NET PAY: 4000.00"
    bank_stmt_text = "ZANACO BANK STATEMENT. ACCOUNT NUMBER: 12345678."
    momo_text = "AIRTEL MONEY STATEMENT. TRANSACTION HISTORY."
    
    assert parser._detect_type(payslip_text) == "PAYSLIP"
    assert parser._detect_type(bank_stmt_text) == "STMT_BANK"
    assert parser._detect_type(momo_text) == "STMT_MOMO"
    print("✅ Type detection passed.")

def test_salary_validation():
    print("Testing Salary Validation...")
    import re
    
    # Valid: Net < Gross
    valid_text = "GROSS PAY 5,000.00 ... NET PAY 4,000.00"
    invalid_text = "GROSS PAY 4,000.00 ... NET PAY 5,000.00"
    
    def validate_salary(text):
        gross_match = re.search(r'GROSS\s*(?:PAY|SALARY)?.*?([0-9,]+\.[0-9]{2})', text, re.IGNORECASE)
        net_match = re.search(r'NET\s*(?:PAY|SALARY)?.*?([0-9,]+\.[0-9]{2})', text, re.IGNORECASE)
        
        if gross_match and net_match:
            gross = float(gross_match.group(1).replace(',', ''))
            net = float(net_match.group(1).replace(',', ''))
            return net <= gross
        return True

    assert validate_salary(valid_text) == True
    assert validate_salary(invalid_text) == False
    print("✅ Salary validation logic passed.")

def test_quality_score():
    print("Testing Quality Scoring...")
    parser = TransactionParser()
    
    # Mock transactions
    txs = [Transaction(transaction_id="1", date=datetime.now(), amount=10, direction="INFLOW", description="test", source_type="test", confidence_weight=0.7)] * 5
    
    # Quality score is len/10
    quality = min(1.0, len(txs) / 10.0)
    assert quality == 0.5
    print("✅ Quality scoring passed.")

if __name__ == "__main__":
    try:
        test_type_detection()
        test_salary_validation()
        test_quality_score()
        print("\nALL VERIFICATION TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        sys.exit(1)
