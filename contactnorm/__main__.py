"""Command line: python -m contactnorm [--region PL] [FILE | -]

Reads one JSON object or a JSON array of objects (from FILE or stdin) and
prints, for each record, the cleaned record, the changes made and the issues
found. Exit status is 0 on success and 2 when the input cannot be used.
"""

import argparse
import dataclasses
import json
import sys
from typing import Any, TextIO

from .phone import SUPPORTED_REGIONS
from .record import clean_record


def main(
    argv: list[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the CLI; the streams are parameters so tests need no subprocess."""
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr

    parser = argparse.ArgumentParser(
        prog="contactnorm",
        description="Normalise phone numbers, Polish postal codes and e-mails "
        "in JSON contact records.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="JSON file with one record or a list of records; '-' reads stdin",
    )
    parser.add_argument(
        "--region",
        default="PL",
        choices=SUPPORTED_REGIONS,
        help="region used to read national phone numbers (default: PL)",
    )
    args = parser.parse_args(argv)

    try:
        if args.input == "-":
            text = stdin.read()
        else:
            with open(args.input, encoding="utf-8") as handle:
                text = handle.read()
        data = json.loads(text)
    except OSError as error:
        print(f"contactnorm: cannot read input: {error}", file=stderr)
        return 2
    except json.JSONDecodeError as error:
        print(f"contactnorm: input is not valid JSON: {error}", file=stderr)
        return 2

    records = [data] if isinstance(data, dict) else data
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        print(
            "contactnorm: input must be a JSON object or an array of objects",
            file=stderr,
        )
        return 2

    output: list[dict[str, Any]] = []
    for record in records:
        result = clean_record(record, default_region=args.region)
        output.append(
            {
                "record": result.record,
                "changes": [dataclasses.asdict(c) for c in result.changes],
                "issues": [dataclasses.asdict(i) for i in result.issues],
            }
        )
    print(json.dumps(output, indent=2, ensure_ascii=False), file=stdout)
    return 0


if __name__ == "__main__":
    # Windows consoles default to a legacy code page that cannot print Polish
    # letters, and stdin must be decoded as UTF-8 to match what JSON files use.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
