from typing import List, Dict, Any
from models.alternative_data import AlternativeData, MobileMoneyTransaction, UtilityPayment
from datetime import datetime, timedelta

class BehavioralAgent:
    """
    Analyzes time-series data from alternative sources to detect trends and risks.
    """

    @staticmethod
    def analyze(alt_data: AlternativeData) -> Dict[str, Any]:
        """
        Calculates behavioral metrics: stability, saving trend, and early warnings.
        """
        results = {
            "behavioral_stability": 0.0,
            "saving_trend": 0.0,
            "early_warnings": [],
            "utility_compliance": 0.0
        }

        if not alt_data:
            return results

        # 1. Analyze Mobile Money Trends
        if alt_data.mobile_money_history:
            total_tx = len(alt_data.mobile_money_history)
            results["behavioral_stability"] = min(total_tx / 20.0, 1.0) # Assume 20+ tx is stable

            # Simple saving trend: Net cash flow over the last month
            one_month_ago = datetime.now() - timedelta(days=30)
            recent_tx = [t for t in alt_data.mobile_money_history if t.timestamp.replace(tzinfo=None) > one_month_ago]
            
            inflow = sum(t.amount for t in recent_tx if t.type in ["DEPOSIT", "TRANSFER"])
            outflow = sum(t.amount for t in recent_tx if t.type in ["WITHDRAWAL", "PAYMENT"])
            
            if inflow > 0:
                results["saving_trend"] = (inflow - outflow) / inflow
            
            # Early Warning: Sudden high spending
            if outflow > inflow * 1.5 and inflow > 0:
                results["early_warnings"].append("SUSPICIOUS_SPENDING_SPIKE")

        # 2. Utility Payment Consistency
        if alt_data.utility_history:
            paid_count = len([u for u in alt_data.utility_history if u.status == "PAID"])
            results["utility_compliance"] = paid_count / len(alt_data.utility_history)
            
            if any(u.status == "MISSED" for u in alt_data.utility_history):
                results["early_warnings"].append("MISSED_UTILITY_PAYMENT")

        return results
