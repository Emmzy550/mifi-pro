import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.extractors.bank_statement import BankStatementExtractor

def test_account_holder_extraction():
    """Test that account holder extraction correctly excludes branch metadata."""
    
    extractor = BankStatementExtractor()
    
    # Test case 1: Valid account holder with branch metadata present
    test_text_1 = """
    ZANACO BANK
    Statement of Account
    
    Account Name:
    EMMANUEL BWANGA
    
    Account Number: 1234567890
    Home Branch: Downtown Branch
    Branch Code: 001
    
    Statement Period: 1 Jan 2024 - 31 Jan 2024
    
    01/01/2024  Opening Balance  1000.00
    05/01/2024  Salary Deposit   5000.00
    """
    
    print("\n" + "="*80)
    print("TEST 1: Valid account holder with branch metadata")
    print("="*80)
    result = extractor._extract_account_holder_name(test_text_1)
    print(f"\nRESULT: '{result}'")
    print(f"EXPECTED: 'Emmanuel Bwanga'")
    assert result is not None, "Account holder should be extracted"
    assert "BRANCH" not in result.upper(), f"Result should not contain 'BRANCH': {result}"
    assert "EMMANUEL" in result.upper(), f"Result should contain 'EMMANUEL': {result}"
    assert "BWANGA" in result.upper(), f"Result should contain 'BWANGA': {result}"
    print("[PASS] Correctly extracted account holder, excluded branch metadata")

    
    # Test case 2: Account holder inline format
    test_text_2 = """
    STANBIC BANK
    
    Account Holder: JOHN MUKUKA CHILESHE
    Branch Name: Lusaka Main
    Account Number: 9876543210
    
    Statement Period: 1 Feb 2024 - 28 Feb 2024
    """
    
    print("\n" + "="*80)
    print("TEST 2: Inline account holder format")
    print("="*80)
    result = extractor._extract_account_holder_name(test_text_2)
    print(f"\nRESULT: '{result}'")
    print(f"EXPECTED: 'John Mukuka Chileshe'")
    assert result is not None, "Account holder should be extracted"
    assert "JOHN" in result.upper(), f"Result should contain 'JOHN': {result}"
    assert "BRANCH" not in result.upper(), f"Result should not contain 'BRANCH': {result}"
    print("[PASS] Correctly extracted inline account holder")
    
    # Test case 3: Only branch metadata, no valid account holder
    test_text_3 = """
    ABSA BANK
    
    Home Branch: City Center
    Branch Code: 123
    Account Number: 5555555555
    
    Statement Period: 1 Mar 2024 - 31 Mar 2024
    """
    
    print("\n" + "="*80)
    print("TEST 3: No valid account holder (only branch metadata)")
    print("="*80)
    result = extractor._extract_account_holder_name(test_text_3)
    print(f"\nRESULT: '{result}'")
    print(f"EXPECTED: None")
    assert result is None, f"Should return None when no valid account holder found, got: {result}"
    print("[PASS] Correctly returned None for missing account holder")
    
    # Test case 4: Priority test - Account Name takes precedence
    test_text_4 = """
    FNB BANK
    
    Customer Name: MARY BANDA
    Account Name: PETER PHIRI MWANZA
    Account Holder: JANE ZULU
    
    Statement Period: 1 Apr 2024 - 30 Apr 2024
    """
    
    print("\n" + "="*80)
    print("TEST 4: Priority ordering (Account Name > Account Holder > Customer Name)")
    print("="*80)
    result = extractor._extract_account_holder_name(test_text_4)
    print(f"\nRESULT: '{result}'")
    print(f"EXPECTED: 'Peter Phiri Mwanza' (highest priority)")
    assert result is not None, "Account holder should be extracted"
    assert "PETER" in result.upper(), f"Should select 'Account Name' over others: {result}"
    assert "MARY" not in result.upper(), f"Should not select lower priority 'Customer Name': {result}"
    assert "JANE" not in result.upper(), f"Should not select lower priority 'Account Holder': {result}"
    print("[PASS] Correctly prioritized Account Name over other fields")
    
    # Test case 5: Single token name (should be rejected)
    test_text_5 = """
    ZANACO BANK
    
    Account Name: Emmanuel
    Account Number: 1111111111
    
    Statement Period: 1 May 2024 - 31 May 2024
    """
    
    print("\n" + "="*80)
    print("TEST 5: Single token name (should be rejected)")
    print("="*80)
    result = extractor._extract_account_holder_name(test_text_5)
    print(f"\nRESULT: '{result}'")
    print(f"EXPECTED: None (single token rejected)")
    assert result is None, f"Single token names should be rejected, got: {result}"
    print("[PASS] Correctly rejected single token name")
    
    print("\n" + "="*80)
    print("ALL TESTS PASSED!")
    print("="*80)
    print("\nSUMMARY:")
    print("[OK] Correctly extracts valid account holder names")
    print("[OK] Excludes branch metadata like 'Home Branch'")
    print("[OK] Returns None when no valid candidate found")
    print("[OK] Enforces priority rules (Account Name > Account Holder > Customer Name)")
    print("[OK] Validates candidates (2+ tokens, 5+ chars)")
    print("="*80)

if __name__ == "__main__":
    test_account_holder_extraction()
