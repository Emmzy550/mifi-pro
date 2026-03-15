import asyncio
import os
import uuid

from admin_router import list_demo_requests
from api import submit_demo_request
from models.demo_request import DemoRequestCreate
from models.user import User, UserRole
from utils.db import Database, MockFirestore


def test_demo_request_submission_creates_admin_records():
    original_db_file = MockFirestore.DB_FILE
    original_db = Database._db
    temp_dir = os.path.join(os.getcwd(), "artifacts")
    os.makedirs(temp_dir, exist_ok=True)
    temp_db_file = os.path.join(temp_dir, f"test_demo_requests_{uuid.uuid4().hex}.json")
    MockFirestore.DB_FILE = temp_db_file
    Database._db = MockFirestore()

    try:
        super_admin = User(
            id="SUPER-ADMIN-1",
            organization_id="PLATFORM_OWNER",
            email="admin@platform.com",
            password_hash="hash",
            role=UserRole.SUPER_ADMIN,
            full_name="Platform Admin"
        )
        Database.save_user(super_admin)

        payload = DemoRequestCreate(
            intent="demo",
            name="john mwansa",
            institution=" Lusaka Teachers SACCO ",
            phone="0978 123 456",
            institution_type="SACCO",
            volume="50 - 200"
        )

        response = asyncio.run(submit_demo_request(payload))

        assert response["status"] == "received"
        assert response["request_id"].startswith("DRQ-")
        assert response["notified_super_admins"] == 1

        requests = Database.list_demo_requests()
        assert len(requests) == 1
        assert requests[0].name == "John Mwansa"
        assert requests[0].institution == "Lusaka Teachers SACCO"
        assert requests[0].phone == "0978123456"
        assert getattr(requests[0].status, "value", requests[0].status) == "NEW"

        notifications = Database.list_notifications_for_user(
            recipient_user_id=super_admin.id,
            recipient_email=super_admin.email,
            organization_id=super_admin.organization_id
        )
        assert len(notifications) == 1
        assert notifications[0].type == "DEMO_REQUEST_SUBMITTED"
        assert notifications[0].metadata["request_id"] == requests[0].request_id

        listed_requests = asyncio.run(list_demo_requests(limit=100, status=None, current_user=super_admin))
        assert len(listed_requests) == 1
        assert listed_requests[0].request_id == requests[0].request_id
    finally:
        Database._db = original_db
        MockFirestore.DB_FILE = original_db_file
        if os.path.exists(temp_db_file):
            os.remove(temp_db_file)
