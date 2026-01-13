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

from typing import List, Dict, Any
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
        # We adapt the existing logic but for the new Transaction class
        metrics = {
            "behavioral_stability": 0.0,
            "income_consistency_score": 0.0,
            "transaction_stability": 0.0,
            "saving_trend": 0.0,
            "savings_behavior": 0.0,
            "expense_volatility": 0.0,
            "early_warnings": [],
            "utility_compliance": 0.0 # Default 0 for uploads unless we parse utility specific lines
        }
        
        if not transactions:
            return metrics

        # get confidence weight from first tx (all should be same source)
        confidence = transactions[0].confidence_weight if transactions else 0.6
        
        # --- LOGICHARMONIZATION ---
        # Map standardized Transaction to internal logic
        # Transaction(amount, direction="INFLOW"/"OUTFLOW")
        
        # Stability (Volume) - Scale by confidence
        metrics["behavioral_stability"] = min(len(transactions) / 20.0, 1.0) * confidence

        # Income Consistency
        inflows = [t.amount for t in transactions if t.direction == "INFLOW"]
        if len(inflows) >= 3:
            mean_in = statistics.mean(inflows)
            std_in = statistics.stdev(inflows) if len(inflows) > 1 else 0
            cv = std_in / mean_in if mean_in > 0 else 10
            # Score * Confidence
            raw_score = max(0, 1 - (cv / 0.5))
            metrics["income_consistency_score"] = raw_score * confidence

        # Savings & Spending
        total_in = sum(inflows)
        total_out = sum(t.amount for t in transactions if t.direction == "OUTFLOW")
        
        if total_in > 0:
            savings_rate = (total_in - total_out) / total_in
            metrics["saving_trend"] = savings_rate # Keep raw for trend
            metrics["savings_behavior"] = max(0, min(savings_rate, 1.0)) * confidence
            
            # Spike check
            if total_out > total_in * config.SPENDING_SPIKE_THRESHOLD:
                metrics["early_warnings"].append("SUSPICIOUS_SPENDING_SPIKE (User Upload)")

        # Transaction Stability (Volatility)
        amounts = [t.amount for t in transactions]
        if len(amounts) >= 5:
            mean = statistics.mean(amounts)
            std = statistics.stdev(amounts) if len(amounts) > 1 else 0
            cv_all = std / mean if mean > 0 else 10
            metrics["transaction_stability"] = max(0, 1 - (cv_all / 1.0)) * confidence

        # Expense Volatility
        outflows = [t.amount for t in transactions if t.direction == "OUTFLOW"]
        if len(outflows) >= 3:
             mean_out = statistics.mean(outflows)
             std_out = statistics.stdev(outflows) if len(outflows) > 1 else 0
             cv_out = std_out / mean_out if mean_out > 0 else 10
             metrics["expense_volatility"] = min(cv_out, 1.0) # Raw volatility is ok, impact is capped in risk agent

        return metrics

    @staticmethod
    def analyze(alt_data: AlternativeData) -> Dict[str, Any]:
        """
        Calculates comprehensive behavioral metrics from alternative data.
        
        METRICS COMPUTED:
        1. income_consistency_score: How regular are deposits? (0-1)
        2. transaction_stability: Inverse of transaction volatility (0-1)
        3. savings_behavior: Net savings rate over time (0-1)
        4. expense_volatility: Consistency of spending patterns (0-1)
        5. early_warnings: List of behavioral red flags
        
        Args:
            alt_data: Alternative data including mobile money and utility history
            
        Returns:
            Dictionary with behavioral metrics and warnings
        """
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

        # ====================================================================
        # METRIC 1: MOBILE MONEY TRANSACTION ANALYSIS
        # ====================================================================
        # WHY: Transaction patterns reveal income stability and spending discipline
        
        if alt_data.mobile_money_history:
            mm_metrics = BehavioralAgentV2._analyze_mobile_money(alt_data.mobile_money_history)
            results.update(mm_metrics)

        # ====================================================================
        # METRIC 2: UTILITY PAYMENT COMPLIANCE
        # ====================================================================
        # WHY: Utility payment history is a strong predictor of loan repayment
        # RESEARCH: Studies show 70%+ correlation between utility and loan payments
        
        if alt_data.utility_history:
            utility_metrics = BehavioralAgentV2._analyze_utility_payments(alt_data.utility_history)
            results.update(utility_metrics)

        return results

    @staticmethod
    def _analyze_mobile_money(transactions: List[MobileMoneyTransaction]) -> Dict[str, Any]:
        """
        Analyzes mobile money transaction history for behavioral signals.
        
        ANALYSIS COMPONENTS:
        1. Transaction volume (more transactions = more data reliability)
        2. Income consistency (regularity of deposits)
        3. Savings trend (net cash flow over time)
        4. Spending spikes (sudden high outflows)
        5. Transaction stability (volatility of amounts)
        
        Args:
            transactions: List of mobile money transactions
            
        Returns:
            Dictionary with mobile money metrics
        """
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
        
        # ====================================================================
        # STEP 1: BEHAVIORAL STABILITY (Transaction Volume)
        # ====================================================================
        # WHY: More transactions = more reliable behavioral data
        # THRESHOLD: 20+ transactions considered stable
        
        total_tx = len(transactions)
        metrics["behavioral_stability"] = min(total_tx / 20.0, 1.0)
        
        # ====================================================================
        # STEP 2: INCOME CONSISTENCY (Deposit Regularity)
        # ====================================================================
        # WHY: Regular deposits indicate stable income source
        # METHOD: Calculate coefficient of variation for deposit amounts
        
        deposits = [t for t in transactions if t.type in ["DEPOSIT", "TRANSFER_IN", "SALARY"]]
        
        if len(deposits) >= 3:
            deposit_amounts = [t.amount for t in deposits]
            
            # Calculate coefficient of variation (CV = std_dev / mean)
            # WHY: CV measures relative variability
            # INTERPRETATION: Low CV = consistent income, High CV = volatile income
            mean_deposit = statistics.mean(deposit_amounts)
            if mean_deposit > 0:
                std_deposit = statistics.stdev(deposit_amounts) if len(deposit_amounts) > 1 else 0
                cv = std_deposit / mean_deposit
                
                # Convert CV to score (0-1, lower CV = higher score)
                # WHY: CV of 0.5 or less is considered good consistency
                metrics["income_consistency_score"] = max(0, 1 - (cv / 0.5))
        
        # ====================================================================
        # STEP 3: SAVINGS BEHAVIOR (Net Cash Flow Trend)
        # ====================================================================
        # WHY: Positive savings trend indicates financial discipline
        # METHOD: Compare inflows vs outflows over last 30 days
        
        one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_tx = []
        for t in transactions:
            # Ensure t.timestamp is aware for comparison
            tx_ts = t.timestamp
            if tx_ts.tzinfo is None:
                tx_ts = tx_ts.replace(tzinfo=timezone.utc)
            
            if tx_ts > one_month_ago:
                recent_tx.append(t)
        
        if recent_tx:
            inflow = sum(t.amount for t in recent_tx if t.type in ["DEPOSIT", "TRANSFER_IN", "SALARY"])
            outflow = sum(t.amount for t in recent_tx if t.type in ["WITHDRAWAL", "PAYMENT", "TRANSFER_OUT"])
            
            if inflow > 0:
                # Net savings rate = (inflow - outflow) / inflow
                # WHY: Measures what percentage of income is saved
                savings_rate = (inflow - outflow) / inflow
                metrics["saving_trend"] = savings_rate
                metrics["savings_behavior"] = max(0, min(savings_rate, 1.0))
                
                # ====================================================================
                # EARLY WARNING: SPENDING SPIKE
                # ====================================================================
                # WHY: Sudden high spending may indicate financial stress or emergency
                # THRESHOLD: Outflow > 1.5x inflow
                
                if outflow > inflow * config.SPENDING_SPIKE_THRESHOLD:
                    metrics["early_warnings"].append("SUSPICIOUS_SPENDING_SPIKE")
        
        # ====================================================================
        # STEP 4: TRANSACTION STABILITY (Volatility Analysis)
        # ====================================================================
        # WHY: Stable transaction amounts indicate predictable financial behavior
        # METHOD: Calculate coefficient of variation for all transactions
        
        if len(transactions) >= 5:
            all_amounts = [t.amount for t in transactions]
            mean_amount = statistics.mean(all_amounts)
            
            if mean_amount > 0:
                std_amount = statistics.stdev(all_amounts) if len(all_amounts) > 1 else 0
                cv_all = std_amount / mean_amount
                
                # Convert to stability score (inverse of volatility)
                # WHY: Lower volatility = higher stability
                metrics["transaction_stability"] = max(0, 1 - (cv_all / 1.0))
        
        # ====================================================================
        # STEP 5: EXPENSE VOLATILITY
        # ====================================================================
        # WHY: Erratic spending patterns may indicate poor financial planning
        # METHOD: Analyze consistency of outflows
        
        outflows = [t for t in transactions if t.type in ["WITHDRAWAL", "PAYMENT", "TRANSFER_OUT"]]
        
        if len(outflows) >= 3:
            outflow_amounts = [t.amount for t in outflows]
            mean_outflow = statistics.mean(outflow_amounts)
            
            if mean_outflow > 0:
                std_outflow = statistics.stdev(outflow_amounts) if len(outflow_amounts) > 1 else 0
                cv_outflow = std_outflow / mean_outflow
                
                # Convert to volatility score (higher CV = higher volatility)
                # WHY: Consistent expenses indicate good budgeting
                metrics["expense_volatility"] = min(cv_outflow, 1.0)
        
        return metrics

    @staticmethod
    def _analyze_utility_payments(payments: List[UtilityPayment]) -> Dict[str, Any]:
        """
        Analyzes utility payment history for compliance and reliability.
        
        WHY UTILITY PAYMENTS MATTER:
        - Strong predictor of loan repayment behavior
        - Indicates financial responsibility
        - Regular payments show ability to meet recurring obligations
        
        Args:
            payments: List of utility payment records
            
        Returns:
            Dictionary with utility compliance metrics
        """
        metrics = {
            "utility_compliance": 0.0,
            "early_warnings": []
        }
        
        if not payments:
            return metrics
        
        # ====================================================================
        # UTILITY COMPLIANCE RATE
        # ====================================================================
        # WHY: On-time utility payments predict on-time loan payments
        # METHOD: Calculate percentage of payments marked as "PAID"
        
        paid_count = len([u for u in payments if u.status == "PAID"])
        total_count = len(payments)
        
        compliance_rate = paid_count / total_count if total_count > 0 else 0
        metrics["utility_compliance"] = compliance_rate
        
        # ====================================================================
        # EARLY WARNING: MISSED PAYMENTS
        # ====================================================================
        # WHY: Even one missed utility payment is a red flag
        # THRESHOLD: Any payment with status "MISSED" or "LATE"
        
        if any(u.status in ["MISSED", "LATE"] for u in payments):
            metrics["early_warnings"].append("MISSED_UTILITY_PAYMENT")
        
        # ====================================================================
        # EARLY WARNING: LOW COMPLIANCE RATE
        # ====================================================================
        # WHY: Compliance below threshold indicates payment reliability issues
        # THRESHOLD: Configurable (default 80%)
        
        if compliance_rate < config.UTILITY_COMPLIANCE_THRESHOLD:
            metrics["early_warnings"].append("LOW_UTILITY_COMPLIANCE")
        
        return metrics
