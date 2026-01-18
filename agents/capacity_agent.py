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
import statistics


class CapacityAgent:
    """
    Calculates demonstrated financial capacity from transaction data.
    """
    
    @staticmethod
    def calculate_demonstrated_capacity(
        borrower_id: str,
        risk_level: str,
        requested_amount: float = 0.0,
        external_transactions: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        Calculates the maximum loanable amount based on demonstrated capacity.
        """
        
        # Initialize result structure
        result = {
            "is_valid": False,
            "capacity_based_max": 0.0,
            "capacity_anchor_amount": 0.0,
            "capacity_anchor_reason": "POLICY_DEFAULT",
            "observed_deposit_volume": 0.0,
            "transaction_count": 0,
            "history_days": 0,
            "observation_window_days": 0,
            "insufficient_observation": False,
            "rejection_reason": None,
            "starter_loan_applied": False,
            "capacity_multiplier_used": 0.0,
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
        
        # STEP 2: CALCULATE OBSERVED DEPOSIT VOLUME
        deposit_result = CapacityAgent._calculate_observed_deposit_volume(transactions)
        result["observed_deposit_volume"] = deposit_result["observed_deposit_volume"]
        result["audit_trail"]["deposit_volume_calculation"] = deposit_result
        
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
        
        # POLICY BYPASS: Lack of time ≠ Bad behavior
        if not validation_result["is_valid"] and result["transaction_count"] > 0:
            reason_low = validation_result.get("reason", "").lower()
            if "observation" in reason_low or "history" in reason_low:
                 # Flag it, but allow it to proceed for score-capping in RiskAgent
                 result["insufficient_observation"] = True
                 validation_result["is_valid"] = True # TEMP Bypassed
                 win_days = result['observation_window_days']
                 win_str = "1 day" if win_days == 1 else f"{win_days} days"
                 print(f"INFO: Observation bypass applied for {borrower_id} ({win_str})")

        # MICRO-STARTER EXCEPTION LAYER (NEW)
        micro_starter_eligible = False
        if not validation_result["is_valid"]:
            # Check if we can apply the micro-starter exception BEFORE rejecting
            if result["transaction_count"] < cap_config.MIN_HISTORY_FOR_NORMAL or result["history_days"] < cap_config.MIN_HISTORY_DAYS:
                
                meets_micro_volume = result["observed_deposit_volume"] >= cap_config.MIN_DEPOSIT_VOLUME_FOR_MICRO
                within_micro_cap = requested_amount <= cap_config.MICRO_LOAN_CAP
                within_volume_multiplier = requested_amount <= (result["observed_deposit_volume"] * cap_config.MICRO_MULTIPLIER)
                
                if meets_micro_volume and within_micro_cap and within_volume_multiplier:
                    micro_starter_eligible = True
                    result["starter_loan_applied"] = True
                    result["micro_loan_exception"] = True
                    result["capacity_based_max"] = requested_amount
                    result["capacity_multiplier_used"] = cap_config.MICRO_MULTIPLIER
                    result["capacity_anchor_amount"] = requested_amount
                    result["capacity_anchor_reason"] = "MICRO_STARTER_POLICY"
                    print(f"INFO: Micro-starter exception applied for borrower {borrower_id}")
                else:
                    result["rejection_reason"] = "INSUFFICIENT_OBSERVATION_WINDOW" if result["insufficient_observation"] else validation_result["reason"]
                    return result
            else:
                result["rejection_reason"] = validation_result["reason"]
                return result
        
        # Check minimum deposit volume threshold for NORMAL loans
        if not micro_starter_eligible and result["observed_deposit_volume"] < cap_config.MIN_CAPACITY_THRESHOLD:
            # If we bypassed validation for time, we still check volume
            result["rejection_reason"] = (
                f"Observed deposit volume ({result['observed_deposit_volume']:.2f}) "
                f"below minimum threshold ({cap_config.MIN_CAPACITY_THRESHOLD})"
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
            result["capacity_anchor_reason"] = "AFFORDABILITY_LIMIT"
            
            # STEP 5: CHECK GENERAL STARTER LOAN ELIGIBILITY
            starter_loan_eligible = CapacityAgent._check_starter_loan_eligibility(
                history_days=result["history_days"],
                observed_deposit_volume=result["observed_deposit_volume"]
            )
            
            result["starter_loan_applied"] = starter_loan_eligible
            if starter_loan_eligible:
                if capacity_based_max > cap_config.STARTER_LOAN_CAP:
                    capacity_based_max = cap_config.STARTER_LOAN_CAP
                    result["capacity_anchor_reason"] = "STARTER_LOAN_CAP"
            
            result["capacity_based_max"] = round(capacity_based_max, 2)
            result["capacity_anchor_amount"] = result["capacity_based_max"]

        # STEP 6: MARK AS VALID
        result["is_valid"] = True
        return result
    
    @staticmethod
    def _get_tx_val(tx: Any, field_names: List[str], default: Any = None) -> Any:
        for field in field_names:
            if isinstance(tx, dict):
                if field in tx:
                    val = tx[field]
                    if val is not None: return val
            else:
                val = getattr(tx, field, None)
                if val is not None: return val
        return default

    @staticmethod
    def _validate_transaction_data(transactions: List) -> Dict[str, Any]:
        if not transactions:
            return {"is_valid": False, "reason": "No transaction history available", "history_days": 0, "transaction_count": 0}
        
        transaction_count = len(transactions)
        timestamps = []
        for tx in transactions:
            ts = CapacityAgent._get_tx_val(tx, ["timestamp", "date"])
            if isinstance(ts, str):
                try: ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except: continue
            if ts and isinstance(ts, datetime):
                if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
                timestamps.append(ts)
        
        if not timestamps:
            return {"is_valid": False, "reason": "No valid timestamps", "history_days": 0, "transaction_count": transaction_count}

        oldest = min(timestamps)
        newest = max(timestamps)
        delta = newest - oldest
        observation_window_days = max(delta.days, 1) if delta.total_seconds() > 0 else 0
        if transaction_count > 0 and observation_window_days == 0:
             if oldest.date() == newest.date(): observation_window_days = 1

        is_window_sufficient = observation_window_days >= cap_config.MIN_HISTORY_DAYS
        
        if transaction_count < cap_config.MIN_TRANSACTION_COUNT:
            return {
                "is_valid": False,
                "reason": f"Insufficient transactions: {transaction_count} (min {cap_config.MIN_TRANSACTION_COUNT})",
                "observation_window_days": observation_window_days,
                "history_days": observation_window_days,
                "transaction_count": transaction_count,
                "insufficient_observation": True
            }
        
        if not is_window_sufficient:
            win_str = "1 day" if observation_window_days == 1 else f"{observation_window_days} days"
            return {
                "is_valid": False,
                "reason": f"INSUFFICIENT OBSERVATION WINDOW: {win_str} (min {cap_config.MIN_HISTORY_DAYS} days)",
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
        if not transactions:
            return {"observed_deposit_volume": 0.0, "period_days": window_days, "total_deposit_volume": 0.0, "deposit_count": 0}
        
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=window_days)
        valid_deposits = []
        
        for tx in transactions:
            amount = CapacityAgent._get_tx_val(tx, ["amount"], 0.0)
            ts = CapacityAgent._get_tx_val(tx, ["timestamp", "date"])
            tx_type = str(CapacityAgent._get_tx_val(tx, ["type"], "")).upper()

            if isinstance(ts, str):
                try: ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except: ts = None
            
            if tx_type == "DEPOSIT" and amount > 0:
                if ts:
                    if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
                    if ts >= start_date: valid_deposits.append(amount)
        
        total_volume = sum(valid_deposits)
        return {
            "observed_deposit_volume": round(total_volume, 2),
            "period_days": window_days,
            "total_deposit_volume": round(total_volume, 2),
            "deposit_count": len(valid_deposits)
        }
    
    @staticmethod
    def _check_starter_loan_eligibility(history_days: int, observed_deposit_volume: float) -> bool:
        if history_days < cap_config.STARTER_HISTORY_THRESHOLD_DAYS: return True
        if observed_deposit_volume < cap_config.STARTER_DEPOSIT_THRESHOLD: return True
        return False
