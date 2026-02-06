import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.extractors.bank_statement import BankStatementExtractor
from models.document import NumericRole

def test_bank_balance_extraction():
    extractor = BankStatementExtractor()
    
    # Test 1: Combined Date and Balance (Zanaco style)
    # The '04' and '2026' should be ignored as balances, and 1623.18 selected
    text1 = """
    Book Balance As At: Jan 04, 2026
    1,623.18
    """
    result1 = extractor.extract(text1)
    summary1 = result1.bank_statement_summary
    print(f"Test 1 (Look-ahead Balance): Closing={summary1.closing_balance}")
    assert summary1.closing_balance == 1623.18
    
    # Test 2: Multiple numbers where one is a date
    # 'Jan 04' has '4'. The extractor should pick 500.00
    text2 = """
    Current Available Balance Jan 04 500.00
    """
    result2 = extractor.extract(text2)
    summary2 = result2.bank_statement_summary
    print(f"Test 2 (Inline with Date): Closing={summary2.closing_balance}")
    assert summary2.closing_balance == 500.0
    
    # Test 3: New synonyms
    text3 = """
    ENDING BALANCE 2500.50
    """
    result3 = extractor.extract(text3)
    summary3 = result3.bank_statement_summary
    print(f"Test 3 (New Synonym): Closing={summary3.closing_balance}")
    assert summary3.closing_balance == 2500.5

    print("\nALL BANK BALANCE TESTS PASSED! ✓")

if __name__ == "__main__":
    test_bank_balance_extraction()
