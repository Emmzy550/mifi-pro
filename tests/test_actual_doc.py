import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from utils.extractors.bank_statement import BankStatementExtractor

# Actual text from the document the user provided
actual_doc_text = """Zanaco Statement of Account
From: Nov 04, 2025
Account Number:        7480701200229
Account Name:          EMMANUEL BWANGA
Home Branch:           040
Account Currency:      ZMW

Statement Period: Nov 04, 2025 - Jan 04, 2026
"""

extractor = BankStatementExtractor()

print("="*80)
print("Testing with ACTUAL document structure")
print("="*80)

result = extractor._extract_account_holder_name(actual_doc_text)

print("\n" + "="*80)
print(f"RESULT: '{result}'")
print(f"EXPECTED: 'Emmanuel Bwanga'")
print("="*80)

if result and "EMMANUEL" in result.upper() and "BWANGA" in result.upper():
    print("\n✓ SUCCESS: Correctly extracted account holder from columnar format!")
else:
    print(f"\n✗ FAILED: Expected 'Emmanuel Bwanga', got '{result}'")
