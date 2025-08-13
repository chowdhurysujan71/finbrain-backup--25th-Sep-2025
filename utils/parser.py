# parser.py - Streamlined hardened expense message parser
import re

# Bengali → ASCII digits
_BN_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_ZERO_WIDTH = r"[\u200B-\u200D\u2060]"
_CURRENCY   = r"[৳$€£₹]"
_NUM        = r"(?:\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"

# Patterns:
# 1) log 250 lunch | spent 120 taxi | add ৳300 groceries
# 2) 250 lunch | ৳250 lunch
# 3) lunch 250 | lunch ৳250
_PATTERNS = [
    rf"^(?:log|spent|add)\s+{_CURRENCY}?\s*(?P<amt>{_NUM})\s+(?P<note>.+)$",
    rf"^{_CURRENCY}?\s*(?P<amt>{_NUM})\s+(?P<note>.+)$",
    rf"^(?P<note>.+?)\s+{_CURRENCY}?\s*(?P<amt>{_NUM})$",
]

def _clean_text(s: str) -> str:
    s = (s or "").translate(_BN_MAP)
    s = re.sub(_ZERO_WIDTH, "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _to_amount(s: str) -> float:
    s = re.sub(_CURRENCY, "", s)
    s = s.replace(",", "")
    return round(float(s), 2)

def parse_expense(msg: str):
    """
    Returns (amount: float, note: str) or None if not parseable.
    Never throws.
    """
    try:
        t = _clean_text(msg)
        for pat in _PATTERNS:
            m = re.match(pat, t, flags=re.IGNORECASE)
            if not m: 
                continue
            amt = _to_amount(m.group("amt"))
            note = (m.group("note") or "").strip(" .-—_/\\|")

            # kill lone decimal artifacts like ".0 " at start (root cause of ".0 coffee")
            note = re.sub(r"^\.(?:0|00)\b\s*", "", note)

            # guard: if note accidentally starts with the amount again (bad split), remove it
            note = re.sub(rf"^({_CURRENCY}?\s*{_NUM})\s+", "", note)

            if not note:
                note = "misc"
            return amt, note
        return None
    except Exception:
        return None