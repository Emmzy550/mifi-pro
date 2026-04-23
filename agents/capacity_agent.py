import logging
logger = logging.getLogger(__name__)
"""
Capacity Agent - Demonstrated Financial Capacity Calculator
============================================================

This agent calculates borrower repayment capacity based on DEMONSTRATED
transaction history, not stated income or requested amounts.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from utils.db import Database
from models.alternative_data import AlternativeData, MobileMoneyTransaction
import lending_config.capacity_config as cap_config
import lending_config.pilot_config as pilot_config  # NEW: Pilot mode configuration
import statistics
from utils.policy_context import policy_value


def _policy_int(key: str, default: int) -> int:
    return int(policy_value(key, default))


def _policy_float(key: str, default: float) -> float:
    return float(policy_value(key, default))


class CapacityAgent:
    """
    Calculates demonstrated financial capacity from transaction data.
    """
    
    @staticmethod
    def calculate_demonstrated_capacity(
        borrower_id: str,
        risk_level: str,
        requested_amount: float = 0.0,
        external_transactions: Optional[List] = None,
        verified_monthly_income: Optional[float] = None,  # NEW: from payslip net_pay
        verified_income_source: Optional[str] = None,  # NEW: "PAYSLIP", "SALARY_CREDIT", etc.
        statement_summary: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Calculates the maximum loanable amount based on demonstrated capacity.
        """
        
        # Initialize result structure
        result = {
            "is_valid": False,
            "capacity_based_max": 0.0,
            "observed_deposit_volume": 0.0,
            "transaction_count": 0,
            "history_days": 0,
            "observation_window_days": 0,
            "insufficient_observation": False,
            "rejection_reason": None,
            "rejection_details": {},  # NEW: Structured rejection info
            "starter_loan_applied": False,
            "capacity_multiplier_used": 0.0,
            "capacity_source": "NONE",  # NEW: "VERIFIED_INCOME", "DEPOSIT_VOLUME", "NONE"
            "verified_income_used": None,  # NEW: Amount of verified income used
            "behavioral_transaction_count": 0,  # NEW: Spending transactions counted
            "data_source": "NONE",
            "audit_trail": {}
        }
        
        # STEP 1: FETCH TRANSACTION DATA
        transactions = []
        data_source = "DATABASE"
        if external_transactions:
            transactions = external_transactions
            data_source = "USER_UPLOAD"
        else:
            alt_data = Database.get_alternative_data(borrower_id)
            if alt_data and alt_data.mobile_money_history:
                transactions = alt_data.mobile_money_history
                data_source = "DATABASE"
        
        result["data_source"] = data_source

        def get_summary_field(field: str) -> Any:
            if not statement_summary:
                return None
            if isinstance(statement_summary, dict):
                return statement_summary.get(field)
            return getattr(statement_summary, field, None)
        
        # STEP 2: CALCULATE OBSERVED DEPOSIT VOLUME
        deposit_result = CapacityAgent._calculate_observed_deposit_volume(transactions)
        result["observed_deposit_volume"] = deposit_result["observed_deposit_volume"]
        result["deposit_count_30d"] = deposit_result.get("deposit_count", 0)
        result["deposit_window_start"] = deposit_result.get("period_start")
        result["deposit_window_end"] = deposit_result.get("period_end")
        result["deposit_window_days"] = deposit_result.get("period_days", 0)
        result["audit_trail"]["deposit_volume_calculation"] = deposit_result

        statement_totals = CapacityAgent._calculate_total_deposit_volume(transactions)
        result["statement_deposit_volume"] = statement_totals.get("total_deposit_volume", 0.0)
        result["statement_deposit_count"] = statement_totals.get("deposit_count", 0)
        result["statement_period_start"] = statement_totals.get("period_start")
        result["statement_period_end"] = statement_totals.get("period_end")
        result["statement_period_days"] = statement_totals.get("period_days", 0)
        result["audit_trail"]["statement_deposit_totals"] = statement_totals
        
        # STEP 3: VALIDATE DATA SUFFICIENCY
        validation_result = CapacityAgent._validate_transaction_data(transactions)
        
        try:
            result["transaction_count"] = validation_result["transaction_count"]
            result["history_days"] = validation_result["history_days"]
            result["observation_window_days"] = validation_result.get("observation_window_days", 0)
            result["insufficient_observation"] = validation_result.get("insufficient_observation", False)
        except (KeyError, TypeError) as e:
            result["transaction_count"] = len(transactions)
            result["history_days"] = 0
            if not isinstance(validation_result, dict) or "is_valid" not in validation_result:
                 validation_result = {"is_valid": False, "reason": f"Internal validation data missing: {e}"}

        summary_period = get_summary_field("statement_period")
        summary_start = None
        summary_end = None
        if summary_period:
            if isinstance(summary_period, dict):
                summary_start = summary_period.get("start")
                summary_end = summary_period.get("end")
            else:
                summary_start = getattr(summary_period, "start", None)
                summary_end = getattr(summary_period, "end", None)

        if summary_start and summary_end:
            try:
                start_dt = datetime.fromisoformat(str(summary_start))
                end_dt = datetime.fromisoformat(str(summary_end))
                summary_days = max((end_dt - start_dt).days, 1) if end_dt >= start_dt else 0
                if summary_days > 0:
                    result["history_days"] = summary_days
                    result["observation_window_days"] = summary_days
                    result["statement_period_start"] = start_dt.isoformat()
                    result["statement_period_end"] = end_dt.isoformat()
                    result["statement_period_days"] = summary_days
            except ValueError:
                pass
        
        # POLICY BYPASS: Lack of time ≠ Bad behavior
        if not validation_result["is_valid"] and result["transaction_count"] > 0:
            reason_low = validation_result.get("reason", "").lower()
            if "observation" in reason_low or "history" in reason_low:
                 # Flag it, but allow it to proceed for score-capping in RiskAgent
                 result["insufficient_observation"] = True
                 validation_result["is_valid"] = True # TEMP Bypassed
                 win_days = result['observation_window_days']
                 win_str = "1 day" if win_days == 1 else f"{win_days} days"
                 logger.info(f"INFO: Observation bypass applied for {borrower_id} ({win_str})")

        # MICRO-STARTER EXCEPTION LAYER (NEW)
        micro_starter_eligible = False
        if not validation_result["is_valid"]:
            # Check if we can apply the micro-starter exception BEFORE rejecting
            if result["transaction_count"] < cap_config.MIN_HISTORY_FOR_NORMAL or result["history_days"] < _policy_int("min_history_days", cap_config.MIN_HISTORY_DAYS):
                
                meets_micro_volume = result["observed_deposit_volume"] >= cap_config.MIN_DEPOSIT_VOLUME_FOR_MICRO
                within_micro_cap = requested_amount <= cap_config.MICRO_LOAN_CAP
                within_volume_multiplier = requested_amount <= (result["observed_deposit_volume"] * cap_config.MICRO_MULTIPLIER)
                
                if meets_micro_volume and within_micro_cap and within_volume_multiplier:
                    micro_starter_eligible = True
                    result["starter_loan_applied"] = True
                    result["micro_loan_exception"] = True
                    result["capacity_based_max"] = requested_amount
                    result["capacity_multiplier_used"] = cap_config.MICRO_MULTIPLIER
                    # Legacy anchor fields removed
                    logger.error(f"INFO: Micro-starter exception applied for borrower {borrower_id}")
                else:
                    result["rejection_reason"] = "INSUFFICIENT_OBSERVATION_WINDOW" if result["insufficient_observation"] else validation_result["reason"]
                    return result
            else:
                result["rejection_reason"] = validation_result["reason"]
                return result
        
        # ================================================================
        # VERIFIED INCOME OVERRIDE (PILOT MODE)
        # ================================================================
        # If verified income is available (from payslip), use it as primary
        # capacity source instead of observed deposit volume
        
        if (pilot_config.PILOT_MODE_ENABLED and 
            pilot_config.ALLOW_VERIFIED_INCOME_OVERRIDE and
            verified_monthly_income is not None and
            verified_monthly_income >= pilot_config.MIN_VERIFIED_INCOME):
            
            logger.info(f"INFO: Verified income detected: {verified_monthly_income} from {verified_income_source or 'PAYSLIP'}")
            
            # Count behavioral transactions to validate spending patterns
            behavioral_result = CapacityAgent._count_behavioral_transactions(transactions)
            result["behavioral_transaction_count"] = behavioral_result["behavioral_transaction_count"]
            result["audit_trail"]["behavioral_analysis"] = behavioral_result
            
            logger.info(f"INFO: Behavioral transactions: {behavioral_result['behavioral_transaction_count']} of {behavioral_result['raw_transaction_count']}")
            
            # Check if we have sufficient behavioral data
            if behavioral_result["behavioral_transaction_count"] < pilot_config.MIN_BEHAVIORAL_TRANSACTIONS:
                result["rejection_reason"] = pilot_config.RejectionReason.INSUFFICIENT_BEHAVIORAL_DATA
                result["rejection_details"] = {
                    "behavioral_txn_count": behavioral_result["behavioral_transaction_count"],
                    "required": pilot_config.MIN_BEHAVIORAL_TRANSACTIONS,
                    "verified_income": verified_monthly_income,
                    "verified_income_source": verified_income_source,
                    "message": pilot_config.get_rejection_message(
                        pilot_config.RejectionReason.INSUFFICIENT_BEHAVIORAL_DATA
                    )
                }
                logger.info(f"REJECTION: {result['rejection_details']['message']}")
                return result
            
            # Use verified income as capacity base
            try:
                capacity_multiplier = pilot_config.get_verified_income_multiplier(risk_level)
            except ValueError as e:
                result["rejection_reason"] = f"Invalid risk level: {risk_level}"
                return result
            
            capacity_based_max = verified_monthly_income * capacity_multiplier
            
            result["capacity_source"] = "VERIFIED_INCOME"
            result["verified_income_used"] = verified_monthly_income
            result["capacity_multiplier_used"] = capacity_multiplier
            result["capacity_based_max"] = round(capacity_based_max, 2)
            result["is_valid"] = True
            
            logger.info(
                f"CAPACITY APPROVED via VERIFIED_INCOME: {capacity_based_max:.2f} "
                f"({verified_monthly_income} * {capacity_multiplier})"
            )
            
            return result
        
        # ================================================================
        # DEPOSIT VOLUME PATH (Fallback or Production Mode)
        # ================================================================
        
        # Check minimum deposit volume threshold for NORMAL loans
        # Use pilot threshold if in pilot mode, otherwise production threshold
        min_threshold = (
            pilot_config.MIN_CAPACITY_THRESHOLD_PILOT
            if pilot_config.PILOT_MODE_ENABLED
            else _policy_float("min_capacity_threshold", cap_config.MIN_CAPACITY_THRESHOLD)
        )
        
        if not micro_starter_eligible and result["observed_deposit_volume"] < min_threshold:
            # If we bypassed validation for time, we still check volume
            result["rejection_reason"] = (
                f"Observed deposit volume ({result['observed_deposit_volume']:.2f}) "
                f"below minimum threshold ({min_threshold})"
            )
            return result
        
        # STEP 4: APPLY CAPACITY MULTIPLIER
        if not micro_starter_eligible:
            try:
                capacity_multiplier = cap_config.get_capacity_multiplier(risk_level)
            except ValueError as e:
                result["rejection_reason"] = f"Invalid risk level: {risk_level}"
                return result
            
            result["capacity_multiplier_used"] = capacity_multiplier
            capacity_based_max = result["observed_deposit_volume"] * capacity_multiplier
            
            # STEP 5: CHECK GENERAL STARTER LOAN ELIGIBILITY
            starter_loan_eligible = CapacityAgent._check_starter_loan_eligibility(
                history_days=result["history_days"],
                observed_deposit_volume=result["observed_deposit_volume"]
            )
            
            result["starter_loan_applied"] = starter_loan_eligible
            if starter_loan_eligible:
                starter_cap = _policy_float("starter_loan_cap", cap_config.STARTER_LOAN_CAP)
                if capacity_based_max > starter_cap:
                    capacity_based_max = starter_cap

            
            result["capacity_based_max"] = round(capacity_based_max, 2)
            # Legacy anchor fields removed

        # STEP 6: MARK AS VALID
        result["is_valid"] = True
        return result
    
    @staticmethod
    def _get_tx_val(tx: Any, field_names: List[str], default: Any = None) -> Any:
        """
        Extracts a value from a transaction object (dict or Pydantic).
        """
        for field in field_names:
            # Try dict access
            if isinstance(tx, dict):
                val = tx.get(field)
                if val is not None: return val
            # Try attribute access (Pydantic or other objects)
            val = getattr(tx, field, None)
            if val is not None: return val
            # Try model_dump() if it's a Pydantic model
            if hasattr(tx, "model_dump"):
                try:
                    val = tx.model_dump().get(field)
                    if val is not None: return val
                except: pass
        return default

    @staticmethod
    def _parse_tx_date(ts: Any) -> Optional[datetime]:
        if not ts: return None
        if isinstance(ts, datetime):
            if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
            return ts
        if isinstance(ts, str):
            try:
                # Remove common noise
                clean_ts = ts.replace("Z", "+00:00").split(".")[0]
                if " " in clean_ts and "T" not in clean_ts:
                    clean_ts = clean_ts.replace(" ", "T")
                ts_obj = datetime.fromisoformat(clean_ts)
                if ts_obj.tzinfo is None: ts_obj = ts_obj.replace(tzinfo=timezone.utc)
                return ts_obj
            except:
                pass
        return None

    @staticmethod
    def _tx_is_credible(tx: Any, min_confidence: float = 0.7) -> bool:
        confidence = CapacityAgent._get_tx_val(tx, ["confidence_score", "confidence"], 1.0)
        flags = CapacityAgent._get_tx_val(tx, ["flags"], [])
        if flags and "LOW_CONFIDENCE_REVIEW" in flags:
            return False
        try:
            return float(confidence) >= min_confidence
        except:
            return True

    @staticmethod
    def _count_behavioral_transactions(transactions: List) -> Dict[str, Any]:
        """
        Count transactions that demonstrate financial behavior.
        
        Behavioral transactions include:
        - All debits/outflows (expenses, transfers, bill payments)
        - Mobile banking transactions (DIGITAL NFS, AIRTEL, MTN)
        - POS purchases
        - Airtime/utility payments
        
        Excludes:
        - Reversals
        - Standalone fee commissions (< 50 units)
        - Duplicate entries
        - Low confidence transactions
        
        Returns:
            Dict with behavioral_count, raw_count, and percentage
        """
        behavioral_count = 0
        raw_count = len(transactions)
        matched_reasons = []
        
        for tx in transactions:
            # Check credibility first
            if not CapacityAgent._tx_is_credible(tx):
                continue
            
            # Get transaction details
            desc = str(CapacityAgent._get_tx_val(tx, ["description"], "")).upper()
            direction = str(CapacityAgent._get_tx_val(tx, ["direction"], "")).upper()
            tx_type = str(CapacityAgent._get_tx_val(tx, ["type"], "")).upper()
            amount = CapacityAgent._get_tx_val(tx, ["amount"], 0.0)
            
            # Skip reversals
            if 'REVERSAL' in desc:
                continue
            
            # Skip standalone small commissions (but keep if it's part of behavioral pattern)
            if 'COMMISSION' in desc and amount < 50:
                # Still check for behavioral patterns as fallback
                if not any(p in desc for p in ['DIGITAL', 'MOBILE', 'NFS']):
                    continue
            
            # Check for outflow/debit direction (various formats)
            is_outflow = direction in ["OUTFLOW", "DEBIT", "D", "DR"]
            
            if is_outflow:
                behavioral_count += 1
                matched_reasons.append(f"OUTFLOW: {desc[:30]}")
                continue
            
            # Check specific behavioral patterns regardless of direction
            # These indicate active account usage
            behavioral_patterns = [
                'DIGITAL NFS', 'MOBILE BANKING', 'POS', 
                'AIRTEL', 'MTN', 'ZAMTEL', 'AIRTIME',
                'BILL PAYMENT', 'TRANSFER', 'WITHDRAWAL',
                'MBBO', 'NFS TRANSACTION', 'TOP UP', 'TOPUP',
                'ACCOUNT MAINTENANCE', 'CHARGE', 'FEE'
            ]
            
            if any(pattern in desc for pattern in behavioral_patterns):
                behavioral_count += 1
                matched_reasons.append(f"PATTERN: {desc[:30]}")
                continue
            
            # Also count inflows as behavioral (shows active account)
            is_inflow = direction in ["INFLOW", "CREDIT", "C", "CR"]
            if is_inflow:
                behavioral_count += 1
                matched_reasons.append(f"INFLOW: {desc[:30]}")
        
        logger.debug(f"DEBUG: Behavioral analysis - {behavioral_count} of {raw_count} matched")
        if matched_reasons:
            logger.debug(f"DEBUG: Matched reasons (first 5): {matched_reasons[:5]}")
        
        return {
            "behavioral_transaction_count": behavioral_count,
            "raw_transaction_count": raw_count,
            "behavioral_percentage": behavioral_count / raw_count if raw_count > 0 else 0
        }


    @staticmethod
    def _validate_transaction_data(transactions: List) -> Dict[str, Any]:
        if not transactions:
            return {"is_valid": False, "reason": "No transaction history available", "history_days": 0, "transaction_count": 0}
        
        credible_transactions = [tx for tx in transactions if CapacityAgent._tx_is_credible(tx)]
        transaction_count = len(credible_transactions)
        timestamps = []
        for tx in credible_transactions:
            ts = CapacityAgent._parse_tx_date(CapacityAgent._get_tx_val(tx, ["timestamp", "date"]))
            if ts: timestamps.append(ts)
        
        if not timestamps:
            return {"is_valid": False, "reason": "No valid timestamps", "history_days": 0, "transaction_count": transaction_count}

        oldest = min(timestamps)
        newest = max(timestamps)
        delta = newest - oldest
        observation_window_days = max(delta.days, 1) if delta.total_seconds() > 0 else 0
        if transaction_count > 0 and observation_window_days == 0:
             if oldest.date() == newest.date(): observation_window_days = 1

        min_history_days = _policy_int("min_history_days", cap_config.MIN_HISTORY_DAYS)
        min_transaction_count = _policy_int("min_transaction_count", cap_config.MIN_TRANSACTION_COUNT)
        is_window_sufficient = observation_window_days >= min_history_days
        
        if transaction_count < min_transaction_count:
            return {
                "is_valid": False,
                "reason": f"Insufficient transactions: {transaction_count} (min {min_transaction_count})",
                "observation_window_days": observation_window_days,
                "history_days": observation_window_days,
                "transaction_count": transaction_count,
                "insufficient_observation": True
            }
        
        if not is_window_sufficient:
            win_str = "1 day" if observation_window_days == 1 else f"{observation_window_days} days"
            return {
                "is_valid": False,
                "reason": f"INSUFFICIENT OBSERVATION WINDOW: {win_str} (min {min_history_days} days)",
                "observation_window_days": observation_window_days,
                "history_days": observation_window_days,
                "transaction_count": transaction_count,
                "insufficient_observation": True
            }
        
        return {
            "is_valid": True,
            "reason": None,
            "observation_window_days": observation_window_days,
            "history_days": observation_window_days,
            "transaction_count": transaction_count,
            "insufficient_observation": False
        }
    
    @staticmethod
    def _calculate_observed_deposit_volume(transactions: List, window_days: int = 30) -> Dict[str, Any]:
        # Pilot override for observation window
        if pilot_config.PILOT_MODE_ENABLED:
            window_days = pilot_config.PILOT_OBSERVATION_WINDOW_DAYS
            
        logger.info(f"[DIAGNOSTIC] Processing {len(transactions)} transactions for capacity window: {window_days} days")
        if not transactions:
            return {"observed_deposit_volume": 0.0, "period_days": window_days, "total_deposit_volume": 0.0, "deposit_count": 0}

        timestamps = []
        for tx in transactions:
            # Look for 'date' (Pydantic model) or 'timestamp' (legacy api.py mapping)
            raw_date = CapacityAgent._get_tx_val(tx, ["date", "timestamp"])
            ts = CapacityAgent._parse_tx_date(raw_date)
            if ts: 
                timestamps.append(ts)
            else:
                if raw_date: logger.error(f"DEBUG: Failed to parse date string: '{raw_date}' from tx: {type(tx)}")
            
        reference_now = max(timestamps) if timestamps else datetime.now(timezone.utc)
        if reference_now.tzinfo is None: reference_now = reference_now.replace(tzinfo=timezone.utc)
        
        start_date = reference_now - timedelta(days=window_days)
        logger.info(f"[DIAGNOSTIC] Reference Date: {reference_now.isoformat()}, Window Start: {start_date.isoformat()}")

        valid_deposits = []
        for idx, tx in enumerate(transactions):
            desc = CapacityAgent._get_tx_val(tx, ["description"], "N/A")
            amount = CapacityAgent._get_tx_val(tx, ["amount"], 0.0)
            direction = CapacityAgent._get_tx_val(tx, ["direction"], "UNKNOWN")
            tx_type = CapacityAgent._get_tx_val(tx, ["type"], "UNKNOWN")
            raw_date = CapacityAgent._get_tx_val(tx, ["date", "timestamp"])
            ts = CapacityAgent._parse_tx_date(raw_date)
            
            is_credible = CapacityAgent._tx_is_credible(tx)
            is_deposit = tx_type in {"DEPOSIT", "SALARY", "CREDIT"} or direction == "INFLOW"
            
            in_window = False
            if ts:
                if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
                if ts >= start_date: in_window = True
                
            logger.info(f"  [TX {idx}] {ts.date() if ts else 'N/A'}: {desc[:20]} | Amt: {amount} | Dir: {direction} | Credible: {is_credible} | Deposit: {is_deposit} | InWindow: {in_window}")

            if is_credible and is_deposit and in_window and amount > 0:
                valid_deposits.append(amount)
        
        total_volume = sum(valid_deposits)
        return {
            "observed_deposit_volume": round(total_volume, 2),
            "period_days": window_days,
            "period_start": start_date.isoformat(),
            "period_end": reference_now.isoformat(),
            "total_deposit_volume": round(total_volume, 2),
            "deposit_count": len(valid_deposits)
        }

    @staticmethod
    def _calculate_total_deposit_volume(transactions: List) -> Dict[str, Any]:
        if not transactions:
            return {
                "total_deposit_volume": 0.0,
                "deposit_count": 0,
                "period_start": None,
                "period_end": None,
                "period_days": 0
            }

        timestamps = []
        total_volume = 0.0
        deposit_count = 0

        for tx in transactions:
            amount = CapacityAgent._get_tx_val(tx, ["amount"], 0.0)
            ts = CapacityAgent._get_tx_val(tx, ["timestamp", "date"])
            tx_type = str(CapacityAgent._get_tx_val(tx, ["type"], "")).upper()
            direction = str(CapacityAgent._get_tx_val(tx, ["direction"], "")).upper()

            ts = CapacityAgent._parse_tx_date(CapacityAgent._get_tx_val(tx, ["timestamp", "date"]))
            if ts: timestamps.append(ts)

            is_deposit = tx_type in {"DEPOSIT", "SALARY", "CREDIT"} or direction == "INFLOW"
            if is_deposit and amount > 0:
                total_volume += amount
                deposit_count += 1

        period_start = min(timestamps).isoformat() if timestamps else None
        period_end = max(timestamps).isoformat() if timestamps else None
        period_days = 0
        if timestamps:
            delta = max(timestamps) - min(timestamps)
            period_days = max(delta.days, 1) if delta.total_seconds() > 0 else 0

        return {
            "total_deposit_volume": round(total_volume, 2),
            "deposit_count": deposit_count,
            "period_start": period_start,
            "period_end": period_end,
            "period_days": period_days
        }
    
    @staticmethod
    def _check_starter_loan_eligibility(history_days: int, observed_deposit_volume: float) -> bool:
        if history_days < _policy_int("starter_history_threshold_days", cap_config.STARTER_HISTORY_THRESHOLD_DAYS):
            return True
        if observed_deposit_volume < _policy_float("starter_deposit_threshold", cap_config.STARTER_DEPOSIT_THRESHOLD):
            return True
        return False
