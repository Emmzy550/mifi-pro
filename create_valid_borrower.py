
import sys
import os
import uuid

sys.path.append(os.getcwd())

from utils.db import Database
from models.borrower import Borrower, EmploymentType

# Target Org
ORG_ID = "ORG-44141161"

new_borrower = Borrower(
    id=f"BOR-{uuid.uuid4().hex[:8].upper()}",
    organization_id=ORG_ID,
    name="Postman Test User",
    phone="+260970000000",
    email="test@example.com",
    employment_type=EmploymentType.TRADER,
    monthly_income=5000,
    monthly_expenses=2000,
    existing_debt=0,
    loan_amount_requested=1000,
    loan_purpose="Testing"
)

Database.save_borrower(new_borrower)
print(f"\nSUCCESS! Created valid borrower for Org {ORG_ID}")
print(f"USE THIS BORROWER ID IN POSTMAN: {new_borrower.id}")
