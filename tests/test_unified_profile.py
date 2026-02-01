"""
Test suite for UnifiedFinancialProfile and ProfileBuilder.

Tests cover:
1. Profile building from complete documents
2. Profile building from partial documents (expect BLOCKED)
3. Assessment gating logic
4. Explicit null handling (no zero-fills)
"""
import sys
import os
sys.path.append(os.getcwd())

from models.document import (
    ExtractionResult,
    DocumentType,
    BankStatementSummary,
    PayslipSummary,
    Transaction,
    StatementPeriod,
)
from models.unified_profile import (
    UnifiedFinancialProfile,
    AssessmentReadiness,
    DocumentPresence,
    VerificationStatus,
)
from utils.profile_builder import ProfileBuilder


def test_profile_build_complete_documents():
    """Test building profile from complete bank statement and payslip."""
    print("Test 1: Building profile from COMPLETE documents...")
    
    # Mock complete bank statement
    bank_summary = BankStatementSummary(
        bank_name="Zanaco",
        account_holder_name="Jane Mwangi",
        currency="ZMW",
        statement_period=StatementPeriod(start="2026-01-01", end="2026-01-31"),
        opening_balance=1000.00,
        closing_balance=1623.18,
        total_money_in=5000.00,
        total_money_out=4376.82,
        salary_detected=True,
        salary_confidence=0.9,
        document_confidence=0.9
    )
    
    # Mock complete payslip
    payslip_summary = PayslipSummary(
        employer_name="CANET CONSULTING LTD",
        employee_name="Jane Mwangi",
        gross_pay=7450.00,
        net_pay=6230.00,
        deductions=1220.00,
        currency="ZMW",
        pay_frequency="MONTHLY",
        document_confidence=0.9
    )
    
    # Mock transactions
    transactions = [
        Transaction(
            date="2026-01-15",
            description="SALARY DEPOSIT",
            amount=6230.00,
            direction="INFLOW",
            balance=None,
            currency="ZMW",
            confidence=0.9,
            flags=["SALARY"]
        ),
        Transaction(
            date="2026-01-20",
            description="GROCERY PURCHASE",
            amount=500.00,
            direction="OUTFLOW",
            balance=None,
            currency="ZMW",
            confidence=0.8,
            flags=[]
        ),
    ]
    
    extraction_results = [
        ExtractionResult(
            document_type=DocumentType.BANK_STATEMENT,
            confidence=0.9,
            bank_statement_summary=bank_summary,
            transactions=transactions
        ),
        ExtractionResult(
            document_type=DocumentType.PAYSLIP,
            confidence=0.9,
            payslip_summary=payslip_summary,
            transactions=[]
        ),
    ]
    
    # Build profile
    profile = ProfileBuilder.build(extraction_results, transactions)
    
    # Assertions
    assert profile.assessment_readiness == AssessmentReadiness.READY, \
        f"Expected READY, got {profile.assessment_readiness}"
    assert len(profile.blocking_reasons) == 0, \
        f"Expected no blocking reasons, got: {profile.blocking_reasons}"
    
    # Identity checks
    assert profile.identity.full_name == "Jane Mwangi", \
        f"Expected 'Jane Mwangi', got '{profile.identity.full_name}'"
    assert profile.identity.bank_name == "Zanaco", \
        f"Expected 'Zanaco', got '{profile.identity.bank_name}'"
    assert profile.identity.employer_name == "CANET CONSULTING LTD", \
        f"Expected 'CANET CONSULTING LTD', got '{profile.identity.employer_name}'"
    
    # Income checks
    assert profile.income.net_pay == 6230.00, \
        f"Expected 6230.00, got {profile.income.net_pay}"
    assert profile.income.gross_pay == 7450.00, \
        f"Expected 7450.00, got {profile.income.gross_pay}"
    assert profile.income.verification_status == VerificationStatus.VERIFIED
    
    # Banking behavior checks
    assert profile.banking_behavior.closing_balance == 1623.18, \
        f"Expected 1623.18, got {profile.banking_behavior.closing_balance}"
    assert profile.banking_behavior.transaction_count == 2, \
        f"Expected 2 transactions, got {profile.banking_behavior.transaction_count}"
    
    # Document coverage checks
    assert profile.document_coverage.bank_statement == DocumentPresence.PRESENT_COMPLETE
    assert profile.document_coverage.payslip == DocumentPresence.PRESENT_COMPLETE
    
    print("✅ Test 1 PASSED: Complete documents create READY profile")


def test_profile_build_missing_payslip():
    """Test that missing payslip results in BLOCKED status."""
    print("\nTest 2: Building profile with MISSING payslip...")
    
    # Only bank statement, no payslip
    bank_summary = BankStatementSummary(
        bank_name="Zanaco",
        currency="ZMW",
        closing_balance=1623.18,
        document_confidence=0.9
    )
    
    extraction_results = [
        ExtractionResult(
            document_type=DocumentType.BANK_STATEMENT,
            confidence=0.9,
            bank_statement_summary=bank_summary,
            transactions=[]
        )
    ]
    
    profile = ProfileBuilder.build(extraction_results, [])
    
    # Should be BLOCKED due to missing payslip
    assert profile.assessment_readiness == AssessmentReadiness.BLOCKED, \
        f"Expected BLOCKED, got {profile.assessment_readiness}"
    assert "Payslip" in str(profile.blocking_reasons), \
        "Expected payslip in blocking reasons"
    assert "payslip" in profile.document_coverage.missing_required_documents
    
    print("✅ Test 2 PASSED: Missing payslip results in BLOCKED status")


def test_profile_build_missing_bank_statement():
    """Test that missing bank statement results in BLOCKED status."""
    print("\nTest 3: Building profile with MISSING bank statement...")
    
    # Only payslip, no bank statement
    payslip_summary = PayslipSummary(
        employer_name="CANET CONSULTING LTD",
        net_pay=6230.00,
        gross_pay=7450.00,
        currency="ZMW",
        document_confidence=0.9
    )
    
    extraction_results = [
        ExtractionResult(
            document_type=DocumentType.PAYSLIP,
            confidence=0.9,
            payslip_summary=payslip_summary,
            transactions=[]
        )
    ]
    
    profile = ProfileBuilder.build(extraction_results, [])
    
    # Should be BLOCKED due to missing bank statement
    assert profile.assessment_readiness == AssessmentReadiness.BLOCKED, \
        f"Expected BLOCKED, got {profile.assessment_readiness}"
    assert "Bank statement" in str(profile.blocking_reasons), \
        "Expected bank statement in blocking reasons"
    assert "bank_statement" in profile.document_coverage.missing_required_documents
    
    print("✅ Test 3 PASSED: Missing bank statement results in BLOCKED status")


def test_explicit_null_handling():
    """Test that missing values are None, not 0."""
    print("\nTest 4: Testing explicit null handling (no zero-fills)...")
    
    # Payslip with only net_pay (gross_pay missing)
    payslip_summary = PayslipSummary(
        net_pay=6230.00,
        gross_pay=None,  # Explicitly None
        deductions=None,
        currency="ZMW",
        document_confidence=0.9
    )
    
    extraction_results = [
        ExtractionResult(
            document_type=DocumentType.PAYSLIP,
            confidence=0.9,
            payslip_summary=payslip_summary,
            transactions=[]
        )
    ]
    
    profile = ProfileBuilder.build(extraction_results, [])
    
    # Check that missing fields are None, NOT 0
    assert profile.income.net_pay == 6230.00, "Net pay should be 6230.00"
    assert profile.income.gross_pay is None, "Gross pay should be None, not 0"
    assert profile.income.deductions is None, "Deductions should be None, not 0"
    
    # Banking behavior defaults
    assert profile.banking_behavior.opening_balance is None, \
        "Opening balance should be None, not 0"
    assert profile.banking_behavior.closing_balance is None, \
        "Closing balance should be None, not 0"
    
    print("✅ Test 4 PASSED: Missing numeric fields are None, not zero-filled")


def test_insufficient_transaction_history():
    """Test that insufficient transaction history results in BLOCKED."""
    print("\nTest 5: Testing insufficient transaction history...")
    
    # Bank statement with very short history (< 7 days)
    bank_summary = BankStatementSummary(
        bank_name="Zanaco",
        currency="ZMW",
        statement_period=StatementPeriod(start="2026-01-01", end="2026-01-03"),  # Only 2 days
        closing_balance=1000.00,
        document_confidence=0.9
    )
    
    payslip_summary = PayslipSummary(
        net_pay=6230.00,
        currency="ZMW",
        document_confidence=0.9
    )
    
    extraction_results = [
        ExtractionResult(
            document_type=DocumentType.BANK_STATEMENT,
            confidence=0.9,
            bank_statement_summary=bank_summary,
            transactions=[]
        ),
        ExtractionResult(
            document_type=DocumentType.PAYSLIP,
            confidence=0.9,
            payslip_summary=payslip_summary,
            transactions=[]
        ),
    ]
    
    profile = ProfileBuilder.build(extraction_results, [])
    
    # Should be BLOCKED due to insufficient history
    assert profile.assessment_readiness == AssessmentReadiness.BLOCKED, \
        f"Expected BLOCKED, got {profile.assessment_readiness}"
    assert any("history" in reason.lower() for reason in profile.blocking_reasons), \
        "Expected history warning in blocking reasons"
    
    print("✅ Test 5 PASSED: Insufficient transaction history results in BLOCKED")


if __name__ == "__main__":
    try:
        test_profile_build_complete_documents()
        test_profile_build_missing_payslip()
        test_profile_build_missing_bank_statement()
        test_explicit_null_handling()
        test_insufficient_transaction_history()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED! ✅")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
