"""Character classes shared by the phone and postal-code parsers."""

# Regex fragment for use *inside* a character class: ASCII hyphen, the Unicode
# dashes U+2010..U+2015 (hyphen, non-breaking hyphen, figure/en/em dash,
# horizontal bar) and the minus sign U+2212. Word processors and spreadsheets
# routinely turn "-" into one of these, and people paste from them.
DASHES = r"\-‐-―−"
