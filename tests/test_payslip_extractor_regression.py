from utils.extractors.payslip import PayslipExtractor


def test_realistic_payslip_line_joins_extracts_correct_values():
    text = """
CENTRAL GLOBAL UPLINK LIMITEDPAYSLIP: DECEMBER 2025
EMP NO: PZ0026
NAME: BWANGA EMMANUEL
PAY RATE: 3,050.00 (ZMW@1.00)
P004 - Lunch Allowance 762.50  D000 - Income Tax/paye 200.00
S001 - Napsa 305.00
S002 - Nhima 30.50
GROSS EARNINGS 6,100.00   GROSS DEDUCTIONS 535.50
NET PAY 5,564.50
"""
    result = PayslipExtractor().extract(text)
    summary = result.payslip_summary

    assert summary is not None
    assert summary.gross_pay == 6100.0
    assert summary.deductions == 535.5
    assert summary.net_pay == 5564.5
    assert summary.employee_name == "Bwanga Emmanuel"
    assert summary.employer_name == "CENTRAL GLOBAL UPLINK LIMITED"
