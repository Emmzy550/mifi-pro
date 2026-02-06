import re
from typing import Optional
from models.document import ExtractionResult, DocumentType, PayslipSummary
from utils.extractors.base import BaseExtractor


class PayslipFallbackExtractor(BaseExtractor):
    """
    Payslip-specific fallback. Kept isolated from other document types.
    """
    def extract(self, text: str) -> ExtractionResult:
        summary = PayslipSummary()
        reasons = []

        amount_pattern = r'([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?|[0-9]{1,3}(?:\.[0-9]{2})?)'
        net_synonyms = r'NET\s*PAY|NET\s*AMOUNT|TAKE\s*HOME|TOTAL\s*PAID|NET\s*SALARY|NET\s*INCOME|NET\s*PAYABLE|TOTAL\s*NET|NET\s*EARNINGS|NET\s*PAID|AMOUNT\s*PAYABLE|NET\s*TAKE\s*HOME|TOTAL\s*PAYABLE'
        net_match = re.search(
            rf'(?:{net_synonyms})[^0-9]*{amount_pattern}',
            text,
            re.IGNORECASE
        )
        gross_match = re.search(
            rf'(?:GROSS\s*PAY|GROSS\s*EARNINGS|GROSS\s*AMOUNT|GROSS\s*SALARY)[^0-9]*{amount_pattern}',
            text,
            re.IGNORECASE
        )

        if net_match:
            summary.net_pay = self._parse_amount(net_match.group(1))
            reasons.append("net_pay_match_fallback")
        if gross_match:
            summary.gross_pay = self._parse_amount(gross_match.group(1))
            reasons.append("gross_pay_match_fallback")

        summary.document_confidence = 0.35 if (summary.net_pay or summary.gross_pay) else 0.1
        summary.confidence_reasons = reasons

        warnings = []
        if not (summary.net_pay or summary.gross_pay):
            warnings.append("Payslip fallback could not detect net/gross pay.")

        return ExtractionResult(
            document_type=DocumentType.PAYSLIP,
            confidence=summary.document_confidence,
            payslip_summary=summary,
            warnings=warnings,
            raw_text_preview=text[:500]
        )

    def _parse_amount(self, amt_str: str) -> Optional[float]:
        try:
            return float(amt_str.replace(',', ''))
        except Exception:
            return None
