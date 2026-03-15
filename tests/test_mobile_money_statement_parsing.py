from models.document import DocumentType, ExtractionResult, PayslipSummary
from models.unified_profile import AssessmentReadiness
from utils.document_readiness import DocumentReadinessEvaluator
from utils.profile_builder import ProfileBuilder
from utils.transaction_parser import TransactionParser


SAMPLE_MOBILE_MONEY_STATEMENT = """Emmanuel Bwanga
Balance statement for the period 975532065
15 Feb 2026 to 15 Mar 2026
Summary
Transaction Type Amount(ZMW)
Total Money Debited 657.22
Total Money Credited 324
Opening Balance 0.01
Closing Balance 132.96
Detailed Statement
Date & Time Details Credited Debited Balance
27/02/26
09:12 AM
Money Deposit to NFS SETTLEMENT ACCOUNT
(CI260227.0912.A46378)
150--150.01
27/02/26
09:12 AM
Loan Repayment to FIKILIZA ZM
(LR260227.0912.C27487)--150 0.01
01/03/26
22:10 PM
Money Sent to John Mwiza
(PP260301.2210.U50853)--100.74 365.44
02/03/26
14:30 PM
Money Sent to GEORGE MSAPENDA
(PP260302.1430.R26042)--11.74 353.7
02/03/26
23:42 PM
Money Sent to Airtel Networks Zambia Plc
(LP260302.2342.S11964)--10 343.7
03/03/26
13:47 PM
Money Sent to KELLY MUSONDA
(PP260303.1347.W91172)--19.74 323.96
04/03/26
13:42 PM
Money Sent to IZWE ZAMBIA
(MP260304.1342.C07219)--79.4 244.56
04/03/26
13:50 PM
Money Sent to KELLY MUSONDA
(PP260304.1350.T62498)
21--265.56
05/03/26
14:15 PM
Money Sent to MUFALALI PUMULO
(PP260305.1415.S35825)--25.74 239.82
05/03/26
16:03 PM
Money Sent to Airtel Networks Zambia Plc
(LP260305.1603.S10671)--10 229.82
06/03/26
17:04 PM
Money Sent to MUFALALI PUMULO
(PP260306.1704.K93350)
153--382.82
06/03/26
22:56 PM
Money Sent to Airtel Networks Zambia Plc
(LP260306.2256.W48772)--10 372.82
07/03/26
12:42 PM
Money Sent to nelly simayumbula
(PP260307.1242.W45129)--26.74 346.08
07/03/26
17:40 PM
Money Sent to Airtel Networks Zambia Plc
(LP260307.1740.R80010)--10 336.08
08/03/26
11:13 AM
Money Withdrawn from Juvenal Sabimana
(CO260308.1113.U02858)--32.5 303.58
08/03/26
12:25 PM
Money Sent to Airtel Networks Zambia Plc
(LP260308.1225.W86594)--2 301.58
08/03/26
20:03 PM
Money Sent to Airtel Networks Zambia Plc
(LP260308.2003.A42366)--10 291.58
09/03/26
15:40 PM
Money Sent to Airtel Networks Zambia Plc
(LP260309.1540.S57010)--10 281.58
09/03/26
16:47 PM
Money Withdrawn from PHYLLIS KAUNDA
(CO260309.1647.W54213)--37.5 244.08
10/03/26
07:52 AM
Money Sent to Airtel Networks Zambia Plc
(LP260310.0752.O39503)--6 238.08
10/03/26
15:29 PM
Money Sent to Airtel Networks Zambia Plc
(LP260310.1529.P08015)--2 236.08
10/03/26
21:55 PM
Money Sent to Airtel Networks Zambia Plc
(LP260310.2155.P80066)--10 226.08
11/03/26
15:36 PM
Money Sent to Airtel Networks Zambia Plc
(LP260311.1536.O41143)--2 224.08
11/03/26
16:29 PM
Money Sent to Airtel Networks Zambia Plc
(MP260311.1629.C75666)--2 222.08
12/03/26
10:40 AM
Money Sent to Airtel Networks Zambia Plc
(LP260312.1040.T88254)--10 212.08
12/03/26
14:09 PM
Money Sent to nelly simayumbula
(PP260312.1409.S16015)--7.74 204.34
12/03/26
22:04 PM
Money Sent to MERCY CHUNGA
(PP260312.2204.L90878)--15.74 188.6
13/03/26
12:32 PM
Money Sent to Airtel Networks Zambia Plc
(MP260313.1232.J82075)--5 183.6
13/03/26
13:33 PM
Money Sent to IZWE ZAMBIA
(MP260313.1333.F61758)--11.9 171.7
13/03/26
14:13 PM
Money Sent to MUFALALI PUMULO
(PP260313.1413.Q36871)--16.74 154.96
13/03/26
15:10 PM
Money Sent to Airtel Networks Zambia Plc
(LP260313.1510.V41431)--10 144.96
14/03/26
12:21 PM
Money Sent to Airtel Networks Zambia Plc
(LP260314.1221.Q69901)--10 134.96
14/03/26 Money Sent to Airtel Networks Zambia Plc --2 132.96
12:37 PM
(MP260314.1237.Q22627)
Need Help? call 1800 | For self-help dial *000# | Terms and condition appl
"""


def test_mobile_money_statement_parser_extracts_summary_and_transactions():
    parser = TransactionParser()
    result = parser.parse(
        SAMPLE_MOBILE_MONEY_STATEMENT.encode("utf-8"),
        "airtel-mobile-money.txt",
        document_hint="mobile_money",
    )

    assert result.document_type == DocumentType.MOBILE_MONEY
    assert len(result.transactions) >= 30
    assert result.bank_statement_summary is not None
    assert result.bank_statement_summary.account_holder_name == "Emmanuel Bwanga"
    assert result.bank_statement_summary.bank_name == "Airtel Money"
    assert result.bank_statement_summary.currency == "ZMW"
    assert result.bank_statement_summary.opening_balance == 0.01
    assert result.bank_statement_summary.closing_balance == 132.96
    assert result.bank_statement_summary.total_money_in == 324.0
    assert result.bank_statement_summary.total_money_out == 657.22
    assert result.bank_statement_summary.statement_period.start == "2026-02-15"
    assert result.bank_statement_summary.statement_period.end == "2026-03-15"


def test_mobile_money_statement_counts_as_required_statement_document():
    parser = TransactionParser()
    mobile_result = parser.parse(
        SAMPLE_MOBILE_MONEY_STATEMENT.encode("utf-8"),
        "airtel-mobile-money.txt",
        document_hint="mobile_money",
    )
    payslip_result = ExtractionResult(
        document_type=DocumentType.PAYSLIP,
        confidence=0.95,
        payslip_summary=PayslipSummary(
            employee_name="Emmanuel Bwanga",
            employer_name="Hytel",
            gross_pay=6100.0,
            net_pay=5564.5,
            deductions=535.5,
            currency="ZMW",
            pay_frequency="MONTHLY",
            document_confidence=0.95,
        ),
    )

    readiness = DocumentReadinessEvaluator.evaluate(
        [mobile_result, payslip_result],
        transactions=mobile_result.transactions,
    )
    profile = ProfileBuilder.build(
        [mobile_result, payslip_result],
        transactions=mobile_result.transactions,
    )

    assert readiness["readiness"] is True
    assert profile.assessment_readiness == AssessmentReadiness.READY
    assert "MOBILE_MONEY" in profile.source_documents
