"""
Capacity Configuration - Bank-Grade Lending Thresholds
========================================================

This module defines all capacity-based lending thresholds and multipliers
for the conservative loan decision engine.

PHILOSOPHY:
- Anchor decisions to DEMONSTRATED CAPACITY (transaction data)
- Be more conservative than a human loan officer
- Ensure every decision is defensible to regulators
- Protect against sparse or manipulated data

All values are configurable for different risk appetites and markets.
"""

# ====================================================================
# TRANSACTION HISTORY REQUIREMENTS
# ====================================================================
# Minimum data requirements to assess repayment capacity

# Minimum number of transactions required to make a lending decision
# WHY: Fewer than 5 transactions provides insufficient behavioral data
MIN_TRANSACTION_COUNT = 5

# Minimum monthly deposit volume (in local currency) to qualify for any loan
# WHY: Below this threshold, repayment capacity cannot be reliably assessed
# EXAMPLE: For USD/KES markets, adjust accordingly
MIN_CAPACITY_THRESHOLD = 1000

# Minimum days of transaction history required
# WHY: Ensures we observe at least one full deposit cycle
MIN_HISTORY_DAYS = 30

# ====================================================================
# CAPACITY MULTIPLIERS BY RISK LEVEL
# ====================================================================
# These define maximum loan as multiple of observed deposit volume
# PHILOSOPHY: Lower risk = higher confidence = higher multiple

# LOW RISK: Strong financial indicators, positive behavioral signals
# Can lend up to 4x observed deposit volume (equivalent to ~4 month payback)
CAPACITY_MULTIPLIER_LOW_RISK = 4.0

# MEDIUM RISK: Some concerns but manageable
# Can lend up to 2x observed deposit volume (equivalent to ~2 month payback)
CAPACITY_MULTIPLIER_MEDIUM_RISK = 2.0

# HIGH RISK: Significant concerns
# Can lend up to 1x observed deposit volume (equivalent to ~1 month payback)
# WHY: Maximum caution - only lend what they deposit in one month
CAPACITY_MULTIPLIER_HIGH_RISK = 1.0

# ====================================================================
# STARTER LOAN POLICY (THIN-FILE BORROWERS)
# ====================================================================
# Special conservative policy for borrowers with limited history

# History threshold (in days) for starter loan classification
# Borrowers with less than this get starter loan terms
STARTER_HISTORY_THRESHOLD_DAYS = 90

# Deposit volume threshold for starter loan classification
# Borrowers with volume less than this get starter loan terms
STARTER_DEPOSIT_THRESHOLD = 5000

# Maximum starter loan amount (absolute cap)
# WHY: Limits exposure for unproven borrowers
STARTER_LOAN_CAP = 1000

# Interest rate premium for starter loans (percentage points)
# WHY: Compensates for higher uncertainty
# EXAMPLE: If base rate is 15%, starter rate is 20%
STARTER_INTEREST_PREMIUM = 5.0

# ====================================================================
# MICRO-STARTER POLICY (THIN-FILE EXCEPTION)
# ====================================================================
# Safe, auditable exception for very small loans with limited history

# Minimum transaction count for normal (non-micro) assessment
MIN_HISTORY_FOR_NORMAL = 5

# Maximum amount allowed under micro-starter exception
MICRO_LOAN_CAP = 300

# Cap as percentage of observed monthly deposit volume (50%)
MICRO_MULTIPLIER = 0.5

# Minimum deposit volume required for micro-starter consideration
MIN_DEPOSIT_VOLUME_FOR_MICRO = 300

# ====================================================================
# LOAN DURATION POLICY
# ====================================================================
# Duration constraints for loan terms

# Minimum loan duration allowed (days)
MIN_DURATION_DAYS = 7

# Maximum loan duration allowed (days)
MAX_DURATION_DAYS = 365

# Maximum duration for starter loans (days)
# WHY: Starter borrowers get shorter terms to build repayment history faster
STARTER_LOAN_MAX_DURATION_DAYS = 30

# Duration-based interest rate adjustments (percentage points)
# Loans shorter than 30 days get a discount, longer than 180 days get a premium
SHORT_TENOR_THRESHOLD_DAYS = 30
LONG_TENOR_THRESHOLD_DAYS = 180
SHORT_TENOR_DISCOUNT = 2.0  # -2% for very short terms
LONG_TENOR_PREMIUM = 3.0    # +3% for long terms

# ====================================================================
# POLICY LIMITS
# ====================================================================
# Hard caps to prevent unreasonable lending

# Maximum loan-to-capacity ratio (safety override)
# WHY: Even for low-risk borrowers, never exceed this multiple
# NOTE: This is a backstop - normal multipliers should prevent hitting this
MAX_LOAN_TO_CAPACITY_RATIO = 4.0

# Maximum loan amount regardless of capacity (absolute ceiling)
# WHY: Risk management - cap exposure to any single borrower
# Set to None for no limit, or a specific amount
MAX_ABSOLUTE_LOAN_AMOUNT = None  # Can be set to e.g., 50000

# ====================================================================
# VALIDATION THRESHOLDS
# ====================================================================
# Thresholds for flagging suspicious data

# Flag if outflow exceeds this multiple of inflow
# WHY: May indicate manipulated data or unsustainable spending
SUSPICIOUS_OUTFLOW_MULTIPLIER = 2.0

# Flag if all transactions are deposits (no expenses)
# WHY: Likely manipulated or incomplete data
MIN_OUTFLOW_RATIO = 0.1  # At least 10% of transactions should be expenses

# ====================================================================
# HELPER FUNCTIONS
# ====================================================================

def get_capacity_multiplier(risk_level: str) -> float:
    """
    Returns the appropriate capacity multiplier for a given risk level.
    
    Args:
        risk_level: One of "LOW", "MEDIUM", "HIGH"
        
    Returns:
        Multiplier to apply to observed deposit volume
        
    Raises:
        ValueError: If risk_level is invalid
    """
    multipliers = {
        "LOW": CAPACITY_MULTIPLIER_LOW_RISK,
        "MEDIUM": CAPACITY_MULTIPLIER_MEDIUM_RISK,
        "HIGH": CAPACITY_MULTIPLIER_HIGH_RISK
    }
    
    if risk_level not in multipliers:
        raise ValueError(f"Invalid risk_level: {risk_level}. Must be LOW, MEDIUM, or HIGH")
    
    return multipliers[risk_level]


def validate_config():
    """
    Validates that configuration values are sensible.
    
    Raises:
        ValueError: If configuration is invalid
    """
    # Multipliers should be descending
    if not (CAPACITY_MULTIPLIER_LOW_RISK >= CAPACITY_MULTIPLIER_MEDIUM_RISK >= CAPACITY_MULTIPLIER_HIGH_RISK):
        raise ValueError("Capacity multipliers must be descending: LOW >= MEDIUM >= HIGH")
    
    # Starter cap should be less than typical low-risk lending
    if MIN_CAPACITY_THRESHOLD * CAPACITY_MULTIPLIER_LOW_RISK < STARTER_LOAN_CAP:
        print(f"WARNING: Starter loan cap ({STARTER_LOAN_CAP}) exceeds minimum capacity lending")
    
    # Interest premium should be positive
    if STARTER_INTEREST_PREMIUM < 0:
        raise ValueError("Starter interest premium must be positive")
    
    # Transaction count must be positive
    if MIN_TRANSACTION_COUNT < 1:
        raise ValueError("Minimum transaction count must be at least 1")
    
    print("[OK] Capacity configuration validated successfully")


# Run validation on import
validate_config()
