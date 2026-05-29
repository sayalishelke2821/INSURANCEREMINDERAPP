"""
whatsapp.py
Generates WhatsApp Click-to-Chat URLs (https://wa.me/...) with a pre-filled,
personalized reminder message. The agent clicks the link to open WhatsApp Web
or the WhatsApp mobile app, then taps Send to deliver the message.

Docs: https://faq.whatsapp.com/5913398998672934
"""

from datetime import datetime
from urllib.parse import quote


# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_TEMPLATE = (
    "Dear {owner},\n\n"
    "This is a friendly reminder that your vehicle insurance is due for renewal.\n\n"
    "*Vehicle Number:* {vehicle}\n"
    "*Policy Number:* {policy}\n"
    "*Renewal Date:* {renewal}\n"
    "*Premium Amount:* Rs. {premium}\n"
    "*Status:* {days}\n\n"
    "Please renew before the due date to avoid policy lapse.\n\n"
    "For any queries, feel free to contact us.\n\n"
    "Thank you,\n"
    "Rahane Insurance Agency"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_mobile(mobile: str) -> str:
    """Normalize an Indian mobile number to digits-only with country code 91."""
    digits = "".join(c for c in mobile if c.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        return digits
    if digits.startswith("0") and len(digits) == 11:
        return "91" + digits[1:]
    if len(digits) == 10:
        return "91" + digits
    return digits


def _days_remaining(renewal_date: str) -> int | None:
    try:
        return (datetime.strptime(renewal_date, "%d/%m/%Y").date() - datetime.now().date()).days
    except (ValueError, TypeError):
        return None


def _format_premium(value) -> str:
    """Format premium amount with Indian comma style."""
    try:
        return f"{int(float(value)):,}"
    except (ValueError, TypeError):
        return str(value) if value else "N/A"


# ── Public API ────────────────────────────────────────────────────────────────

def build_reminder_message(record: dict) -> str:
    """
    Build the personalized reminder text from a record using the template
    configured in the database. Supported placeholders:
        {owner}    – Owner name
        {vehicle}  – Vehicle number
        {policy}   – Policy number
        {renewal}  – Renewal date
        {premium}  – Premium amount (comma-formatted)
        {days}     – Days remaining text
        {chassis}  – Chassis number
        {engine}   – Engine number
        {model}    – Vehicle make/model
        {office}   – Issuing office
        {due}      – Payment due date
    """
    try:
        from database import get_setting
        template = get_setting("message_template", DEFAULT_TEMPLATE) or DEFAULT_TEMPLATE
    except Exception:
        template = DEFAULT_TEMPLATE

    owner    = record.get("owner_name")        or "Customer"
    vehicle  = record.get("vehicle_number")    or "N/A"
    policy   = record.get("policy_number")     or "N/A"
    renewal  = record.get("renewal_date")      or "N/A"
    premium  = _format_premium(record.get("premium_amount"))
    chassis  = record.get("chassis_number")    or "N/A"
    engine   = record.get("engine_number")     or "N/A"
    model    = record.get("vehicle_make_model") or "N/A"
    office   = record.get("issuing_office")    or "N/A"
    due      = record.get("payment_due_date")  or renewal

    days = _days_remaining(renewal)
    if days is None:
        days_text = "Renewal due soon"
    elif days < 0:
        days_text = f"Overdue by {abs(days)} day(s)"
    elif days == 0:
        days_text = "Due today!"
    else:
        days_text = f"Due in {days} day(s)"

    try:
        return template.format(
            owner=owner, vehicle=vehicle, policy=policy, renewal=renewal,
            premium=premium, days=days_text, chassis=chassis, engine=engine,
            model=model, office=office, due=due,
        )
    except (KeyError, IndexError):
        return DEFAULT_TEMPLATE.format(
            owner=owner, vehicle=vehicle, policy=policy, renewal=renewal,
            premium=premium, days=days_text,
        )


def build_whatsapp_url(record: dict) -> dict:
    """
    Build a wa.me click-to-chat URL with the pre-filled personalized message.

    Returns:
      {"success": True,  "url": "https://wa.me/...", "message": "..."}
      {"success": False, "error": "..."}
    """
    mobile_raw = (record.get("mobile_number") or "").strip()
    if not mobile_raw:
        return {"success": False, "error": "No mobile number for this record"}

    mobile = _normalize_mobile(mobile_raw)
    if not mobile:
        return {"success": False, "error": "Invalid mobile number"}

    message = build_reminder_message(record)
    url     = f"https://wa.me/{mobile}?text={quote(message)}"

    return {"success": True, "url": url, "message": message}
