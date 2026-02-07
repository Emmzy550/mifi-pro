import re

text = """
STANBIC BANK

Account Holder: JOHN MUKUKA CHILESHE
Branch Name: Lusaka Main
"""

pattern = r'ACCOUNT\s+HOLDER\s*:\s*([A-Za-z][A-Za-z\s\'\-\.]{4,})'
match = re.search(pattern, text, re.IGNORECASE)

if match:
    print(f"Pattern matched: '{match.group(0)}'")
    print(f"Captured: '{match.group(1)}'")
else:
    print("Pattern did NOT match")

# Test with different format
text2 = "Account Holder: JOHN MUKUKA CHILESHE"
match2 = re.search(pattern, text2, re.IGNORECASE)

if match2:
    print(f"\nPattern 2 matched: '{match2.group(0)}'")
    print(f"Captured 2: '{match2.group(1)}'")
else:
    print("\nPattern 2 did NOT match")
