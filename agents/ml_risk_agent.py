import xgboost as xgb
import pandas as pd
import os
import numpy as np
from typing import Dict, Any, List
from models.borrower import Borrower
from models.alternative_data import AlternativeData

class MLRiskAgent:
    """
    Next-Gen ML Risk Agent using XGBoost and SHAP for explainable scoring.
    """
    _model = None
    _features = None

    @classmethod
    def load_model(cls):
        if cls._model is None:
            model_path = os.path.join("ml_models", "risk_model.json")
            feature_path = os.path.join("ml_models", "features.txt")
            
            if os.path.exists(model_path):
                cls._model = xgb.XGBClassifier()
                cls._model.load_model(model_path)
                
                with open(feature_path, "r") as f:
                    cls._features = f.read().split(",")
                print(f"DEBUG: ML Risk Model loaded from {model_path}")
            else:
                print("WARNING: ML Risk Model not found. inference will be disabled.")
        return cls._model

    @classmethod
    def predict(cls, borrower: Borrower, alt_data: AlternativeData = None) -> Dict[str, Any]:
        model = cls.load_model()
        if model is None:
            return {"error": "Model not loaded"}

        # Prepare input data
        # We need to match the feature names used during training
        input_dict = {
            'monthly_income': borrower.monthly_income,
            'monthly_expenses': borrower.monthly_expenses,
            'existing_debt': borrower.existing_debt,
            'loan_amount_requested': borrower.loan_amount_requested,
            'airtime_usage_avg': alt_data.airtime_usage_avg if alt_data else 0.0,
            'mm_tx_vol': len(alt_data.mobile_money_history) if alt_data else 0.0,
            'saving_trend': 0.0 # Placeholder for now, could be derived from MM history
        }

        # Ensure all required features are present
        X = pd.DataFrame([input_dict])
        
        # Inference
        prob_default = float(model.predict_proba(X)[0][1])
        repayment_score = 1 - prob_default

        # SHAP Explainability (XAI)
        try:
            import shap
        except ImportError:
            return {"error": "SHAP not installed. Install shap to enable ML explanations."}

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        
        # Get top 3 contributing features
        feature_importance = []
        if isinstance(shap_values, list): # For multiclass/multioutput
            sv = shap_values[1][0]
        else:
            sv = shap_values[0]
            
        for i, val in enumerate(sv):
            feature_importance.append({
                "feature": cls._features[i],
                "impact": float(val)
            })
        
        # Sort by absolute impact
        feature_importance = sorted(feature_importance, key=lambda x: abs(x["impact"]), reverse=True)[:3]

        return {
            "prob_default": prob_default,
            "repayment_score": repayment_score,
            "feature_importance": feature_importance,
            "ml_risk_level": "HIGH" if prob_default > 0.6 else ("MEDIUM" if prob_default > 0.3 else "LOW")
        }
