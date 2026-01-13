"""
Lending Rules Engine - Deterministic Business Logic
====================================================

This module implements core lending rules that form the foundation
of the credit decision system. These rules are:

1. DETERMINISTIC: Same inputs always produce same outputs
2. AUDITABLE: Every rule has a clear business justification
3. REGULATORY-COMPLIANT: Based on industry standards and local regulations
4. OVERRIDING: Rules ALWAYS take precedence over ML predictions

Changes to these rules must be approved by the risk committee
and logged for regulatory audit purposes.
"""

from models.borrower import Borrower
from typing import Tuple
import config

# Import thresholds from central configuration
# WHY: Centralized config allows easy adjustment without code changes
MIN_MONTHLY_INCOME = config.MIN_MONTHLY_INCOME
MAX_DEBT_TO_INCOME_RATIO = config.MAX_DEBT_TO_INCOME_RATIO
AFFORDABILITY_RATIO_TARGET = config.AFFORDABILITY_RATIO_TARGET
MIN_BUSINESS_STABILITY_MONTHS = config.MIN_BUSINESS_STABILITY_MONTHS


def check_income_stability(borrower: Borrower) -> bool:
    """
    Verifies borrower meets minimum income threshold.
    
    WHY THIS RULE EXISTS:
    - Ensures borrower has basic capacity to repay any loan
    - Protects both lender (from defaults) and borrower (from over-leverage)
    - Industry standard: Most MFIs require minimum income threshold
    
    REGULATORY CONTEXT:
    - Consumer protection laws often mandate affordability assessments
    - Prevents predatory lending to extremely low-income individuals
    
    Args:
        borrower: Borrower profile with financial information
        
    Returns:
        True if income >= minimum threshold, False otherwise
        
    Example:
        >>> borrower = Borrower(monthly_income=150)
        >>> check_income_stability(borrower)
        True  # Meets 100 minimum
    """
    return borrower.monthly_income >= MIN_MONTHLY_INCOME


def check_dti_ratio(borrower: Borrower) -> float:
    """
    Calculates Debt-to-Income (DTI) ratio.
    
    WHY THIS RULE EXISTS:
    - DTI is the gold standard metric for assessing debt burden
    - High DTI indicates borrower is already over-leveraged
    - Strong predictor of default risk across all credit markets
    
    REGULATORY CONTEXT:
    - Many jurisdictions mandate maximum DTI (typically 40-50%)
    - Basel III banking standards emphasize DTI in risk assessment
    - Consumer Financial Protection Bureau (CFPB) uses DTI in ability-to-repay rules
    
    CALCULATION:
    DTI = Total Monthly Debt Payments / Gross Monthly Income
    
    INTERPRETATION:
    - DTI < 0.3: Healthy debt load
    - DTI 0.3-0.4: Manageable but elevated
    - DTI > 0.4: Over-leveraged, high risk
    
    Args:
        borrower: Borrower profile with income and debt information
        
    Returns:
        DTI ratio as a float (0.0 to 1.0+)
        Returns 1.0 if income is zero (worst case)
        
    Example:
        >>> borrower = Borrower(monthly_income=1000, existing_debt=300)
        >>> check_dti_ratio(borrower)
        0.3  # 30% DTI
    """
    # Edge case: Zero or negative income
    # WHY: Prevents division by zero, assumes worst-case DTI
    if borrower.monthly_income <= 0:
        return 1.0
    
    return borrower.existing_debt / borrower.monthly_income


def check_affordability(borrower: Borrower, loan_term_months: int = 12) -> Tuple[bool, float]:
    """
    Assesses whether borrower can afford the requested loan.
    
    WHY THIS RULE EXISTS:
    - Ensures loan repayment doesn't consume all disposable income
    - Borrowers need income for living expenses beyond debt service
    - Prevents "debt trap" where borrowers can't meet basic needs
    
    REGULATORY CONTEXT:
    - "Ability to Repay" rules require lenders to verify affordability
    - Responsible lending codes mandate consideration of living expenses
    - Microfinance industry best practices (SMART Campaign)
    
    CALCULATION:
    1. Net Income = Gross Income - Monthly Expenses
    2. Estimated Monthly Payment = Loan Amount / Term (months)
    3. Affordability Ratio = Monthly Payment / Net Income
    4. Pass if Ratio <= Target (default 30%)
    
    WHY 30% TARGET:
    - Industry standard: Housing costs should be <30% of income
    - Extends to all debt: Total debt service <30% leaves room for savings
    - Conservative threshold protects vulnerable borrowers
    
    Args:
        borrower: Borrower profile with income, expenses, and loan request
        loan_term_months: Assumed loan term for payment calculation (default: 12)
        
    Returns:
        Tuple of (passes_check: bool, affordability_ratio: float)
        
    Example:
        >>> borrower = Borrower(
        ...     monthly_income=1000,
        ...     monthly_expenses=600,
        ...     loan_amount_requested=1200
        ... )
        >>> check_affordability(borrower)
        (True, 0.25)  # 100/month payment is 25% of 400 net income
    """
    # Calculate net disposable income
    # WHY: Only disposable income is available for debt service
    net_income = borrower.monthly_income - borrower.monthly_expenses
    
    # Edge case: Negative or zero net income
    # WHY: Borrower already spending more than they earn, cannot afford new debt
    if net_income <= 0:
        return False, float('inf')  # Infinite ratio = unaffordable
    
    # Estimate monthly payment (simple amortization)
    # NOTE: This is a simplified calculation. Production systems should use
    # proper amortization formulas accounting for interest rates.
    estimated_monthly_payment = borrower.loan_amount_requested / loan_term_months
    
    # Calculate affordability ratio
    affordability_ratio = estimated_monthly_payment / net_income
    
    # Apply threshold
    passes = affordability_ratio <= AFFORDABILITY_RATIO_TARGET
    
    return passes, affordability_ratio


def check_critical_flags(borrower: Borrower) -> Tuple[bool, list]:
    """
    Checks for critical red flags that trigger automatic rejection.
    
    WHY THIS RULE EXISTS:
    - Some risk factors are so severe they override all other considerations
    - Protects lender from obvious high-risk cases
    - Protects borrower from taking on unaffordable debt
    
    CRITICAL FLAGS:
    1. Income below minimum threshold
    2. DTI exceeds maximum allowed
    3. Negative net income (expenses > income)
    
    These flags represent HARD STOPS that ML cannot override.
    
    Args:
        borrower: Borrower profile to evaluate
        
    Returns:
        Tuple of (has_critical_flags: bool, list_of_flags: list)
        
    Example:
        >>> borrower = Borrower(monthly_income=50, existing_debt=100)
        >>> check_critical_flags(borrower)
        (True, ['CRITICAL: MINIMUM_INCOME_NOT_MET', 'CRITICAL: HIGH_DEBT_TO_INCOME'])
    """
    flags = []
    
    # Check 1: Minimum income
    if not check_income_stability(borrower):
        flags.append("CRITICAL: MINIMUM_INCOME_NOT_MET")
    
    # Check 2: DTI ratio
    dti = check_dti_ratio(borrower)
    if dti > MAX_DEBT_TO_INCOME_RATIO:
        flags.append("CRITICAL: HIGH_DEBT_TO_INCOME")
    
    # Check 3: Affordability
    affordable, ratio = check_affordability(borrower)
    if not affordable:
        flags.append("CRITICAL: INSUFFICIENT_AFFORDABILITY")
    
    return len(flags) > 0, flags

