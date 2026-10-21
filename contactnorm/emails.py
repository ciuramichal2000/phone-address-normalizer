"""Pragmatic e-mail syntax checking with common-typo suggestions.

This is deliberately not RFC 5322: quoted local parts, comments, IP-literal
domains and internationalised domains are all rejected. The goal is to catch
what really goes wrong in contact data, not to accept every legal address.
A syntactically valid address is also not proof that the mailbox exists.
"""

import re
from dataclasses import dataclass

from .reasons import Reason

MAX_ADDRESS_LENGTH = 254
MAX_LOCAL_PART_LENGTH = 64

_LOCAL_CHAR = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]"
_DOMAIN_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_EMAIL = re.compile(
    rf"{_LOCAL_CHAR}+(?:\.{_LOCAL_CHAR}+)*"  # no leading, trailing or double dots
    rf"@(?:{_DOMAIN_LABEL}\.)+[A-Za-z]{{2,63}}"  # at least one dot, alphabetic TLD
)

# Misspelt top-level domains that are not real TLDs, so correcting them is safe.
_TLD_TYPOS = {
    "con": "com",
    "cmo": "com",
    "ocm": "com",
    "vom": "com",
    "coom": "com",
    "comm": "com",
    "lp": "pl",
}

# Misspellings of big mail providers, keyed by the typo with a correct ".com".
_DOMAIN_TYPOS = {
    "gmial.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gmil.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmeil.com": "gmail.com",
    "gmail.co": "gmail.com",
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "yahou.com": "yahoo.com",
    "hotmial.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "homail.com": "hotmail.com",
    "hotnail.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "otlook.com": "outlook.com",
    "outlookk.com": "outlook.com",
    "iclod.com": "icloud.com",
    "icoud.com": "icloud.com",
    "iclould.com": "icloud.com",
}


@dataclass(frozen=True)
class EmailResult:
    """Outcome of checking one e-mail address.

    `normalized` is the trimmed, lower-cased address (None when invalid).
    `suggestion` is a corrected address when the domain looks like a typo of
    a well-known one; the address is still `valid` because the typo is
    syntactically fine and only a human can confirm the fix.
    """

    original: str
    valid: bool
    normalized: str | None
    suggestion: str | None
    reasons: tuple[Reason, ...]


def check_email(raw: str) -> EmailResult:
    """Validate the syntax of `raw` and suggest a fix for likely domain typos.

    The whole address is lower-cased. Strictly the local part is case
    sensitive, but in practice every mail provider treats it as case
    insensitive and mixed case in contact data is nearly always accidental.

    Raises TypeError if `raw` is not a string; bad addresses come back with
    `valid=False` and the reasons.
    """
    if not isinstance(raw, str):
        raise TypeError(f"e-mail address must be a string, got {type(raw).__name__}")

    text = raw.strip()
    if not text:
        return _invalid(raw, Reason.EMPTY)

    reasons: list[Reason] = []
    if any(ch.isspace() for ch in text):
        reasons.append(Reason.CONTAINS_WHITESPACE)
    at_signs = text.count("@")
    if at_signs == 0:
        reasons.append(Reason.MISSING_AT)
    elif at_signs > 1:
        reasons.append(Reason.MULTIPLE_AT)
    else:
        local, domain = text.split("@")
        if not local:
            reasons.append(Reason.EMPTY_LOCAL_PART)
        elif len(local) > MAX_LOCAL_PART_LENGTH:
            reasons.append(Reason.LOCAL_PART_TOO_LONG)
        if not domain:
            reasons.append(Reason.EMPTY_DOMAIN)
        elif "." not in domain:
            reasons.append(Reason.DOMAIN_WITHOUT_DOT)
    if len(text) > MAX_ADDRESS_LENGTH:
        reasons.append(Reason.ADDRESS_TOO_LONG)
    # The regex is the final arbiter; the checks above only explain *why*
    # common failures fail, so the regex verdict is added only when they
    # found nothing to say.
    if not reasons and not _EMAIL.fullmatch(text):
        reasons.append(Reason.INVALID_FORMAT)
    if reasons:
        return _invalid(raw, *reasons)

    normalized = text.lower()
    return EmailResult(raw, True, normalized, _suggest_fix(normalized), ())


def _invalid(raw: str, *reasons: Reason) -> EmailResult:
    return EmailResult(raw, False, None, None, tuple(reasons))


def _suggest_fix(address: str) -> str | None:
    """Return the address with a mistyped TLD and/or provider domain corrected.

    The TLD is fixed first so "gmial.con" is repaired in two steps to
    "gmail.com". Returns None when nothing needed fixing.
    """
    local, _, domain = address.rpartition("@")
    name, _, tld = domain.rpartition(".")
    candidate = f"{name}.{_TLD_TYPOS.get(tld, tld)}"
    candidate = _DOMAIN_TYPOS.get(candidate, candidate)
    if candidate == domain:
        return None
    return f"{local}@{candidate}"
