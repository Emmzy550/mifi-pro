from typing import Dict, List, Optional, Tuple


CountryProfile = Dict[str, object]


COUNTRY_PROFILES: Dict[str, CountryProfile] = {
    "zambia": {
        "signals": {
            "NAPSA": 4,
            "NHIMA": 4,
            "TPIN": 3,
            "NRC:": 3,
            "ZMW": 2,
            "ZRA": 2,
        },
        "currency_codes": ["ZMW"],
        "currency_symbols": [],
        "gross_labels": ["EMOLUMENTS", "GROSS EMOLUMENTS"],
        "net_labels": ["NET PAYABLE", "AMOUNT PAYABLE"],
        "deduction_labels": ["STATUTORY DEDUCTIONS", "TOTAL STATUTORY DEDUCTIONS"],
        "deduction_tokens": ["NAPSA", "NHIMA", "PAYE", "ZRA"],
        "employee_labels": ["NAME", "EMPLOYEE NAME"],
        "employer_labels": ["EMPLOYER", "COMPANY"],
    },
    "kenya": {
        "signals": {
            "KRA": 4,
            "PIN NO": 3,
            "NHIF": 3,
            "NSSF": 3,
            "SHA": 3,
            "KES": 2,
            "HELB": 2,
            "HOUSING LEVY": 2,
        },
        "currency_codes": ["KES"],
        "currency_symbols": [],
        "gross_labels": ["TAXABLE PAY", "TOTAL TAXABLE PAY"],
        "net_labels": ["NET SALARY", "PAY THIS PERIOD"],
        "deduction_labels": ["STATUTORY DEDUCTIONS", "TOTAL TAX"],
        "deduction_tokens": ["KRA", "NHIF", "NSSF", "HELB", "SHA", "HOUSING LEVY", "PAYE"],
        "employee_labels": ["EMPLOYEE NAME", "STAFF NAME", "NAME"],
        "employer_labels": ["EMPLOYER", "COMPANY", "ORGANISATION"],
    },
    "south_africa": {
        "signals": {
            "SARS": 4,
            "UIF": 4,
            "SDL": 3,
            "IRP5": 3,
            "ZAR": 2,
            "PAYE": 1,
            "TAX NUMBER": 2,
        },
        "currency_codes": ["ZAR"],
        "currency_symbols": ["R"],
        "gross_labels": ["COST TO COMPANY", "TOTAL PACKAGE", "TAXABLE INCOME"],
        "net_labels": ["NETT PAY", "PAY THIS PERIOD"],
        "deduction_labels": ["TOTAL DEDUCTIONS", "STATUTORY DEDUCTIONS"],
        "deduction_tokens": ["SARS", "UIF", "SDL", "PAYE"],
        "employee_labels": ["EMPLOYEE NAME", "STAFF NAME", "EMPLOYEE"],
        "employer_labels": ["EMPLOYER", "COMPANY"],
    },
    "india": {
        "signals": {
            "PAN": 3,
            "UAN": 3,
            "EPF": 4,
            "ESIC": 3,
            "TDS": 3,
            "INR": 2,
            "CTC": 2,
            "PROFESSIONAL TAX": 2,
        },
        "currency_codes": ["INR"],
        "currency_symbols": ["\u20B9"],
        "gross_labels": ["CTC", "GROSS CTC", "EARNED GROSS", "TOTAL EARNINGS"],
        "net_labels": ["IN HAND SALARY", "TAKE HOME PAY", "NET PAYABLE"],
        "deduction_labels": ["TOTAL DEDUCTIONS", "PRE-TAX DEDUCTIONS", "POST-TAX DEDUCTIONS"],
        "deduction_tokens": ["EPF", "PF", "ESIC", "TDS", "PROFESSIONAL TAX", "PT"],
        "employee_labels": ["EMPLOYEE NAME", "ASSOCIATE NAME", "EMP NAME", "NAME"],
        "employer_labels": ["EMPLOYER", "COMPANY", "ORGANIZATION"],
    },
    "uk": {
        "signals": {
            "HMRC": 4,
            "NI NUMBER": 4,
            "NATIONAL INSURANCE": 3,
            "TAX CODE": 3,
            "P60": 2,
            "P45": 2,
            "GBP": 2,
            "\u00A3": 2,
        },
        "currency_codes": ["GBP"],
        "currency_symbols": ["\u00A3"],
        "gross_labels": ["TAXABLE PAY", "TOTAL GROSS", "GROSS FOR TAX"],
        "net_labels": ["NET FOR PAY PERIOD", "PAY THIS MONTH", "NET PAY"],
        "deduction_labels": ["TOTAL DEDUCTIONS", "TOTAL TAX", "TOTAL NI"],
        "deduction_tokens": ["HMRC", "NATIONAL INSURANCE", "NI", "STUDENT LOAN", "PENSION"],
        "employee_labels": ["EMPLOYEE NAME", "NAME"],
        "employer_labels": ["EMPLOYER", "COMPANY"],
    },
}


def detect_country_profile(text: str) -> Optional[Tuple[str, CountryProfile]]:
    text_upper = text.upper()
    best_key: Optional[str] = None
    best_score = 0

    for key, profile in COUNTRY_PROFILES.items():
        signals = profile.get("signals", {})
        score = 0
        for token, weight in signals.items():
            if token in text_upper:
                score += int(weight)
        if score > best_score:
            best_score = score
            best_key = key

    if not best_key:
        return None
    if best_score < 3:
        return None
    return best_key, COUNTRY_PROFILES[best_key]


def profile_terms(profile: Optional[CountryProfile], key: str) -> List[str]:
    if not profile:
        return []
    terms = profile.get(key, [])
    if not isinstance(terms, list):
        return []
    return [str(t) for t in terms]
