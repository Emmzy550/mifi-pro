"""
Pilot Configuration - Relaxed Thresholds for Early Adopters
=============================================================

These thresholds are more lenient to enable pilot testing with:
- Salary-based borrowers (not mobile money heavy users)
- Short statement periods (1-2 months)
- Verified income from payslips

This configuration works alongside capacity_config.py:
- capacity_config.py = Production-grade conservative thresholds
- pilot_config.py = Pilot-friendly relaxed thresholds (THIS FILE)

Toggle between modes using PILOT_MODE_ENABLED flag.
"""

# ====================================================================
# PILOT MODE TOGGLE
# ====================================================================

PILOT_MODE_ENABLED = True  # Set to False for production deployment

# ====================================================================
# VERIFIED INCOME OVERRIDES (PILOT)
# ====================================================================
# Allow verified income (payslip) to replace deposit volume requirement

# Enable verified income as primary capacity source
ALLOW_VERIFIED_INCOME_OVERRIDE = True

# Minimum verified income required (in local currency)
# Borrower must have at least this much net pay to use income-based capacity
MIN_VERIFIED_INCOME = 2000

# Capacity multipliers when using verified income as base
# These are more conservative than deposit volume multipliers
# because we're trusting documented income over observed behavior
VERIFIED_INCOME_MULTIPLIER_LOW_RISK = 1.5    # Can borrow 1.5x monthly net income
VERIFIED_INCOME_MULTIPLIER_MEDIUM_RISK = 1.0 # Can borrow 1x monthly net income
VERIFIED_INCOME_MULTIPLIER_HIGH_RISK = 0.5   # Can borrow 0.5x monthly net income

# ====================================================================
# BEHAVIORAL DATA REQUIREMENTS (PILOT)
# ====================================================================
# Even with verified income, we need to see spending behavior

# Minimum behavioral transactions (spending/expense transactions)
# Reduced from production standard to allow shorter statements
MIN_BEHAVIORAL_TRANSACTIONS = 3  # Production would be 20-30

# Minimum statement period when verified income is available
# With verified income, we can tolerate shorter transaction history
MIN_HISTORY_DAYS_WITH_VERIFIED_INCOME = 14  # 2 weeks instead of 30 days

# ====================================================================
# DEPOSIT VOLUME FALLBACK (PILOT)
# ====================================================================
# If no verified income available, use relaxed deposit volume threshold

# Minimum deposit volume for non-verified-income path (pilot)
MIN_CAPACITY_THRESHOLD_PILOT = 500  # Reduced from 1000 (production)

# Minimum transactions for deposit volume path (pilot)
MIN_TRANSACTION_COUNT_PILOT = 3  # Reduced from 5 (production)

# ====================================================================
# REJECTION REASON CODES
# ====================================================================

class RejectionReason:
    """Structured rejection reason codes for clear user guidance"""
    
    INSUFFICIENT_DEPOSIT_VOLUME = "INSUFFICIENT_DEPOSIT_VOLUME"
    INSUFFICIENT_BEHAVIORAL_DATA = "INSUFFICIENT_BEHAVIORAL_DATA"
    SHORT_STATEMENT_PERIOD = "SHORT_STATEMENT_PERIOD"
    NO_TRANSACTION_HISTORY = "NO_TRANSACTION_HISTORY"
    INCOME_PRESENT_BUT_BEHAVIOR_LIMITED = "INCOME_PRESENT_BUT_BEHAVIOR_LIMITED"
    VERIFIED_INCOME_TOO_LOW = "VERIFIED_INCOME_TOO_LOW"
    NO_VERIFIED_INCOME_OR_DEPOSIT_VOLUME = "NO_VERIFIED_INCOME_OR_DEPOSIT_VOLUME"

# ====================================================================
# USER-FRIENDLY MESSAGES
# ====================================================================

REJECTION_MESSAGES = {
    RejectionReason.INSUFFICIENT_BEHAVIORAL_DATA: (
        "Account verified. Income verified. More transaction history is required to assess spending behavior. "
        "Please upload a bank statement covering at least 30 days."
    ),
    RejectionReason.INSUFFICIENT_DEPOSIT_VOLUME: (
        "Insufficient transaction history detected. "
        "Please upload a recent payslip to verify income, or a longer bank statement."
    ),
    RejectionReason.SHORT_STATEMENT_PERIOD: (
        "Bank statement period is too short. "
        "Please upload a statement covering at least 30 days, or provide a recent payslip."
    ),
    RejectionReason.NO_TRANSACTION_HISTORY: (
        "No transaction history found. "
        "Please upload a bank statement with transaction details."
    ),
    RejectionReason.INCOME_PRESENT_BUT_BEHAVIOR_LIMITED: (
        "Income verified successfully. However, more spending transaction data is needed. "
        "Please upload a bank statement showing at least 2-4 weeks of transactions."
    ),
    RejectionReason.VERIFIED_INCOME_TOO_LOW: (
        f"Verified income is below minimum threshold (ZMW {MIN_VERIFIED_INCOME}). "
        "Please upload a more recent payslip or bank statement with higher income deposits."
    ),
    RejectionReason.NO_VERIFIED_INCOME_OR_DEPOSIT_VOLUME: (
        "Unable to verify repayment capacity. "
        "Please upload both a recent payslip and a bank statement with transaction history."
    )
}

def get_rejection_message(reason_code: str, **context) -> str:
    """
    Get user-friendly rejection message for a given reason code.
    
    Args:
        reason_code: One of RejectionReason codes
        **context: Additional context for message formatting
        
    Returns:
        User-friendly message string
    """
    message = REJECTION_MESSAGES.get(reason_code, "Insufficient data for assessment.")
    
    # Allow message customization with context
    try:
        return message.format(**context)
    except:
        return message

# ====================================================================
# HELPER FUNCTIONS
# ====================================================================

def get_verified_income_multiplier(risk_level: str) -> float:
    """
    Returns capacity multiplier for verified income-based lending.
    
    Args:
        risk_level: One of "LOW", "MEDIUM", "HIGH"
        
    Returns:
        Multiplier to apply to verified monthly income
    """
    multipliers = {
        "LOW": VERIFIED_INCOME_MULTIPLIER_LOW_RISK,
        "MEDIUM": VERIFIED_INCOME_MULTIPLIER_MEDIUM_RISK,
        "HIGH": VERIFIED_INCOME_MULTIPLIER_HIGH_RISK
    }
    
    if risk_level not in multipliers:
        raise ValueError(f"Invalid risk_level: {risk_level}. Must be LOW, MEDIUM, or HIGH")
    
    return multipliers[risk_level]

# ====================================================================
# VALIDATION
# ====================================================================

def validate_pilot_config():
    """Validates that pilot configuration is sensible"""
    
    # Verify multipliers are positive
    assert VERIFIED_INCOME_MULTIPLIER_LOW_RISK > 0, "Income multipliers must be positive"
    assert VERIFIED_INCOME_MULTIPLIER_MEDIUM_RISK > 0, "Income multipliers must be positive"
    assert VERIFIED_INCOME_MULTIPLIER_HIGH_RISK > 0, "Income multipliers must be positive"
    
    # Verify multipliers are descending
    assert (VERIFIED_INCOME_MULTIPLIER_LOW_RISK >= 
            VERIFIED_INCOME_MULTIPLIER_MEDIUM_RISK >= 
            VERIFIED_INCOME_MULTIPLIER_HIGH_RISK), \
            "Income multipliers must be descending: LOW >= MEDIUM >= HIGH"
    
    # Verify minimum income is positive
    assert MIN_VERIFIED_INCOME > 0, "Minimum verified income must be positive"
    
    # Verify behavioral requirements are reasonable
    assert MIN_BEHAVIORAL_TRANSACTIONS >= 1, "Must require at least 1 behavioral transaction"
    assert MIN_HISTORY_DAYS_WITH_VERIFIED_INCOME >= 1, "Must require at least 1 day of history"
    
    if PILOT_MODE_ENABLED:
        print("[OK] Pilot configuration validated successfully (PILOT MODE ACTIVE)")
    else:
        print("[OK] Pilot configuration validated successfully (PRODUCTION MODE)")

# Run validation on import
validate_pilot_config()
