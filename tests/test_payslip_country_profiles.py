import pytest

from utils.extractors.payslip import PayslipExtractor


@pytest.mark.parametrize(
    "country_reason_fragment,text,expected_currency",
    [
        (
            "country_profile_detected_zambia",
            "NRC: 1111/22/1 TPIN: 123 NAPSA 300 NHIMA 50 GROSS PAY 5000 NET PAY 4200 ZMW",
            "ZMW",
        ),
        (
            "country_profile_detected_kenya",
            "KRA PIN NO A123 NHIF 300 NSSF 400 SHA 200 GROSS PAY 60000 NET PAY 50000 KES",
            "KES",
        ),
        (
            "country_profile_detected_south_africa",
            "SARS UIF 150 SDL 25 GROSS PAY 40000 NET PAY 32000 ZAR",
            "ZAR",
        ),
        (
            "country_profile_detected_india",
            "PAN ABCD UAN 100 EPF 1800 TDS 2000 GROSS PAY 75000 NET PAY 62000 INR",
            "INR",
        ),
        (
            "country_profile_detected_uk",
            "HMRC NI NUMBER QQ123 TAX CODE 1257L NATIONAL INSURANCE 250 GROSS PAY 3200 NET PAY 2600 GBP",
            "GBP",
        ),
    ],
)
def test_country_profile_detection_and_currency(country_reason_fragment: str, text: str, expected_currency: str):
    result = PayslipExtractor().extract(text)
    summary = result.payslip_summary

    assert summary is not None
    assert summary.currency == expected_currency
    assert any(country_reason_fragment in reason for reason in summary.confidence_reasons)
