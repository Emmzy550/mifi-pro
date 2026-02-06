import re
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple, Any
from models.document import (
    ExtractionResult,
    DocumentType,
    Transaction,
    BankStatementSummary,
    NumericRole,
    NumericToken,
    StatementPeriod,
)

logger = logging.getLogger(__name__)
from utils.extractors.base import BaseExtractor

class BankStatementExtractor(BaseExtractor):
    def __init__(self):
        self.statement_year = datetime.now().year
        self.statement_month = datetime.now().month
        self.currency = "UNKNOWN"
        
        # Patterns
        self.month_map = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                          "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12,
                          "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
                          "July":7,"August":8,"September":9,"October":10,"November":11,"December":12}
        
        # Bi-directional word dates: '1 Feb' or 'Feb 1'
        self.date_word_ptrn = re.compile(r'(?:(\d{1,2})\s*([A-Za-z]{3,})|([A-Za-z]{3,})\s*(\d{1,2}))(?:,?\s*(\d{4}))?', re.IGNORECASE)
        self.date_num_ptrn = re.compile(r'(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2,4}))?')
        self.date_iso_ptrn = re.compile(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})')
        self.amount_token_ptrn = re.compile(r'(?<!\w)(?:[£$€]|ZMW|GBP|USD|EUR|[DC])?\s*[-+]?(?:\d[\d,\.]*\d|\d|\.\d{1,2})\b')
        self.time_ptrn = re.compile(r'\b\d{1,2}:\d{2}\b')
        
        self.keywords_in = ["DEPOSIT", "CREDIT", "SALARY", "RCV", "EARNINGS", "CREDITED", "DIRECT DEPOSIT", "INCOMING FUNDS TRANSFER"]
        self.keywords_out = ["WITHDRAWAL", "PAYMENT", "DEBIT", "SENT", "CHECK", "PAID", "CARD PAYMENT", "DIRECT DEBIT", "POS SALE", "ACCOUNT MAINTENANCE", "COMMISSION"]
        self.summary_keywords = [
            "BALANCE AT",
            "TOTAL MONEY IN",
            "TOTAL MONEY OUT",
            "TOTAL CREDITS",
            "TOTAL DEBITS",
            "TOTAL CREDIT",
            "TOTAL DEBIT",
            "STATEMENT SUMMARY",
            "OPENING BALANCE",
            "CLOSING BALANCE",
            "BALANCE BROUGHT FORWARD",
            "BALANCE CARRIED FORWARD",
            "TOTAL DEBIT ENTRIES",
            "TOTAL CREDIT ENTRIES",
            "TOTAL ENTRIES",
            "CURRENT BOOK BALANCE",
            "BOOK BALANCE",
            "CURRENT AVAILABLE BALANCE",
            "ENDING BALANCE",
            "FINAL BALANCE",
            "BALANCE AS AT",
            "TOTAL BALANCE",
            "ACCOUNT BALANCE",
            "AVAILABLE BALANCE",
            "LEDGER BALANCE",
            "OUTSTANDING BALANCE",
        ]
        self.non_financial_keywords = [
            "ACCOUNT NUMBER",
            "ACCOUNT NO",
            "SORT CODE",
            "PAGE",
            "STATEMENT",
            "CUSTOMER",
            "BRANCH CODE",
            "BRANCH NAME",
            "ACCOUNT CLASS",
            "CLASS DESCRIPTION",
            "HOME BRANCH",
            "CURRENT BOOK BALANCE",
            "UNCLEARED BALANCE",
            "ACCRUED DEBIT INTEREST",
            "ACCRUED CREDIT INTEREST",
            "DATE LAST DEBIT",
            "DATE LAST CREDIT",
            "BLOCKED AMOUNT",
            "MIN REQUIRED BALANCE",
            "TRANSACTION DETAILS",
        ]
        self.time_keywords = ["TIMED", "POSTED", "AT", "TIME"]

    def extract(self, text: str) -> ExtractionResult:
        # 1. Normalize
        text = self._normalize_ocr(text)
        lines = text.split('\n')
        self.statement_year = self._infer_statement_year(text)
        self.currency, currency_warnings = self._infer_currency(text)
        statement_period = self._extract_statement_period(text)
        if statement_period and statement_period.end:
            try:
                self.statement_month = int(statement_period.end.split("-")[1])
                self.statement_year = int(statement_period.end.split("-")[0])
            except: pass
        column_order = self._detect_column_headers(lines)
        
        
        # Extract identity fields with validation
        logger.info(f"\n{'='*80}\nDEBUG: OCR TEXT PREVIEW (first 1500 chars):\n{'-'*80}\n{text[:1500]}\n{'='*80}\n")
        account_holder_name = self._extract_account_holder_name(text)
        bank_name = self._extract_bank_name(lines)
        
        # Track extraction warnings
        extraction_warnings = currency_warnings.copy()
        if account_holder_name is None:
            extraction_warnings.append("ACCOUNT_HOLDER_EXTRACTION_FAILED: Unable to extract account holder name from document")
        
        summary_fields = {
            "opening_balance": None,
            "closing_balance": None,
            "total_money_in": None,
            "total_money_out": None,
            "deposit_count": None,
        }
        numeric_tokens: List[NumericToken] = []
        
        # 2. Extract
        txs = self._extract_transactions_core(
            lines,
            numeric_tokens=numeric_tokens,
            summary_fields=summary_fields,
            column_order=column_order,
            statement_period=statement_period,
        )
        
        if not statement_period and txs:
            statement_period = self._infer_period_from_transactions(txs)

        # 3. Summarize
        if statement_period:
            try:
                # Use end date to anchor the year rollover logic
                end_dt = datetime.strptime(statement_period.end, "%Y-%m-%d")
                self.statement_year = end_dt.year
                self.statement_month = end_dt.month
            except: pass

        summary = self._generate_summary(
            txs,
            summary_fields,
            statement_period,
            account_holder_name,
            bank_name
        )
        
        # SAFETY CHECK: Verify identity fields were preserved in summary
        if account_holder_name is not None and summary.account_holder_name is None:
            logger.error(f"⚠️  CRITICAL: account_holder_name was '{account_holder_name}' but became None in summary!")
        if bank_name is not None and summary.bank_name is None:
            logger.error(f"⚠️  CRITICAL: bank_name was '{bank_name}' but became None in summary!")
        
        logger.info(f"✓ SUMMARY CREATED: account_holder='{summary.account_holder_name}', bank='{summary.bank_name}'")
        return ExtractionResult(
            document_type=DocumentType.BANK_STATEMENT,
            confidence=0.9 if txs else 0.1,
            transactions=txs,
            bank_statement_summary=summary,
            numeric_tokens=numeric_tokens,
            warnings=extraction_warnings,  # Updated to include account holder warnings
            raw_text_preview=text[:500]
        )

    def _normalize_ocr(self, text: str) -> str:
        # 1. Merge split words like 'Ba nk'
        text = re.sub(r'([A-Z])\s+([a-z]{2,})', r'\1\2', text)
        # 2. Separate stuck numbers and months like '040Nov'
        text = re.sub(r'(\d)([A-Z][a-z]{2,})', r'\1 \2', text)
        # 3. Separate stuck years and months like '2025Nov'
        text = re.sub(r'(\d{4})([A-Z][a-z]{2,})', r'\1 \2', text)
        # 4. Separate stuck D/C from amounts like 'D300.00'
        text = re.sub(r'\b([DC])(\d)', r'\1 \2', text)
        return text

    def _infer_statement_year(self, text: str) -> int:
        # Priority 1: Statement Date: YYYY
        m = re.search(r'Statement Date:.*?(\d{4})', text, re.IGNORECASE)
        if m: return int(m.group(1))
        
        # Priority 2: Book Balance As At: Month DD, YYYY
        m = re.search(r'Balance As At:\s*[A-Za-z]{3,}\s+\d{1,2},?\s+(\d{4})', text, re.IGNORECASE)
        if m: return int(m.group(1))
        
        # Priority 3: Any date line at the end of the header
        m = re.search(r'To:\s*[A-Za-z]{3,}\s+\d{1,2},?\s+(\d{4})', text, re.IGNORECASE)
        if m: return int(m.group(1))

        return datetime.now().year

    def _infer_currency(self, text: str) -> Tuple[str, List[str]]:
        warnings = []
        detected = []
        if "£" in text or "GBP" in text: detected.append("GBP")
        if "$" in text or "USD" in text: detected.append("USD")
        if "€" in text or "EUR" in text: detected.append("EUR")
        if "ZMW" in text: detected.append("ZMW")
        if not detected:
            warnings.append("No currency detected; currency locked to UNKNOWN.")
            return "UNKNOWN", warnings
        if len(set(detected)) > 1:
            warnings.append(f"Mixed currencies detected: {sorted(set(detected))}. Using first and rejecting mismatches.")
        return detected[0], warnings

    def _extract_statement_period(self, text: str) -> Optional[StatementPeriod]:
        # 0. "Statement Period" label with value on next line (common in column layouts)
        lines = [l.strip() for l in text.splitlines()]
        for idx, line in enumerate(lines[:-1]):
            if re.fullmatch(r'STATEMENT\s+PERIOD', line, re.IGNORECASE):
                next_line = lines[idx + 1].strip()
                if next_line:
                    period_ptrn = re.compile(
                        r'(\d{1,2}\s+[A-Za-z]{3,}\s*,?\s*\d{4}|\d{1,2}\s+[A-Za-z]{3,})\s*(?:to|\-|–|â€“)\s*(\d{1,2}\s+[A-Za-z]{3,}\s*,?\s*\d{4}|\d{1,2}\s+[A-Za-z]{3,})',
                        re.IGNORECASE
                    )
                    m_label = period_ptrn.search(next_line)
                    if m_label:
                        start_raw, end_raw = m_label.groups()
                        end_dt = self._parse_date(end_raw)
                        start_dt = self._parse_date(start_raw)
                        if end_dt and start_dt:
                            start_year_match = re.search(r'\b(\d{4})\b', start_raw)
                            if not start_year_match:
                                start_dt = start_dt.replace(year=end_dt.year)
                            return StatementPeriod(start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"))

        # 1. Standard From: ... To: ...
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
                return StatementPeriod(start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"))

        # 2. Separate lines (Zanaco style)
        from_match = re.search(r'^From:\s*([A-Za-z]{3,}\s+\d{1,2},?\s+\d{4})', text, re.IGNORECASE | re.MULTILINE)
        to_match = re.search(r'To:\s*([A-Za-z]{3,}\s+\d{1,2},?\s+\d{4})', text, re.IGNORECASE)
        if from_match and to_match:
            start_dt = self._parse_date(from_match.group(1))
            end_dt = self._parse_date(to_match.group(1))
            if start_dt and end_dt:
                return StatementPeriod(start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"))

        # 3. Flexible "to/ -" patterns
        period_ptrn = re.compile(
            r'(\d{1,2}\s+[A-Za-z]{3,}\s*,?\s*\d{4}|\d{1,2}\s+[A-Za-z]{3,})\s*(?:to|\-)\s*(\d{1,2}\s+[A-Za-z]{3,}\s*,?\s*\d{4}|\d{1,2}\s+[A-Za-z]{3,})',
            re.IGNORECASE
        )
        m = period_ptrn.search(text)
        if not m:
            numeric_ptrn = re.compile(
                r'(?:STATEMENT\s+PERIOD|PERIOD|FROM)?\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|\-|–)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                re.IGNORECASE
            )
            m = numeric_ptrn.search(text)
            
        if m:
            start_raw, end_raw = m.groups()
            end_dt = self._parse_date(end_raw)
            start_dt = self._parse_date(start_raw)
            if end_dt and start_dt:
                start_year_match = re.search(r'\b(\d{4})\b', start_raw)
                if not start_year_match:
                    start_dt = start_dt.replace(year=end_dt.year)
                return StatementPeriod(start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"))

        return None

    def _infer_period_from_transactions(self, txs: List[Transaction]) -> Optional[StatementPeriod]:
        dates = []
        for t in txs:
            try:
                dates.append(datetime.strptime(t.date, "%Y-%m-%d"))
            except Exception:
                continue
        if not dates:
            return None
        dates.sort()
        return StatementPeriod(
            start=dates[0].strftime("%Y-%m-%d"),
            end=dates[-1].strftime("%Y-%m-%d")
        )

    def _extract_account_holder_name(self, text: str) -> Optional[str]:
        """
        Extract account holder name with strict validation and exclusions.
        
        REQUIREMENTS:
        1. Hard exclusions for branch-related terms
        2. Priority ordering: Account Name > Account Holder > Customer Name
        3. Context validation: 2+ tokens, 5+ chars, alphabetic
        4. Debug logging for all candidates
        5. Return None if no valid candidate found
        """
        # HARD EXCLUSIONS - Never extract these as names
        BRANCH_EXCLUSIONS = [
            'BRANCH', 'HOME BRANCH', 'BRANCH NAME', 'BRANCH CODE',
            'SORT CODE', 'SWIFT CODE', 'IFSC', 'ROUTING',
            'ACCOUNT NUMBER', 'ACCOUNT NO', 'A/C NO',
            'STATEMENT', 'BALANCE', 'CURRENCY', 'DATE'
        ]
        
        def is_valid_name_candidate(candidate: str) -> tuple[bool, str]:
            """
            Validate if a candidate string is a legitimate person name.
            Returns: (is_valid, reason)
            """
            if not candidate:
                return False, "empty string"
            
            # Check for branch-related exclusions
            candidate_upper = candidate.upper()
            for exclusion in BRANCH_EXCLUSIONS:
                if exclusion in candidate_upper:
                    return False, f"contains excluded term '{exclusion}'"
            
            # Must contain alphabetic characters
            if not re.search(r'[A-Za-z]', candidate):
                return False, "no alphabetic characters"
            
            # Must be at least 5 characters
            if len(candidate.strip()) < 5:
                return False, f"too short ({len(candidate)} chars)"
            
            # Must contain at least 2 tokens (first + last name)
            tokens = candidate.strip().split()
            if len(tokens) < 2:
                return False, f"only {len(tokens)} token(s), need 2+"
            
            # Should not be mostly numeric
            if sum(c.isdigit() for c in candidate) > len(candidate) / 2:
                return False, "mostly numeric"
            
            return True, "valid"
        
        candidates = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        
        # PRIORITY 1: Check for "Account Name:" patterns (both multiline and inline)
        logger.debug("DEBUG: Checking for 'Account Name:' pattern...")
        
        # Check multiline format first - handle columnar layouts
        for idx, line in enumerate(lines[:-1]):
            # Check if line contains "Account Name:" or is a standalone label
            if re.search(r'Account\s+Name\s*:', line, re.IGNORECASE) or re.fullmatch(r'Account\s+Name', line, re.IGNORECASE):
                # First, check if the value is on the SAME line (columnar format)
                # Pattern: "Account Name:     EMMANUEL BWANGA" or "Account Name: EMMANUEL BWANGA"
                same_line_match = re.search(r'Account\s+Name\s*:\s+([A-Za-z][A-Za-z \t\'\-\.]{4,})$', line, re.IGNORECASE)
                if same_line_match:
                    candidate = same_line_match.group(1).strip()
                    is_valid, reason = is_valid_name_candidate(candidate)
                    logger.debug(f"DEBUG: Found 'Account Name:' (same line) -> '{candidate}' | Valid: {is_valid} | Reason: {reason}")
                    if is_valid:
                        candidates.append(('PRIORITY_1_ACCOUNT_NAME', candidate, 1))
                        break
                    else:
                        logger.warning(f"WARNING: Account Name on same line but candidate '{candidate}' was rejected: {reason}")
                
                # If not on same line, scan ahead for the actual name (skip labels and numbers)
                # The OCR might have: Account Name: \n Home Branch: \n 7480701200229 \n EMMANUEL BWANGA
                if idx + 1 < len(lines):
                    # Look ahead up to 5 lines to find the actual name
                    for offset in range(1, min(6, len(lines) - idx)):
                        next_line = lines[idx + offset].strip()
                        
                        # Skip lines that are just labels (end with colon)
                        if re.match(r'^[A-Za-z\s]+:\s*$', next_line):
                            logger.debug(f"DEBUG: Skipping label line at offset {offset}: '{next_line}'")
                            continue
                        
                        # Skip numeric-only lines (account numbers, branch codes)
                        if re.match(r'^\d+$', next_line):
                            logger.debug(f"DEBUG: Skipping numeric line at offset {offset}: '{next_line}'")
                            continue
                        
                        # Skip very short lines (less than 5 chars)
                        if len(next_line) < 5:
                            logger.debug(f"DEBUG: Skipping short line at offset {offset}: '{next_line}'")
                            continue
                        
                        # Check if this looks like a person name
                        is_valid, reason = is_valid_name_candidate(next_line)
                        logger.debug(f"DEBUG: Found 'Account Name:' (offset {offset}) -> '{next_line}' | Valid: {is_valid} | Reason: {reason}")
                        if is_valid:
                            candidates.append(('PRIORITY_1_ACCOUNT_NAME', next_line, 1))
                            break
                        else:
                            logger.debug(f"DEBUG: Candidate '{next_line}' rejected: {reason}")
                    
                    # If we found a candidate, break out of the main loop
                    if candidates:
                        break


        
        # Check inline format if multiline not found
        if not candidates:
            account_name_patterns = [
                r'ACCOUNT\s+NAME\s*:\s*([A-Za-z][A-Za-z \t\'\-\.]{4,})',
            ]
            for pattern in account_name_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    candidate = match.group(1).strip()
                    candidate = re.sub(r'[0-9]+$', '', candidate).strip()  # Remove trailing numbers
                    is_valid, reason = is_valid_name_candidate(candidate)
                    logger.debug(f"DEBUG: Found 'Account Name' (inline) -> '{candidate}' | Valid: {is_valid} | Reason: {reason}")
                    if is_valid:
                        candidates.append(('PRIORITY_1_ACCOUNT_NAME', candidate, 1))
                        break
        
        # PRIORITY 2: Check for \"Account Holder:\" patterns
        if not candidates:
            logger.debug("DEBUG: Checking for 'Account Holder' patterns...")
            holder_patterns = [
                r'ACCOUNT\s+HOLDER\s*:\s*([A-Za-z][A-Za-z \t\'\-\.]{4,})',
                r'ACCOUNT\s+HOLDER\s+NAME\s*:\s*([A-Za-z][A-Za-z \t\'\-\.]{4,})',
            ]
            for pattern in holder_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    candidate = match.group(1).strip()
                    is_valid, reason = is_valid_name_candidate(candidate)
                    logger.debug(f"DEBUG: Found 'Account Holder' -> '{candidate}' | Valid: {is_valid} | Reason: {reason}")
                    if is_valid:
                        candidates.append(('PRIORITY_2_ACCOUNT_HOLDER', candidate, 2))
                        break
        
        # PRIORITY 3: Check for "Customer Name:" patterns
        if not candidates:
            logger.debug("DEBUG: Checking for 'Customer Name' patterns...")
            customer_patterns = [
                r'CUSTOMER\s+NAME\s*:\s*([A-Za-z][A-Za-z \t\'\-\.]{4,})',
                r'CLIENT\s+NAME\s*:\s*([A-Za-z][A-Za-z \t\'\-\.]{4,})',
            ]
            for pattern in customer_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    candidate = match.group(1).strip()
                    is_valid, reason = is_valid_name_candidate(candidate)
                    logger.debug(f"DEBUG: Found 'Customer Name' -> '{candidate}' | Valid: {is_valid} | Reason: {reason}")
                    if is_valid:
                        candidates.append(('PRIORITY_3_CUSTOMER_NAME', candidate, 3))
                        break
        
        # Select best candidate (lowest priority number = highest priority)
        if candidates:
            candidates.sort(key=lambda x: x[2])  # Sort by priority
            selected_source, selected_name, priority = candidates[0]
            logger.debug(f"✅ DEBUG: Account holder SELECTED: '{selected_name}' via {selected_source}")
            return selected_name.title().strip()
        
        # No valid candidate found
        logger.error("❌ DEBUG: Account holder NAME extraction FAILED - no valid candidates found")
        return None

    def _extract_bank_name(self, lines: List[str]) -> Optional[str]:
        """Extract bank name with enhanced patterns and comprehensive known bank fallback."""
        header_lines = lines[:30]  # Increased from 20 to capture more header content
        full_text = "\n".join(header_lines)
        
        # Pattern-based extraction
        for idx, line in enumerate(header_lines):
            # Label-only line "Bank" followed by bank name on next line
            if re.fullmatch(r'BANK', line, re.IGNORECASE) and idx + 1 < len(header_lines):
                next_line = header_lines[idx + 1].strip()
                if next_line and len(next_line.split()) <= 8:
                    name = re.sub(r'\s+\(.*?\)\s*$', '', next_line).strip()
                    logger.debug(f"DEBUG: Bank name extracted: '{name}' via BANK label line")
                    return name.title()

            # Pattern: "XYZ STATEMENT OF ACCOUNT"
            match = re.search(r'^\s*([A-Za-z0-9 &]+)\s+STATEMENT\s+OF\s+ACCOUNT', line, re.IGNORECASE)
            if match:
                name = match.group(1).strip().title()
                logger.debug(f"DEBUG: Bank name extracted: '{name}' via 'STATEMENT OF ACCOUNT' pattern")
                return name
            
            # Pattern: "XYZ BANK" or "XYZ BANK PLC/LTD"
            match = re.search(r'^\s*([A-Za-z0-9 &]+)\s+BANK(?:\s+(?:PLC|LTD|LIMITED))?\b', line, re.IGNORECASE)
            if match:
                name = match.group(1).strip().title() + " Bank"
                logger.debug(f"DEBUG: Bank name extracted: '{name}' via 'BANK' pattern")
                return name
            
            # Pattern: "BANK NAME: XYZ" or "BANK: XYZ"
            match = re.search(r'BANK\s*(?:NAME)?\s*[:\-]\s*([A-Za-z0-9 &]+)', line, re.IGNORECASE)
            if match:
                name = match.group(1).strip().title()
                logger.debug(f"DEBUG: Bank name extracted: '{name}' via 'BANK NAME:' pattern")
                return name
            
            # Multiline: "BANK STATEMENT" with bank name on previous line
            if re.search(r'BANK\s+STATEMENT', line, re.IGNORECASE) and idx > 0:
                prev_line = header_lines[idx - 1].strip()
                if prev_line and len(prev_line.split()) <= 5 and not re.search(r'\d{4}', prev_line):
                    logger.debug(f"DEBUG: Bank name extracted: '{prev_line}' via multiline BANK STATEMENT")
                    return prev_line.title()
            
            # Multiline: "Statement of Account" with bank name on previous line
            if re.search(r'STATEMENT\s+OF\s+ACCOUNT', line, re.IGNORECASE) and idx > 0:
                prev_line = header_lines[idx - 1].strip()
                if prev_line and len(prev_line.split()) <= 5:
                    logger.debug(f"DEBUG: Bank name extracted: '{prev_line}' via multiline STATEMENT OF ACCOUNT")
                    return prev_line.title()
        
        # Comprehensive known banks fallback - check full header text
        header_text = full_text.upper()
        known_banks = [
            # Zambian Banks
            "ZAMBIA NATIONAL COMMERCIAL BANK", "ZANACO",
            "ABSA BANK ZAMBIA", "ABSA ZAMBIA", "ABSA",
            "STANBIC BANK ZAMBIA", "STANBIC BANK", "STANBIC",
            "FIRST NATIONAL BANK ZAMBIA", "FNB ZAMBIA", "FNB",
            "STANDARD CHARTERED BANK ZAMBIA", "STANDARD CHARTERED",
            "BARCLAYS BANK ZAMBIA", "BARCLAYS",
            "ATLAS MARA", "INDO ZAMBIA BANK",
            "ACCESS BANK ZAMBIA", "ACCESS BANK",
            "BANK OF ZAMBIA", "INVESTRUST", "CAVMONT BANK",
            "FIRST ALLIANCE BANK", "UNITED BANK FOR AFRICA", "UBA",
            # International Banks
            "HSBC", "CITIBANK", "DEUTSCHE BANK",
            "LLOYDS BANK", "NATWEST", "SANTANDER",
            # Mobile Money / Digital
            "MTN MOBILE MONEY", "AIRTEL MONEY", "ECONET",
        ]
        for bank in known_banks:
            if bank in header_text:
                logger.debug(f"DEBUG: Bank name extracted: '{bank}' via known banks list")
                return bank.title()
        
        logger.error("DEBUG: Bank NAME extraction FAILED - no patterns or known banks matched")
        return None

    def _detect_column_headers(self, lines: List[str]) -> Optional[List[str]]:
        for line in lines:
            lowered = line.lower()
            if "money out" in lowered and "money in" in lowered and "balance" in lowered:
                return ["money out", "money in", "balance"]
            if "debit" in lowered and "credit" in lowered and "balance" in lowered:
                return ["debit", "credit", "balance"]
        return None

    def _extract_transactions_core(
        self,
        lines: List[str],
        numeric_tokens: List[NumericToken],
        summary_fields: Dict[str, Optional[float]],
        column_order: Optional[List[str]],
        statement_period: Optional[StatementPeriod],
    ) -> List[Transaction]:
        txs = []
        current_date_obj = None
        pending_tx = None
        tx_conf_threshold = 0.7

        def is_header_line(value: str) -> bool:
            lowered = value.lower()
            return any(k in lowered for k in ["description", "debit", "credit", "balance", "money in", "money out"])

        def strip_amounts(value: str, tokens: List[str]) -> str:
            cleaned = value
            for token in tokens:
                cleaned = cleaned.replace(token, " ")
            return re.sub(r"\s+", " ", cleaned).strip()

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            is_summary_line = self._is_summary_line(line)
            if is_summary_line:
                amount_tokens = self._extract_amount_tokens(line)
                
                # Check if tokens on current line are just dates/noise
                is_just_dates = amount_tokens and all(self._looks_like_date_number(t) for t in amount_tokens)
                
                # Look-ahead logic if no tokens OR only date-like tokens on current line
                if (not amount_tokens or is_just_dates) and idx + 1 < len(lines):
                    # Try the next 3 lines
                    for offset in range(1, 4):
                        next_line = lines[idx + offset].strip()
                        if not next_line: continue
                        # If we find another summary line label, stop look-ahead
                        if self._is_summary_line(next_line): break
                        
                        next_tokens = self._extract_amount_tokens(next_line)
                        # Filter out dates from next tokens too - we want real amounts
                        if next_tokens and not all(self._looks_like_date_number(t) for t in next_tokens):
                            logger.debug(f"DEBUG: Found summary value(s) '{next_tokens}' for label '{line}' on line +{offset}")
                            amount_tokens = next_tokens
                            break

                if amount_tokens:
                    roles = self._classify_amounts_in_line(
                        line=line,
                        amount_tokens=amount_tokens,
                        column_order=column_order,
                        statement_period=statement_period,
                        current_date=current_date_obj,
                        summary_fields=summary_fields,
                    )
                    for token_info in roles:
                        numeric_tokens.append(token_info)
                continue

            if self._is_non_financial_line(line) or is_header_line(line):
                continue

            date_in_line = self._parse_date(line, reference_date=current_date_obj)
            if date_in_line:
                if pending_tx and pending_tx.get("balance") is not None and (
                    pending_tx.get("credit") is not None or pending_tx.get("debit") is not None
                ):
                    finalize = self._finalize_transaction(pending_tx, tx_conf_threshold)
                    if finalize:
                        logger.debug(f"DEBUG: Finalizing TX: {finalize.date} | {finalize.description[:30]} | CR: {finalize.credit} | DR: {finalize.debit}")
                        txs.append(finalize)
                current_date_obj = date_in_line
                pending_tx = {
                    "date": current_date_obj.strftime("%Y-%m-%d"),
                    "description": self._strip_date_from_line(line),
                    "credit": None,
                    "debit": None,
                    "balance": None,
                    "pending_amount": None,
                    "confidence": 0.4,
                    "reasons": ["date_anchor"],
                }

            time_tokens = self._extract_time_tokens(line)
            for token in time_tokens:
                numeric_tokens.append(token)

            amount_tokens = self._extract_amount_tokens(line)
            if not amount_tokens:
                if pending_tx and not date_in_line:
                    pending_tx["description"] = (pending_tx["description"] + " " + line).strip()
                continue

            roles = self._classify_amounts_in_line(
                line=line,
                amount_tokens=amount_tokens,
                column_order=column_order,
                statement_period=statement_period,
                current_date=current_date_obj,
                summary_fields=summary_fields,
            )
            for token_info in roles:
                numeric_tokens.append(token_info)

            if not current_date_obj:
                # Fallback: If no date found yet, use statement start or 
                # a placeholder so we don't lose the transaction
                fallback_date = None
                if statement_period:
                    try:
                        fallback_date = datetime.strptime(statement_period.start, "%Y-%m-%d")
                    except: pass
                
                current_date_obj = fallback_date or datetime.now()
                # Don't update current_date_obj permanently if it was a lucky guess
                # wait, let's just use it as start and we'll update it when we find a real date
                logger.debug(f"DEBUG: Using fallback date {current_date_obj.date()} for early transaction")

            if not pending_tx:
                pending_tx = {
                    "date": current_date_obj.strftime("%Y-%m-%d"),
                    "description": strip_amounts(line, amount_tokens),
                    "credit": None,
                    "debit": None,
                    "balance": None,
                    "pending_amount": None,
                    "salary_detected": False,
                    "confidence": 0.4,
                    "reasons": ["date_anchor"],
                }
            elif not date_in_line:
                pending_tx["description"] = (pending_tx["description"] + " " + strip_amounts(line, amount_tokens)).strip()

            if pending_tx and any(keyword in pending_tx["description"].upper() for keyword in ["SALARY", "PAYROLL"]):
                pending_tx["salary_detected"] = True
                if "salary_context" not in pending_tx["reasons"]:
                    pending_tx["reasons"].append("salary_context")

            tx_amounts = [t for t in roles if t.role in [NumericRole.TRANSACTION_CREDIT, NumericRole.TRANSACTION_DEBIT]]
            running_balances = [t for t in roles if t.role == NumericRole.RUNNING_BALANCE]

            if tx_amounts:
                credit_tokens = [t for t in tx_amounts if t.role == NumericRole.TRANSACTION_CREDIT]
                debit_tokens = [t for t in tx_amounts if t.role == NumericRole.TRANSACTION_DEBIT]
                direction_hint = self._direction_role_from_line(line.upper())
                if credit_tokens and debit_tokens:
                    if direction_hint == NumericRole.TRANSACTION_CREDIT and pending_tx.get("credit") is None:
                        pending_tx["credit"] = credit_tokens[0].normalized_value
                        pending_tx["reasons"].append("column_or_keyword_credit")
                    elif direction_hint == NumericRole.TRANSACTION_DEBIT and pending_tx.get("debit") is None:
                        pending_tx["debit"] = debit_tokens[0].normalized_value
                        pending_tx["reasons"].append("column_or_keyword_debit")
                elif credit_tokens and pending_tx.get("credit") is None:
                    pending_tx["credit"] = credit_tokens[0].normalized_value
                    pending_tx["reasons"].append("column_or_keyword_credit")
                elif debit_tokens and pending_tx.get("debit") is None:
                    pending_tx["debit"] = debit_tokens[0].normalized_value
                    pending_tx["reasons"].append("column_or_keyword_debit")
            else:
                amount_vals = [self._normalize_amount(t) for t in amount_tokens]
                amount_vals = [v for v in amount_vals if v is not None]
                if amount_vals:
                    if len(amount_vals) >= 2:
                        pending_tx["balance"] = amount_vals[-1]
                        amount_val = amount_vals[-2]
                        direction_hint = self._direction_role_from_line(line.upper())
                        if direction_hint == NumericRole.TRANSACTION_CREDIT and pending_tx.get("credit") is None:
                            pending_tx["credit"] = amount_val
                            pending_tx["reasons"].append("inferred_credit")
                        elif direction_hint == NumericRole.TRANSACTION_DEBIT and pending_tx.get("debit") is None:
                            pending_tx["debit"] = amount_val
                            pending_tx["reasons"].append("inferred_debit")
                        else:
                            if pending_tx.get("credit") is None and pending_tx.get("debit") is None:
                                pending_tx["credit"] = amount_val
                                pending_tx["reasons"].append("inferred_credit_default")
                    elif len(amount_vals) == 1:
                        single_val = amount_vals[0]
                        if pending_tx.get("balance") is not None and (
                            pending_tx.get("credit") is None and pending_tx.get("debit") is None
                        ):
                            direction_hint = self._direction_role_from_line(line.upper())
                            if direction_hint == NumericRole.TRANSACTION_DEBIT:
                                pending_tx["debit"] = single_val
                                pending_tx["reasons"].append("inferred_debit_single")
                            else:
                                pending_tx["credit"] = single_val
                                pending_tx["reasons"].append("inferred_credit_single")
                        elif pending_tx.get("credit") is not None or pending_tx.get("debit") is not None:
                            pending_tx["balance"] = single_val
                            pending_tx["reasons"].append("inferred_balance_single")
                        elif pending_tx.get("pending_amount") is not None:
                            direction_hint = self._direction_role_from_line(line.upper())
                            if direction_hint == NumericRole.TRANSACTION_DEBIT:
                                pending_tx["debit"] = pending_tx["pending_amount"]
                                pending_tx["reasons"].append("paired_debit_single")
                            else:
                                pending_tx["credit"] = pending_tx["pending_amount"]
                                pending_tx["reasons"].append("paired_credit_single")
                            pending_tx["balance"] = single_val
                            pending_tx["pending_amount"] = None
                            pending_tx["reasons"].append("paired_balance_single")
                        else:
                            pending_tx["pending_amount"] = single_val
                            pending_tx["reasons"].append("pending_amount_single")

            if running_balances:
                pending_tx["balance"] = running_balances[-1].normalized_value
                pending_tx["reasons"].append("running_balance_context")

            pending_tx["confidence"] = self._score_transaction_confidence(pending_tx)

        if pending_tx and pending_tx.get("balance") is not None and (
            pending_tx.get("credit") is not None or pending_tx.get("debit") is not None
        ):
            finalize = self._finalize_transaction(pending_tx, tx_conf_threshold)
            if finalize: txs.append(finalize)

        return txs

    def _parse_date(self, line: str, reference_date: Optional[datetime] = None) -> Optional[datetime]:
        """
        Parses a date from a line. 
        If year is missing, it intelligently uses reference_date or self.statement_year.
        Corrects for year-rollover (e.g. Nov 2025 on a Jan 2026 statement).
        """
        parsed_dt = None
        
        # 1. ISO format (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
        m = self.date_iso_ptrn.search(line)
        if m:
            y, mo, d = m.groups()
            try:
                parsed_dt = datetime(int(y), int(mo), int(d))
            except ValueError:
                pass

        # 2. Word format: 'Nov 04', 'Nov 04, 2025'
        if not parsed_dt:
            m = self.date_word_ptrn.search(line)
            if m:
                d1, m1, m2, d2, y = m.groups()
                m_name = m1 or m2
                d_val = d1 or d2
                month = self.month_map.get(m_name.title(), self.month_map.get(m_name.title()[:3], 1))
                year = int(y) if y else (reference_date.year if reference_date else self.statement_year)
                try:
                    parsed_dt = datetime(year, month, int(d_val))
                except ValueError:
                    pass
        
        # 3. Numeric format: '04/11/2025'
        if not parsed_dt:
            m = self.date_num_ptrn.search(line)
            if m:
                v1, v2, y = m.groups()
                year = int(y) + (2000 if y and int(y) < 100 else 0) if y else (reference_date.year if reference_date else self.statement_year)
                if year < 1990 or year > 2100: year = self.statement_year
                
                v1_i, v2_i = int(v1), int(v2)
                if v1_i > 12: month, day = v2_i, v1_i
                else: month, day = v1_i, v2_i
                
                if 1 <= month <= 12 and 1 <= day <= 31:
                    try:
                        parsed_dt = datetime(year, month, day)
                    except ValueError:
                        pass
        
        if not parsed_dt: return None
        
        # YEAR ROLLOVER LOGIC:
        # Instead of subtracting relative to the previous line (which causes drift),
        # we anchor it to the statement's own end date (self.statement_year/month).
        # We only subtract 1 year if the parsed month is high (Nov/Dec) 
        # but the statement end is low (Jan/Feb).
        if not y: # Only auto-adjust if year was missing in text
            stmt_end_month = self.statement_month or 1
            # If the date found in the text has a month LATER than the statement's own end month
            # (e.g. statement ends Jan 04, but we found a Nov 04 transaction),
            # then that transaction must belong to the PREVIOUS year.
            if parsed_dt.month > stmt_end_month:
                try:
                    parsed_dt = parsed_dt.replace(year=self.statement_year - 1)
                except: pass
            else:
                # Default to statement year
                try:
                    parsed_dt = parsed_dt.replace(year=self.statement_year)
                except: pass
        
        return parsed_dt

    def _extract_time_tokens(self, line: str) -> List[NumericToken]:
        tokens = []
        for m in self.time_ptrn.finditer(line):
            raw = m.group(0)
            tokens.append(NumericToken(
                raw_text=raw,
                normalized_value=None,
                currency=None,
                role=NumericRole.TIMESTAMP,
                confidence=0.95,
                metadata={"line_context": line}
            ))
        return tokens

    def _extract_amount_tokens(self, line: str) -> List[str]:
        return [m.group(0).strip() for m in self.amount_token_ptrn.finditer(line)]

    def _classify_amounts_in_line(
        self,
        line: str,
        amount_tokens: List[str],
        column_order: Optional[List[str]],
        statement_period: Optional[StatementPeriod],
        current_date: Optional[datetime],
        summary_fields: Dict[str, Optional[float]],
    ) -> List[NumericToken]:
        tokens: List[NumericToken] = []
        upper_line = line.upper()

        if self._is_summary_line(line):
            summary_role = self._summary_role_from_line(line, statement_period)
            count_match = re.search(r'TOTAL\s+CREDIT\s+ENTRIES\s+(\d+)', upper_line)
            if count_match and summary_fields.get("deposit_count") is None:
                summary_fields["deposit_count"] = int(count_match.group(1))
            selected_idx = self._select_summary_amount_index(amount_tokens)
            for idx, raw in enumerate(amount_tokens):
                if summary_role and idx == selected_idx:
                    role = summary_role
                    normalized = self._normalize_amount(raw)
                    confidence = 0.9
                else:
                    role = NumericRole.TIMESTAMP if self._looks_like_date_number(raw) else NumericRole.UNKNOWN
                    normalized = None
                    confidence = 0.6 if role == NumericRole.TIMESTAMP else 0.3
                tokens.append(self._build_numeric_token(raw, normalized, role, line, confidence))
                if role == NumericRole.SUMMARY_TOTAL_IN and summary_fields.get("total_money_in") is None:
                    summary_fields["total_money_in"] = normalized
                elif role == NumericRole.SUMMARY_TOTAL_OUT and summary_fields.get("total_money_out") is None:
                    summary_fields["total_money_out"] = normalized
                elif role == NumericRole.OPENING_BALANCE and summary_fields.get("opening_balance") is None:
                    summary_fields["opening_balance"] = normalized
                elif role == NumericRole.CLOSING_BALANCE:
                    # Overwrite if current is None or if current is a suspect year value
                    current = summary_fields.get("closing_balance")
                    if current is None or (current in [2024.0, 2025.0, 2026.0] and normalized not in [2024.0, 2025.0, 2026.0]):
                        summary_fields["closing_balance"] = normalized
            return tokens

        if self._is_non_financial_line(line):
            for raw in amount_tokens:
                tokens.append(self._build_numeric_token(raw, None, NumericRole.NON_FINANCIAL_NUMBER, line, 0.8))
            return tokens

        if self._line_has_time_context(line):
            for raw in amount_tokens:
                tokens.append(self._build_numeric_token(raw, None, NumericRole.TIMESTAMP, line, 0.8))
            return tokens

        if self._line_has_date_context(line) and all(self._looks_like_date_number(t) for t in amount_tokens):
            for raw in amount_tokens:
                tokens.append(self._build_numeric_token(raw, None, NumericRole.TIMESTAMP, line, 0.7))
            return tokens

        dc_marker = self._extract_dc_marker(line)
        amount_like_tokens = [t for t in amount_tokens if self._is_amount_like(t)]
        if dc_marker and amount_like_tokens:
            amount_idx = -1
            balance_idx = None
            if len(amount_like_tokens) >= 2:
                amount_idx = -2
                balance_idx = -1
            amount_raw = amount_like_tokens[amount_idx]
            amount_val = self._normalize_amount(amount_raw)
            if dc_marker == "C":
                tokens.append(self._build_numeric_token(amount_raw, amount_val, NumericRole.TRANSACTION_CREDIT, line, 0.85))
            else:
                tokens.append(self._build_numeric_token(amount_raw, amount_val, NumericRole.TRANSACTION_DEBIT, line, 0.85))
            if balance_idx is not None:
                bal_raw = amount_like_tokens[balance_idx]
                bal_val = self._normalize_amount(bal_raw)
                tokens.append(self._build_numeric_token(bal_raw, bal_val, NumericRole.RUNNING_BALANCE, line, 0.75))
            for raw in amount_tokens:
                if raw not in amount_like_tokens:
                    tokens.append(self._build_numeric_token(raw, None, NumericRole.NON_FINANCIAL_NUMBER, line, 0.8))
            return tokens

        if column_order and len(amount_tokens) == len(column_order):
            for raw, column in zip(amount_tokens, column_order):
                role = self._role_from_column(column)
                normalized = self._normalize_amount(raw)
                tokens.append(self._build_numeric_token(raw, normalized, role, line, 0.9))
            return tokens

        if column_order and "balance" in column_order and len(amount_tokens) == 2:
            normalized_first = self._normalize_amount(amount_tokens[0])
            normalized_last = self._normalize_amount(amount_tokens[1])
            direction_role = self._direction_role_from_line(upper_line)
            if direction_role:
                tokens.append(self._build_numeric_token(amount_tokens[0], normalized_first, direction_role, line, 0.75))
                tokens.append(self._build_numeric_token(amount_tokens[1], normalized_last, NumericRole.RUNNING_BALANCE, line, 0.75))
            else:
                tokens.append(self._build_numeric_token(amount_tokens[0], None, NumericRole.UNKNOWN, line, 0.4))
                tokens.append(self._build_numeric_token(amount_tokens[1], None, NumericRole.UNKNOWN, line, 0.4))
            return tokens

        direction_role = self._direction_role_from_line(upper_line)
        if direction_role and amount_tokens:
            for idx, raw in enumerate(amount_tokens):
                role = direction_role if idx == 0 else NumericRole.RUNNING_BALANCE
                normalized = self._normalize_amount(raw) if role != NumericRole.RUNNING_BALANCE else self._normalize_amount(raw)
                confidence = 0.7 if role != NumericRole.RUNNING_BALANCE else 0.6
                tokens.append(self._build_numeric_token(raw, normalized, role, line, confidence))
            return tokens

        for raw in amount_tokens:
            tokens.append(self._build_numeric_token(raw, None, NumericRole.UNKNOWN, line, 0.3))
        return tokens

    def _build_numeric_token(
        self,
        raw_text: str,
        normalized_value: Optional[float],
        role: NumericRole,
        line: str,
        confidence: float
    ) -> NumericToken:
        if self._looks_like_identifier(raw_text):
            role = NumericRole.NON_FINANCIAL_NUMBER
            normalized_value = None
            confidence = 0.85
        token_currency = self._extract_currency_from_token(raw_text)
        if token_currency and token_currency != self.currency:
            role = NumericRole.UNKNOWN
            normalized_value = None
            confidence = 0.2
        if role in [NumericRole.TIMESTAMP, NumericRole.NON_FINANCIAL_NUMBER, NumericRole.UNKNOWN]:
            normalized_value = None
        return NumericToken(
            raw_text=raw_text,
            normalized_value=normalized_value,
            currency=token_currency or (self.currency if self.currency != "UNKNOWN" else None),
            role=role,
            confidence=confidence,
            metadata={"line_context": line}
        )

    def _summary_role_from_line(self, line: str, statement_period: Optional[StatementPeriod]) -> Optional[NumericRole]:
        upper_line = line.upper()
        if "TOTAL MONEY IN" in upper_line or "TOTAL DEPOSITS" in upper_line:
            return NumericRole.SUMMARY_TOTAL_IN
        if "TOTAL MONEY OUT" in upper_line or "TOTAL WITHDRAWALS" in upper_line:
            return NumericRole.SUMMARY_TOTAL_OUT
        if "TOTAL CREDIT ENTRIES" in upper_line:
            return NumericRole.SUMMARY_TOTAL_IN
        if "TOTAL DEBIT ENTRIES" in upper_line:
            return NumericRole.SUMMARY_TOTAL_OUT
        if any(k in upper_line for k in ["BALANCE BROUGHT FORWARD", "OPENING BALANCE", "BEGINNING BALANCE", "START BALANCE"]):
            return NumericRole.OPENING_BALANCE
        if any(k in upper_line for k in ["BALANCE CARRIED FORWARD", "CLOSING BALANCE", "ENDING BALANCE", "FINAL BALANCE", "TOTAL BALANCE", "ACCOUNT BALANCE", "AVAILABLE BALANCE", "LEDGER BALANCE", "OUTSTANDING BALANCE"]):
            return NumericRole.CLOSING_BALANCE
        
        # New: "CURRENT AVAILABLE BALANCE" or "CURRENT BOOK BALANCE" is definitely closing
        if "CURRENT AVAILABLE BALANCE" in upper_line or "CURRENT BOOK BALANCE" in upper_line:
            return NumericRole.CLOSING_BALANCE

        if "BOOK BALANCE" in upper_line:
            date_in_line = self._parse_date(line)
            if date_in_line:
                if statement_period and self._matches_statement_date(statement_period.end, date_in_line):
                    return NumericRole.CLOSING_BALANCE
                # If no period yet, but it's a balance as at some date, it's likely closing
                if "AS AT" in upper_line:
                    return NumericRole.CLOSING_BALANCE
                    
        if "BALANCE AT" in upper_line:
            date_in_line = self._parse_date(line)
            if date_in_line:
                if statement_period:
                    if self._matches_statement_date(statement_period.start, date_in_line):
                        return NumericRole.OPENING_BALANCE
                    if self._matches_statement_date(statement_period.end, date_in_line):
                        return NumericRole.CLOSING_BALANCE
                else: 
                    # Without period, we can't be sure, but "Balance At" usually closing if it's the only one
                    return NumericRole.CLOSING_BALANCE
            return None
        return None

    def _select_summary_amount_index(self, amount_tokens: List[str]) -> Optional[int]:
        if not amount_tokens:
            return None
        
        # Priority 1: Tokens with currency markers
        for idx, raw in enumerate(amount_tokens):
            if self._extract_currency_from_token(raw):
                return idx
        
        # Priority 2: Candidates that look like amounts (have decimals)
        # and are NOT suspect years (2024, 2025...)
        decimal_candidates = []
        for idx, raw in enumerate(amount_tokens):
            if '.' in raw or ',' in raw:
                val = self._normalize_amount(raw)
                if val not in [2024.0, 2025.0, 2026.0, 2027.0]:
                    decimal_candidates.append(idx)
        
        if decimal_candidates:
            return decimal_candidates[-1]

        # Priority 3: Large integers that aren't dates
        # Many Zanaco statements show balance as an integer if no cents
        candidates = []
        for idx, raw in enumerate(amount_tokens):
            if self._looks_like_date_number(raw):
                continue
            candidates.append(idx)
            
        if candidates:
             # Exclude suspect years if other candidates exist
             non_year_candidates = [idx for idx in candidates if re.sub(r'\D', '', amount_tokens[idx]) not in ["2024", "2025", "2026", "2027"]]
             if non_year_candidates: return non_year_candidates[-1]
             return candidates[-1]
        
        # Absolute fallback: avoid picking a 4-digit number (year) if there are others
        if len(amount_tokens) > 1:
             for idx, raw in enumerate(amount_tokens):
                  clean = re.sub(r'\D', '', raw)
                  if len(clean) != 4: return idx

        return len(amount_tokens) - 1

    def _matches_statement_date(self, statement_date: Optional[str], candidate: datetime) -> bool:
        if not statement_date:
            return False
        try:
            stmt_dt = datetime.strptime(statement_date, "%Y-%m-%d")
        except:
            return False
        return stmt_dt.month == candidate.month and stmt_dt.day == candidate.day

    def _role_from_column(self, column: str) -> NumericRole:
        column = column.lower()
        if "balance" in column:
            return NumericRole.RUNNING_BALANCE
        if "money in" in column or "credit" in column:
            return NumericRole.TRANSACTION_CREDIT
        return NumericRole.TRANSACTION_DEBIT

    def _direction_role_from_line(self, upper_line: str) -> Optional[NumericRole]:
        if any(self._has_keyword(upper_line, k) for k in self.keywords_in):
            return NumericRole.TRANSACTION_CREDIT
        if any(self._has_keyword(upper_line, k) for k in self.keywords_out):
            return NumericRole.TRANSACTION_DEBIT
        return None

    def _has_keyword(self, upper_line: str, keyword: str) -> bool:
        return re.search(rf"\b{re.escape(keyword)}\b", upper_line) is not None

    def _extract_dc_marker(self, line: str) -> Optional[str]:
        matches = re.findall(r"\b([DC])\b", line.upper())
        if matches:
            return matches[-1]
        return None

    def _is_amount_like(self, raw: str) -> bool:
        if self._extract_currency_from_token(raw):
            return True
        if re.search(r"(?:\d+|[.,])\d{2}\b", raw):
            return True
        return False

    def _looks_like_identifier(self, raw: str) -> bool:
        if self._extract_currency_from_token(raw):
            return False
        if re.search(r"[.,]\d{2}\b", raw):
            return False
        digits = re.sub(r"\D", "", raw)
        return len(digits) >= 7

    def _line_has_time_context(self, line: str) -> bool:
        upper_line = line.upper()
        return any(k in upper_line for k in self.time_keywords)

    def _line_has_date_context(self, line: str) -> bool:
        return bool(self.date_word_ptrn.search(line) or self.date_num_ptrn.search(line))

    def _looks_like_date_number(self, raw: str) -> bool:
        """
        Check if a string looks like a day (1-31) or a year (2024-2027).
        Used to filter out noise from summary lines.
        """
        if "." in raw or "," in raw: return False
        clean = re.sub(r'[^\d]', '', raw)
        if not clean:
            return False
        
        # Strict: 4 digit numbers that look like years
        if len(clean) == 4:
            return 2020 <= int(clean) <= 2030
            
        # Strict: 1-2 digit numbers that look like days
        # If the number is small (e.g. 4), and we are in a summary context,
        # it's almost certainly part of a date like "Jan 04"
        if len(clean) <= 2:
            try:
                val = int(clean)
                return 1 <= val <= 31
            except:
                return False
                
        return False

    def _is_summary_line(self, line: str) -> bool:
        upper_line = line.upper()
        return any(keyword in upper_line for keyword in self.summary_keywords)

    def _is_non_financial_line(self, line: str) -> bool:
        upper_line = line.upper()
        return any(keyword in upper_line for keyword in self.non_financial_keywords)

    def _strip_date_from_line(self, line: str) -> str:
        return self.date_word_ptrn.sub("", self.date_num_ptrn.sub("", line)).strip()

    def _score_transaction_confidence(self, tx_data: Dict[str, Optional[float]]) -> float:
        score = 0.4
        if tx_data.get("credit") is not None or tx_data.get("debit") is not None:
            score += 0.3
        if "column_or_keyword_credit" in tx_data.get("reasons", []) or "column_or_keyword_debit" in tx_data.get("reasons", []):
            score += 0.2
        if tx_data.get("balance") is not None:
            score += 0.1
        if tx_data.get("salary_detected"):
            score += 0.1
        return min(score, 1.0)

    def _finalize_transaction(self, tx_data: Dict[str, Any], threshold: float) -> Optional[Transaction]:
        credit = tx_data.get("credit")
        debit = tx_data.get("debit")
        direction = "INFLOW" if credit is not None else "OUTFLOW"
        amount = credit if credit is not None else debit
        reasons = tx_data.get("reasons", [])
        confidence_score = tx_data.get("confidence", 0.0)
        flags = []
        
        description = tx_data.get("description") or "Transaction"
        
        # JUNK FILTER: Ignore transactions that are likely OCR noise
        # 1. Amounts too small (e.g. picking up page numbers or dates as amounts)
        if amount is not None and amount < 1.0: return None
        
        # 2. Reject amounts that match potential years (junk artifact from headers)
        if amount in [2024.0, 2025.0, 2026.0]:
            return None

        # 3. Description is just a keyword or fragment typically found in headers
        desc_upper = description.upper()
        if any(desc_upper == k for k in ["ACCOUNT NAME", "HOME BRANCH", "ZANACO", "STATEMENT OF ACCOUNT", "BRANCH NAME", "VALUE DATE", "POST DATE", "TRANSACTION DETAILS"]):
            return None
            
        # 4. Description is just a date fragment (e.g. "NOV 04", "20 04,")
        if re.match(r'^[A-Z]{3,}\s+\d{1,2}$', desc_upper): return None
        if re.match(r'^\d{2}\s+\d{2},?$', desc_upper): return None # Filter "20 04,"

        if confidence_score < threshold:
            flags.append("LOW_CONFIDENCE_REVIEW")
            
        if tx_data.get("salary_detected") or any(keyword in desc_upper for keyword in ["SALARY", "PAYROLL"]):
            flags.append("SALARY")
            
        return Transaction(
            date=tx_data.get("date"),
            description=description,
            amount=amount,
            credit=credit,
            debit=debit,
            direction=direction,
            balance=tx_data.get("balance"),
            currency=self.currency,
            confidence=confidence_score,
            confidence_score=confidence_score,
            confidence_reasons=reasons,
            flags=flags
        )

    def _normalize_amount(self, amt_str: str) -> Optional[float]:
        clean = re.sub(r'[^\d\.,]', '', amt_str)
        if not clean:
            return None
        if clean.count('.') > 1 and clean.count(',') == 0:
            last = clean.rfind('.')
            clean = clean[:last].replace('.', '') + '.' + clean[last+1:]
        elif clean.count(',') > 1 and clean.count('.') == 0:
            last = clean.rfind(',')
            clean = clean[:last].replace(',', '') + '.' + clean[last+1:]
        elif '.' in clean and ',' in clean:
            if clean.rfind('.') > clean.rfind(','):
                clean = clean.replace(',', '')
            else:
                clean = clean.replace('.', '').replace(',', '.')
        elif ',' in clean and '.' not in clean:
            if len(clean.split(',')[-1]) == 2:
                clean = clean.replace(',', '.')
            else:
                clean = clean.replace(',', '')
        try:
            return float(clean)
        except:
            return None

    def _extract_currency_from_token(self, raw: str) -> Optional[str]:
        if "£" in raw or "GBP" in raw: return "GBP"
        if "$" in raw or "USD" in raw: return "USD"
        if "€" in raw or "EUR" in raw: return "EUR"
        if "ZMW" in raw: return "ZMW"
        return None

    def _generate_summary(
        self,
        txs: List[Transaction],
        summary_fields: Dict[str, Optional[float]],
        statement_period: Optional[StatementPeriod],
        account_holder_name: Optional[str],
        bank_name: Optional[str],
    ) -> BankStatementSummary:
        if not txs and not any(summary_fields.values()):
            return BankStatementSummary(
                currency=self.currency,
                bank_name=bank_name,
                statement_period=statement_period,
                account_holder_name=account_holder_name,
                document_confidence=0.0
            )
            
        total_in_calc = sum(t.amount for t in txs if t.direction == "INFLOW" and t.confidence_score >= 0.7)
        total_out_calc = sum(t.amount for t in txs if t.direction == "OUTFLOW" and t.confidence_score >= 0.7)
        balances = [t.balance for t in txs if t.balance is not None and t.confidence_score >= 0.7]
        opening_calc = balances[0] if balances else None
        closing_calc = balances[-1] if balances else None
        
        total_in = summary_fields.get("total_money_in")
        total_out = summary_fields.get("total_money_out")
        opening = summary_fields.get("opening_balance")
        closing = summary_fields.get("closing_balance")

        salary_txs = [t for t in txs if "SALARY" in t.description.upper() and t.confidence_score >= 0.7]
        salary_detected = bool(salary_txs)
        deposit_count = summary_fields.get("deposit_count")
        if deposit_count is None:
            deposit_count = len([t for t in txs if t.direction == "INFLOW" and t.confidence_score >= 0.7])
        salary_frequency = self._infer_salary_frequency(salary_txs)
        
        flags = []
        if any("GAMBLING" in t.description.upper() or "BETWAY" in t.description.upper() for t in txs):
            flags.append("GAMBLING_DETECTED")
        if any("LOAN REPAYMENT" in t.description.upper() for t in txs):
             flags.append("LOAN_REPAYMENT_DETECTED")

        return BankStatementSummary(
            currency=self.currency,
            bank_name=bank_name,
            statement_period=statement_period,
            account_holder_name=account_holder_name,
            opening_balance=opening,
            closing_balance=closing,
            total_money_in=total_in,
            total_money_out=total_out,
            deposit_count=deposit_count,
            calculated_total_money_in=total_in_calc if total_in is None else None,
            calculated_total_money_out=total_out_calc if total_out is None else None,
            calculated_opening_balance=opening_calc if opening is None else None,
            calculated_closing_balance=closing_calc if closing is None else None,
            salary_detected=salary_detected,
            salary_deposit_detected=salary_detected,
            salary_frequency=salary_frequency,
            salary_confidence=1.0 if salary_detected else 0.0,
            document_confidence=0.9 if txs else 0.1,
            risk_flags=flags
        )

    def _infer_salary_frequency(self, salary_txs: List[Transaction]) -> Optional[str]:
        if len(salary_txs) < 2:
            return None
        dates = []
        for t in salary_txs:
            try:
                dates.append(datetime.fromisoformat(t.date))
            except:
                continue
        if len(dates) < 2:
            return None
        dates.sort()
        deltas = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        if not deltas:
            return None
        monthly_like = [d for d in deltas if 26 <= d <= 35]
        if len(monthly_like) == len(deltas):
            return "Monthly (high confidence)"
        if len(monthly_like) >= max(1, len(deltas) // 2):
            return "Likely monthly"
        return "Irregular"
