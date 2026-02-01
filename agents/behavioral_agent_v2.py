"""
Behavioral Agent V2 - Enhanced Alternative Data Analysis
=========================================================

This agent analyzes alternative data sources (mobile money, utilities, airtime)
to assess borrower behavior and financial stability.

V2 ENHANCEMENTS over V1:
1. Income consistency scoring (regularity of deposits)
2. Transaction stability metrics (volatility analysis)
3. Savings behavior trends (3/6/12 month analysis)
4. Expense volatility detection (spending pattern irregularity)

WHY BEHAVIORAL DATA MATTERS:
- Many borrowers lack traditional credit history ("thin-file")
- Mobile money and utility payments predict loan repayment
- Behavioral patterns reveal financial discipline
- Alternative data reduces bias against informal sector workers

IMPORTANT: This agent does NOT use ML. All metrics are rule-based
and transparent, making them audit-friendly and explainable.
"""

import sys
import os
from typing import List, Dict, Any

# Fix for direct execution: ensure project root is in path
if __name__ == "__main__" or __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.alternative_data import AlternativeData, MobileMoneyTransaction, UtilityPayment
from datetime import datetime, timedelta, timezone
import statistics
import config


class BehavioralAgentV2:
    """
    Analyzes time-series alternative data to detect behavioral patterns and risks.
    
    This is a DETERMINISTIC agent - same inputs always produce same outputs.
    No machine learning is used in V2.
    """

    @staticmethod
    def analyze_transactions(transactions: list) -> Dict[str, Any]:
        """
        Analyzes standardized transaction data from user uploads.
        Applies confidence weighting to all scores.
        """
        # 1. Calculate raw metrics using standard logic
        metrics = {
            "behavioral_stability": 0.0,
            "income_consistency_score": 0.0,
            "transaction_stability": 0.0,
            "saving_trend": 0.0,
            "savings_behavior": 0.0,
            "expense_volatility": 0.0,
            "early_warnings": [],
            "utility_compliance": 0.0
        }
        
        if not transactions:
            return metrics

        # get confidence from first tx (all should be same source)
        confidence = transactions[0].confidence if transactions else 0.6
        
        # --- LOGIC HARMONIZATION ---
        # Calculate observation window for confidence tagging
        timestamps = []
        for t in transactions:
            try:
                # Handle YYYY-MM-DD
                ts = datetime.strptime(t.date, "%Y-%m-%d")
                timestamps.append(ts)
            except: pass

        window_days = 0
        if timestamps:
            delta = max(timestamps) - min(timestamps)
            window_days = max(delta.days, 1)
        
        is_thin_history = window_days < 1 
        metrics["observation_window_days"] = window_days
        metrics["metric_confidence"] = "LOW" if is_thin_history else "NORMAL"
        metrics["behavioral_status"] = "ANALYSIS_COMPLETE" if len(transactions) > 0 else "INSUFFICIENT_DATA"

        if is_thin_history and len(transactions) == 0:
            metrics["transactions"] = transactions
            return metrics

        # Stability (Volume) - Scale by confidence
        metrics["behavioral_stability"] = min(len(transactions) / 20.0, 1.0) * confidence

        # Income Consistency
        # direction="INFLOW" or fallback credit check
        inflow_amounts = []
        outflow_amounts = []
        
        for t in transactions:
            amt = t.amount
            if getattr(t, 'direction', None) == "INFLOW":
                inflow_amounts.append(amt)
            elif getattr(t, 'direction', None) == "OUTFLOW":
                outflow_amounts.append(amt)
            else:
                # Fallback for old models if mixed
                if getattr(t, 'credit', None): inflow_amounts.append(t.credit)
                if getattr(t, 'debit', None): outflow_amounts.append(t.debit)

        if len(inflow_amounts) >= 3:
            mean_in = statistics.mean(inflow_amounts)
            std_in = statistics.stdev(inflow_amounts) if len(inflow_amounts) > 1 else 0
            cv = std_in / mean_in if mean_in > 0 else 10
            raw_score = max(0, 1 - (cv / 0.5))
            metrics["income_consistency_score"] = raw_score * confidence

        # Savings & Spending
        total_in = sum(inflow_amounts)
        total_out = sum(outflow_amounts)
        
        if total_in > 0:
            savings_rate = (total_in - total_out) / total_in
            metrics["saving_trend"] = savings_rate
            metrics["savings_behavior"] = max(0, min(savings_rate, 1.0)) * confidence
            
            if total_out > total_in * config.SPENDING_SPIKE_THRESHOLD:
                metrics["early_warnings"].append("SUSPICIOUS_SPENDING_SPIKE (User Upload)")

        # Transaction Stability (Volatility)
        all_amounts = inflow_amounts + outflow_amounts
        if len(all_amounts) >= 5:
            mean = statistics.mean(all_amounts)
            std = statistics.stdev(all_amounts) if len(all_amounts) > 1 else 0
            cv_all = std / mean if mean > 0 else 10
            metrics["transaction_stability"] = max(0, 1 - (cv_all / 1.0)) * confidence

        # Expense Volatility
        if len(outflow_amounts) >= 3:
             mean_out = statistics.mean(outflow_amounts)
             std_out = statistics.stdev(outflow_amounts) if len(outflow_amounts) > 1 else 0
             cv_out = std_out / mean_out if mean_out > 0 else 10
             metrics["expense_volatility"] = min(cv_out, 1.0)

        # LINK: Return raw transactions for CapacityAgent
        metrics["transactions"] = transactions
        return metrics

    @staticmethod
    def analyze(alt_data: AlternativeData) -> Dict[str, Any]:
        results = {
            "behavioral_stability": 0.0,
            "income_consistency_score": 0.0,
            "transaction_stability": 0.0,
            "saving_trend": 0.0,
            "savings_behavior": 0.0,
            "expense_volatility": 0.0,
            "early_warnings": [],
            "utility_compliance": 0.0
        }

        if not alt_data:
            return results

        if alt_data.mobile_money_history:
            mm_metrics = BehavioralAgentV2._analyze_mobile_money(alt_data.mobile_money_history)
            results.update(mm_metrics)

        if alt_data.utility_history:
            utility_metrics = BehavioralAgentV2._analyze_utility_payments(alt_data.utility_history)
            results.update(utility_metrics)

        return results

    @staticmethod
    def _analyze_mobile_money(transactions: List[MobileMoneyTransaction]) -> Dict[str, Any]:
        metrics = {
            "behavioral_stability": 0.0,
            "income_consistency_score": 0.0,
            "transaction_stability": 0.0,
            "saving_trend": 0.0,
            "savings_behavior": 0.0,
            "expense_volatility": 0.0,
            "early_warnings": []
        }
        
        if not transactions:
            return metrics
        
        total_tx = len(transactions)
        metrics["behavioral_stability"] = min(total_tx / 20.0, 1.0)
        
        deposits = [t for t in transactions if t.type in ["DEPOSIT", "TRANSFER_IN", "SALARY"]]
        
        if len(deposits) >= 3:
            deposit_amounts = [t.amount for t in deposits]
            mean_deposit = statistics.mean(deposit_amounts)
            if mean_deposit > 0:
                std_deposit = statistics.stdev(deposit_amounts) if len(deposit_amounts) > 1 else 0
                cv = std_deposit / mean_deposit
                metrics["income_consistency_score"] = max(0, 1 - (cv / 0.5))
        
        one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_tx = []
        for t in transactions:
            tx_ts = t.timestamp
            if tx_ts.tzinfo is None:
                tx_ts = tx_ts.replace(tzinfo=timezone.utc)
            if tx_ts > one_month_ago:
                recent_tx.append(t)
        
        if recent_tx:
            inflow = sum(t.amount for t in recent_tx if t.type in ["DEPOSIT", "TRANSFER_IN", "SALARY"])
            outflow = sum(t.amount for t in recent_tx if t.type in ["WITHDRAWAL", "PAYMENT", "TRANSFER_OUT"])
            
            if inflow > 0:
                savings_rate = (inflow - outflow) / inflow
                metrics["saving_trend"] = savings_rate
                metrics["savings_behavior"] = max(0, min(savings_rate, 1.0))
                
                if outflow > inflow * config.SPENDING_SPIKE_THRESHOLD:
                    metrics["early_warnings"].append("SUSPICIOUS_SPENDING_SPIKE")
        
        if len(transactions) >= 5:
            all_amounts = [t.amount for t in transactions]
            mean_amount = statistics.mean(all_amounts)
            if mean_amount > 0:
                std_amount = statistics.stdev(all_amounts) if len(all_amounts) > 1 else 0
                cv_all = std_amount / mean_amount
                metrics["transaction_stability"] = max(0, 1 - (cv_all / 1.0))
        
        outflows = [t for t in transactions if t.type in ["WITHDRAWAL", "PAYMENT", "TRANSFER_OUT"]]
        if len(outflows) >= 3:
            outflow_amounts = [t.amount for t in outflows]
            mean_outflow = statistics.mean(outflow_amounts)
            if mean_outflow > 0:
                std_outflow = statistics.stdev(outflow_amounts) if len(outflow_amounts) > 1 else 0
                cv_outflow = std_outflow / mean_outflow
                metrics["expense_volatility"] = min(cv_outflow, 1.0)
        
        return metrics

    @staticmethod
    def _analyze_utility_payments(payments: List[UtilityPayment]) -> Dict[str, Any]:
        metrics = {
            "utility_compliance": 0.0,
            "early_warnings": []
        }
        
        if not payments:
            return metrics
        
        paid_count = len([u for u in payments if u.status == "PAID"])
        total_count = len(payments)
        compliance_rate = paid_count / total_count if total_count > 0 else 0
        metrics["utility_compliance"] = compliance_rate
        
        if any(u.status in ["MISSED", "LATE"] for u in payments):
            metrics["early_warnings"].append("MISSED_UTILITY_PAYMENT")
        
        if compliance_rate < config.UTILITY_COMPLIANCE_THRESHOLD:
            metrics["early_warnings"].append("LOW_UTILITY_COMPLIANCE")
        
        return metrics
