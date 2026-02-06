from utils.db import Database
from models.loan import LoanStatus
from agents.audit_agent import AuditAgent
from ml_models.training_pipeline import train_bootstrap_model
import threading
import datetime
import logging
logger = logging.getLogger(__name__)

class SelfHealingAgent:
    """
    Automates the 'Closed-Loop' learning of the AI Engine.
    Monitors loan outcomes and triggers retraining when enough new data is available.
    """
    
    _PENDING_CLOSURES = 0
    RETRAIN_THRESHOLD = 5 # Retrain every 5 new outcomes (low for demo)

    @classmethod
    def register_outcome(cls, loan_id: str, status: LoanStatus):
        """
        Called when a loan is marked as PAID or DEFAULTED.
        Tracks the count of new data points and triggers asynchronous retraining.
        """
        cls._PENDING_CLOSURES += 1
        
        AuditAgent.log_event("SELF_HEALING_OBSERVATION", "SYSTEM", {
            "loan_id": loan_id,
            "outcome": status,
            "total_pending": cls._PENDING_CLOSURES
        })
        
        if cls._PENDING_CLOSURES >= cls.RETRAIN_THRESHOLD:
            logger.info(f"SELF-HEALING: Threshold of {cls.RETRAIN_THRESHOLD} reached. Triggering AutoML update.")
            cls.trigger_retrain()
            cls._PENDING_CLOSURES = 0

    @classmethod
    def trigger_retrain(cls):
        """Runs retraining in a separate thread to avoid blocking the API."""
        thread = threading.Thread(target=cls._perform_retrain)
        thread.start()

    @staticmethod
    def _perform_retrain():
        try:
            logger.info("SELF-HEALING: Background retraining started...")
            train_bootstrap_model()
            # Clear MLRiskAgent cache
            from agents.ml_risk_agent import MLRiskAgent
            MLRiskAgent._model = None 
            AuditAgent.log_event("SELF_HEALING_COMPLETE", "SYSTEM", {"status": "SUCCESS"})
            logger.info("SELF-HEALING: AI Engine has successfully learned from recent outcomes.")
        except Exception as e:
            import traceback
            with open("self_healing_error.log", "a") as f:
                f.write(f"--- ERROR AT {datetime.datetime.now()} ---\n")
                f.write(traceback.format_exc())
                f.write("\n")
            AuditAgent.log_event("SELF_HEALING_FAILED", "SYSTEM", {"error": str(e)})
            logger.error(f"SELF-HEALING: Error during background training: {e}")