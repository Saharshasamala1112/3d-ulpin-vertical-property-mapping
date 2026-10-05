"""Deterministic VDC CHECKSUM engine (VDC Specification 1.0, section 9).

The checksum is a two-character Base-36 integrity check over the first four
canonical segments. It is a typo-detection aid, not a cryptographic hash and
not tamper-proof authentication (see specification section 15).

The computation is pure: no randomness, no timestamps, no process state. The
same canonical segments always yield the same two characters.
"""

from __future__ import annotations

from app.schemas.vdc import VDCParsed
from app.validators.vdc_parser import VDCValidationError, parse_vdc

CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(CHARSET)
VALUE = {char: index for index, char in enumerate(CHARSET)}


def compute_checksum(segments: VDCParsed) -> str:
    """Compute the CHECKSUM for a parsed VDC.

    Implements specification section 9.3 exactly: the checksum input is the
    concatenation ``ULPIN + DOMAIN + LEVEL + UNIT`` with no separators, and
    two independent mod-36 accumulators are folded over it -- a plain
    checksum and a positionally weighted checksum.

    The input is never mutated, and the returned value is always exactly two
    uppercase Base-36 characters.

    The caller is responsible for supplying canonical segments: the segments of
    a ``VDCParsed`` produced by the parser. A non-canonical character outside
    the Base-36 alphabet has no value and raises ``KeyError`` rather than being
    coerced.
    """
    checksum_input = segments.ulpin + segments.domain + segments.level + segments.unit
    c1 = 0
    c2 = 0
    for position, char in enumerate(checksum_input, start=1):
        value = VALUE[char]
        c1 = (c1 + value) % BASE
        c2 = (c2 + position * value) % BASE
    return CHARSET[c1] + CHARSET[c2]


def verify_checksum(vdc_string: str) -> bool:
    """Report whether a VDC string is structurally valid and checksum-correct.

    Parses the VDC with the Feature 15 parser, then compares the recomputed
    checksum against the supplied one. Any structurally invalid or tampered
    VDC yields ``False`` instead of an exception, which makes this suitable for
    use as a boolean guard.

    Outer whitespace is stripped by the parser before validation, per
    specification section 10.1. Lowercase input is rejected rather than folded,
    per specification section 10.2.

    A non-string argument raises ``TypeError``, matching the parser contract.
    """
    try:
        segments = parse_vdc(vdc_string)
    except VDCValidationError:
        return False
    return segments.checksum == compute_checksum(segments)
