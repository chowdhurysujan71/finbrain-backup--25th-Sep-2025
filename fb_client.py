import os, re, requests

PAGE_TOKEN = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]
GRAPH = "https://graph.facebook.com/v19.0/me/messages"

_psid_re = re.compile(r"^\d{10,}$")  # page-scoped IDs are long numeric strings

def is_valid_psid(psid: str) -> bool:
    if not psid:
        return False
    
    # Check normal PSID format first
    if _psid_re.match(psid):
        return True
    
    # In non-production, allow dev PSIDs from allowlist
    if os.getenv("ENV") != "production":
        from utils.allowlist import is_dev_psid
        if is_dev_psid(psid):
            return True
    
    return False

def send_text(psid: str, text: str):
    if not is_valid_psid(psid):
        raise ValueError(f"Invalid PSID '{psid}'. Must be a numeric page-scoped ID from a real chat.")
    payload = {"recipient": {"id": psid}, "messaging_type": "RESPONSE", "message": {"text": text[:560]}}
    r = requests.post(
        GRAPH,
        params={"access_token": PAGE_TOKEN},
        json=payload,
        timeout=10
    )
    if r.status_code != 200:
        raise RuntimeError(f"FB send failed {r.status_code}: {r.text}")
    return r.json()