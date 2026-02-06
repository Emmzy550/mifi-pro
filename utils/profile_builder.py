import logging
logger = logging.getLogger(__name__)
"""
ProfileBuilder: Service to build UnifiedFinancialProfile from document extractions.

This service:
1. Takes a list of ExtractionResult objects
2. Merges data into a single UnifiedFinancialProfile
3. Validates completeness and sets assessment readiness
4. Never zero-fills missing data
"""
from typing import List, Optional
from models.document import (
    ExtractionResult,
    DocumentType,
    BankStatementSummary,
    PayslipSummary,
    NRCIdentitySummary,
    Transaction,
)
from models.unified_profile import (
    UnifiedFinancialProfile,
    IdentityProfile,
    IncomeProfile,
    BankingBehaviorProfile,
    DocumentCoverage,
    DocumentPresence,
    VerificationStatus,
    AssessmentReadiness,
)


# Configuration: Minimum requirements for assessment
MIN_TRANSACTION_HISTORY_DAYS = 7  # Minimum days of bank history required
MIN_INCOME_CONFIDENCE = 0.5       # Minimum confidence for income verification


class ProfileBuilder:
    """
    Builds a UnifiedFinancialProfile from multiple document extraction results.
    
    This is the ONLY path to create a profile for assessment.
    """
    
    @staticmethod
    def build(
        extraction_results: List[ExtractionResult],
        transactions: Optional[List[Transaction]] = None
    ) -> UnifiedFinancialProfile:
        """
        Build a unified profile from extraction results.
        
        Args:
            extraction_results: List of ExtractionResult from document parsing
            transactions: Optional list of extracted transactions
            
        Returns:
            UnifiedFinancialProfile with assessment readiness determined
        """
        profile = UnifiedFinancialProfile()
        
        # Extract summaries by type
        bank_summary: Optional[BankStatementSummary] = None
        payslip_summary: Optional[PayslipSummary] = None
        nrc_summary: Optional[NRCIdentitySummary] = None
        
        for result in extraction_results:
            if result.bank_statement_summary:
                bank_summary = result.bank_statement_summary
                profile.source_documents.append("BANK_STATEMENT")
            if result.payslip_summary:
                payslip_summary = result.payslip_summary
                profile.source_documents.append("PAYSLIP")
            if result.nrc_summary:
                nrc_summary = result.nrc_summary
                profile.source_documents.append("NRC_ID")
        
        # Build each profile component
        profile.identity = ProfileBuilder._build_identity(
            bank_summary, payslip_summary, nrc_summary
        )
        profile.income = ProfileBuilder._build_income(payslip_summary)
        profile.banking_behavior = ProfileBuilder._build_banking_behavior(
            bank_summary, transactions or []
        )
        profile.document_coverage = ProfileBuilder._build_document_coverage(
            extraction_results
        )
        
        # Build UI summaries
        profile.ui_document_summaries = ProfileBuilder._build_ui_summaries(
            extraction_results
        )
        
        # Determine assessment readiness
        profile.assessment_readiness, profile.blocking_reasons = (
            ProfileBuilder._evaluate_readiness(profile)
        )
        
        return profile
    
    @staticmethod
    def _build_identity(
        bank_summary: Optional[BankStatementSummary],
        payslip_summary: Optional[PayslipSummary],
        nrc_summary: Optional[NRCIdentitySummary]
    ) -> IdentityProfile:
        """Build identity profile from available summaries."""
        identity = IdentityProfile()
        
        # Priority: NRC > Payslip > Bank Statement for full name
        if nrc_summary and nrc_summary.full_name:
            identity.full_name = nrc_summary.full_name
            identity.full_name_source = "NRC_ID"
            identity.id_number = nrc_summary.id_number
        elif payslip_summary and payslip_summary.employee_name:
            identity.full_name = payslip_summary.employee_name
            identity.full_name_source = "PAYSLIP"
        elif bank_summary and bank_summary.account_holder_name:
            identity.full_name = bank_summary.account_holder_name
            identity.full_name_source = "BANK_STATEMENT"
        
        # Employer from payslip
        if payslip_summary and payslip_summary.employer_name:
            identity.employer_name = payslip_summary.employer_name
        
        # Bank details from bank statement
        if bank_summary:
            identity.bank_name = bank_summary.bank_name
            identity.account_holder_name = bank_summary.account_holder_name
            logger.debug(f"DEBUG [ProfileBuilder]: Copying from bank_summary -> identity.bank_name='{identity.bank_name}', identity.account_holder_name='{identity.account_holder_name}'")
            
            # SAFETY CHECK: Verify we're not losing data
            if bank_summary.account_holder_name is not None and identity.account_holder_name is None:
                logger.error(f"⚠️  CRITICAL: bank_summary.account_holder_name was '{bank_summary.account_holder_name}' but identity.account_holder_name is None!")
        else:
            logger.debug(f"DEBUG [ProfileBuilder]: No bank_summary available for identity fields")
        
        # Determine verification status
        has_name = identity.full_name is not None
        has_employer = identity.employer_name is not None
        has_bank = identity.bank_name is not None
        
        if has_name and has_employer and has_bank:
            identity.verification_status = VerificationStatus.VERIFIED
            identity.confidence = 0.9
        elif has_name:
            identity.verification_status = VerificationStatus.PARTIAL
            identity.confidence = 0.5
        else:
            identity.verification_status = VerificationStatus.UNVERIFIED
            identity.confidence = 0.0
        
        return identity
    
    @staticmethod
    def _build_income(payslip_summary: Optional[PayslipSummary]) -> IncomeProfile:
        """Build income profile from payslip. Never zero-fill."""
        income = IncomeProfile()
        
        if not payslip_summary:
            income.verification_status = VerificationStatus.UNVERIFIED
            return income
        
        # Copy values directly - None stays None
        income.gross_pay = payslip_summary.gross_pay
        income.net_pay = payslip_summary.net_pay
        income.deductions = payslip_summary.deductions
        income.pay_frequency = payslip_summary.pay_frequency
        income.pay_period_start = payslip_summary.pay_period_start
        income.pay_period_end = payslip_summary.pay_period_end
        income.currency = payslip_summary.currency
        
        # Determine verification status
        has_net = income.net_pay is not None
        has_gross = income.gross_pay is not None
        
        if has_net and has_gross:
            income.verification_status = VerificationStatus.VERIFIED
            income.confidence = payslip_summary.document_confidence
        elif has_net or has_gross:
            income.verification_status = VerificationStatus.PARTIAL
            income.confidence = payslip_summary.document_confidence * 0.7
        else:
            income.verification_status = VerificationStatus.UNVERIFIED
            income.confidence = 0.0
        
        return income
    
    @staticmethod
    def _build_banking_behavior(
        bank_summary: Optional[BankStatementSummary],
        transactions: List[Transaction]
    ) -> BankingBehaviorProfile:
        """Build banking behavior profile from bank statement."""
        behavior = BankingBehaviorProfile()
        
        if not bank_summary:
            behavior.verification_status = VerificationStatus.UNVERIFIED
            return behavior
        
        # Copy balance information - None stays None
        behavior.opening_balance = bank_summary.opening_balance
        behavior.closing_balance = bank_summary.closing_balance
        behavior.total_money_in = bank_summary.total_money_in
        behavior.total_money_out = bank_summary.total_money_out
        behavior.currency = bank_summary.currency
        
        # Transaction metrics
        behavior.transaction_count = len(transactions)
        
        # Salary detection
        behavior.salary_detected = bank_summary.salary_detected or bank_summary.salary_deposit_detected
        behavior.salary_confidence = bank_summary.salary_confidence or 0.0
        
        # Statement period
        if bank_summary.statement_period:
            behavior.statement_period_start = bank_summary.statement_period.start
            behavior.statement_period_end = bank_summary.statement_period.end
            
            # Calculate history days
            if bank_summary.statement_period.start and bank_summary.statement_period.end:
                try:
                    from datetime import datetime
                    start = datetime.strptime(bank_summary.statement_period.start, "%Y-%m-%d")
                    end = datetime.strptime(bank_summary.statement_period.end, "%Y-%m-%d")
                    behavior.history_days = (end - start).days
                except Exception:
                    behavior.history_days = 0
        
        # Determine verification status
        has_balance = behavior.closing_balance is not None
        has_transactions = behavior.transaction_count > 0
        
        if has_balance and has_transactions:
            behavior.verification_status = VerificationStatus.VERIFIED
            behavior.confidence = bank_summary.document_confidence
        elif has_balance or has_transactions:
            behavior.verification_status = VerificationStatus.PARTIAL
            behavior.confidence = bank_summary.document_confidence * 0.7
        else:
            behavior.verification_status = VerificationStatus.UNVERIFIED
            behavior.confidence = 0.0
        
        return behavior
    
    @staticmethod
    def _build_document_coverage(
        extraction_results: List[ExtractionResult]
    ) -> DocumentCoverage:
        """Determine which documents are present and their quality."""
        coverage = DocumentCoverage()
        
        for result in extraction_results:
            if result.document_type == DocumentType.BANK_STATEMENT:
                if result.bank_statement_summary:
                    has_balance = result.bank_statement_summary.closing_balance is not None
                    has_txns = len(result.transactions) > 0
                    if has_balance or has_txns:
                        coverage.bank_statement = DocumentPresence.PRESENT_COMPLETE
                    else:
                        coverage.bank_statement = DocumentPresence.PRESENT_INCOMPLETE
                    coverage.bank_statement_confidence = result.confidence
                else:
                    coverage.bank_statement = DocumentPresence.PRESENT_INCOMPLETE
                    coverage.bank_statement_confidence = result.confidence
                    
            elif result.document_type == DocumentType.PAYSLIP:
                if result.payslip_summary:
                    has_income = (
                        result.payslip_summary.net_pay is not None or 
                        result.payslip_summary.gross_pay is not None
                    )
                    if has_income:
                        coverage.payslip = DocumentPresence.PRESENT_COMPLETE
                    else:
                        coverage.payslip = DocumentPresence.PRESENT_INCOMPLETE
                    coverage.payslip_confidence = result.confidence
                else:
                    coverage.payslip = DocumentPresence.PRESENT_INCOMPLETE
                    coverage.payslip_confidence = result.confidence
                    
            elif result.document_type == DocumentType.NRC_ID:
                if result.nrc_summary and result.nrc_summary.full_name:
                    coverage.nrc_id = DocumentPresence.PRESENT_COMPLETE
                else:
                    coverage.nrc_id = DocumentPresence.PRESENT_INCOMPLETE
                coverage.nrc_confidence = result.confidence
        
        return coverage
    
    @staticmethod
    def _build_ui_summaries(
        extraction_results: List[ExtractionResult]
    ) -> List[dict]:
        """Build document summaries for UI display (NOT for assessment)."""
        summaries = []
        
        for result in extraction_results:
            if result.bank_statement_summary:
                summaries.append({
                    "summary_profile": result.bank_statement_summary.summary_profile,
                    "closing_balance": result.bank_statement_summary.closing_balance,
                    "statement_period": (
                        result.bank_statement_summary.statement_period.model_dump()
                        if result.bank_statement_summary.statement_period else None
                    ),
                    "bank_name": result.bank_statement_summary.bank_name,
                    "account_holder_name": result.bank_statement_summary.account_holder_name,
                    "currency": result.bank_statement_summary.currency,
                    "risk_flags": result.bank_statement_summary.risk_flags,
                    "raw_text_preview": result.raw_text_preview
                })
                
            if result.payslip_summary:
                summaries.append({
                    "summary_profile": result.payslip_summary.summary_profile,
                    "net_pay": result.payslip_summary.net_pay,
                    "gross_pay": result.payslip_summary.gross_pay,
                    "deductions": result.payslip_summary.deductions,
                    "employer_name": result.payslip_summary.employer_name,
                    "employee_name": result.payslip_summary.employee_name,
                    "pay_period_start": result.payslip_summary.pay_period_start,
                    "pay_period_end": result.payslip_summary.pay_period_end,
                    "pay_date": result.payslip_summary.pay_date,
                    "pay_frequency": result.payslip_summary.pay_frequency,
                    "currency": result.payslip_summary.currency,
                    "raw_text_preview": result.raw_text_preview
                })
                
            if result.nrc_summary:
                summaries.append({
                    "summary_profile": result.nrc_summary.summary_profile,
                    "full_name": result.nrc_summary.full_name,
                    "id_number": result.nrc_summary.id_number,
                    "date_of_birth": result.nrc_summary.date_of_birth,
                    "gender": result.nrc_summary.gender,
                    "raw_text_preview": result.raw_text_preview
                })
        
        return summaries
    
    @staticmethod
    def _evaluate_readiness(
        profile: UnifiedFinancialProfile
    ) -> tuple[AssessmentReadiness, List[str]]:
        """
        Evaluate if profile has sufficient data for assessment.
        
        CRITICAL: This is the gating logic that prevents partial assessments.
        Required documents: PAYSLIP + BANK_STATEMENT (both must be PRESENT_COMPLETE)
        """
        logger.info(f"\n{'='*80}")
        logger.debug(f"DEBUG [ProfileBuilder]: Evaluating assessment readiness")
        logger.info(f"  - Payslip status: {profile.document_coverage.payslip}")
        logger.info(f"  - Bank statement status: {profile.document_coverage.bank_statement}")
        logger.info(f"  - Identity full_name: '{profile.identity.full_name}'")
        logger.info(f"  - Identity account_holder_name: '{profile.identity.account_holder_name}'")
        logger.info(f"  - Identity bank_name: '{profile.identity.bank_name}'")
        logger.info(f"  - Income net_pay: {profile.income.net_pay}")
        logger.info(f"  - Banking transaction_count: {profile.banking_behavior.transaction_count}")
        logger.info(f"{'='*80}\n")
        
        blocking_reasons = []
        
        # Check 1: Payslip required for verified income
        if profile.document_coverage.payslip == DocumentPresence.MISSING:
            blocking_reasons.append("Payslip document is required for income verification")
        elif profile.document_coverage.payslip == DocumentPresence.PRESENT_INCOMPLETE:
            blocking_reasons.append("Payslip uploaded but income details could not be extracted")
        elif profile.income.net_pay is None and profile.income.gross_pay is None:
            blocking_reasons.append("No income information found in payslip")
        
        # Check 2: Bank statement required for transaction history
        if profile.document_coverage.bank_statement == DocumentPresence.MISSING:
            blocking_reasons.append("Bank statement document is required for transaction analysis")
        elif profile.document_coverage.bank_statement == DocumentPresence.PRESENT_INCOMPLETE:
            blocking_reasons.append("Bank statement uploaded but could not be fully extracted")
        elif profile.banking_behavior.transaction_count == 0:
            blocking_reasons.append("No transactions found in bank statement")
        
        # Check 3: Account holder identity required for verification
        if profile.identity.account_holder_name is None:
            blocking_reasons.append("Account holder name could not be extracted from bank statement - identity verification required")
        
        # Check 4: Minimum history requirement
        if (profile.banking_behavior.history_days > 0 and 
            profile.banking_behavior.history_days < MIN_TRANSACTION_HISTORY_DAYS):
            blocking_reasons.append(
                f"Insufficient transaction history: {profile.banking_behavior.history_days} days "
                f"(minimum {MIN_TRANSACTION_HISTORY_DAYS} days required)"
            )
        
        # STRICT GATING: If ANY blocking reason exists, return BLOCKED
        # No PARTIAL assessments - this enforces data integrity
        if blocking_reasons:
            logger.debug(f"DEBUG [ProfileBuilder]: Assessment BLOCKED. Reasons: {blocking_reasons}")
            return AssessmentReadiness.BLOCKED, blocking_reasons
        
        logger.debug(f"DEBUG [ProfileBuilder]: Assessment READY ✓")
        return AssessmentReadiness.READY, []