# contactnorm

A small, dependency-free Python library that cleans contact data: phone numbers (Poland, US/Canada, UK) to E.164, Polish postal codes to `NN-NNN`, and e-mail addresses with typo suggestions. A single function takes a messy record and returns the cleaned record together with the list of changes it made and the problems it found.

## Interesting engineering

- Rejections are structured: every validator returns a result object with a tuple of `Reason` codes (`wrong_length`, `invalid_area_code`, ...) instead of raising, so dirty rows can be reported in bulk. Only programmer errors (non-string input, unknown region) raise.
- `clean_record` never destroys data it cannot repair. Invalid values stay exactly as received and become an `Issue`; likely e-mail typos are suggested but not applied. Every rewrite is logged as a `Change(field, before, after, kind)`.
- Phone parsing resolves real ambiguities: `48501234567` (country code without `+`) versus a 9-digit Polish number that starts with the Radom area code `48` is decided by total length, and `+44 (0)20 ...` has its trunk zero dropped.
- Polish line type (mobile / landline / unknown) comes from the two-digit prefix against explicit tables; unrecognised prefixes are reported as `unknown` instead of guessed.
- Standard library only; tests use pytest and are deterministic (no clocks, network or randomness).

## Usage

```python
from contactnorm import clean_record, normalize_phone, normalize_postal_code_pl, check_email

normalize_phone("0048 501-234-567")
# PhoneResult(valid=True, e164='+48501234567', country='PL', line_type=<LineType.MOBILE: 'mobile'>, ...)
normalize_phone("(212) 555-0100", default_region="US").e164   # '+12125550100'
normalize_phone("020 7946 0958", default_region="GB").e164    # '+442079460958'
normalize_phone("+48 501 234 56").reasons                      # (Reason.WRONG_LENGTH,)

normalize_postal_code_pl("00950").value                        # '00-950'
check_email("jan@gmial.com").suggestion                        # 'jan@gmail.com'

record, changes, issues = clean_record({
    "name": "  Jan   Kowalski ",
    "phone": "0048 501-234-567",
    "postal_code": "00950",
    "email": "Jan@Gmial.com",
})
# record  -> {'name': 'Jan Kowalski', 'phone': '+48501234567',
#             'postal_code': '00-950', 'email': 'jan@gmial.com'}
# changes -> name, phone, postal_code and email were rewritten (kind: whitespace,
#            phone_e164, postal_format, email_normalised)
# issues  -> [Issue(field='email', reasons=(Reason.LIKELY_TYPO,), suggestion='jan@gmail.com')]
```

Command line (one JSON object or an array of objects, from a file or stdin):

```
echo '{"phone": "(212) 555-0100"}' | python -m contactnorm --region US
```

By default `clean_record` treats the fields `phone`, `postal_code` and `email` specially; pass `phone_fields=`, `postal_fields=` or `email_fields=` to use other names. All other text values only get whitespace trimmed and collapsed.

## Running the tests

```
python -m pytest -q
```

## Limitations

- Only Poland (+48), US/Canada (+1) and the UK (+44) are supported; other country codes are rejected with `unsupported_country_code`.
- Line type is a guess from the number prefix and only exists for Poland and the UK. It says nothing about the current carrier or whether the number is in service. US/Canada numbers are always `unknown`.
- `+1` numbers are labelled `CA` only if the area code is in a built-in snapshot of Canadian area codes; all other `+1` numbers, including Caribbean NANP countries and newer Canadian overlays, are labelled `US`.
- UK numbers must have 10 significant digits after the trunk zero, which excludes a few short legacy ranges. Extensions (`ext. 12`) and vanity letters are rejected rather than parsed.
- Postal codes are checked for shape only, not against the official list of assigned codes. E-mail checking is syntax-only: no DNS lookup, no internationalised domains or quoted local parts.
- The typo tables are small and hand-picked; they cover common cases such as `gmial.com` and `.con`, not every possible misspelling.

Built with AI coding assistance.
