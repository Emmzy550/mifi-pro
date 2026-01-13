"""
Validators and Normalizers
Ensures input data is clean and consistent.
"""
import re

def normalize_phone(phone: str) -> str:
    """Basic phone normalization - removes non-numeric characters except +."""
    return re.sub(r"[^\d+]", "", phone)

def validate_income_range(income: float) -> bool:
    """Sanity check for income."""
    return income >= 0 and income < 100000000 # 100M cap for V1

def clean_name(name: str) -> str:
    """Trims and title-cases names."""
    return name.strip().title()
