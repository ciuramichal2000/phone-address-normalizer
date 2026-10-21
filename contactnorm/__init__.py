"""contactnorm: normalise and validate phone numbers, postal codes and e-mails."""

from .emails import EmailResult, check_email
from .phone import SUPPORTED_REGIONS, LineType, PhoneResult, normalize_phone
from .postal import PostalResult, normalize_postal_code_pl
from .reasons import Reason
from .record import Change, ChangeKind, CleanResult, Issue, clean_record

__all__ = [
    "SUPPORTED_REGIONS",
    "Change",
    "ChangeKind",
    "CleanResult",
    "EmailResult",
    "Issue",
    "LineType",
    "PhoneResult",
    "PostalResult",
    "Reason",
    "check_email",
    "clean_record",
    "normalize_phone",
    "normalize_postal_code_pl",
]
