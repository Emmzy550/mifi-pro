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
from utils.policy_context import policy_value

# Helpers: resolve per-org policy overrides when set
def _min_monthly_income() -> float:
    return float(policy_value("min_monthly_income", config.MIN_MONTHLY_INCOME))

def _max_dti() -> float:
    return float(policy_value("max_debt_to_income_ratio", config.MAX_DEBT_TO_INCOME_RATIO))

def _affordability_target() -> float:
    return float(policy_value("affordability_ratio_target", config.AFFORDABILITY_RATIO_TARGET))

MIN_BUSINESS_STABILITY_MONTHS = config.MIN_BUSINESS_STABILITY_MONTHS


def loan_term_months_from_days(requested_duration_days: int) -> float:
    """
    Converts a requested tenor in days into an equivalent month fraction.

    We use a simple 30-day month so short-tenor products keep their intended
    repayment pressure instead of being diluted across a default annual term.
    """
    try:
        days = float(requested_duration_days)
    except (TypeError, ValueError):
        return 12.0

    if days <= 0:
        return 12.0

    return max(days / 30.0, 1.0 / 30.0)


def calculate_affordable_amount(borrower: Borrower, loan_term_months: float = 12.0) -> float:
    """
    Computes the maximum principal supportable within the affordability target.
    """
    net_income = borrower.monthly_income - borrower.monthly_expenses
    if net_income <= 0:
        return 0.0

    safe_term_months = max(float(loan_term_months), 1.0 / 30.0)
    affordable_amount = net_income * _affordability_target() * safe_term_months
    return max(0.0, affordable_amount)


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
    return borrower.monthly_income >= _min_monthly_income()


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


def check_affordability(borrower: Borrower, loan_term_months: float = 12.0) -> Tuple[bool, float]:
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
    safe_term_months = max(float(loan_term_months), 1.0 / 30.0)
    estimated_monthly_payment = borrower.loan_amount_requested / safe_term_months
    
    # Calculate affordability ratio
    affordability_ratio = estimated_monthly_payment / net_income
    
    # Apply threshold
    passes = affordability_ratio <= _affordability_target()
    
    return passes, affordability_ratio


def check_critical_flags(
    borrower: Borrower,
    loan_term_months: float = 12.0,
    allow_affordability_cap: bool = False,
) -> Tuple[bool, list]:
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
    if dti > _max_dti():
        flags.append("CRITICAL: HIGH_DEBT_TO_INCOME")
    
    # Check 3: Affordability
    affordable, _ = check_affordability(borrower, loan_term_months=loan_term_months)
    if not affordable:
        affordable_amount = calculate_affordable_amount(
            borrower,
            loan_term_months=loan_term_months,
        )
        if allow_affordability_cap and affordable_amount > 0:
            flags.append("WARNING: AFFORDABILITY_CAP_REQUIRED")
        else:
            flags.append("CRITICAL: INSUFFICIENT_AFFORDABILITY")

    return len(flags) > 0, flags

