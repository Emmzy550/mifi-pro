import pytest
from datetime import datetime, timedelta, timezone

from agents.audit_agent import AuditAgent
from agents.payment_agent import PaymentAgent
from models.organization import Organization, PaymentStatus as OrgPaymentStatus
from models.payment import Payment, PaymentGateway, PaymentStatus as AppPaymentStatus
from utils.db import Database


def _make_org() -> Organization:
    return Organization(id="ORG-PAYMENT", name="Payment Test Org")


def _make_payment(status: AppPaymentStatus) -> Payment:
    return Payment(
        payment_id="PAY-TEST123",
        org_id="ORG-PAYMENT",
        plan="STARTER",
        amount=299.0,
        currency="ZMW",
        gateway=PaymentGateway.LIPILA,
        status=status,
        phone_number="260971234567",
        transaction_id="LPL-ABC123",
        metadata={"retry_state": "active", "retry_job_active": True},
    )


def test_initiate_payment_blocks_duplicate_active_request(monkeypatch):
    active_payment = _make_payment(AppPaymentStatus.PROMPT_SENT)

    monkeypatch.setattr(PaymentAgent, "list_payments_for_org", lambda org_id: [active_payment])
    monkeypatch.setattr(AuditAgent, "log_event", lambda *args, **kwargs: None)

    with pytest.raises(PaymentAgent.DuplicateActivePaymentError) as exc:
        PaymentAgent.initiate_payment(
            org=_make_org(),
            plan_name="STARTER",
            gateway="LIPILA",
            extra_data={"phone_number": "0971234567"},
        )

    assert exc.value.payment.payment_id == active_payment.payment_id


def test_cancel_payment_marks_request_cancelling_and_invalidates_retries(monkeypatch):
    payment = _make_payment(AppPaymentStatus.PROMPT_SENT)
    org = _make_org()
    org.payment_status = OrgPaymentStatus.PENDING
    org.last_payment_id = payment.payment_id

    saved_payment_statuses = []
    saved_org_statuses = []

    monkeypatch.setattr(Database, "get_organization", lambda org_id: org)
    monkeypatch.setattr(Database, "save_payment", lambda item: saved_payment_statuses.append(item.status.value))
    monkeypatch.setattr(Database, "save_organization", lambda item: saved_org_statuses.append((item.payment_status.value, item.last_payment_id)))
    monkeypatch.setattr(AuditAgent, "log_event", lambda *args, **kwargs: None)

    result = PaymentAgent.cancel_payment(payment, requested_by="officer@mifi.pro")

    assert result["status"] == AppPaymentStatus.CANCELLING.value
    assert payment.status == AppPaymentStatus.CANCELLING
    assert payment.metadata["retry_state"] == "invalidated"
    assert payment.metadata["retry_job_active"] is False
    assert payment.metadata["cancel_requested_by"] == "officer@mifi.pro"
    assert AppPaymentStatus.CANCELLING.value in saved_payment_statuses
    assert AppPaymentStatus.CANCELLED.value not in saved_payment_statuses
    assert saved_org_statuses == []


def test_refresh_payment_status_returns_cancelled_without_hitting_gateway(monkeypatch):
    payment = _make_payment(AppPaymentStatus.CANCELLED)
    gateway_calls = {"count": 0}

    def fail_if_called(*args, **kwargs):
        gateway_calls["count"] += 1
        raise AssertionError("Gateway status check should not run for cancelled payments")

    monkeypatch.setattr(PaymentAgent, "_check_lipila_collection_status", fail_if_called)

    result = PaymentAgent.refresh_payment_status(payment)

    assert result["status"] == AppPaymentStatus.CANCELLED.value
    assert gateway_calls["count"] == 0


def test_refresh_payment_status_keeps_cancelling_until_grace_window_elapses(monkeypatch):
    payment = _make_payment(AppPaymentStatus.CANCELLING)
    payment.metadata.update(
        {
            "cancel_requested_at": datetime.now(timezone.utc).isoformat(),
            "cancel_deadline_at": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat(),
        }
    )
    org = _make_org()
    org.payment_status = OrgPaymentStatus.PENDING
    saved_org_statuses = []

    monkeypatch.setattr(
        PaymentAgent,
        "_check_lipila_collection_status",
        lambda reference_id: {"referenceId": reference_id, "status": "Pending", "message": "Still pending"},
    )
    monkeypatch.setattr(Database, "get_organization", lambda org_id: org)
    monkeypatch.setattr(Database, "save_payment", lambda item: None)
    monkeypatch.setattr(Database, "save_organization", lambda item: saved_org_statuses.append(item.payment_status.value))

    result = PaymentAgent.refresh_payment_status(payment)

    assert result["status"] == AppPaymentStatus.CANCELLING.value
    assert payment.status == AppPaymentStatus.CANCELLING
    assert saved_org_statuses == []


def test_refresh_payment_status_marks_cancelled_after_cancellation_deadline(monkeypatch):
    payment = _make_payment(AppPaymentStatus.CANCELLING)
    payment.metadata.update(
        {
            "cancel_requested_at": (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat(),
            "cancel_deadline_at": (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat(),
        }
    )
    org = _make_org()
    org.payment_status = OrgPaymentStatus.PENDING
    org.last_payment_id = payment.payment_id

    saved_payment_statuses = []
    saved_org_statuses = []

    monkeypatch.setattr(
        PaymentAgent,
        "_check_lipila_collection_status",
        lambda reference_id: {"referenceId": reference_id, "status": "Pending", "message": "Still pending"},
    )
    monkeypatch.setattr(Database, "get_organization", lambda org_id: org)
    monkeypatch.setattr(Database, "save_payment", lambda item: saved_payment_statuses.append(item.status.value))
    monkeypatch.setattr(Database, "save_organization", lambda item: saved_org_statuses.append((item.payment_status.value, item.last_payment_id)))
    monkeypatch.setattr(AuditAgent, "log_event", lambda *args, **kwargs: None)

    result = PaymentAgent.refresh_payment_status(payment)

    assert result["status"] == AppPaymentStatus.CANCELLED.value
    assert payment.status == AppPaymentStatus.CANCELLED
    assert ("UNPAID", None) in saved_org_statuses
    assert AppPaymentStatus.CANCELLED.value in saved_payment_statuses


def test_cancelled_payment_ignores_non_success_webhook(monkeypatch):
    payment = _make_payment(AppPaymentStatus.CANCELLED)
    saved_statuses = []

    monkeypatch.setattr(Database, "get_payment", lambda payment_id: payment if payment_id == payment.payment_id else None)
    monkeypatch.setattr(Database, "get_payment_by_transaction_id", lambda transaction_id: None)
    monkeypatch.setattr(Database, "save_payment", lambda item: saved_statuses.append(item.status.value))
    monkeypatch.setattr(AuditAgent, "log_event", lambda *args, **kwargs: None)

    handled = PaymentAgent.handle_webhook(
        "LIPILA",
        {"referenceId": payment.payment_id, "status": "Pending", "message": "Still queued"},
    )

    assert handled is True
    assert payment.status == AppPaymentStatus.CANCELLED
    assert AppPaymentStatus.CANCELLED.value in saved_statuses


@pytest.mark.parametrize("status", [AppPaymentStatus.FAILED, AppPaymentStatus.EXPIRED])
def test_terminal_payment_ignores_non_success_webhook(monkeypatch, status):
    payment = _make_payment(status)
    saved_statuses = []

    monkeypatch.setattr(Database, "get_payment", lambda payment_id: payment if payment_id == payment.payment_id else None)
    monkeypatch.setattr(Database, "get_payment_by_transaction_id", lambda transaction_id: None)
    monkeypatch.setattr(Database, "save_payment", lambda item: saved_statuses.append(item.status.value))
    monkeypatch.setattr(AuditAgent, "log_event", lambda *args, **kwargs: None)

    handled = PaymentAgent.handle_webhook(
        "LIPILA",
        {"referenceId": payment.payment_id, "status": "Pending", "message": "Still queued"},
    )

    assert handled is True
    assert payment.status == status
    assert status.value in saved_statuses
    assert AppPaymentStatus.PROMPT_SENT.value not in saved_statuses


def test_cancelling_payment_ignores_pending_webhook(monkeypatch):
    payment = _make_payment(AppPaymentStatus.CANCELLING)
    payment.metadata.update(
        {
            "cancel_requested_at": datetime.now(timezone.utc).isoformat(),
            "cancel_deadline_at": (datetime.now(timezone.utc) + timedelta(seconds=45)).isoformat(),
        }
    )
    saved_statuses = []

    monkeypatch.setattr(Database, "get_payment", lambda payment_id: payment if payment_id == payment.payment_id else None)
    monkeypatch.setattr(Database, "get_payment_by_transaction_id", lambda transaction_id: None)
    monkeypatch.setattr(Database, "save_payment", lambda item: saved_statuses.append(item.status.value))
    monkeypatch.setattr(AuditAgent, "log_event", lambda *args, **kwargs: None)

    handled = PaymentAgent.handle_webhook(
        "LIPILA",
        {"referenceId": payment.payment_id, "status": "Pending", "message": "Still queued"},
    )

    assert handled is True
    assert payment.status == AppPaymentStatus.CANCELLING
    assert AppPaymentStatus.CANCELLING.value in saved_statuses


def test_list_payments_for_org_expires_superseded_active_request(monkeypatch):
    older = _make_payment(AppPaymentStatus.PROMPT_SENT)
    older.payment_id = "PAY-OLDER"
    older.timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)

    newer = _make_payment(AppPaymentStatus.PENDING)
    newer.payment_id = "PAY-NEWER"
    newer.timestamp = datetime.now(timezone.utc) - timedelta(minutes=1)

    store = {
        older.payment_id: older,
        newer.payment_id: newer,
    }
    org = _make_org()
    org.payment_status = OrgPaymentStatus.PENDING
    org.last_payment_id = newer.payment_id

    monkeypatch.setattr(Database, "list_payments", lambda org_id: list(store.values()))
    monkeypatch.setattr(Database, "get_payment", lambda payment_id: store.get(payment_id))
    monkeypatch.setattr(Database, "save_payment", lambda item: store.__setitem__(item.payment_id, item))
    monkeypatch.setattr(Database, "get_organization", lambda org_id: org)
    monkeypatch.setattr(Database, "save_organization", lambda item: None)
    monkeypatch.setattr(AuditAgent, "log_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(PaymentAgent, "refresh_payment_status", lambda payment: PaymentAgent._serialize_payment(payment))

    payments = PaymentAgent.list_payments_for_org("ORG-PAYMENT")
    resolved = {payment.payment_id: payment for payment in payments}

    assert resolved["PAY-NEWER"].status == AppPaymentStatus.PENDING
    assert resolved["PAY-OLDER"].status == AppPaymentStatus.EXPIRED
    assert resolved["PAY-OLDER"].metadata["expiration_reason"] == "list_payments_superseded_by_PAY-NEWER"
