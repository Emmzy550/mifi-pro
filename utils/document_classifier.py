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
            
        if any(x in text_upper for x in ["BANK STATEMENT", "ACCOUNT STATEMENT", "ZANACO", "_BALANCE AT_", "BALANCE BROUGHT FORWARD"]):
            return DocumentType.BANK_STATEMENT, 0.85
            
        if any(x in text_upper for x in ["MOBILE MONEY", "M-PESA", "AIRTEL MONEY"]):
            # For now, treat Mobile Money as Bank Statement (transaction list)
            return DocumentType.BANK_STATEMENT, 0.6
            
        return DocumentType.UNKNOWN, 0.0
