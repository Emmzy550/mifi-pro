import logging
import re
from datetime import datetime
from typing import List, Optional, Tuple

from models.document import (
    BankStatementSummary,
    DocumentType,
    ExtractionResult,
    StatementPeriod,
    SummaryProfile,
    Transaction,
)
from utils.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class MobileMoneyExtractor(BaseExtractor):
    DATE_LINE_PATTERN = re.compile(r'^(?P<date>\d{2}/\d{2}/\d{2})(?:\s+(?P<rest>.*))?$')
    TIME_PATTERN = re.compile(r'\b(?P<time>\d{1,2}:\d{2}\s*(?:AM|PM))\b', re.IGNORECASE)
    REF_PATTERN = re.compile(r'\((?P<ref>[A-Z]{2}\d{6}\.\d{4}\.[A-Z0-9]+)\)', re.IGNORECASE)
    CREDIT_BALANCE_PATTERN = re.compile(r'(?<![\d.])(?P<credit>[\d,]+(?:\.\d+)?)\s*--\s*(?P<balance>[\d,]+(?:\.\d+)?)(?![\d.])')
    DEBIT_BALANCE_PATTERN = re.compile(r'--\s*(?P<debit>[\d,]+(?:\.\d+)?)\s+(?P<balance>[\d,]+(?:\.\d+)?)(?![\d.])')
    PERIOD_PATTERN = re.compile(
        r'(?P<start>\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})\s+to\s+(?P<end>\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})',
        re.IGNORECASE,
    )
    AMOUNT_LINE_PATTERN = re.compile(r'[\d,]+(?:\.\d+)?\s*--\s*[\d,]+(?:\.\d+)?|--\s*[\d,]+(?:\.\d+)?\s+[\d,]+(?:\.\d+)?')

    def extract(self, text: str) -> ExtractionResult:
        normalized_text = self._normalize_text(text)
        lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]

        account_holder = self._extract_account_holder(lines)
        provider = self._detect_provider(normalized_text)
        currency = self._detect_currency(normalized_text)
        statement_period = self._extract_statement_period(normalized_text)
        summary_fields = self._extract_summary_fields(normalized_text)
        transactions = self._extract_transactions(lines, currency)

        if summary_fields["total_money_in"] is None:
            summary_fields["total_money_in"] = round(
                sum(tx.credit or 0.0 for tx in transactions if tx.direction == "INFLOW"), 2
            ) if transactions else None
        if summary_fields["total_money_out"] is None:
            summary_fields["total_money_out"] = round(
                sum(tx.debit or 0.0 for tx in transactions if tx.direction == "OUTFLOW"), 2
            ) if transactions else None
        if summary_fields["opening_balance"] is None and transactions:
            first_tx = transactions[0]
            if first_tx.balance is not None:
                if first_tx.direction == "INFLOW" and first_tx.credit is not None:
                    summary_fields["opening_balance"] = round(first_tx.balance - first_tx.credit, 2)
                elif first_tx.direction == "OUTFLOW" and first_tx.debit is not None:
                    summary_fields["opening_balance"] = round(first_tx.balance + first_tx.debit, 2)
        if summary_fields["closing_balance"] is None and transactions:
            summary_fields["closing_balance"] = transactions[-1].balance

        warnings: List[str] = []
        if not account_holder:
            warnings.append("Could not confidently extract account holder name from mobile money statement.")
        if not statement_period:
            warnings.append("Could not confidently extract statement period from mobile money statement.")
        if not transactions:
            warnings.append("No transactions were extracted from mobile money statement.")

        document_confidence = 0.92 if transactions else 0.25
        if statement_period and account_holder:
            document_confidence = min(0.98, document_confidence + 0.03)

        summary = BankStatementSummary(
            summary_profile=SummaryProfile.BANK_STATEMENT_SUMMARY.value,
            currency=currency,
            bank_name=provider,
            statement_period=statement_period,
            account_holder_name=account_holder,
            opening_balance=summary_fields["opening_balance"],
            closing_balance=summary_fields["closing_balance"],
            total_money_in=summary_fields["total_money_in"],
            total_money_out=summary_fields["total_money_out"],
            deposit_count=sum(1 for tx in transactions if tx.direction == "INFLOW"),
            calculated_total_money_in=round(sum(tx.credit or 0.0 for tx in transactions if tx.direction == "INFLOW"), 2) if transactions else None,
            calculated_total_money_out=round(sum(tx.debit or 0.0 for tx in transactions if tx.direction == "OUTFLOW"), 2) if transactions else None,
            calculated_opening_balance=summary_fields["opening_balance"],
            calculated_closing_balance=summary_fields["closing_balance"],
            salary_detected=any("salary" in (tx.description or "").lower() for tx in transactions),
            salary_deposit_detected=any("salary" in (tx.description or "").lower() for tx in transactions if tx.direction == "INFLOW"),
            salary_frequency=None,
            salary_confidence=0.0,
            document_confidence=document_confidence,
            confidence_reasons=["mobile_money_statement", "summary_fields_detected" if statement_period else "transactions_only"],
            risk_flags=[],
        )

        return ExtractionResult(
            document_type=DocumentType.MOBILE_MONEY,
            confidence=document_confidence,
            transactions=transactions,
            bank_statement_summary=summary,
            warnings=warnings,
            raw_text_preview=normalized_text[:500],
        )

    def _normalize_text(self, text: str) -> str:
        normalized = (
            text.replace("\r", "\n")
            .replace("—", "--")
            .replace("–", "--")
            .replace("−", "-")
        )
        normalized = re.sub(r'[ \t]+', ' ', normalized)
        normalized = re.sub(r'\n{3,}', '\n\n', normalized)
        return normalized

    def _extract_account_holder(self, lines: List[str]) -> Optional[str]:
        for idx, line in enumerate(lines[:5]):
            if not line:
                continue
            lowered = line.lower()
            if any(token in lowered for token in ["balance statement", "summary", "detailed statement", "transaction type"]):
                continue
            if re.search(r'\d{6,}', line):
                continue
            if idx + 1 < len(lines) and "balance statement for the period" in lines[idx + 1].lower():
                return line.title()
            if len(line.split()) >= 2 and len(line) < 80:
                return line.title()
        return None

    def _detect_provider(self, text: str) -> str:
        text_upper = text.upper()
        if "AIRTEL" in text_upper or "*000#" in text_upper:
            return "Airtel Money"
        if "MTN" in text_upper:
            return "MTN Mobile Money"
        if "M-PESA" in text_upper or "MPESA" in text_upper:
            return "M-Pesa"
        return "Mobile Money"

    def _detect_currency(self, text: str) -> str:
        text_upper = text.upper()
        if "ZMW" in text_upper:
            return "ZMW"
        if "KES" in text_upper:
            return "KES"
        if "USD" in text_upper:
            return "USD"
        return "UNKNOWN"

    def _extract_statement_period(self, text: str) -> Optional[StatementPeriod]:
        match = self.PERIOD_PATTERN.search(text)
        if not match:
            return None
        start = self._parse_word_date(match.group("start"))
        end = self._parse_word_date(match.group("end"))
        if not start or not end:
            return None
        return StatementPeriod(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

    def _extract_summary_fields(self, text: str) -> dict:
        return {
            "total_money_out": self._extract_named_amount(text, [r"Total\s+Money\s+Debited", r"Total\s+Money\s+Out"]),
            "total_money_in": self._extract_named_amount(text, [r"Total\s+Money\s+Credited", r"Total\s+Money\s+In"]),
            "opening_balance": self._extract_named_amount(text, [r"Opening\s+Balance"]),
            "closing_balance": self._extract_named_amount(text, [r"Closing\s+Balance"]),
        }

    def _extract_named_amount(self, text: str, labels: List[str]) -> Optional[float]:
        for label in labels:
            match = re.search(rf"{label}\s+([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
            if match:
                return self._parse_amount(match.group(1))
        return None

    def _extract_transactions(self, lines: List[str], currency: str) -> List[Transaction]:
        blocks: List[List[str]] = []
        current_block: List[str] = []

        for line in lines:
            lowered = line.lower()
            if lowered.startswith("need help?") or lowered.startswith("for self-help") or lowered.startswith("terms and condition"):
                break
            if self.DATE_LINE_PATTERN.match(line):
                if current_block:
                    blocks.append(current_block)
                current_block = [line]
            elif current_block:
                current_block.append(line)
        if current_block:
            blocks.append(current_block)

        transactions: List[Transaction] = []
        for index, block in enumerate(blocks):
            parsed = self._parse_transaction_block(block, currency, index)
            if parsed:
                transactions.append(parsed)

        transactions.sort(key=lambda tx: tx.metadata.get("block_index", 0))
        return transactions

    def _parse_transaction_block(self, block: List[str], currency: str, index: int) -> Optional[Transaction]:
        first_line = block[0]
        date_match = self.DATE_LINE_PATTERN.match(first_line)
        if not date_match:
            return None

        date_value = self._parse_numeric_date(date_match.group("date"))
        if not date_value:
            return None

        remainder_parts: List[str] = []
        if date_match.group("rest"):
            remainder_parts.append(date_match.group("rest"))
        remainder_parts.extend(block[1:])
        joined = " ".join(part.strip() for part in remainder_parts if part.strip())
        joined = re.sub(r"\s+", " ", joined).strip()
        if not joined:
            return None

        time_match = self.TIME_PATTERN.search(joined)
        time_value = time_match.group("time").upper() if time_match else None
        if time_match:
            joined = f"{joined[:time_match.start()]} {joined[time_match.end():]}".strip()

        ref_match = self.REF_PATTERN.search(joined)
        reference = ref_match.group("ref") if ref_match else None
        if ref_match:
            joined = f"{joined[:ref_match.start()]} {joined[ref_match.end():]}".strip()

        amount, credit, debit, balance, direction = self._extract_amount_roles(joined)
        if amount is None:
            return None

        description = self._clean_description(joined)
        confidence_reasons = ["mobile_money_block"]
        if reference:
            confidence_reasons.append("reference_detected")
        if time_value:
            confidence_reasons.append("time_detected")

        return Transaction(
            date=date_value.strftime("%Y-%m-%d"),
            description=description or "Mobile money transaction",
            amount=amount,
            credit=credit,
            debit=debit,
            direction=direction,
            balance=balance,
            currency=currency,
            confidence=0.9,
            confidence_score=0.9,
            confidence_reasons=confidence_reasons,
            metadata={
                "statement_source": "mobile_money",
                "reference": reference,
                "time": time_value,
                "block_index": index,
            },
        )

    def _extract_amount_roles(self, text: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], str]:
        debit_match = self.DEBIT_BALANCE_PATTERN.search(text)
        if debit_match:
            debit = self._parse_amount(debit_match.group("debit"))
            balance = self._parse_amount(debit_match.group("balance"))
            if debit is not None:
                return debit, None, debit, balance, "OUTFLOW"

        credit_match = self.CREDIT_BALANCE_PATTERN.search(text)
        if credit_match:
            credit = self._parse_amount(credit_match.group("credit"))
            balance = self._parse_amount(credit_match.group("balance"))
            if credit is not None:
                return credit, credit, None, balance, "INFLOW"

        numeric_tokens = [self._parse_amount(token) for token in re.findall(r'[\d,]+(?:\.\d+)?', text)]
        numeric_tokens = [token for token in numeric_tokens if token is not None]
        if len(numeric_tokens) >= 2:
            amount = numeric_tokens[-2]
            balance = numeric_tokens[-1]
            direction = "INFLOW" if self._looks_like_inflow(text) else "OUTFLOW"
            return amount, amount if direction == "INFLOW" else None, amount if direction == "OUTFLOW" else None, balance, direction
        return None, None, None, None, "OUTFLOW"

    def _clean_description(self, text: str) -> str:
        cleaned = self.TIME_PATTERN.sub(" ", text)
        cleaned = self.REF_PATTERN.sub(" ", cleaned)
        cleaned = self.AMOUNT_LINE_PATTERN.sub(" ", cleaned)
        cleaned = re.sub(r'[\d,]+(?:\.\d+)?', lambda match: " " if "--" in match.group(0) else match.group(0), cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
        return cleaned

    def _looks_like_inflow(self, text: str) -> bool:
        text_upper = text.upper()
        return any(token in text_upper for token in ["DEPOSIT", "CREDIT", "RECEIVED", "CASH IN"])

    def _parse_numeric_date(self, raw: str) -> Optional[datetime]:
        for fmt in ("%d/%m/%y", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return None

    def _parse_word_date(self, raw: str) -> Optional[datetime]:
        cleaned = re.sub(r"\s+", " ", raw.strip())
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return None

    def _parse_amount(self, raw: Optional[str]) -> Optional[float]:
        if raw is None:
            return None
        cleaned = str(raw).replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            logger.debug("Failed to parse amount '%s' from mobile money statement", raw)
            return None
