import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from utils.extractors.bank_statement import BankStatementExtractor

# Test different possible OCR formats
test_cases = [
    # Format 1: Separate lines
    """
Account Number:
7480701200229
Account Name:
Home Branch:
040
""",
    # Format 2: Mixed
    """
Account Number:
7480701200229
Account Name:
EMMANUEL BWANGA
Home Branch:
040
""",
    # Format 3: What we think it might be
    """
Account Name:
Home Branch:
"""
]

extractor = BankStatementExtractor()

for i, text in enumerate(test_cases, 1):
    print(f"\n{'='*80}")
    print(f"TEST CASE {i}")
    print(f"{'='*80}")
    print(f"INPUT TEXT:\n{text}")
    print(f"{'-'*80}")
    result = extractor._extract_account_holder_name(text)
    print(f"\nRESULT: '{result}'")
    print(f"{'='*80}")
