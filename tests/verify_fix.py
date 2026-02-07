"""
Quick test to verify the fix is working with the current code.
This will simulate what the API is doing.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from utils.extractors.bank_statement import BankStatementExtractor

# Simulated text that might be coming from the actual document
test_cases = [
    # Case 1: "Home Branch" appears but should NOT be extracted
    """
    ZANACO BANK
    Statement of Account
    
    Account Name:
    Home Branch
    
    Account Number: 1234567890
    Statement Period: 1 Jan 2024 - 31 Jan 2024
    """,
    
    # Case 2: "Home Branch" as a field label
    """
    ZANACO BANK
    
    Home Branch: Downtown
    Account Number: 1234567890
    
    Statement Period: 1 Jan 2024 - 31 Jan 2024
    """,
    
    # Case 3: Valid name present
    """
    ZANACO BANK
    Statement of Account
    
    Account Name: EMMANUEL BWANGA
    Home Branch: Downtown
    
    Statement Period: 1 Jan 2024 - 31 Jan 2024
    """,
]

extractor = BankStatementExtractor()

for i, text in enumerate(test_cases, 1):
    print(f"\n{'='*80}")
    print(f"TEST CASE {i}")
    print(f"{'='*80}")
    result = extractor._extract_account_holder_name(text)
    print(f"\nEXTRACTED: {result}")
    print(f"{'='*80}")
