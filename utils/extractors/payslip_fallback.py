import re
from typing import List, Optional

from models.document import DocumentType, ExtractionResult, PayslipSummary
from utils.extractors.base import BaseExtractor
from utils.extractors.payslip_profiles import detect_country_profile, profile_terms


class PayslipFallbackExtractor(BaseExtractor):
    """
    Payslip-specific fallback. Kept isolated from other document types.
    """

    def extract(self, text: str) -> ExtractionResult:
        summary = PayslipSummary()
        reasons: List[str] = []

        normalized_text = re.sub(
            r"(?i)(LIMITED|LTD|PLC|INC|INCORPORATED|COMPANY|CORP)(PAYSLIP)",
            r"\1 \2",
            text,
        )
        profile_detection = detect_country_profile(normalized_text)
        country_key = profile_detection[0] if profile_detection else None
        country_profile = profile_detection[1] if profile_detection else None
        if country_key:
            reasons.append(f"country_profile_detected_{country_key}_fallback")
        upper_text = normalized_text.upper()
        lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]

        amount_pattern = r"([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?|[0-9]{1,3}(?:\.[0-9]{2})?)"
        amount_re = re.compile(amount_pattern)
        ignore_context_tokens = (
            "YTD",
            "YEAR TO DATE",
            "ACCRUED",
            "OPENING BALANCE",
            "CARRIED FORWARD",
            "BROUGHT FORWARD",
        )

        def _is_ignored_context(line_upper: str) -> bool:
            return any(token in line_upper for token in ignore_context_tokens)

        def _amount_after_label_in_line(line: str, label_patterns: List[str]) -> Optional[float]:
            line_upper = line.upper()
            for pat in label_patterns:
                start = line_upper.find(pat)
                if start == -1:
                    continue
                tail = line[start + len(pat) :]
                tail_amounts = amount_re.findall(tail)
                if tail_amounts:
                    return self._parse_amount(tail_amounts[0])
            amounts = amount_re.findall(line)
            if amounts:
                return self._parse_amount(amounts[-1])
            return None

        def _amount_from_line(label_patterns: List[str], fallback_lines: int = 1) -> Optional[float]:
            for idx, line in enumerate(lines):
                line_upper = line.upper()
                if _is_ignored_context(line_upper):
                    continue
                if any(pat in line_upper for pat in label_patterns):
                    amount = _amount_after_label_in_line(line, label_patterns)
                    if amount is not None:
                        return amount
                    for j in range(1, fallback_lines + 1):
                        if idx + j >= len(lines):
                            break
                        next_line = lines[idx + j]
                        if _is_ignored_context(next_line.upper()):
                            continue
                        next_amounts = amount_re.findall(next_line)
                        if next_amounts:
                            return self._parse_amount(next_amounts[0])
            return None

        gross_priority_labels = [
            "GROSS EARNINGS",
            "TOTAL EARNINGS",
            "GROSS PAY",
            "TOTAL GROSS",
            "GROSS AMOUNT",
            "GROSS SALARY",
            "GROSS WAGES",
            "TOTAL PAY",
            "TAXABLE PAY",
            "TOTAL TAXABLE PAY",
            "GROSS EMOLUMENTS",
        ]
        gross_priority_labels.extend(profile_terms(country_profile, "gross_labels"))
        basic_gross_labels = [
            "BASIC PAY",
            "BASIC SALARY",
            "REGULAR PAY",
            "REGULAR EARNINGS",
            "BASE PAY",
            "PAY RATE",
        ]
        net_priority_labels = [
            "NET PAY",
            "NET AMOUNT",
            "NET SALARY",
            "NET INCOME",
            "NET EARNINGS",
            "NET PAID",
            "NET PAYABLE",
            "TOTAL NET",
            "TOTAL PAID",
            "AMOUNT PAYABLE",
            "TOTAL PAYABLE",
            "TAKE HOME",
            "TAKE HOME PAY",
            "IN HAND",
            "PAY TO BANK",
            "PAID TO BANK",
            "SALARY PAYABLE",
            "AMOUNT DUE",
            "PAY THIS PERIOD",
        ]
        net_priority_labels.extend(profile_terms(country_profile, "net_labels"))
        deductions_priority_labels = [
            "GROSS DEDUCTIONS",
            "TOTAL DEDUCTIONS",
            "DEDUCTIONS TOTAL",
            "TOTAL WITHHOLDINGS",
            "WITHHOLDINGS TOTAL",
            "TOTAL STATUTORY DEDUCTIONS",
            "STATUTORY DEDUCTIONS",
            "TOTAL EMPLOYEE DEDUCTIONS",
            "PRE-TAX DEDUCTIONS",
            "POST-TAX DEDUCTIONS",
            "TOTAL TAX",
            "TOTAL TAXES",
        ]
        deductions_priority_labels.extend(profile_terms(country_profile, "deduction_labels"))

        net_synonyms = (
            r"NET\s*PAY|NET\s*AMOUNT|NET\s*SALARY|NET\s*INCOME|NET\s*EARNINGS|NET\s*PAID|NET\s*PAYABLE|NET\s*WAGES?"
            r"|TOTAL\s*NET|TOTAL\s*PAID|AMOUNT\s*PAYABLE|TOTAL\s*PAYABLE"
            r"|TAKE\s*-?\s*HOME(?:\s*PAY)?|IN[-\s]*HAND"
            r"|SALARY\s*PAYABLE|AMOUNT\s*DUE|PAY\s*THIS\s*PERIOD"
            r"|PAY\s*TO\s*BANK|PAID\s*TO\s*BANK"
        )
        gross_synonyms = (
            r"GROSS\s*PAY|GROSS\s*EARNINGS|GROSS\s*AMOUNT|GROSS\s*SALARY|GROSS\s*WAGES?"
            r"|TOTAL\s*GROSS|TOTAL\s*EARNINGS|TOTAL\s*WAGES?"
            r"|BASIC\s*PAY|BASIC\s*SALARY|REGULAR\s*PAY|REGULAR\s*EARNINGS|BASE\s*PAY"
            r"|TOTAL\s*PAY|TAXABLE\s*PAY|TOTAL\s*TAXABLE\s*PAY"
            r"|GROSS\s*EMOLUMENTS?|TOTAL\s*EMOLUMENTS?"
            r"|PAY\s*BEFORE\s*DEDUCTIONS?|PAY\s*BEFORE\s*TAX|PRE\s*-?\s*TAX\s*PAY"
        )
        deductions_synonyms = (
            r"TOTAL\s+DEDUCTIONS?|GROSS\s*DEDUCTIONS?|DEDUCTIONS?\s+TOTAL"
            r"|TOTAL\s+WITHHOLDINGS?|WITHHOLDINGS?\s+TOTAL"
            r"|TOTAL\s+TAX(?:ES)?|TAX\s+DEDUCTED"
            r"|TOTAL\s+EMPLOYEE\s+DEDUCTIONS?|TOTAL\s+STATUTORY\s+DEDUCTIONS?"
            r"|TOTAL\s+BENEFIT\s+DEDUCTIONS?|TOTAL\s+CONTRIBUTIONS?"
            r"|PRE\s*-?\s*TAX\s+DEDUCTIONS?|POST\s*-?\s*TAX\s+DEDUCTIONS?"
        )

        gross_line_amount = _amount_from_line(gross_priority_labels, fallback_lines=1)
        if gross_line_amount is not None:
            summary.gross_pay = gross_line_amount
            reasons.append("gross_pay_match_line_fallback")

        net_line_amount = _amount_from_line(net_priority_labels, fallback_lines=1)
        if net_line_amount is not None:
            summary.net_pay = net_line_amount
            reasons.append("net_pay_match_line_fallback")

        deductions_line_amount = _amount_from_line(deductions_priority_labels, fallback_lines=1)
        if deductions_line_amount is not None:
            summary.deductions = deductions_line_amount
            reasons.append("deductions_match_line_fallback")

        if summary.net_pay is None:
            net_match = re.search(rf"(?:{net_synonyms})[^0-9]*{amount_pattern}", normalized_text, re.IGNORECASE)
            if net_match:
                summary.net_pay = self._parse_amount(net_match.group(1))
                reasons.append("net_pay_match_fallback")

        if summary.gross_pay is None:
            gross_match = re.search(rf"(?:{gross_synonyms})[^0-9]*{amount_pattern}", normalized_text, re.IGNORECASE)
            if gross_match:
                summary.gross_pay = self._parse_amount(gross_match.group(1))
                reasons.append("gross_pay_match_fallback")

        if summary.gross_pay is None:
            basic_line_amount = _amount_from_line(basic_gross_labels, fallback_lines=0)
            if basic_line_amount is not None:
                summary.gross_pay = basic_line_amount
                reasons.append("gross_pay_match_basic_fallback")

        if summary.deductions is None:
            deductions_match = re.search(
                rf"(?:{deductions_synonyms})[^0-9]*{amount_pattern}",
                normalized_text,
                re.IGNORECASE,
            )
            if deductions_match:
                summary.deductions = self._parse_amount(deductions_match.group(1))
                reasons.append("deductions_match_fallback")

        if summary.deductions is None:
            if summary.gross_pay is not None and summary.net_pay is not None:
                inferred = round(summary.gross_pay - summary.net_pay, 2)
                if inferred >= 0:
                    summary.deductions = inferred
                    reasons.append("calculated_deductions_from_gross_net_fallback")
            else:
                token_patterns = [
                    r"\bPAYE\b",
                    r"\bNATIONAL\s*INSURANCE\b",
                    r"\bNI\b",
                    r"\bFICA\b",
                    r"\bSOCIAL\s*SECURITY\b",
                    r"\bMEDICARE\b",
                    r"\bTDS\b",
                    r"\bPF\b",
                    r"\bEPF\b",
                    r"\bESI\b",
                    r"\bESIC\b",
                    r"\bPROVIDENT\s*FUND\b",
                    r"\bPROFESSIONAL\s*TAX\b",
                    r"\bPENSION\b",
                    r"\bSUPERANNUATION\b",
                    r"\bNSSF\b",
                    r"\bNHIF\b",
                    r"\bNHIS\b",
                    r"\bNAPSA\b",
                    r"\bNHIMA\b",
                    r"\bUIF\b",
                    r"\bCPF\b",
                    r"\bNIC\b",
                    r"\bNIS\b",
                    r"\bPAYG\b",
                    r"\bAIDS\s*LEVY\b",
                    r"\bHOUSING\s*LEVY\b",
                    r"\bPAYROLL\s*TAX\b",
                ]
                for profile_token in profile_terms(country_profile, "deduction_tokens"):
                    token = profile_token.strip()
                    if not token:
                        continue
                    token_regex = r"\b" + re.escape(token).replace(r"\ ", r"\s*") + r"\b"
                    if token_regex not in token_patterns:
                        token_patterns.append(token_regex)
                token_amounts = []
                for token in token_patterns:
                    match = re.findall(rf"{token}[^0-9]*{amount_pattern}", normalized_text, re.IGNORECASE)
                    for amt in match:
                        parsed = self._parse_amount(amt)
                        if parsed is not None:
                            token_amounts.append(parsed)
                if token_amounts:
                    summary.deductions = round(sum(token_amounts), 2)
                    reasons.append("deductions_sum_from_tokens_fallback")

        deduction_tokens = [
            "PAYE",
            "TAX",
            "NATIONAL INSURANCE",
            "NI",
            "FICA",
            "SOCIAL SECURITY",
            "MEDICARE",
            "TDS",
            "PF",
            "EPF",
            "ESI",
            "ESIC",
            "PROVIDENT FUND",
            "PROFESSIONAL TAX",
            "PENSION",
            "SUPERANNUATION",
            "NSSF",
            "NHIF",
            "NHIS",
            "NAPSA",
            "NHIMA",
            "UIF",
            "CPF",
            "NIC",
            "NIS",
            "PAYG",
            "AIDS LEVY",
            "HOUSING LEVY",
            "PAYROLL TAX",
        ]
        deduction_tokens.extend(profile_terms(country_profile, "deduction_tokens"))
        if any(token in upper_text for token in deduction_tokens):
            summary.is_tax_deducted = True
            reasons.append("deduction_token_detected_fallback")

        profile_currency_codes = profile_terms(country_profile, "currency_codes")
        for currency_code in profile_currency_codes:
            if currency_code and currency_code in upper_text:
                summary.currency = currency_code
                break
        if summary.currency is None:
            profile_currency_symbols = profile_terms(country_profile, "currency_symbols")
            for symbol in profile_currency_symbols:
                if symbol and symbol in normalized_text:
                    summary.currency = profile_currency_codes[0] if profile_currency_codes else None
                    break
        if summary.currency is None:
            if "ZMW" in upper_text:
                summary.currency = "ZMW"
            elif "KES" in upper_text:
                summary.currency = "KES"
            elif "ZAR" in upper_text:
                summary.currency = "ZAR"
            elif "INR" in upper_text or "\u20B9" in normalized_text:
                summary.currency = "INR"
            elif "GBP" in upper_text or "\u00A3" in normalized_text:
                summary.currency = "GBP"
            elif "USD" in upper_text or "$" in normalized_text:
                summary.currency = "USD"

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
            raw_text_preview=normalized_text[:500],
        )

    def _parse_amount(self, amt_str: str) -> Optional[float]:
        try:
            return float(amt_str.replace(",", ""))
        except Exception:
            return None
