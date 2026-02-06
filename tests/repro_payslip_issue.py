import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.extractors.payslip import PayslipExtractor

def test_payslip_extraction():
    extractor = PayslipExtractor()
    
    # Test 1: No decimals
    text1 = "GROSS PAY 6100\nNET PAY 5564"
    result1 = extractor.extract(text1)
    print(f"Test 1 (No decimals): Gross={result1.payslip_summary.gross_pay}, Net={result1.payslip_summary.net_pay}")
    assert result1.payslip_summary.gross_pay == 6100.0
    assert result1.payslip_summary.net_pay == 5564.0
    
    # Test 2: New line after label
    text2 = "GROSS EARNINGS\n6,100.00\nNET PAYABLE\n5,564.50"
    result2 = extractor.extract(text2)
    print(f"Test 2 (New line): Gross={result2.payslip_summary.gross_pay}, Net={result2.payslip_summary.net_pay}")
    assert result2.payslip_summary.gross_pay == 6100.0
    assert result2.payslip_summary.net_pay == 5564.5
    
    # Test 3: Fallback calculation (Net missing but Gross/Deductions present)
    text3 = "GROSS EARNINGS 6100.00\nGROSS DEDUCTIONS 535.50"
    result3 = extractor.extract(text3)
    print(f"Test 3 (Calculation): Gross={result3.payslip_summary.gross_pay}, Deductions={result3.payslip_summary.deductions}, Net={result3.payslip_summary.net_pay}")
    assert result3.payslip_summary.gross_pay == 6100.0
    assert result3.payslip_summary.deductions == 535.5
    assert result3.payslip_summary.net_pay == 5564.5
    assert "calculated_net_pay" in result3.payslip_summary.confidence_reasons

    # Test 4: New synonym
    text4 = "TOTAL PAYABLE 3000.00"
    result4 = extractor.extract(text4)
    print(f"Test 4 (New synonym): Net={result4.payslip_summary.net_pay}")
    assert result4.payslip_summary.net_pay == 3000.0

    print("\nALL TESTS PASSED! ✓")

if __name__ == "__main__":
    test_payslip_extraction()
