import re
from datetime import datetime
from typing import Optional
from models.document import ExtractionResult, DocumentType, BankStatementSummary, StatementPeriod
from utils.extractors.base import BaseExtractor


class BankStatementFallbackExtractor(BaseExtractor):
    """
    Bank statement-specific fallback. Kept isolated from other document types.
    """
    def extract(self, text: str) -> ExtractionResult:
        summary = BankStatementSummary()
        reasons = []

        closing_match = re.search(r'(?:CLOSING\s+BALANCE|BALANCE\s+CARRIED\s+FORWARD)\s*[:\-]?\s*([0-9,]+\.[0-9]{2})', text, re.IGNORECASE)
        if closing_match:
            summary.closing_balance = self._parse_amount(closing_match.group(1))
            reasons.append("closing_balance_fallback")

        period = self._extract_statement_period(text)
        if period:
            summary.statement_period = period
            reasons.append("statement_period_fallback")

        summary.document_confidence = 0.4 if summary.closing_balance and summary.statement_period else 0.15
        summary.confidence_reasons = reasons

        warnings = []
        if not (summary.closing_balance and summary.statement_period):
            warnings.append("Bank statement fallback missing closing balance or statement period.")

        return ExtractionResult(
            document_type=DocumentType.BANK_STATEMENT,
            confidence=summary.document_confidence,
            bank_statement_summary=summary,
            warnings=warnings,
            raw_text_preview=text[:500]
        )

    def _extract_statement_period(self, text: str) -> Optional[StatementPeriod]:
        from_to_ptrn = re.compile(
            r'FROM:\s*([A-Za-z]{3,}\s+\d{1,2},?\s+\d{4})\s+TO:\s*([A-Za-z]{3,}\s+\d{1,2},?\s+\d{4})',
            re.IGNORECASE
        )
        m_from_to = from_to_ptrn.search(text)
        if m_from_to:
            start_raw, end_raw = m_from_to.groups()
            start_dt = self._parse_date(start_raw)
            end_dt = self._parse_date(end_raw)
            if start_dt and end_dt:
                return StatementPeriod(
                    start=start_dt.strftime("%Y-%m-%d"),
                    end=end_dt.strftime("%Y-%m-%d")
                )
        return None

    def _parse_date(self, raw: str) -> Optional[datetime]:
        for fmt in ("%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
        return None

    def _parse_amount(self, amt_str: str) -> Optional[float]:
        try:
            return float(amt_str.replace(',', ''))
        except Exception:
            return None
