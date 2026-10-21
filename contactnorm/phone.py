"""Phone-number normalisation to E.164 for Poland, US/Canada and the UK.

Contact lists mix "0048 501-234-567", "(22) 123 45 67" and "+44 (0)20 ..."
in one column. This module turns each of them into one canonical E.164 string
or says precisely why it cannot. Only these numbering plans are implemented;
anything else is rejected instead of being guessed at.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple

from ._chars import DASHES
from .reasons import Reason

SUPPORTED_REGIONS = ("PL", "US", "CA", "GB")

# Country calling code and length of the national significant number (the
# digits after the country code and any trunk prefix) per default region.
_PLANS = {
    "PL": ("48", 9),
    "GB": ("44", 10),
    "US": ("1", 10),
    "CA": ("1", 10),
}
_CALLING_CODES = ("48", "44", "1")

# Polish mobile ranges and geographic (landline) area codes. Type is decided
# by these two-digit prefixes only; anything else is reported as unknown
# because new ranges are allocated over time and guessing would be worse.
_PL_MOBILE_PREFIXES = frozenset(
    {"45", "50", "51", "53", "57", "60", "66", "69", "72", "73", "78", "79", "88"}
)
_PL_LANDLINE_AREA_CODES = frozenset(
    {
        "12", "13", "14", "15", "16", "17", "18",
        "22", "23", "24", "25", "29",
        "32", "33", "34",
        "41", "42", "43", "44", "46", "48",
        "52", "54", "55", "56", "58", "59",
        "61", "62", "63", "65", "67", "68",
        "71", "74", "75", "76", "77",
        "81", "82", "83", "84", "85", "86", "87", "89",
        "91", "94", "95",
    }
)

# Canadian NANP area codes (a snapshot; newer overlays may be missing and
# would then be labelled "US"). All other +1 numbers are labelled "US".
_CANADIAN_AREA_CODES = frozenset(
    {
        "204", "226", "236", "249", "250", "263", "289", "306", "343", "354",
        "365", "367", "368", "382", "403", "416", "418", "428", "431", "437",
        "438", "450", "468", "474", "506", "514", "519", "548", "579", "581",
        "584", "587", "604", "613", "639", "647", "672", "683", "705", "709",
        "742", "753", "778", "780", "782", "807", "819", "825", "867", "873",
        "879", "902", "905", "942",
    }
)

_DISALLOWED_CHARACTER = re.compile(rf"[^0-9+()./\s{DASHES}]")
_NON_DIGIT = re.compile(r"[^0-9]")


class LineType(StrEnum):
    """Best guess at the kind of line, from the number prefix alone."""

    MOBILE = "mobile"
    LANDLINE = "landline"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PhoneResult:
    """Outcome of normalising one phone number.

    `e164` and `country` are None when the number was rejected; `reasons`
    is empty when it was accepted.
    """

    original: str
    valid: bool
    e164: str | None
    country: str | None
    line_type: LineType
    reasons: tuple[Reason, ...]


class _Check(NamedTuple):
    country: str | None
    line_type: LineType
    significant: str
    reasons: tuple[Reason, ...]


def normalize_phone(raw: str, default_region: str = "PL") -> PhoneResult:
    """Normalise `raw` to E.164.

    Numbers written with a leading "+" or "00" carry their own country code.
    Anything else is read as a national number of `default_region`, and may
    also start with that region's country code written without "+".

    Raises TypeError if `raw` is not a string and ValueError if
    `default_region` is not one of SUPPORTED_REGIONS. A number that merely
    looks wrong is not an exception: it comes back with `valid=False` and the
    reasons, because rejected numbers are routine in dirty data.
    """
    if not isinstance(raw, str):
        raise TypeError(f"phone number must be a string, got {type(raw).__name__}")
    if default_region not in _PLANS:
        raise ValueError(
            f"unsupported region {default_region!r}; use one of {SUPPORTED_REGIONS}"
        )

    text = raw.strip()
    if not text:
        return _rejected(raw, Reason.EMPTY)

    problems = _character_problems(text)
    if problems:
        return _rejected(raw, *problems)

    digits = _NON_DIGIT.sub("", text)
    if not digits:
        return _rejected(raw, Reason.NO_DIGITS)

    split = _split_calling_code(text, digits, default_region)
    if split is None:
        return _rejected(raw, Reason.UNSUPPORTED_COUNTRY_CODE)
    calling_code, national = split

    check = _CHECKS[calling_code](national)
    if check.reasons:
        return _rejected(raw, *check.reasons)
    return PhoneResult(
        original=raw,
        valid=True,
        e164=f"+{calling_code}{check.significant}",
        country=check.country,
        line_type=check.line_type,
        reasons=(),
    )


def _rejected(raw: str, *reasons: Reason) -> PhoneResult:
    return PhoneResult(raw, False, None, None, LineType.UNKNOWN, tuple(reasons))


def _character_problems(text: str) -> list[Reason]:
    """Find characters that make the input ambiguous before any digit parsing.

    Letters are reported separately because "1-800-FLOWERS" and "ext. 12"
    are a different problem from stray symbols: they cannot be mapped to
    digits safely, so such numbers are rejected rather than half-parsed.
    """
    problems: list[Reason] = []
    if any(ch.isalpha() for ch in text):
        problems.append(Reason.LETTERS)
    if "+" in text[1:]:
        problems.append(Reason.MISPLACED_PLUS)
    without_letters = "".join(ch for ch in text if not ch.isalpha())
    if _DISALLOWED_CHARACTER.search(without_letters):
        problems.append(Reason.INVALID_CHARACTERS)
    if not _parentheses_balanced(text):
        problems.append(Reason.UNBALANCED_PARENTHESES)
    return problems


def _parentheses_balanced(text: str) -> bool:
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _split_calling_code(
    text: str, digits: str, default_region: str
) -> tuple[str, str] | None:
    """Return (calling code, national digits), or None for an unknown code."""
    if text.startswith("+"):
        international = digits
    elif digits.startswith("00"):
        international = digits[2:]
    else:
        code, national_length = _PLANS[default_region]
        # "48501234567" is the country code written without "+". Matching on
        # total length keeps a 9-digit Polish number that happens to begin
        # with 48 (the Radom area code) from being misread.
        if len(digits) == len(code) + national_length and digits.startswith(code):
            international = digits
        else:
            return code, digits
    for code in _CALLING_CODES:
        if international.startswith(code):
            return code, international[len(code):]
    return None


def _check_pl(national: str) -> _Check:
    reasons: list[Reason] = []
    if len(national) != 9:
        reasons.append(Reason.WRONG_LENGTH)
    if national.startswith("0"):
        # Poland has no trunk prefix, so a leading 0 is never legitimate.
        reasons.append(Reason.INVALID_LEADING_DIGIT)
    prefix = national[:2]
    if prefix in _PL_MOBILE_PREFIXES:
        line_type = LineType.MOBILE
    elif prefix in _PL_LANDLINE_AREA_CODES:
        line_type = LineType.LANDLINE
    else:
        line_type = LineType.UNKNOWN
    return _Check("PL", line_type, national, tuple(reasons))


def _check_gb(national: str) -> _Check:
    # The national trunk prefix "0" is dropped in E.164. It is also dropped
    # when it appears right after the country code, as in "+44 (0)20 ...".
    significant = national[1:] if national.startswith("0") else national
    reasons: list[Reason] = []
    if len(significant) != 10:
        reasons.append(Reason.WRONG_LENGTH)
    if not significant or significant[0] not in "1235789":
        # Ranges 04 and 06 are unallocated; a second leading 0 is never valid.
        reasons.append(Reason.INVALID_LEADING_DIGIT)
    if significant[:1] == "7" and significant[1:2] not in ("0", "6"):
        line_type = LineType.MOBILE  # 070 is personal numbering, 076 pagers
    elif significant[:1] in ("1", "2"):
        line_type = LineType.LANDLINE
    else:
        line_type = LineType.UNKNOWN
    return _Check("GB", line_type, significant, tuple(reasons))


def _check_nanp(national: str) -> _Check:
    """North American Numbering Plan: NXX-NXX-XXXX with N in 2-9."""
    if len(national) != 10:
        return _Check(None, LineType.UNKNOWN, national, (Reason.WRONG_LENGTH,))
    area, exchange = national[:3], national[3:6]
    reasons: list[Reason] = []
    if area[0] in "01" or area[1:] == "11":
        reasons.append(Reason.INVALID_AREA_CODE)  # N11 codes are service codes
    if exchange[0] in "01" or exchange[1:] == "11":
        reasons.append(Reason.INVALID_EXCHANGE_CODE)
    country = "CA" if area in _CANADIAN_AREA_CODES else "US"
    return _Check(country, LineType.UNKNOWN, national, tuple(reasons))


_CHECKS = {"48": _check_pl, "44": _check_gb, "1": _check_nanp}
