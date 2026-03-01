import xgboost as xgb
import pandas as pd
import os
import numpy as np
from typing import Dict, Any, List
from models.borrower import Borrower
from models.alternative_data import AlternativeData
import logging
logger = logging.getLogger(__name__)

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

                if os.path.exists(feature_path):
                    with open(feature_path, "r") as f:
                        cls._features = [name for name in f.read().split(",") if name]
                else:
                    booster = cls._model.get_booster()
                    cls._features = booster.feature_names or []
                logger.debug(f"DEBUG: ML Risk Model loaded from {model_path}")
            else:
                logger.warning("WARNING: ML Risk Model not found. inference will be disabled.")
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

        feature_order = cls._features or list(input_dict.keys())
        ordered_input = {name: float(input_dict.get(name, 0.0)) for name in feature_order}
        X = pd.DataFrame([ordered_input], columns=feature_order)
        
        # Inference: prefer sklearn wrapper, but fall back to Booster predict when
        # model metadata (e.g. n_classes_) is unavailable after JSON load.
        prob_default = None
        try:
            proba = model.predict_proba(X)
            if isinstance(proba, np.ndarray) and proba.ndim == 2 and proba.shape[1] > 1:
                prob_default = float(proba[0][1])
            else:
                prob_default = float(np.asarray(proba).reshape(-1)[0])
        except Exception as e:
            logger.warning(f"WARN: predict_proba unavailable ({e}). Falling back to booster.predict.")
            booster = model.get_booster() if hasattr(model, "get_booster") else model
            dmatrix = xgb.DMatrix(X, feature_names=feature_order)
            raw_pred = booster.predict(dmatrix)
            prob_default = float(np.asarray(raw_pred).reshape(-1)[0])

        prob_default = max(0.0, min(prob_default, 1.0))
        repayment_score = 1 - prob_default

        # SHAP Explainability (XAI)
        feature_importance = []
        try:
            import shap
            shap_model = model.get_booster() if hasattr(model, "get_booster") else model
            explainer = shap.TreeExplainer(shap_model)
            shap_values = explainer.shap_values(X)

            if isinstance(shap_values, list):  # multiclass/multioutput
                sv = shap_values[1][0]
            else:
                sv = np.asarray(shap_values)[0]

            for i, val in enumerate(sv):
                if i >= len(feature_order):
                    break
                feature_importance.append({
                    "feature": feature_order[i],
                    "impact": float(val)
                })

            feature_importance = sorted(feature_importance, key=lambda x: abs(x["impact"]), reverse=True)[:3]
        except ImportError:
            logger.info("INFO: SHAP not installed; returning ML score without feature importance.")
        except Exception as e:
            logger.warning(f"WARN: SHAP explainability failed: {e}")

        return {
            "prob_default": prob_default,
            "repayment_score": repayment_score,
            "feature_importance": feature_importance,
            "ml_risk_level": "HIGH" if prob_default > 0.6 else ("MEDIUM" if prob_default > 0.3 else "LOW")
        }
