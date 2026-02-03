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
        normalized_text = self._normalize_text(text)
        amount_pattern = r'([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)'
        net_labels = [
            r'NET\s*PAY',
            r'NET\s*SALARY',
            r'NET\s*AMOUNT',
            r'TAKE\s*HOME',
            r'TAKEHOME',
            r'NET\s*EARNINGS',
            r'NET\s*INCOME',
        ]
        gross_labels = [
            r'GROSS\s*PAY',
            r'GROSS\s*SALARY',
            r'GROSS\s*AMOUNT',
            r'GROSS\s*EARNINGS',
            r'TOTAL\s*EARNINGS',
            r'TOTAL\s*PAY',
        ]

        net_match = self._search_labeled_amount(net_labels, amount_pattern, text, normalized_text)
        gross_match = self._search_labeled_amount(gross_labels, amount_pattern, text, normalized_text)

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

    def _normalize_text(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

    def _search_labeled_amount(
        self,
        labels,
        amount_pattern: str,
        raw_text: str,
        normalized_text: str
    ) -> Optional[re.Match]:
        for label in labels:
            match = re.search(
                rf'{label}[^0-9]*{amount_pattern}',
                raw_text,
                re.IGNORECASE
            )
            if match:
                return match
            match = re.search(
                rf'{label}.{{0,40}}{amount_pattern}',
                normalized_text,
                re.IGNORECASE
            )
            if match:
                return match
        return None
