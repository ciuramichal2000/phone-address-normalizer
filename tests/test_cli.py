import os, sys; sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import io
import json

import pytest

from contactnorm.__main__ import main


def run(argv, stdin_text=""):
    stdout, stderr = io.StringIO(), io.StringIO()
    code = main(argv, stdin=io.StringIO(stdin_text), stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_single_record_from_stdin_is_cleaned_and_printed_as_json():
    payload = json.dumps({"name": " Zażółć ", "phone": "0048 501-234-567", "postal_code": "00950"})

    code, out, err = run([], payload)

    assert code == 0
    assert err == ""
    [item] = json.loads(out)
    assert item["record"] == {
        "name": "Zażółć",
        "phone": "+48501234567",
        "postal_code": "00-950",
    }
    assert [c["field"] for c in item["changes"]] == ["name", "phone", "postal_code"]
    assert item["issues"] == []
    assert "Zażółć" in out  # Polish letters are printed as-is, not \u-escaped


def test_list_of_records_gives_one_result_per_record_in_order():
    payload = json.dumps([{"phone": "501234567"}, {"phone": "12"}])

    code, out, _ = run(["-"], payload)

    results = json.loads(out)
    assert code == 0
    assert results[0]["record"] == {"phone": "+48501234567"}
    assert results[1]["record"] == {"phone": "12"}
    assert results[1]["issues"] == [
        {"field": "phone", "value": "12", "reasons": ["wrong_length"], "suggestion": None}
    ]


def test_region_option_changes_how_national_numbers_are_read():
    payload = json.dumps({"phone": "(212) 555-0100"})

    code, out, _ = run(["--region", "US"], payload)

    assert code == 0
    assert json.loads(out)[0]["record"] == {"phone": "+12125550100"}


def test_input_can_be_read_from_a_file(tmp_path):
    path = tmp_path / "contacts.json"
    path.write_text(json.dumps({"postal_code": "30001"}), encoding="utf-8")

    code, out, _ = run([str(path)])

    assert code == 0
    assert json.loads(out)[0]["record"] == {"postal_code": "30-001"}


@pytest.mark.parametrize(
    "payload, expected_message",
    [
        ("{not json", "not valid JSON"),
        ("42", "JSON object or an array of objects"),
        ('"just a string"', "JSON object or an array of objects"),
        ('[{"phone": "1"}, 7]', "JSON object or an array of objects"),
    ],
)
def test_unusable_input_gives_exit_code_2_and_a_message_on_stderr(
    payload, expected_message
):
    code, out, err = run([], payload)

    assert code == 2
    assert out == ""
    assert expected_message in err


def test_missing_file_gives_exit_code_2(tmp_path):
    code, out, err = run([str(tmp_path / "missing.json")])

    assert code == 2
    assert out == ""
    assert "cannot read input" in err


def test_unknown_region_is_rejected_by_the_argument_parser():
    with pytest.raises(SystemExit) as exit_info:
        run(["--region", "DE"], "{}")

    assert exit_info.value.code == 2
