from agents.payment_agent import PaymentAgent
from models.payment import PaymentStatus as AppPaymentStatus


def test_normalize_local_zambian_phone_number():
    assert PaymentAgent._normalize_zambian_phone_number("0975532065") == "260975532065"


def test_normalize_rejects_extra_digits_instead_of_truncating():
    try:
        PaymentAgent._normalize_zambian_phone_number("09755320665")
    except ValueError as exc:
        assert "too many digits" in str(exc)
        return
    raise AssertionError("Expected extra-digit phone numbers to be rejected")


def test_failed_feedback_replaces_success_copy():
    feedback = PaymentAgent._build_lipila_client_feedback(
        AppPaymentStatus.FAILED,
        {"gateway_message": "Provider did not deliver the prompt.", "raw": {}},
        "260975532065",
    )

    assert feedback["message"] == "Provider did not deliver the prompt."
    assert "failed or expired" in feedback["instructions"]
    assert feedback["phone_number"] == "260975532065"
