"""
Loan Officer AI - Central Configuration
========================================

This module contains all configurable parameters for the system.
Feature flags allow gradual rollout and instant fallback if needed.

IMPORTANT: Changes to this file affect decision logic.
All modifications should be logged and reviewed by compliance team.
"""

from typing import Dict, Any
import os

# ============================================================================
# FEATURE FLAGS
# ============================================================================
# These flags control which AI components are active.
# Disable flags to fall back to rule-based operation for regulatory compliance.

# V3: Enable ML-based risk scoring (XGBoost + SHAP)
# WHY: Improves accuracy for borderline cases with alternative data
# SAFETY: Rules ALWAYS override ML when critical flags are present
ENABLE_ML_RISK_SCORING: bool = os.getenv("ENABLE_ML_RISK_SCORING", "true").lower() == "true"

# V4: Enable LLM-powered explanation rephrasing
# WHY: Makes explanations more natural and easier to understand
# SAFETY: LLM never sees raw scores or makes decisions, only rephrases pre-computed text
ENABLE_LLM_EXPLANATIONS: bool = os.getenv("ENABLE_LLM_EXPLANATIONS", "false").lower() == "true"

# V2: Enable enhanced behavioral intelligence
# WHY: Alternative data (mobile money, utilities) provides signals for thin-file borrowers
# SAFETY: Purely analytical, no AI involved in V2 behavioral metrics
ENABLE_BEHAVIORAL_V2: bool = os.getenv("ENABLE_BEHAVIORAL_V2", "true").lower() == "true"

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================
# Controls how ML predictions are weighted in ensemble scoring

# Current ML model version (updated by training pipeline)
ML_MODEL_VERSION: str = "v1.0.0"

# Ensemble weights (must sum to 1.0)
# WHY: Conservative weighting (70% rules, 30% ML) ensures rules dominate
# ADJUST: Increase ML_WEIGHT gradually after validating performance in production
ML_WEIGHT: float = 0.3  # 30% weight for ML probability of default
RULE_WEIGHT: float = 0.7  # 70% weight for rule-based score

# Minimum confidence threshold for ML predictions
# WHY: If ML model is uncertain (probability near 0.5), rely more on rules
ML_CONFIDENCE_THRESHOLD: float = 0.2  # If abs(prob - 0.5) < threshold, reduce ML weight

# ============================================================================
# BUSINESS RULES - INCOME & AFFORDABILITY
# ============================================================================
# These thresholds define institutional lending policy.
# Changes require approval from risk committee.

# Minimum monthly income to qualify for any loan
# WHY: Ensures borrower has basic repayment capacity
MIN_MONTHLY_INCOME: float = 100.0  # Local currency units

# Maximum debt-to-income ratio (total debt / monthly income)
# WHY: Industry standard for consumer lending, prevents over-leverage
# REGULATORY: Many jurisdictions mandate DTI < 40-50%
MAX_DEBT_TO_INCOME_RATIO: float = 0.4  # 40%

# Target affordability ratio (monthly payment / net income)
# WHY: Ensures loan repayment doesn't consume all disposable income
# CALCULATION: Net income = monthly_income - monthly_expenses
AFFORDABILITY_RATIO_TARGET: float = 0.3  # 30%

# Minimum business stability for traders/farmers (months)
# WHY: Self-employed income is volatile, need track record
# NOTE: Not yet implemented in V1, placeholder for V2
MIN_BUSINESS_STABILITY_MONTHS: int = 6

# ============================================================================
# BUSINESS RULES - LOAN TERMS
# ============================================================================
# Default interest rates and adjustment rules

# Base interest rate for approved loans (annual percentage rate)
# WHY: Institutional cost of capital + operational overhead
BASE_INTEREST_RATE: float = 15.0  # 15% APR

# Interest rate for conditional approvals (medium risk)
# WHY: Risk premium for borrowers with warnings but no critical flags
CONDITIONAL_INTEREST_RATE: float = 20.0  # 20% APR

# Interest rate for behavioral caution flags
# WHY: Slight premium for behavioral concerns (between base and conditional)
CAUTION_INTEREST_RATE: float = 18.0  # 18% APR

# Loan amount haircut for conditional approvals
# WHY: Reduce exposure for medium-risk borrowers
CONDITIONAL_AMOUNT_MULTIPLIER: float = 0.7  # 70% of requested amount

# ============================================================================
# BEHAVIORAL INTELLIGENCE THRESHOLDS (V2)
# ============================================================================
# Thresholds for alternative data analysis

# Minimum behavioral stability score (0-1)
# WHY: Low transaction volume suggests unreliable income source
BEHAVIORAL_STABILITY_THRESHOLD: float = 0.6

# Minimum savings trend (net cash flow / income)
# WHY: Negative savings trend indicates financial stress
SAVINGS_TREND_THRESHOLD: float = 0.1  # 10% net savings rate

# Minimum utility payment compliance (0-1)
# WHY: Utility payment history predicts loan repayment behavior
UTILITY_COMPLIANCE_THRESHOLD: float = 0.8  # 80% on-time payments

# Spending spike multiplier threshold
# WHY: Sudden high spending may indicate emergency or instability
SPENDING_SPIKE_THRESHOLD: float = 1.5  # Outflow > 1.5x inflow triggers warning

# ============================================================================
# RISK SCORING PARAMETERS
# ============================================================================
# Controls how risk scores are calculated and interpreted

# Risk level thresholds (risk score is 0-1)
# WHY: Categorizes continuous risk score into actionable buckets
RISK_LEVEL_THRESHOLDS: Dict[str, tuple] = {
    "LOW": (0.0, 0.3),      # 0-30%: Strong profile, approve
    "MEDIUM": (0.3, 0.6),   # 30-60%: Acceptable with conditions
    "HIGH": (0.6, 1.0)      # 60-100%: Reject or require collateral
}

# Behavioral penalty per warning flag
# WHY: Each behavioral red flag incrementally increases risk score
BEHAVIORAL_PENALTY_PER_FLAG: float = 0.1  # +10% risk per flag

# Maximum impact user-uploaded behavioral data can have on the score
# WHY: Safety cap for pilot/unverified data sources
MAX_BEHAVIORAL_IMPACT_CAP: float = 0.2

# ============================================================================
# ML MODEL PATHS
# ============================================================================
# File system locations for ML artifacts

ML_MODEL_PATH: str = os.path.join("ml_models", "risk_model.json")
ML_FEATURES_PATH: str = os.path.join("ml_models", "features.txt")
ML_REGISTRY_PATH: str = os.path.join("ml_models", "model_registry.json")

# ============================================================================
# LLM CONFIGURATION (V4)
# ============================================================================
# Settings for optional LLM-powered explanation rephrasing

# LLM provider: "openai", "anthropic", or "vertex_ai"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "vertex_ai")

# Google Vertex AI Configuration
VERTEX_PROJECT_ID: str = os.getenv("VERTEX_PROJECT_ID", "mfi--pro")
VERTEX_REGION: str = os.getenv("VERTEX_REGION", "us-central1")
VERTEX_MODEL_NAME: str = os.getenv("VERTEX_MODEL_NAME", "gemini-1.5-flash")

# API keys (loaded from environment for security)
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# Model selection (fallback/legacy)
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Maximum tokens for explanation generation
LLM_MAX_TOKENS: int = 600

# Temperature (0-1, lower = more deterministic)
# WHY: We want consistent, professional explanations, not creative ones
LLM_TEMPERATURE: float = 0.1

# Timeout for LLM API calls (seconds)
# WHY: Prevent slow LLM responses from blocking assessments
LLM_TIMEOUT: int = 15

# ============================================================================
# AUDIT & LOGGING
# ============================================================================
# Configuration for compliance and monitoring

# Enable detailed audit logging
ENABLE_DETAILED_AUDIT: bool = True

# Log ML predictions even when ML is disabled (for comparison)
LOG_ML_PREDICTIONS_ALWAYS: bool = True

# Audit log retention (days)
AUDIT_LOG_RETENTION_DAYS: int = 2555  # 7 years for regulatory compliance

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_config_snapshot() -> Dict[str, Any]:
    """
    Returns current configuration as a dictionary.
    Used for audit logging to track what settings were active at decision time.
    """
    return {
        "feature_flags": {
            "ml_enabled": ENABLE_ML_RISK_SCORING,
            "llm_enabled": ENABLE_LLM_EXPLANATIONS,
            "behavioral_v2_enabled": ENABLE_BEHAVIORAL_V2
        },
        "model_config": {
            "ml_version": ML_MODEL_VERSION,
            "ml_weight": ML_WEIGHT,
            "rule_weight": RULE_WEIGHT
        },
        "business_rules": {
            "min_income": MIN_MONTHLY_INCOME,
            "max_dti": MAX_DEBT_TO_INCOME_RATIO,
            "affordability_target": AFFORDABILITY_RATIO_TARGET,
            "base_rate": BASE_INTEREST_RATE
        }
    }

def validate_config() -> bool:
    """
    Validates configuration consistency.
    Called at startup to catch configuration errors early.
    """
    errors = []
    
    # Ensemble weights must sum to 1.0
    if abs((ML_WEIGHT + RULE_WEIGHT) - 1.0) > 0.01:
        errors.append(f"ML_WEIGHT ({ML_WEIGHT}) + RULE_WEIGHT ({RULE_WEIGHT}) must equal 1.0")
    
    # Interest rates must be positive
    if BASE_INTEREST_RATE <= 0 or CONDITIONAL_INTEREST_RATE <= 0:
        errors.append("Interest rates must be positive")
    
    # Thresholds must be in valid ranges
    if not (0 <= MAX_DEBT_TO_INCOME_RATIO <= 1):
        errors.append("MAX_DEBT_TO_INCOME_RATIO must be between 0 and 1")
    
    if not (0 <= AFFORDABILITY_RATIO_TARGET <= 1):
        errors.append("AFFORDABILITY_RATIO_TARGET must be between 0 and 1")
    
    # LLM config validation
    if ENABLE_LLM_EXPLANATIONS:
        if LLM_PROVIDER == "vertex_ai" and not VERTEX_PROJECT_ID:
            errors.append("Vertex AI enabled but VERTEX_PROJECT_ID is missing")
        elif LLM_PROVIDER in ["openai", "anthropic"] and not (OPENAI_API_KEY or ANTHROPIC_API_KEY):
            errors.append(f"{LLM_PROVIDER} enabled but no API key provided")
    
    if errors:
        print("Configuration validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print("[OK] Configuration validated successfully")
    return True

# Validate on import
if __name__ != "__main__":
    validate_config()
