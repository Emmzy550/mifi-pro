import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from utils.extractors.bank_statement import BankStatementExtractor

# Actual OCR format from the terminal output
actual_ocr_text = """Zanaco Statement of Account
From: Nov 04, 2025
Account Number:
Account Name:
Home Branch:
Account Currency:To: Jan 04, 2026
7480701200229
EMMANUEL BWANGA
040
ZMW"""

extractor = BankStatementExtractor()

print("="*80)
print("Testing with ACTUAL OCR FORMAT")
print("="*80)

result = extractor._extract_account_holder_name(actual_ocr_text)

print("\n" + "="*80)
print(f"RESULT: '{result}'")
print(f"EXPECTED: 'Emmanuel Bwanga'")
print("="*80)

if result and "EMMANUEL" in result.upper() and "BWANGA" in result.upper():
    print("\nSUCCESS: Correctly extracted account holder!")
else:
    print(f"\nFAILED: Expected 'Emmanuel Bwanga', got '{result}'")
