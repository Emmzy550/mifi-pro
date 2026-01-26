import firebase_admin
from firebase_admin import credentials, firestore
import os
from typing import Dict, List, Optional
from datetime import datetime
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
                print(f"WARNING: Failed to load mock DB: {e}")

    def save(self):
        import json
        data = {}
        for col_name, col_obj in self.collections.items():
            data[col_name] = {doc_id: doc.data for doc_id, doc in col_obj.docs.items() if doc.data}
        
        with open(self.DB_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"DEBUG: Mock DB saved to {self.DB_FILE}")

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

from models.sms_log import SMSLog

class Database:
    _db = None

    @classmethod
    def get_db(cls):
        if cls._db is None:
            service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT", "serviceAccountKey.json")
            
            try:
                if os.path.exists(service_account_path):
                    cred = credentials.Certificate(service_account_path)
                    # Check if app is already initialized to avoid ValueError
                    if not len(firebase_admin._apps):
                        firebase_admin.initialize_app(cred)
                    cls._db = firestore.client()
                    print(f"DEBUG: Firestore initialized using {service_account_path}")
                else:
                    # Production / Cloud Functions: Use Application Default Credentials
                    print("DEBUG: Service key not found. Attempting Application Default Credentials (ADC)...")
                    if not len(firebase_admin._apps):
                        firebase_admin.initialize_app()
                    cls._db = firestore.client()
                    print("DEBUG: Firestore initialized using ADC")
            except Exception as e:
                print(f"WARNING: Real Firestore failed, falling back to Mock. Error: {e}")
                cls._db = MockFirestore()
        return cls._db

    @classmethod
    def reload_db(cls):
        """Forces a reload of the database connection or mock data."""
        if cls._db and isinstance(cls._db, MockFirestore):
            print("DEBUG: Reloading MockFirestore from disk...")
            cls._db.load()

    @classmethod
    def save_borrower(cls, borrower: Borrower):
        db = cls.get_db()
        # Encrypt PII before saving
        data = borrower.model_dump()
        data["phone"] = EncryptionAgent.encrypt(borrower.phone)
        db.collection("borrowers").document(borrower.id).set(data)

    @classmethod
    def get_borrower(cls, borrower_id: str) -> Optional[Borrower]:
        db = cls.get_db()
        doc = db.collection("borrowers").document(borrower_id).get()
        if doc.exists:
            data = doc.to_dict()
            # Decrypt PII after retrieval
            data["phone"] = EncryptionAgent.decrypt(data.get("phone", ""))
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
            results.append(Borrower(**data))
        return results

    @classmethod
    def save_assessment(cls, assessment: Assessment):
        db = cls.get_db()
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
                print(f"Skipping malformed assessment {doc.id}: {e}")
        return cls._sort_assessments_by_time(results)

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

    @classmethod
    def save_loan(cls, loan: Loan):
        db = cls.get_db()
        db.collection("loans").document(loan.loan_id).set(loan.model_dump(mode='json'))

    @classmethod
    def get_assessments_by_org(cls, organization_id: str, limit: int = 50) -> List[Assessment]:
        """Fetches the most recent assessments for a specific organization."""
        db = cls.get_db()
        # Note: In real Firestore, you'd need a composite index on organization_id + timestamp
        
        # Query: where org_id == X, ordered by timestamp (if we had one, or rely on client-side sort for V1)
        query = db.collection("assessments").where("organization_id", "==", organization_id)
        
        # Since Mock/Real might act differently on orderBy without index, we'll fetch then sort/slice for now
        docs = query.stream()
        results = []
        for doc in docs:
            try:
                # Basic validation
                results.append(Assessment(**doc.to_dict()))
            except Exception as e:
                print(f"Skipping malformed assessment {doc.id}: {e}")
                
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

    # ============================================================================
    # B2B DASHBOARD METHODS
    # ============================================================================

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
    def list_all_users(cls) -> List[User]:
        db = cls.get_db()
        docs = db.collection("users").stream()
        return [User(**doc.to_dict()) for doc in docs]

    @classmethod
    def save_api_key(cls, api_key: APIKey):
        db = cls.get_db()
        # Store by hash to allow lookup by hash
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
        # In real Firestore this needs an index
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
        # db.stream() returns generator, convert to list
        results = [doc for doc in docs]
        if results:
            return User(**results[0].to_dict())
        return None
    
    # ============================================================================
    # BILLING METHODS
    # ============================================================================
    
    @classmethod
    def save_usage_log(cls, usage_log: UsageLog):
        """Save a billable usage log entry."""
        db = cls.get_db()
        db.collection("usage_logs").document(usage_log.log_id).set(usage_log.model_dump(mode='json'))
    
    @classmethod
    def get_usage_logs(cls, org_id: str, limit: int = 100, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[UsageLog]:
        """
        Get usage logs for an organization.
        
        Args:
            org_id: Organization ID
            limit: Maximum number of logs to return
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of UsageLog records
        """
        db = cls.get_db()
        query = db.collection("usage_logs").where("org_id", "==", org_id)
        
        # Note: Date filtering would require composite indexes in real Firestore
        # For now, we fetch and filter client-side
        docs = query.stream()
        results = []
        
        for doc in docs:
            try:
                log = UsageLog(**doc.to_dict())
                
                # Apply date filters if provided
                if start_date and log.timestamp < start_date:
                    continue
                if end_date and log.timestamp > end_date:
                    continue
                    
                results.append(log)
            except Exception as e:
                print(f"Skipping malformed usage log {doc.id}: {e}")
        
        # Sort by timestamp descending (most recent first)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        
        return results[:limit]
    @classmethod
    def save_usage_record(cls, record: UsageRecord):
        """Save an environment-specific usage record."""
        db = cls.get_db()
        # Convert environment enum to string for consistent storage
        doc_id = f"{record.organization_id}_{str(record.environment.value if hasattr(record.environment, 'value') else record.environment)}"
        data = record.model_dump(mode='json')
        # Ensure environment is stored as string
        if 'environment' in data:
            data['environment'] = str(data['environment'])
        db.collection("usage_records").document(doc_id).set(data)

    @classmethod
    def get_usage_record(cls, org_id: str, environment: OrgEnvironment) -> UsageRecord:
        """Get or create an environment-specific usage record."""
        db = cls.get_db()
        # Convert environment enum to string for consistent lookup
        env_str = str(environment.value if hasattr(environment, 'value') else environment)
        doc_id = f"{org_id}_{env_str}"
        doc = db.collection("usage_records").document(doc_id).get()
        if doc.exists:
            return UsageRecord(**doc.to_dict())
        
        # Create default if non-existent
        record = UsageRecord(organization_id=org_id, environment=environment)
        cls.save_usage_record(record)
        return record

    @classmethod
    def list_usage_records(cls, org_id: str) -> List[UsageRecord]:
        """List all usage records for an organization."""
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
        if doc.exists:
            return Payment(**doc.to_dict())
        return None

    @classmethod
    def get_payment_by_transaction_id(cls, transaction_id: str) -> Optional[Payment]:
        db = cls.get_db()
        query = db.collection("payments").where("transaction_id", "==", transaction_id)
        docs = query.stream()
        results = [doc for doc in docs]
        if results:
            return Payment(**results[0].to_dict())
        return None

    @classmethod
    def list_payments(cls, org_id: str) -> List[Payment]:
        db = cls.get_db()
        docs = db.collection("payments").where("org_id", "==", org_id).stream()
        return [Payment(**doc.to_dict()) for doc in docs]

    # ============================================================================
    # DECISION EXPORTS
    # ============================================================================

    @classmethod
    def save_decision_export(cls, export: DecisionExport):
        db = cls.get_db()
        db.collection("decision_exports").document(export.id).set(export.model_dump(mode='json'))

    @classmethod
    def get_decision_export(cls, export_id: str) -> Optional[DecisionExport]:
        db = cls.get_db()
        doc = db.collection("decision_exports").document(export_id).get()
        if doc.exists:
            return DecisionExport(**doc.to_dict())
        return None

    @classmethod
    def list_decision_exports(cls, decision_id: str) -> List[DecisionExport]:
        db = cls.get_db()
        docs = db.collection("decision_exports").where("decision_id", "==", decision_id).stream()
        return [DecisionExport(**doc.to_dict()) for doc in docs]

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
                if hasattr(doc, "reference"):
                    doc.reference.delete()
                else:
                    db.collection("decision_counterfactuals").document(doc.id).delete()
            except Exception:
                pass
    @classmethod
    def save_officer_action(cls, action: OfficerAction):
        db = cls.get_db()
        db.collection("officer_actions").document(action.assessment_id).set(action.model_dump(mode='json'))
        if hasattr(db, 'save'): db.save()

    @classmethod
    def get_officer_action(cls, assessment_id: str) -> Optional[OfficerAction]:
        db = cls.get_db()
        doc = db.collection("officer_actions").document(assessment_id).get()
        if doc.exists:
            return OfficerAction(**doc.to_dict())
        return None

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
