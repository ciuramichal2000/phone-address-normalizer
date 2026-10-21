import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from contactnorm import Reason, check_email


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("jan.kowalski@firma.pl", "jan.kowalski@firma.pl"),
        ("  Jan.Kowalski@Firma.PL  ", "jan.kowalski@firma.pl"),
        ("a+tag@sub.domain.example.com", "a+tag@sub.domain.example.com"),
        ("o'brien@example.ie", "o'brien@example.ie"),
        ("first_last-1@my-company.co.uk", "first_last-1@my-company.co.uk"),
        ("x@y.io", "x@y.io"),
        ("1234567890@example.com", "1234567890@example.com"),
    ],
)
def test_ordinary_addresses_are_accepted_and_lower_cased(raw, expected):
    result = check_email(raw)

    assert result.valid
    assert result.normalized == expected
    assert result.suggestion is None
    assert result.reasons == ()
    assert result.original == raw


@pytest.mark.parametrize(
    "raw, expected_reasons",
    [
        ("", (Reason.EMPTY,)),
        ("   ", (Reason.EMPTY,)),
        ("plainaddress", (Reason.MISSING_AT,)),
        ("a@b@example.com", (Reason.MULTIPLE_AT,)),
        ("@example.com", (Reason.EMPTY_LOCAL_PART,)),
        ("jan@", (Reason.EMPTY_DOMAIN,)),
        ("jan@localhost", (Reason.DOMAIN_WITHOUT_DOT,)),
        ("jan kowalski@example.com", (Reason.CONTAINS_WHITESPACE,)),
        (
            "jan@exa mple",
            (Reason.CONTAINS_WHITESPACE, Reason.DOMAIN_WITHOUT_DOT),
        ),
        ("jan..kowalski@example.com", (Reason.INVALID_FORMAT,)),
        (".jan@example.com", (Reason.INVALID_FORMAT,)),
        ("jan.@example.com", (Reason.INVALID_FORMAT,)),
        ("jan@-example.com", (Reason.INVALID_FORMAT,)),
        ("jan@example-.com", (Reason.INVALID_FORMAT,)),
        ("jan@example..com", (Reason.INVALID_FORMAT,)),
        ("jan@example.com.", (Reason.INVALID_FORMAT,)),
        ("jan@example.c", (Reason.INVALID_FORMAT,)),
        ("jan@example.c0m", (Reason.INVALID_FORMAT,)),
        ("jan@exa_mple.com", (Reason.INVALID_FORMAT,)),
        ("jan,kowalski@example.com", (Reason.INVALID_FORMAT,)),
        ("zażółć@example.com", (Reason.INVALID_FORMAT,)),
        ("jan@przykład.pl", (Reason.INVALID_FORMAT,)),
    ],
)
def test_bad_addresses_are_rejected_with_the_matching_reason(raw, expected_reasons):
    result = check_email(raw)

    assert not result.valid
    assert result.normalized is None
    assert result.suggestion is None
    assert result.reasons == expected_reasons


def test_length_limits_are_enforced():
    just_fits = "a" * 64 + "@example.com"
    local_too_long = "a" * 65 + "@example.com"
    whole_address_too_long = "a" * 64 + "@" + ".".join(["b" * 63] * 3) + ".com"

    assert check_email(just_fits).valid
    assert check_email(local_too_long).reasons == (Reason.LOCAL_PART_TOO_LONG,)
    assert len(whole_address_too_long) > 254
    assert check_email(whole_address_too_long).reasons == (Reason.ADDRESS_TOO_LONG,)


def test_domain_label_longer_than_63_characters_is_rejected():
    assert check_email("jan@" + "b" * 63 + ".com").valid
    assert check_email("jan@" + "b" * 64 + ".com").reasons == (Reason.INVALID_FORMAT,)


@pytest.mark.parametrize(
    "raw, expected_suggestion",
    [
        ("jan@gmial.com", "jan@gmail.com"),
        ("jan@gmai.com", "jan@gmail.com"),
        ("jan@gnail.com", "jan@gmail.com"),
        ("jan@gmail.co", "jan@gmail.com"),
        ("jan@gmail.con", "jan@gmail.com"),  # only the TLD is wrong
        ("jan@gmial.con", "jan@gmail.com"),  # both parts are wrong
        ("jan@hotmial.com", "jan@hotmail.com"),
        ("jan@yaho.com", "jan@yahoo.com"),
        ("jan@outlok.com", "jan@outlook.com"),
        ("jan@firma.con", "jan@firma.com"),  # unknown company, still a bad TLD
        ("jan@firma.lp", "jan@firma.pl"),
        ("JAN@GMIAL.COM", "jan@gmail.com"),
    ],
)
def test_likely_typos_get_a_suggestion_but_stay_valid(raw, expected_suggestion):
    result = check_email(raw)

    assert result.valid  # syntactically fine; only a human can confirm the fix
    assert result.suggestion == expected_suggestion
    assert result.normalized == raw.strip().lower()


@pytest.mark.parametrize(
    "raw",
    [
        "jan@gmail.com",
        "jan@gmx.com",  # real provider that merely resembles a typo
        "jan@gmail.co.uk",
        "jan@firma.pl",
        "jan@example.org",
    ],
)
def test_correct_domains_get_no_suggestion(raw):
    assert check_email(raw).suggestion is None


@pytest.mark.parametrize("bad", [None, 12345, b"jan@example.com", ["jan@example.com"]])
def test_non_string_input_raises_type_error(bad):
    with pytest.raises(TypeError):
        check_email(bad)
