"""Clean a whole messy contact record and report exactly what changed."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, NamedTuple

from .emails import check_email
from .phone import SUPPORTED_REGIONS, normalize_phone
from .postal import normalize_postal_code_pl
from .reasons import Reason


class ChangeKind(StrEnum):
    """What kind of edit a Change represents."""

    WHITESPACE = "whitespace"
    PHONE_E164 = "phone_e164"
    POSTAL_FORMAT = "postal_format"
    EMAIL_NORMALISED = "email_normalised"


@dataclass(frozen=True)
class Change:
    """A value that was rewritten."""

    field: str
    before: str
    after: str
    kind: ChangeKind


@dataclass(frozen=True)
class Issue:
    """A value that was left as-is because it is invalid or doubtful.

    `suggestion` carries a proposed replacement when there is one (currently
    only for likely e-mail domain typos).
    """

    field: str
    value: Any
    reasons: tuple[Reason, ...]
    suggestion: str | None = None


class CleanResult(NamedTuple):
    """The cleaned record plus an audit trail of what was done to it."""

    record: dict[str, Any]
    changes: list[Change]
    issues: list[Issue]


class _Outcome(NamedTuple):
    value: str
    kind: ChangeKind
    issues: tuple[Issue, ...]


def clean_record(
    record: Mapping[str, Any],
    *,
    default_region: str = "PL",
    phone_fields: tuple[str, ...] = ("phone",),
    postal_fields: tuple[str, ...] = ("postal_code",),
    email_fields: tuple[str, ...] = ("email",),
) -> CleanResult:
    """Return a cleaned copy of `record`, the changes made and the problems found.

    - Phone fields are rewritten to E.164 (national numbers are read in
      `default_region`), postal fields to "NN-NNN", e-mail fields to trimmed
      lower case.
    - Every other text value only gets whitespace trimmed and collapsed.
    - A managed value that fails validation is kept exactly as it came in and
      reported as an Issue, so cleaning never destroys data it cannot repair.
      A likely e-mail typo is likewise reported with a suggestion, not applied.
    - Blank managed fields become "" without an Issue (absent is not invalid);
      None and non-text values pass through, and a non-text value in a
      managed field is reported as NOT_TEXT.

    The input mapping is never modified. Raises TypeError if `record` is not a
    mapping and ValueError for an unsupported `default_region`.
    """
    if not isinstance(record, Mapping):
        raise TypeError(f"record must be a mapping, got {type(record).__name__}")
    if default_region not in SUPPORTED_REGIONS:
        raise ValueError(
            f"unsupported region {default_region!r}; use one of {SUPPORTED_REGIONS}"
        )

    managed = {*phone_fields, *postal_fields, *email_fields}
    cleaned: dict[str, Any] = {}
    changes: list[Change] = []
    issues: list[Issue] = []

    for field, value in record.items():
        if not isinstance(value, str):
            cleaned[field] = value
            if value is not None and field in managed:
                issues.append(Issue(field, value, (Reason.NOT_TEXT,)))
            continue

        collapsed = " ".join(value.split())
        if not collapsed or field not in managed:
            outcome = _Outcome(collapsed, ChangeKind.WHITESPACE, ())
        elif field in phone_fields:
            outcome = _clean_phone(field, value, default_region)
        elif field in postal_fields:
            outcome = _clean_postal(field, value)
        else:
            outcome = _clean_email(field, value)

        cleaned[field] = outcome.value
        issues.extend(outcome.issues)
        if outcome.value != value:
            changes.append(Change(field, value, outcome.value, outcome.kind))

    return CleanResult(cleaned, changes, issues)


def _clean_phone(field: str, value: str, region: str) -> _Outcome:
    result = normalize_phone(value, region)
    kind = ChangeKind.PHONE_E164
    if not result.valid:
        return _Outcome(value, kind, (Issue(field, value, result.reasons),))
    return _Outcome(result.e164, kind, ())


def _clean_postal(field: str, value: str) -> _Outcome:
    result = normalize_postal_code_pl(value)
    kind = ChangeKind.POSTAL_FORMAT
    if not result.valid:
        return _Outcome(value, kind, (Issue(field, value, result.reasons),))
    return _Outcome(result.value, kind, ())


def _clean_email(field: str, value: str) -> _Outcome:
    result = check_email(value)
    kind = ChangeKind.EMAIL_NORMALISED
    if not result.valid:
        return _Outcome(value, kind, (Issue(field, value, result.reasons),))
    found: tuple[Issue, ...] = ()
    if result.suggestion:
        found = (Issue(field, value, (Reason.LIKELY_TYPO,), result.suggestion),)
    return _Outcome(result.normalized, kind, found)
