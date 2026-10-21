"""Machine-readable reasons shared by every validator in the package."""

from enum import StrEnum


class Reason(StrEnum):
    """Why a value was rejected or flagged.

    Short codes instead of prose, so callers can branch on them and tests do
    not depend on wording. They are strings, so they serialise to JSON as-is.
    """

    # Shared by several validators.
    EMPTY = "empty"
    NOT_TEXT = "not_text"
    INVALID_CHARACTERS = "invalid_characters"
    WRONG_LENGTH = "wrong_length"
    INVALID_FORMAT = "invalid_format"

    # Phone numbers.
    NO_DIGITS = "no_digits"
    LETTERS = "letters"
    MISPLACED_PLUS = "misplaced_plus"
    UNBALANCED_PARENTHESES = "unbalanced_parentheses"
    UNSUPPORTED_COUNTRY_CODE = "unsupported_country_code"
    INVALID_LEADING_DIGIT = "invalid_leading_digit"
    INVALID_AREA_CODE = "invalid_area_code"
    INVALID_EXCHANGE_CODE = "invalid_exchange_code"

    # E-mail addresses.
    CONTAINS_WHITESPACE = "contains_whitespace"
    MISSING_AT = "missing_at"
    MULTIPLE_AT = "multiple_at"
    EMPTY_LOCAL_PART = "empty_local_part"
    LOCAL_PART_TOO_LONG = "local_part_too_long"
    EMPTY_DOMAIN = "empty_domain"
    DOMAIN_WITHOUT_DOT = "domain_without_dot"
    ADDRESS_TOO_LONG = "address_too_long"
    LIKELY_TYPO = "likely_typo"
