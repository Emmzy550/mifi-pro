from typing import Dict, List, Optional

from models.document import DocumentType
from models.document import ExtractionResult


class DocumentReadinessEvaluator:
    """
    Determines whether required documents are present for a full assessment.
    """

    REQUIRED = [
        DocumentType.PAYSLIP,
        DocumentType.BANK_STATEMENT,
    ]

    @staticmethod
    def evaluate(results: List[ExtractionResult], transactions: Optional[List[object]] = None) -> Dict[str, object]:
        present = set()
        bank_complete = False
        payslip_complete = False
        for result in results:
            if result.document_type == DocumentType.NRC_ID and result.nrc_summary:
                present.add(DocumentType.NRC_ID)
            if result.document_type == DocumentType.PAYSLIP and result.payslip_summary:
                present.add(DocumentType.PAYSLIP)
                payslip_complete = bool(result.payslip_summary.net_pay or result.payslip_summary.gross_pay)
            if result.document_type == DocumentType.BANK_STATEMENT and result.bank_statement_summary:
                present.add(DocumentType.BANK_STATEMENT)
                bank_complete = True

        if transactions is not None:
            bank_complete = bank_complete and len(transactions) > 0

        missing: List[str] = []
        for doc in DocumentReadinessEvaluator.REQUIRED:
            if doc not in present:
                missing.append(doc.value.lower())
            elif doc == DocumentType.PAYSLIP and not payslip_complete:
                missing.append(doc.value.lower())
            elif doc == DocumentType.BANK_STATEMENT and not bank_complete:
                missing.append(doc.value.lower())
        readiness = len(missing) == 0
        if readiness:
            reason = "All required documents provided."
        else:
            if DocumentType.BANK_STATEMENT.value.lower() in missing and DocumentType.BANK_STATEMENT in present:
                reason = "Bank statement uploaded but transaction history could not be verified. Please upload a clearer statement."
            elif DocumentType.PAYSLIP.value.lower() in missing and DocumentType.PAYSLIP in present:
                reason = "Payslip uploaded but income details could not be verified. Please upload a clearer payslip."
            else:
                reason = "Additional documents are required to complete assessment."
        return {
            "readiness": readiness,
            "missing_documents": missing,
            "reason": reason
        }
