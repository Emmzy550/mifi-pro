import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.extractors.bank_statement import BankStatementExtractor

# Test case 2
test_text = """
STANBIC BANK

Account Holder: JOHN MUKUKA CHILESHE
Branch Name: Lusaka Main
Account Number: 9876543210

Statement Period: 1 Feb 2024 - 28 Feb 2024
"""

print("Test text:")
print(test_text)
print("\n" + "="*80)

extractor = BankStatementExtractor()
result = extractor._extract_account_holder_name(test_text)

print("\n" + "="*80)
print(f"FINAL RESULT: {result}")
print("="*80)
