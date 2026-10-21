import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import copy

import pytest

from contactnorm import Change, ChangeKind, Issue, Reason, clean_record


def test_messy_record_is_cleaned_and_every_edit_is_reported():
    messy = {
        "name": "  Jan   Kowalski ",
        "phone": " +48 (501) 234-567 ",
        "postal_code": "00950",
        "email": " Jan.Kowalski@Firma.PL ",
        "age": 41,
    }

    record, changes, issues = clean_record(messy)

    assert record == {
        "name": "Jan Kowalski",
        "phone": "+48501234567",
        "postal_code": "00-950",
        "email": "jan.kowalski@firma.pl",
        "age": 41,
    }
    assert changes == [
        Change("name", "  Jan   Kowalski ", "Jan Kowalski", ChangeKind.WHITESPACE),
        Change("phone", " +48 (501) 234-567 ", "+48501234567", ChangeKind.PHONE_E164),
        Change("postal_code", "00950", "00-950", ChangeKind.POSTAL_FORMAT),
        Change(
            "email",
            " Jan.Kowalski@Firma.PL ",
            "jan.kowalski@firma.pl",
            ChangeKind.EMAIL_NORMALISED,
        ),
    ]
    assert issues == []


def test_clean_record_returns_a_copy_and_leaves_the_input_untouched():
    messy = {"name": " Ann ", "phone": "501 234 567", "tags": ["a", " b "]}
    snapshot = copy.deepcopy(messy)

    record, _, _ = clean_record(messy)

    assert messy == snapshot
    assert record is not messy
    assert record["phone"] == "+48501234567"


def test_already_clean_record_produces_no_changes_and_no_issues():
    tidy = {
        "name": "Jan Kowalski",
        "phone": "+48501234567",
        "postal_code": "00-950",
        "email": "jan@firma.pl",
    }

    record, changes, issues = clean_record(tidy)

    assert record == tidy
    assert changes == []
    assert issues == []


def test_invalid_values_are_kept_verbatim_and_reported_with_reasons():
    broken = {"phone": " 12345 ", "postal_code": "9500", "email": "not-an-email"}

    record, changes, issues = clean_record(broken)

    assert record == broken  # nothing destroyed, not even the stray spaces
    assert changes == []
    assert issues == [
        Issue("phone", " 12345 ", (Reason.WRONG_LENGTH,)),
        Issue("postal_code", "9500", (Reason.WRONG_LENGTH,)),
        Issue("email", "not-an-email", (Reason.MISSING_AT,)),
    ]


def test_email_typo_is_suggested_but_never_applied():
    record, changes, issues = clean_record({"email": "Jan@Gmial.com"})

    assert record == {"email": "jan@gmial.com"}  # only normalised
    assert changes == [
        Change("email", "Jan@Gmial.com", "jan@gmial.com", ChangeKind.EMAIL_NORMALISED)
    ]
    assert issues == [
        Issue("email", "Jan@Gmial.com", (Reason.LIKELY_TYPO,), "jan@gmail.com")
    ]


def test_default_region_controls_how_national_phone_numbers_are_read():
    us_record, _, us_issues = clean_record(
        {"phone": "(212) 555-0100"}, default_region="US"
    )
    pl_record, _, pl_issues = clean_record({"phone": "(212) 555-0100"})

    assert us_record == {"phone": "+12125550100"} and us_issues == []
    assert pl_record == {"phone": "(212) 555-0100"}
    assert [i.reasons for i in pl_issues] == [(Reason.WRONG_LENGTH,)]


def test_field_names_are_configurable_and_unlisted_fields_are_left_alone():
    record, changes, issues = clean_record(
        {"tel": "501 234 567", "phone": "501 234 567", "mail": "A@B.IO"},
        phone_fields=("tel",),
        email_fields=("mail",),
    )

    # "phone" is not a managed field here, so only its whitespace is tidied.
    assert record == {"tel": "+48501234567", "phone": "501 234 567", "mail": "a@b.io"}
    assert [c.field for c in changes] == ["tel", "mail"]
    assert issues == []


def test_blank_none_and_non_text_values_are_handled_without_crashing():
    record, changes, issues = clean_record(
        {"phone": "   ", "email": "", "postal_code": None, "note": "  \t "}
    )

    assert record == {"phone": "", "email": "", "postal_code": None, "note": ""}
    assert [(c.field, c.after) for c in changes] == [("phone", ""), ("note", "")]
    assert issues == []  # a missing value is not an invalid value

    record, changes, issues = clean_record({"phone": 48501234567, "age": 30})

    assert record == {"phone": 48501234567, "age": 30}
    assert changes == []
    assert issues == [Issue("phone", 48501234567, (Reason.NOT_TEXT,))]


def test_empty_record_gives_empty_results():
    assert clean_record({}) == ({}, [], [])


def test_output_keeps_the_key_order_of_the_input():
    record, _, _ = clean_record({"z": " 1", "email": "A@B.IO", "a": " 2"})

    assert list(record) == ["z", "email", "a"]


@pytest.mark.parametrize("bad", [None, "phone=501234567", [("phone", "501234567")]])
def test_non_mapping_record_raises_type_error(bad):
    with pytest.raises(TypeError):
        clean_record(bad)


def test_unsupported_region_raises_even_when_no_phone_field_is_present():
    with pytest.raises(ValueError):
        clean_record({"name": "Jan"}, default_region="DE")
