import re


def normalize_az_phone_number(phone: str) -> str:
    """Normalize an Azerbaijani phone number to +994XXXXXXXXX format."""
    digits = re.sub(r"[^\d+]", "", phone.strip())
    if digits.startswith("+994") and len(digits) == 13:
        return digits
    only_digits = re.sub(r"\D", "", digits)
    if only_digits.startswith("994") and len(only_digits) == 12:
        return f"+{only_digits}"
    if only_digits.startswith("0") and len(only_digits) == 10:
        return f"+994{only_digits[1:]}"
    if len(only_digits) == 9:
        return f"+994{only_digits}"
    return phone.strip()


def is_valid_az_phone_number(phone: str) -> bool:
    """Validate whether a phone number matches the Azerbaijani +994 (XX) XXX-XX-XX format."""
    normalized = normalize_az_phone_number(phone)
    return bool(re.match(r"^\+994(10|50|51|55|60|70|77|99|12)\d{7}$", normalized))

