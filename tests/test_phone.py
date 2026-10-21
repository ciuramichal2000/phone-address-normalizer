import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import re

import pytest

from contactnorm import LineType, Reason, normalize_phone


# --- Poland -----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "+48 501 234 567",
        "0048 501-234-567",
        "48501234567",
        "501234567",
        "501 234 567",
        "+48 (501) 234-567",
        "  +48.501.234.567  ",
        "+48 501 234 567",  # non-breaking spaces from a web page
        "+48–501–234–567",  # en dashes from a word processor
        "0048/501/234/567",
    ],
)
def test_every_polish_spelling_of_one_mobile_number_gives_the_same_e164(raw):
    result = normalize_phone(raw)

    assert result.valid
    assert result.e164 == "+48501234567"
    assert result.country == "PL"
    assert result.line_type == LineType.MOBILE
    assert result.reasons == ()
    assert result.original == raw


@pytest.mark.parametrize(
    "raw, expected_e164",
    [
        ("(22) 123-45-67", "+48221234567"),  # Warsaw
        ("+48 12 345 67 89", "+48123456789"),  # Krakow
        ("0048 58 301 23 45", "+48583012345"),  # Gdansk
    ],
)
def test_polish_landlines_are_recognised_by_area_code(raw, expected_e164):
    result = normalize_phone(raw)

    assert result.valid
    assert result.e164 == expected_e164
    assert result.line_type == LineType.LANDLINE


@pytest.mark.parametrize(
    "national, expected_type",
    [
        ("501234567", LineType.MOBILE),
        ("451234567", LineType.MOBILE),
        ("601234567", LineType.MOBILE),
        ("791234567", LineType.MOBILE),
        ("881234567", LineType.MOBILE),
        ("221234567", LineType.LANDLINE),
        ("891234567", LineType.LANDLINE),
        ("801234567", LineType.UNKNOWN),  # 80x toll-free: neither
        ("701234567", LineType.UNKNOWN),
    ],
)
def test_polish_line_type_follows_the_two_digit_prefix(national, expected_type):
    result = normalize_phone(national)

    assert result.valid
    assert result.e164 == "+48" + national
    assert result.line_type == expected_type


def test_nine_digit_polish_number_starting_with_48_is_not_mistaken_for_a_country_code():
    # 48 is the Radom area code. Only 11 digits can mean "country code 48".
    result = normalize_phone("481234567")

    assert result.e164 == "+48481234567"
    assert result.line_type == LineType.LANDLINE


@pytest.mark.parametrize(
    "raw, expected_reasons",
    [
        ("+48 501 234 56", (Reason.WRONG_LENGTH,)),
        ("+48 501 234 5678", (Reason.WRONG_LENGTH,)),
        ("012345678", (Reason.INVALID_LEADING_DIGIT,)),
        ("022 123 45 67", (Reason.WRONG_LENGTH, Reason.INVALID_LEADING_DIGIT)),
        ("+48", (Reason.WRONG_LENGTH,)),
    ],
)
def test_malformed_polish_numbers_are_rejected_with_specific_reasons(
    raw, expected_reasons
):
    result = normalize_phone(raw)

    assert not result.valid
    assert result.e164 is None
    assert result.country is None
    assert result.reasons == expected_reasons


# --- US / Canada ------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, region",
    [
        ("(212) 555-0100", "US"),
        ("212.555.0100", "US"),
        ("1-212-555-0100", "US"),
        ("+1 (212) 555-0100", "CA"),
        ("+1 212 555 0100", "PL"),  # explicit +1 beats the default region
        ("001 212 555 0100", "PL"),  # 00 is the exit code used in Europe
    ],
)
def test_north_american_spellings_normalise_to_one_e164(raw, region):
    result = normalize_phone(raw, default_region=region)

    assert result.valid
    assert result.e164 == "+12125550100"
    assert result.country == "US"
    assert result.line_type == LineType.UNKNOWN  # no prefix rule for NANP


@pytest.mark.parametrize(
    "raw, expected_e164",
    [
        ("(416) 555-0199", "+14165550199"),  # Toronto
        ("+1 604 555 0123", "+16045550123"),  # Vancouver
        ("514-555-0142", "+15145550142"),  # Montreal
    ],
)
def test_canadian_area_codes_are_labelled_canada(raw, expected_e164):
    result = normalize_phone(raw, default_region="CA")

    assert result.e164 == expected_e164
    assert result.country == "CA"


@pytest.mark.parametrize(
    "raw, expected_reasons",
    [
        ("(112) 555-0100", (Reason.INVALID_AREA_CODE,)),  # area code starts with 1
        ("(012) 555-0100", (Reason.INVALID_AREA_CODE,)),  # ... or 0
        ("(911) 555-0100", (Reason.INVALID_AREA_CODE,)),  # N11 service code
        ("(212) 155-0100", (Reason.INVALID_EXCHANGE_CODE,)),
        ("(212) 411-0100", (Reason.INVALID_EXCHANGE_CODE,)),
        (
            "(112) 055-0100",
            (Reason.INVALID_AREA_CODE, Reason.INVALID_EXCHANGE_CODE),
        ),
        ("212 555 010", (Reason.WRONG_LENGTH,)),  # 9 digits
        ("212 555 01000", (Reason.WRONG_LENGTH,)),  # 11 digits, not starting with 1
        ("1 (212) 555-010", (Reason.INVALID_AREA_CODE,)),  # 1 + 9 digits: no country code
    ],
)
def test_invalid_north_american_numbers_are_rejected(raw, expected_reasons):
    result = normalize_phone(raw, default_region="US")

    assert not result.valid
    assert result.e164 is None
    assert result.reasons == expected_reasons


def test_the_default_region_decides_how_a_national_number_is_read():
    raw = "212 555 0100"

    as_us = normalize_phone(raw, default_region="US")
    as_pl = normalize_phone(raw, default_region="PL")

    assert as_us.valid and as_us.e164 == "+12125550100"
    assert not as_pl.valid and as_pl.reasons == (Reason.WRONG_LENGTH,)


# --- United Kingdom ---------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "020 7946 0958",
        "(020) 7946 0958",
        "02079460958",
        "442079460958",
        "+44 20 7946 0958",
        "+44 (0)20 7946 0958",  # trunk 0 written after the country code
        "0044 20 7946 0958",
    ],
)
def test_uk_trunk_zero_is_dropped_however_the_number_is_written(raw):
    result = normalize_phone(raw, default_region="GB")

    assert result.valid
    assert result.e164 == "+442079460958"
    assert result.country == "GB"
    assert result.line_type == LineType.LANDLINE


@pytest.mark.parametrize(
    "raw, expected_e164, expected_type",
    [
        ("07911 123456", "+447911123456", LineType.MOBILE),
        ("+44 7911 123456", "+447911123456", LineType.MOBILE),
        ("01234 567890", "+441234567890", LineType.LANDLINE),
        ("07012 345678", "+447012345678", LineType.UNKNOWN),  # 070 personal numbers
        ("07612 345678", "+447612345678", LineType.UNKNOWN),  # 076 pagers
        ("0300 123 4567", "+443001234567", LineType.UNKNOWN),  # non-geographic
    ],
)
def test_uk_line_type_follows_the_leading_digits(raw, expected_e164, expected_type):
    result = normalize_phone(raw, default_region="GB")

    assert result.e164 == expected_e164
    assert result.line_type == expected_type


@pytest.mark.parametrize(
    "raw, expected_reasons",
    [
        ("+44 7911 12345", (Reason.WRONG_LENGTH,)),
        ("020 7946 095", (Reason.WRONG_LENGTH,)),
        ("049 1234 5678", (Reason.INVALID_LEADING_DIGIT,)),  # 04 is unallocated
        ("061 1234 5678", (Reason.INVALID_LEADING_DIGIT,)),  # 06 is unallocated
    ],
)
def test_malformed_uk_numbers_are_rejected(raw, expected_reasons):
    result = normalize_phone(raw, default_region="GB")

    assert not result.valid
    assert result.reasons == expected_reasons


# --- Rejected input shared by all regions -----------------------------------


@pytest.mark.parametrize(
    "raw, expected_reasons",
    [
        ("", (Reason.EMPTY,)),
        ("   \t", (Reason.EMPTY,)),
        ("()", (Reason.NO_DIGITS,)),
        ("---", (Reason.NO_DIGITS,)),
        ("+49 30 123456", (Reason.UNSUPPORTED_COUNTRY_CODE,)),
        ("0033 1 23 45 67 89", (Reason.UNSUPPORTED_COUNTRY_CODE,)),
        ("1-800-FLOWERS", (Reason.LETTERS,)),
        ("+48 501 234 567 ext. 12", (Reason.LETTERS,)),
        ("+48 501+234 567", (Reason.MISPLACED_PLUS,)),
        ("(22 123 45 67", (Reason.UNBALANCED_PARENTHESES,)),
        (")22( 123 45 67", (Reason.UNBALANCED_PARENTHESES,)),
        ("+48 501 234 567 #12", (Reason.INVALID_CHARACTERS,)),
        ("+٤٨ 501 234 567", (Reason.INVALID_CHARACTERS,)),  # Arabic-Indic digits
    ],
)
def test_unusable_input_is_rejected_with_the_matching_reason(raw, expected_reasons):
    result = normalize_phone(raw)

    assert not result.valid
    assert result.e164 is None
    assert result.line_type == LineType.UNKNOWN
    assert result.reasons == expected_reasons


@pytest.mark.parametrize("bad", [None, 48501234567, 501.234567, ["+48501234567"]])
def test_non_string_input_raises_type_error(bad):
    with pytest.raises(TypeError):
        normalize_phone(bad)


@pytest.mark.parametrize("region", ["DE", "pl", "", "POLAND"])
def test_unsupported_region_raises_value_error(region):
    with pytest.raises(ValueError):
        normalize_phone("501234567", default_region=region)


def test_normalised_output_is_a_fixed_point_and_fits_the_e164_shape():
    samples = [
        ("0048 501-234-567", "PL"),
        ("(22) 123-45-67", "PL"),
        ("(416) 555-0199", "CA"),
        ("1-212-555-0100", "US"),
        ("+44 (0)20 7946 0958", "GB"),
        ("07911 123456", "GB"),
    ]
    for raw, region in samples:
        first = normalize_phone(raw, default_region=region)
        again = normalize_phone(first.e164, default_region=region)

        assert re.fullmatch(r"\+[1-9][0-9]{7,14}", first.e164)
        assert again.e164 == first.e164
        assert again.line_type == first.line_type
        assert again.country == first.country
