
import asyncio
from api import get_loan_by_assessment, AuthUser
from models.user import User

async def test_healing():
    # Mock user (Platform Admin)
    user = User(
        id="API-PLATFORM_OWNER",
        email="admin@platform.com",
        organization_id="PLATFORM_OWNER",
        role="SUPER_ADMIN",
        full_name="Platform Admin",
        password_hash="fake_hash"
    )
    
    print("Testing get_loan_by_assessment for ASMT-CFB52429...")
    loan = await get_loan_by_assessment("ASMT-CFB52429", user)
    
    if loan:
        print(f"SUCCESS: Found/Healed loan: {loan.loan_id}")
        print(f"  Status: {loan.status}")
        print(f"  Amount: {loan.amount}")
    else:
        print("FAILED: Endpoint returned None")

if __name__ == "__main__":
    asyncio.run(test_healing())
