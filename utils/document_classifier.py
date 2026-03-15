from typing import Tuple
from models.document import DocumentType

class DocumentClassifier:
    @staticmethod
    def classify(text: str, filename: str = "") -> Tuple[DocumentType, float]:
        if filename.lower().endswith('.csv'):
             return DocumentType.GENERIC_CSV, 0.9
             
        text_upper = text.upper()
        
        if any(x in text_upper for x in ["PAYSLIP", "SALARY ADVICE", "EARNINGS STATEMENT", "NET PAY", "GROSS PAY"]):
            return DocumentType.PAYSLIP, 0.85

        if any(x in text_upper for x in ["NATIONAL REGISTRATION", "NRC", "REPUBLIC OF ZAMBIA", "ID NUMBER"]):
            return DocumentType.NRC_ID, 0.8

        mobile_money_markers = [
            "MOBILE MONEY",
            "M-PESA",
            "AIRTEL MONEY",
            "BALANCE STATEMENT FOR THE PERIOD",
            "TOTAL MONEY DEBITED",
            "TOTAL MONEY CREDITED",
            "MONEY SENT TO",
            "MONEY DEPOSIT TO",
            "LOAN REPAYMENT TO",
        ]
        mobile_hits = sum(1 for marker in mobile_money_markers if marker in text_upper)
        if mobile_hits >= 2:
            return DocumentType.MOBILE_MONEY, 0.82
            
        if any(x in text_upper for x in ["BANK STATEMENT", "ACCOUNT STATEMENT", "ZANACO", "_BALANCE AT_", "BALANCE BROUGHT FORWARD"]):
            return DocumentType.BANK_STATEMENT, 0.85
            
        return DocumentType.UNKNOWN, 0.0
