import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from contactnorm import Reason, normalize_postal_code_pl


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("00950", "00-950"),  # the hyphen was lost
        ("00-950", "00-950"),  # already canonical
        ("  00-950  ", "00-950"),
        ("00 950", "00-950"),
        ("00 - 950", "00-950"),
        ("00–950", "00-950"),  # en dash
        ("00−950", "00-950"),  # minus sign
        ("30-001", "30-001"),
        ("PL 00-950", "00-950"),
        ("pl-00950", "00-950"),
        ("PL00950", "00-950"),
    ],
)
def test_valid_spellings_become_the_canonical_nn_nnn_form(raw, expected):
    result = normalize_postal_code_pl(raw)

    assert result.valid
    assert result.value == expected
    assert result.reasons == ()
    assert result.original == raw


@pytest.mark.parametrize(
    "raw, expected_reason",
    [
        ("", Reason.EMPTY),
        ("   ", Reason.EMPTY),
        ("0095", Reason.WRONG_LENGTH),
        ("009500", Reason.WRONG_LENGTH),
        ("00-95", Reason.WRONG_LENGTH),
        ("PL", Reason.WRONG_LENGTH),
        ("00-95O", Reason.INVALID_CHARACTERS),  # letter O instead of zero
        ("00_950", Reason.INVALID_CHARACTERS),
        ("W-wa 00-950", Reason.INVALID_CHARACTERS),
        ("009-50", Reason.INVALID_FORMAT),  # five digits, hyphen in the wrong place
        ("0 0950", Reason.INVALID_FORMAT),
        ("00-9 50", Reason.INVALID_FORMAT),
        ("00--950", Reason.INVALID_FORMAT),
    ],
)
def test_malformed_codes_are_rejected_with_one_clear_reason(raw, expected_reason):
    result = normalize_postal_code_pl(raw)

    assert not result.valid
    assert result.value is None
    assert result.reasons == (expected_reason,)


@pytest.mark.parametrize("bad", [None, 95000, 0.0095, ["00-950"]])
def test_non_string_input_raises_type_error(bad):
    with pytest.raises(TypeError):
        normalize_postal_code_pl(bad)


def test_canonical_output_is_a_fixed_point():
    once = normalize_postal_code_pl("00950")
    twice = normalize_postal_code_pl(once.value)

    assert twice.valid
    assert twice.value == once.value == "00-950"
