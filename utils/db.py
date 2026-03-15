import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth
import os
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from models.borrower import Borrower
from models.assessment import Assessment
from models.loan import Loan
from models.alternative_data import AlternativeData
from utils.encryption import EncryptionAgent
from models.organization import Organization
from models.decision_export import DecisionExport
from models.decision_counterfactual import DecisionCounterfactual
from models.api_key import APIKey
from models.user import User
from models.usage_log import UsageLog
from models.usage_record import UsageRecord
from models.payment import Payment
from models.organization import OrgEnvironment
from models.officer_action import OfficerAction
from models.sms_log import SMSLog
from models.follow_up_task import FollowUpTask
from models.notification import Notification
from models.demo_request import DemoRequest
from models.document_insight import DocumentInsightRecord
import logging
logger = logging.getLogger(__name__)

class MockFirestore:
    """A simple in-memory mock to simulate Firestore locally with basic filtering.
    Now with JSON file persistence!"""
    DB_FILE = os.path.join(os.getcwd(), "mock_firestore.json")

    def __init__(self):
        self.collections = {}
        self.load()

    def load(self):
        import json
        if os.path.exists(self.DB_FILE):
             try:
                with open(self.DB_FILE, 'r') as f:
                    data = json.load(f)
                    for col_name, col_data in data.items():
                        # Reconstruct collections and docs
                        collection = self.collection(col_name)
                        for doc_id, doc_data in col_data.items():
                            collection.document(doc_id).set(doc_data)
             except Exception as e:
                logger.error(f"WARNING: Failed to load mock DB: {e}")

    def save(self):
        import json
        data = {}
        for col_name, col_obj in self.collections.items():
            data[col_name] = {doc_id: doc.data for doc_id, doc in col_obj.docs.items() if doc.data}
        
        with open(self.DB_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug(f"DEBUG: Mock DB saved to {self.DB_FILE}")

    def collection(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection(self)
        return self.collections[name]

class MockCollection:
    def __init__(self, db_instance, docs=None):
        self.db_instance = db_instance
        self.docs = docs if docs is not None else {}

    def document(self, id):
        if id not in self.docs:
            self.docs[id] = MockDocument(id, self.db_instance)
        return self.docs[id]

    def stream(self):
        return [doc for doc in self.docs.values() if doc.data]

    def where(self, field, op, value):
        """Simulate basic equality filtering for multi-tenancy."""
        if op == "==":
            filtered_docs = {id: doc for id, doc in self.docs.items() if doc.data and doc.data.get(field) == value}
            return MockCollection(self.db_instance, filtered_docs)
        return self

class MockDocument:
    def __init__(self, id, db_instance):
        self.id = id
        self.db_instance = db_instance
        self.data = None
        self.exists = False

    def set(self, data):
        self.data = data
        self.exists = True
        # Auto-save on writes
        if self.db_instance:
             self.db_instance.save()

    def get(self):
        return self

    def delete(self):
        self.data = None
        self.exists = False
        if self.db_instance:
            self.db_instance.save()

    def to_dict(self):
        return self.data

class Database:
    _db = None

    @classmethod
    def get_db(cls):
        if cls._db is None:
            # Check if we are on Cloud Run
            is_cloud_run = os.getenv("K_SERVICE") is not None
            service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT", "serviceAccountKey.json")
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "mfi--pro")
            
            logger.debug(f"DEBUG: Initializing Database. Cloud Run: {is_cloud_run}, Project: {project_id}")
            
            try:
                # Priority 1: Service Account Key File (mostly for local development)
                if os.path.exists(service_account_path):
                    logger.debug(f"DEBUG: Found service account key at {service_account_path}")
                    cred = credentials.Certificate(service_account_path)
                    if not len(firebase_admin._apps):
                        firebase_admin.initialize_app(cred, {'projectId': project_id})
                    cls._db = firestore.client()
                    logger.debug(f"DEBUG: Firestore initialized using key file.")
                
                # Priority 2: Application Default Credentials (for Cloud Run / GCP)
                else:
                    logger.debug(f"DEBUG: Service key NOT found. Attempting Application Default Credentials (ADC)...")
                    if not len(firebase_admin._apps):
                        # On Cloud Run, this should automatically use the per-service identity
                        try:
                            firebase_admin.initialize_app(options={'projectId': project_id})
                            logger.debug(f"DEBUG: Firebase Admin initialized with project_id={project_id}")
                        except Exception as init_err:
                            logger.error(f"DEBUG: Simple initialization failed: {init_err}")
                            # Fallback: maybe it's already initialized but without project_id?
                            if len(firebase_admin._apps):
                                logger.debug("DEBUG: App already exists, continuing to firestore.client()")
                            else:
                                raise init_err
                    
                    cls._db = firestore.client()
                    logger.debug(f"DEBUG: Firestore client created successfully via ADC.")
                
                sys.stdout.flush()
            except Exception as e:
                import traceback
                logger.error(f"CRITICAL: Real Firestore initialization failed! Fallback to Mock occurred.")
                logger.error(f"Error Details: {e}")
                traceback.print_exc()
                sys.stdout.flush()
                # We still fall back to Mock to avoid crashing the whole app, 
                # but we've logged exactly why it failed.
                cls._db = MockFirestore()
        return cls._db

    @classmethod
    def reload_db(cls):
        """Forces a reload of the database connection or mock data."""
        if cls._db and isinstance(cls._db, MockFirestore):
            logger.debug("DEBUG: Reloading MockFirestore from disk...")
            cls._db.load()

    @classmethod
    def save_borrower(cls, borrower: Borrower):
        db = cls.get_db()
        # Encrypt PII before saving
        data = borrower.model_dump()
        data["phone"] = EncryptionAgent.encrypt(borrower.phone)
        if borrower.national_id:
            data["national_id"] = EncryptionAgent.encrypt(borrower.national_id)
        db.collection("borrowers").document(borrower.id).set(data)

    @classmethod
    def get_borrower(cls, borrower_id: str) -> Optional[Borrower]:
        db = cls.get_db()
        doc = db.collection("borrowers").document(borrower_id).get()
        if doc.exists:
            data = doc.to_dict()
            # Decrypt PII after retrieval
            data["phone"] = EncryptionAgent.decrypt(data.get("phone", ""))
            if data.get("national_id"):
                data["national_id"] = EncryptionAgent.decrypt(data["national_id"])
            return Borrower(**data)
        return None

    @classmethod
    def list_borrowers(cls, organization_id: Optional[str] = None) -> List[Borrower]:
        db = cls.get_db()
        query = db.collection("borrowers")
        if organization_id:
            query = query.where("organization_id", "==", organization_id)
        
        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["phone"] = EncryptionAgent.decrypt(data.get("phone", ""))
            if data.get("national_id"):
                data["national_id"] = EncryptionAgent.decrypt(data["national_id"])
            results.append(Borrower(**data))
        return results

    @classmethod
    def save_assessment(cls, assessment: Assessment):
        db = cls.get_db()
        logger.info(f"[DB SAVE] Saving assessment {assessment.assessment_id} to collection 'assessments' with org_id: {assessment.organization_id}. DB Type: {type(db)}")
        sys.stdout.flush()
        db.collection("assessments").document(assessment.assessment_id).set(assessment.model_dump())

    @classmethod
    def get_assessment(cls, assessment_id: str) -> Optional[Assessment]:
        db = cls.get_db()
        doc = db.collection("assessments").document(assessment_id).get()
        if doc.exists:
            return Assessment(**doc.to_dict())
        return None

    @classmethod
    def list_assessments(cls, organization_id: Optional[str] = None) -> List[Assessment]:
        db = cls.get_db()
        query = db.collection("assessments")
        if organization_id:
            query = query.where("organization_id", "==", organization_id)
            
        docs = query.stream()
        results = []
        for doc in docs:
            try:
                results.append(Assessment(**doc.to_dict()))
            except Exception as e:
                logger.info(f"Skipping malformed assessment {doc.id}: {e}")
        return cls._sort_assessments_by_time(results)

    @classmethod
    def delete_assessment(cls, assessment_id: str):
        db = cls.get_db()
        db.collection("assessments").document(assessment_id).delete()
        if hasattr(db, "save"):
            db.save()

    @classmethod
    def save_alternative_data(cls, data: AlternativeData):
        db = cls.get_db()
        db.collection("alternative_data").document(data.borrower_id).set(data.model_dump())

    @classmethod
    def get_alternative_data(cls, borrower_id: str) -> Optional[AlternativeData]:
        db = cls.get_db()
        doc = db.collection("alternative_data").document(borrower_id).get()
        if doc.exists:
            return AlternativeData(**doc.to_dict())
        return None

    # ------------------------------------------------------------------
    # SMS/USSD Sessions (Borrower Journeys)
    # ------------------------------------------------------------------

    @classmethod
    def save_channel_session(cls, session_id: str, data: Dict[str, Any]):
        db = cls.get_db()
        db.collection("channel_sessions").document(session_id).set(data)

    @classmethod
    def get_channel_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        db = cls.get_db()
        doc = db.collection("channel_sessions").document(session_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    # ------------------------------------------------------------------
    # Consent Events (Regulatory Ledger)
    # ------------------------------------------------------------------

    @classmethod
    def save_consent_event(cls, event_id: str, data: Dict[str, Any]):
        db = cls.get_db()
        db.collection("consent_events").document(event_id).set(data)

    @classmethod
    def get_consent_event(cls, event_id: str) -> Optional[Dict[str, Any]]:
        db = cls.get_db()
        doc = db.collection("consent_events").document(event_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    @classmethod
    def list_consent_events_for_borrower(cls, borrower_id: str) -> List[Dict[str, Any]]:
        db = cls.get_db()
        docs = db.collection("consent_events").where("borrower_id", "==", borrower_id).stream()
        return [doc.to_dict() for doc in docs]

    @classmethod
    def save_loan(cls, loan: Loan):
        db = cls.get_db()
        db.collection("loans").document(loan.loan_id).set(loan.model_dump(mode='json'))

    # ------------------------------------------------------------------
    # Document Ingestion Jobs (Async Uploads)
    # ------------------------------------------------------------------

    @classmethod
    def save_ingestion_job(cls, job_id: str, data: Dict[str, Any]):
        db = cls.get_db()
        db.collection("ingestion_jobs").document(job_id).set(data)

    @classmethod
    def get_ingestion_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        db = cls.get_db()
        doc = db.collection("ingestion_jobs").document(job_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    @classmethod
    def get_ingestion_job_by_idempotency_key(cls, org_id: str, key: str) -> Optional[Dict[str, Any]]:
        if not key:
            return None
        db = cls.get_db()
        query = db.collection("ingestion_jobs").where("organization_id", "==", org_id).where("idempotency_key", "==", key)
        docs = query.stream()
        for doc in docs:
            return doc.to_dict()
        return None

    @classmethod
    def get_assessments_by_org(cls, organization_id: str, limit: int = 50) -> List[Assessment]:
        """Fetches the most recent assessments for a specific organization."""
        db = cls.get_db()
        query = db.collection("assessments").where("organization_id", "==", organization_id)
        docs = query.stream()
        results = []
        for doc in docs:
            try:
                results.append(Assessment(**doc.to_dict()))
            except Exception as e:
                logger.info(f"Skipping malformed assessment {doc.id}: {e}")
                
        results = cls._sort_assessments_by_time(results)
        return results[:limit]

    @staticmethod
    def _sort_assessments_by_time(assessments: List[Assessment]) -> List[Assessment]:
        def _extract_ts(assessment: Assessment):
            ts = getattr(assessment, "decision_timestamp", None)
            if isinstance(ts, str):
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    return datetime.min
            if isinstance(ts, datetime):
                return ts
            return datetime.min

        return sorted(assessments, key=_extract_ts, reverse=True)

    @classmethod
    def get_loan(cls, loan_id: str) -> Optional[Loan]:
        db = cls.get_db()
        doc = db.collection("loans").document(loan_id).get()
        if doc.exists:
            return Loan(**doc.to_dict())
        return None

    @classmethod
    def list_loans(cls, organization_id: Optional[str] = None) -> List[Loan]:
        db = cls.get_db()
        query = db.collection("loans")
        if organization_id:
            query = query.where("organization_id", "==", organization_id)
            
        docs = query.stream()
        return [Loan(**doc.to_dict()) for doc in docs]

    @classmethod
    def delete_loans_by_assessment(cls, assessment_id: str):
        db = cls.get_db()
        docs = db.collection("loans").where("assessment_id", "==", assessment_id).stream()
        for doc in docs:
            try:
                if hasattr(doc, "reference"):
                    doc.reference.delete()
                else:
                    db.collection("loans").document(doc.id).delete()
            except Exception:
                pass
        if hasattr(db, "save"):
            db.save()

    @classmethod
    def save_organization(cls, org: Organization):
        db = cls.get_db()
        db.collection("organizations").document(org.id).set(org.model_dump(mode='json'))

    @classmethod
    def get_organization(cls, org_id: str) -> Optional[Organization]:
        db = cls.get_db()
        doc = db.collection("organizations").document(org_id).get()
        if doc.exists:
            return Organization(**doc.to_dict())
        return None

    @classmethod
    def list_organizations(cls) -> List[Organization]:
        db = cls.get_db()
        docs = db.collection("organizations").stream()
        return [Organization(**doc.to_dict()) for doc in docs]

    @classmethod
    def delete_organization_cascade(cls, org_id: str) -> Dict[str, int]:
        """
        Permanently removes an organization and all related records.
        Returns counts of deleted records by area.
        """
        db = cls.get_db()
        summary = {
            "organizations": 0,
            "assessments": 0,
            "loans": 0,
            "decision_exports": 0,
            "decision_counterfactuals": 0,
            "officer_actions": 0,
            "sms_logs": 0,
            "follow_up_tasks": 0,
            "notifications": 0,
            "borrowers": 0,
            "alternative_data": 0,
            "users": 0,
            "api_keys": 0,
            "usage_logs": 0,
            "usage_records": 0,
            "payments": 0,
        }

        def _delete_doc(collection_name: str, doc_id: str) -> bool:
            try:
                db.collection(collection_name).document(doc_id).delete()
                return True
            except Exception:
                return False

        def _delete_query_docs(collection_name: str, field: str, value: str) -> int:
            deleted = 0
            docs = db.collection(collection_name).where(field, "==", value).stream()
            for doc in docs:
                try:
                    if hasattr(doc, "reference"):
                        doc.reference.delete()
                    else:
                        db.collection(collection_name).document(doc.id).delete()
                    deleted += 1
                except Exception:
                    continue
            return deleted

        # 1) Assessments and dependent records
        assessment_docs = db.collection("assessments").where("organization_id", "==", org_id).stream()
        assessment_ids = [doc.id for doc in assessment_docs]
        for assessment_id in assessment_ids:
            summary["decision_exports"] += len(cls.list_decision_exports(assessment_id))
            cls.delete_decision_exports(assessment_id)
            summary["decision_counterfactuals"] += len(cls.list_decision_counterfactuals(assessment_id))
            cls.delete_decision_counterfactuals(assessment_id)
            if cls.get_officer_action(assessment_id):
                cls.delete_officer_action(assessment_id)
                summary["officer_actions"] += 1
            sms_count = len(cls.list_sms_logs(assessment_id))
            if sms_count:
                cls.delete_sms_logs(assessment_id)
                summary["sms_logs"] += sms_count
            task_count = len(cls.list_follow_up_tasks(assessment_id=assessment_id))
            if task_count:
                cls.delete_follow_up_tasks(assessment_id)
                summary["follow_up_tasks"] += task_count
            loan_count = len([l for l in cls.list_loans(organization_id=org_id) if l.assessment_id == assessment_id])
            if loan_count:
                cls.delete_loans_by_assessment(assessment_id)
                summary["loans"] += loan_count
            cls.delete_assessment(assessment_id)
            summary["assessments"] += 1

        # 2) Borrowers and alt data
        borrower_docs = db.collection("borrowers").where("organization_id", "==", org_id).stream()
        borrower_ids = [doc.id for doc in borrower_docs]
        for borrower_id in borrower_ids:
            if _delete_doc("alternative_data", borrower_id):
                summary["alternative_data"] += 1
            if _delete_doc("borrowers", borrower_id):
                summary["borrowers"] += 1

        # 3) Follow-up tasks that may not be attached to an assessment
        summary["follow_up_tasks"] += _delete_query_docs("follow_up_tasks", "organization_id", org_id)
        summary["notifications"] += _delete_query_docs("notifications", "organization_id", org_id)

        # 4) Usage and billing data
        summary["usage_logs"] += _delete_query_docs("usage_logs", "org_id", org_id)
        summary["usage_records"] += _delete_query_docs("usage_records", "organization_id", org_id)
        summary["payments"] += _delete_query_docs("payments", "org_id", org_id)

        # 5) API keys
        summary["api_keys"] += _delete_query_docs("api_keys", "organization_id", org_id)

        # 6) Users (delete Firestore + best-effort Firebase Auth account)
        user_docs = db.collection("users").where("organization_id", "==", org_id).stream()
        user_ids = [doc.id for doc in user_docs]
        for user_id in user_ids:
            if _delete_doc("users", user_id):
                summary["users"] += 1
            try:
                firebase_auth.delete_user(user_id)
            except Exception:
                # Firestore deletion is authoritative for app authorization.
                pass

        # 7) Organization record
        if _delete_doc("organizations", org_id):
            summary["organizations"] = 1

        if hasattr(db, "save"):
            db.save()

        return summary

    @classmethod
    def list_all_users(cls) -> List[User]:
        db = cls.get_db()
        docs = db.collection("users").stream()
        return [User(**doc.to_dict()) for doc in docs]

    @classmethod
    def list_users_by_org(cls, organization_id: str) -> List[User]:
        db = cls.get_db()
        query = db.collection("users").where("organization_id", "==", organization_id)
        docs = query.stream()
        return [User(**doc.to_dict()) for doc in docs]

    @classmethod
    def save_api_key(cls, api_key: APIKey):
        db = cls.get_db()
        db.collection("api_keys").document(api_key.key_hash).set(api_key.model_dump(mode='json'))

    @classmethod
    def get_api_key(cls, key_hash: str) -> Optional[APIKey]:
        db = cls.get_db()
        doc = db.collection("api_keys").document(key_hash).get()
        if doc.exists:
            return APIKey(**doc.to_dict())
        return None
    
    @classmethod
    def list_api_keys(cls, organization_id: str) -> List[APIKey]:
        db = cls.get_db()
        query = db.collection("api_keys").where("organization_id", "==", organization_id)
        docs = query.stream()
        return [APIKey(**doc.to_dict()) for doc in docs]

    @classmethod
    def save_user(cls, user: User):
        db = cls.get_db()
        db.collection("users").document(user.id).set(user.model_dump(mode='json'))

    @classmethod
    def get_user_by_email(cls, email: str) -> Optional[User]:
        db = cls.get_db()
        query = db.collection("users").where("email", "==", email)
        docs = query.stream()
        results = [doc for doc in docs]
        if results:
            return User(**results[0].to_dict())
        return None

    @classmethod
    def get_user_by_id(cls, user_id: str) -> Optional[User]:
        db = cls.get_db()
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            return User(**doc.to_dict())
        return None
    
    @classmethod
    def save_usage_log(cls, usage_log: UsageLog):
        db = cls.get_db()
        db.collection("usage_logs").document(usage_log.log_id).set(usage_log.model_dump(mode='json'))
    
    @classmethod
    def get_usage_logs(cls, org_id: str, limit: int = 100, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[UsageLog]:
        db = cls.get_db()
        query = db.collection("usage_logs").where("org_id", "==", org_id)
        docs = query.stream()
        results = []
        for doc in docs:
            try:
                log = UsageLog(**doc.to_dict())
                if start_date and log.timestamp < start_date: continue
                if end_date and log.timestamp > end_date: continue
                results.append(log)
            except Exception as e:
                logger.info(f"Skipping malformed usage log {doc.id}: {e}")
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]

    @classmethod
    def save_usage_record(cls, record: UsageRecord):
        db = cls.get_db()
        doc_id = f"{record.organization_id}_{str(record.environment.value if hasattr(record.environment, 'value') else record.environment)}"
        data = record.model_dump(mode='json')
        if 'environment' in data: data['environment'] = str(data['environment'])
        db.collection("usage_records").document(doc_id).set(data)

    @classmethod
    def get_usage_record(cls, org_id: str, environment: OrgEnvironment) -> UsageRecord:
        db = cls.get_db()
        env_str = str(environment.value if hasattr(environment, 'value') else environment)
        doc_id = f"{org_id}_{env_str}"
        doc = db.collection("usage_records").document(doc_id).get()
        if doc.exists: return UsageRecord(**doc.to_dict())
        record = UsageRecord(organization_id=org_id, environment=environment)
        cls.save_usage_record(record)
        return record

    @classmethod
    def list_usage_records(cls, org_id: str) -> List[UsageRecord]:
        db = cls.get_db()
        docs = db.collection("usage_records").where("organization_id", "==", org_id).stream()
        return [UsageRecord(**doc.to_dict()) for doc in docs]

    @classmethod
    def save_payment(cls, payment: Payment):
        db = cls.get_db()
        db.collection("payments").document(payment.payment_id).set(payment.model_dump(mode='json'))

    @classmethod
    def get_payment(cls, payment_id: str) -> Optional[Payment]:
        db = cls.get_db()
        doc = db.collection("payments").document(payment_id).get()
        if doc.exists: return Payment(**doc.to_dict())
        return None

    @classmethod
    def get_payment_by_transaction_id(cls, transaction_id: str) -> Optional[Payment]:
        db = cls.get_db()
        query = db.collection("payments").where("transaction_id", "==", transaction_id)
        docs = query.stream()
        results = [doc for doc in docs]
        if results: return Payment(**results[0].to_dict())
        return None

    @classmethod
    def list_payments(cls, org_id: str) -> List[Payment]:
        db = cls.get_db()
        docs = db.collection("payments").where("org_id", "==", org_id).stream()
        return [Payment(**doc.to_dict()) for doc in docs]

    @classmethod
    def save_decision_export(cls, export: DecisionExport):
        db = cls.get_db()
        db.collection("decision_exports").document(export.id).set(export.model_dump(mode='json'))

    @classmethod
    def get_decision_export(cls, export_id: str) -> Optional[DecisionExport]:
        db = cls.get_db()
        doc = db.collection("decision_exports").document(export_id).get()
        if doc.exists: return DecisionExport(**doc.to_dict())
        return None

    @classmethod
    def list_decision_exports(cls, decision_id: str) -> List[DecisionExport]:
        db = cls.get_db()
        docs = db.collection("decision_exports").where("decision_id", "==", decision_id).stream()
        return [DecisionExport(**doc.to_dict()) for doc in docs]

    @classmethod
    def delete_decision_exports(cls, decision_id: str):
        db = cls.get_db()
        docs = db.collection("decision_exports").where("decision_id", "==", decision_id).stream()
        for doc in docs:
            try:
                if hasattr(doc, "reference"):
                    doc.reference.delete()
                else:
                    db.collection("decision_exports").document(doc.id).delete()
            except Exception:
                pass
        if hasattr(db, "save"):
            db.save()

    @classmethod
    def save_decision_counterfactual(cls, counterfactual: DecisionCounterfactual):
        db = cls.get_db()
        db.collection("decision_counterfactuals").document(counterfactual.id).set(counterfactual.model_dump(mode='json'))

    @classmethod
    def list_decision_counterfactuals(cls, decision_id: str) -> List[DecisionCounterfactual]:
        db = cls.get_db()
        docs = db.collection("decision_counterfactuals").where("decision_id", "==", decision_id).stream()
        return [DecisionCounterfactual(**doc.to_dict()) for doc in docs]

    @classmethod
    def delete_decision_counterfactuals(cls, decision_id: str):
        db = cls.get_db()
        docs = db.collection("decision_counterfactuals").where("decision_id", "==", decision_id).stream()
        for doc in docs:
            try:
                if hasattr(doc, "reference"): doc.reference.delete()
                else: db.collection("decision_counterfactuals").document(doc.id).delete()
            except Exception: pass

    @classmethod
    def save_officer_action(cls, action: OfficerAction):
        db = cls.get_db()
        db.collection("officer_actions").document(action.assessment_id).set(action.model_dump(mode='json'))
        if hasattr(db, 'save'): db.save()

    @classmethod
    def get_officer_action(cls, assessment_id: str) -> Optional[OfficerAction]:
        db = cls.get_db()
        doc = db.collection("officer_actions").document(assessment_id).get()
        if doc.exists: return OfficerAction(**doc.to_dict())
        return None

    @classmethod
    def delete_officer_action(cls, assessment_id: str):
        db = cls.get_db()
        db.collection("officer_actions").document(assessment_id).delete()
        if hasattr(db, "save"):
            db.save()

    @classmethod
    def save_sms_log(cls, log: SMSLog):
        db = cls.get_db()
        db.collection("sms_logs").document(log.id).set(log.model_dump(mode='json'))
        if hasattr(db, 'save'): db.save()

    @classmethod
    def list_sms_logs(cls, assessment_id: str) -> List[SMSLog]:
        db = cls.get_db()
        query = db.collection("sms_logs").where("assessment_id", "==", assessment_id)
        docs = query.stream()
        return [SMSLog(**doc.to_dict()) for doc in docs]

    @classmethod
    def delete_sms_logs(cls, assessment_id: str):
        db = cls.get_db()
        docs = db.collection("sms_logs").where("assessment_id", "==", assessment_id).stream()
        for doc in docs:
            try:
                if hasattr(doc, "reference"):
                    doc.reference.delete()
                else:
                    db.collection("sms_logs").document(doc.id).delete()
            except Exception:
                pass
        if hasattr(db, "save"):
            db.save()

    # ------------------------------------------------------------------
    # Follow-up Tasks (Officer Workflow)
    # ------------------------------------------------------------------

    @classmethod
    def save_follow_up_task(cls, task: FollowUpTask):
        db = cls.get_db()
        db.collection("follow_up_tasks").document(task.task_id).set(task.model_dump(mode='json'))
        if hasattr(db, 'save'): db.save()

    @classmethod
    def get_follow_up_task(cls, task_id: str) -> Optional[FollowUpTask]:
        db = cls.get_db()
        doc = db.collection("follow_up_tasks").document(task_id).get()
        if not doc.exists:
            return None
        try:
            return FollowUpTask(**doc.to_dict())
        except Exception as e:
            logger.info(f"Skipping malformed follow-up task {task_id}: {e}")
            return None

    @classmethod
    def list_follow_up_tasks(
        cls,
        organization_id: Optional[str] = None,
        assessment_id: Optional[str] = None
    ) -> List[FollowUpTask]:
        db = cls.get_db()
        query = db.collection("follow_up_tasks")
        if organization_id:
            query = query.where("organization_id", "==", organization_id)
        if assessment_id:
            query = query.where("assessment_id", "==", assessment_id)
        docs = query.stream()
        tasks = []
        for doc in docs:
            try:
                tasks.append(FollowUpTask(**doc.to_dict()))
            except Exception as e:
                logger.info(f"Skipping malformed follow-up task {doc.id}: {e}")

        if organization_id and not tasks:
            try:
                all_docs = db.collection("follow_up_tasks").stream()
                normalized_org = str(organization_id).strip().upper()
                for doc in all_docs:
                    payload = doc.to_dict()
                    if not payload:
                        continue
                    payload_org = str(payload.get("organization_id") or "").strip().upper()
                    payload_assessment = str(payload.get("assessment_id") or "").strip()
                    if payload_org != normalized_org:
                        continue
                    if assessment_id and payload_assessment != assessment_id:
                        continue
                    try:
                        tasks.append(FollowUpTask(**payload))
                    except Exception as e:
                        logger.info(f"Skipping malformed follow-up task {doc.id}: {e}")
            except Exception as e:
                logger.info(f"Case-insensitive follow-up fallback failed: {e}")

        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    @classmethod
    def delete_follow_up_tasks(cls, assessment_id: str):
        db = cls.get_db()
        docs = db.collection("follow_up_tasks").where("assessment_id", "==", assessment_id).stream()
        for doc in docs:
            try:
                if hasattr(doc, "reference"):
                    doc.reference.delete()
                else:
                    db.collection("follow_up_tasks").document(doc.id).delete()
            except Exception:
                pass
        if hasattr(db, "save"):
            db.save()

    # ------------------------------------------------------------------
    # Document Insights (Decision Chamber)
    # ------------------------------------------------------------------

    @classmethod
    def save_notification(cls, notification: Notification):
        db = cls.get_db()
        db.collection("notifications").document(notification.notification_id).set(notification.model_dump(mode='json'))
        if hasattr(db, 'save'):
            db.save()

    @classmethod
    def get_notification(cls, notification_id: str) -> Optional[Notification]:
        db = cls.get_db()
        doc = db.collection("notifications").document(notification_id).get()
        if doc.exists:
            return Notification(**doc.to_dict())
        return None

    @classmethod
    def list_notifications_for_user(
        cls,
        recipient_user_id: str,
        recipient_email: Optional[str] = None,
        organization_id: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        db = cls.get_db()
        docs = []
        # Prefer a narrow query but gracefully fall back to full scan if query filters fail.
        try:
            query = db.collection("notifications").where("recipient_user_id", "==", recipient_user_id)
            docs = query.stream()
        except Exception as query_error:
            logger.warning(f"Notification user query failed, falling back to scan: {query_error}")
            docs = db.collection("notifications").stream()

        notifications = []
        target_user_id = (recipient_user_id or "").strip()
        target_email = (recipient_email or "").strip().lower()
        target_org = (organization_id or "").strip().upper() if organization_id else None
        for doc in docs:
            try:
                notification = Notification(**doc.to_dict())
                notification_user_id = (notification.recipient_user_id or "").strip()
                notification_email = (notification.recipient_email or "").strip().lower()
                notification_org = (notification.organization_id or "").strip().upper()

                is_recipient_match = (
                    notification_user_id == target_user_id
                    or (target_email and notification_email == target_email)
                )
                if not is_recipient_match:
                    continue
                if target_org and notification_org != target_org:
                    continue
                if unread_only and notification.is_read:
                    continue

                notifications.append(notification)
            except Exception as e:
                logger.info(f"Skipping malformed notification {doc.id}: {e}")

        notifications.sort(key=lambda n: n.created_at, reverse=True)
        return notifications[:limit]

    @classmethod
    def mark_notification_read(cls, notification_id: str, recipient_user_id: str) -> bool:
        notification = cls.get_notification(notification_id)
        if not notification or notification.recipient_user_id != recipient_user_id:
            return False
        if notification.is_read:
            return True

        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        cls.save_notification(notification)
        return True

    @classmethod
    def mark_all_notifications_read(cls, recipient_user_id: str, organization_id: str) -> int:
        notifications = cls.list_notifications_for_user(
            recipient_user_id=recipient_user_id,
            recipient_email=None,
            organization_id=organization_id,
            unread_only=True,
            limit=1000
        )
        updated = 0
        for notification in notifications:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            cls.save_notification(notification)
            updated += 1
        return updated

    @classmethod
    def save_demo_request(cls, demo_request: DemoRequest):
        db = cls.get_db()
        db.collection("demo_requests").document(demo_request.request_id).set(demo_request.model_dump(mode="json"))
        if hasattr(db, "save"):
            db.save()

    @classmethod
    def list_demo_requests(
        cls,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[DemoRequest]:
        db = cls.get_db()
        docs = db.collection("demo_requests").stream()
        requests = []
        normalized_status = (status or "").strip().upper() if status else None

        for doc in docs:
            try:
                demo_request = DemoRequest(**doc.to_dict())
                request_status = getattr(demo_request.status, "value", demo_request.status)
                if normalized_status and str(request_status).upper() != normalized_status:
                    continue
                requests.append(demo_request)
            except Exception as e:
                logger.info(f"Skipping malformed demo request {doc.id}: {e}")

        def _extract_created_at(request: DemoRequest):
            created_at = getattr(request, "created_at", None)
            if isinstance(created_at, str):
                try:
                    return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except Exception:
                    return datetime.min.replace(tzinfo=timezone.utc)
            if isinstance(created_at, datetime):
                return created_at
            return datetime.min.replace(tzinfo=timezone.utc)

        requests.sort(key=_extract_created_at, reverse=True)
        return requests[:limit]

    @classmethod
    def save_document_insight(cls, insight: DocumentInsightRecord):
        db = cls.get_db()
        db.collection("document_insights").document(insight.docId).set(insight.model_dump(mode="json"))
        if hasattr(db, "save"):
            db.save()

    @classmethod
    def get_document_insight(cls, doc_id: str) -> Optional[DocumentInsightRecord]:
        db = cls.get_db()
        doc = db.collection("document_insights").document(doc_id).get()
        if doc.exists:
            return DocumentInsightRecord(**doc.to_dict())
        return None
