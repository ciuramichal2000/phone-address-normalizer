"""Polish postal codes (kod pocztowy): NN-NNN.

Forms and spreadsheet imports often lose the hyphen ("00950") or replace it
with a space or a typographic dash, so the common repair is writing the
canonical hyphen back.
"""

import re
from dataclasses import dataclass

from ._chars import DASHES
from .reasons import Reason

_CODE = re.compile(rf"([0-9]{{2}})\s*[{DASHES}]?\s*([0-9]{{3}})")
_COUNTRY_PREFIX = re.compile(rf"PL[{DASHES}\s]*", re.IGNORECASE)
_DISALLOWED_CHARACTER = re.compile(rf"[^0-9{DASHES}\s]")


@dataclass(frozen=True)
class PostalResult:
    """Outcome of normalising one postal code.

    `value` is the canonical "NN-NNN" form, or None when rejected; `reasons`
    is empty when the code was accepted.
    """

    original: str
    valid: bool
    value: str | None
    reasons: tuple[Reason, ...]


def normalize_postal_code_pl(raw: str) -> PostalResult:
    """Normalise a Polish postal code to "NN-NNN".

    Accepts the digits with no separator, with a space or any dash between the
    two groups, and an optional leading "PL" country marker. Only the shape is
    checked: whether the code is actually assigned to a post office is not.

    Raises TypeError if `raw` is not a string; malformed codes come back with
    `valid=False` and the reasons.
    """
    if not isinstance(raw, str):
        raise TypeError(f"postal code must be a string, got {type(raw).__name__}")

    text = raw.strip()
    if not text:
        return PostalResult(raw, False, None, (Reason.EMPTY,))

    prefix = _COUNTRY_PREFIX.match(text)
    if prefix:
        text = text[prefix.end():]

    match = _CODE.fullmatch(text)
    if match:
        return PostalResult(raw, True, f"{match[1]}-{match[2]}", ())

    if _DISALLOWED_CHARACTER.search(text):
        reason = Reason.INVALID_CHARACTERS
    elif sum(ch in "0123456789" for ch in text) != 5:
        reason = Reason.WRONG_LENGTH
    else:
        # Five digits but separated in the wrong place, e.g. "009-50".
        reason = Reason.INVALID_FORMAT
    return PostalResult(raw, False, None, (reason,))
