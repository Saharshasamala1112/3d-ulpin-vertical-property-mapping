from __future__ import annotations

import inspect

import pytest

from app.schemas.vdc import VDCErrorDetail
from app.services import vdc_generator
from app.services.vdc_generator import canonical_level, generate_vdc
from app.validators.vdc_checksum import verify_checksum
from app.validators.vdc_parser import VDCValidationError, parse_vdc

# Worked examples, verbatim from docs/vdc-specification.md section 11.
SPEC_EXAMPLES = [
    ("GEOSX00001", "A", "G", "1", "GEOSX00001-A-G-1-ZY"),
    ("GEOSX00002", "A", "F5", "3", "GEOSX00002-A-F5-3-6I"),
    ("GEOSX00003", "A", "F12", "804", "GEOSX00003-A-F12-804-E6"),
    ("GEOSX00004", "A", "B1", "4", "GEOSX00004-A-B1-4-1O"),
    ("GEOSX00005", "A", "B3", "7", "GEOSX00005-A-B3-7-7U"),
    ("GEOSX00006", "B", "G", "105", "GEOSX00006-B-G-105-AQ"),
    ("GEOSX00007", "C", "F120", "25B", "GEOSX00007-C-F120-25B-QF"),
    ("GEOSX00008", "A", "G", "1001", "GEOSX00008-A-G-1001-7C"),
    ("GEOSX00009", "B", "B2", "9A", "GEOSX00009-B-B2-9A-NU"),
    ("GEOSX00010", "A", "F9", "5", "GEOSX00010-A-F9-5-BF"),
    ("GEOSX00011", "A", "F999", "1234AB", "GEOSX00011-A-F999-1234AB-KZ"),
    ("GEOSX00012", "D", "B9", "3", "GEOSX00012-D-B9-3-AS"),
]

DOMAINS = ["A", "B", "C", "D"]
LEVELS = ["G", "F1", "F5", "F9", "F12", "F120", "F999", "B1", "B3", "B9", "B999"]
UNITS = ["1", "5", "9", "10", "105", "804", "1001", "25B", "9A", "1234AB", "AB12", "Z9"]
ULPINS = ["GEOSX00000", "GEOSX00001", "GEOSX00042", "GEOSX12345", "GEOSX99999"]


def _errors_for(ulpin, domain, level, unit) -> tuple[VDCErrorDetail, ...]:
    with pytest.raises(VDCValidationError) as excinfo:
        generate_vdc(ulpin, domain, level, unit)
    return excinfo.value.errors


def _error_for(ulpin, domain, level, unit, segment: str | None = None) -> VDCErrorDetail:
    errors = _errors_for(ulpin, domain, level, unit)
    if segment is not None:
        matches = [error for error in errors if error.segment == segment]
        assert matches, f"no error for {segment!r} in {[e.segment for e in errors]}"
        return matches[0]
    return errors[0]


def _assert_valid(ulpin: str, domain: str, level, unit: str) -> str:
    """Generate, then prove the result parses and verifies with Features 15 and 16."""
    vdc = generate_vdc(ulpin, domain, level, unit)
    expected_level = canonical_level(level)
    assert vdc.rsplit("-", 1)[0] == "-".join([ulpin, domain, expected_level, unit])
    parsed = parse_vdc(vdc)
    assert (parsed.ulpin, parsed.domain, parsed.level, parsed.unit) == (
        ulpin,
        domain,
        expected_level,
        unit,
    )
    assert verify_checksum(vdc) is True
    return vdc


class TestWorkedExamples:
    @pytest.mark.parametrize("ulpin,domain,level,unit,expected", SPEC_EXAMPLES)
    def test_generates_specification_example(self, ulpin, domain, level, unit, expected):
        assert generate_vdc(ulpin, domain, level, unit) == expected

    @pytest.mark.parametrize("ulpin,domain,level,unit,expected", SPEC_EXAMPLES)
    def test_specification_example_round_trips(self, ulpin, domain, level, unit, expected):
        assert _assert_valid(ulpin, domain, level, unit) == expected
        assert parse_vdc(expected).model_dump() == {
            "ulpin": ulpin,
            "domain": domain,
            "level": level,
            "unit": unit,
            "checksum": expected.rsplit("-", 1)[1],
        }

    def test_integer_level_api_reproduces_specification_examples(self):
        # 0 -> G, positive -> F<n>, negative -> B<n>, always without a sign or a pad.
        assert generate_vdc("GEOSX00001", "A", 0, "1") == "GEOSX00001-A-G-1-ZY"
        assert generate_vdc("GEOSX00002", "A", 5, "3") == "GEOSX00002-A-F5-3-6I"
        assert generate_vdc("GEOSX00003", "A", 12, "804") == "GEOSX00003-A-F12-804-E6"
        assert generate_vdc("GEOSX00004", "A", -1, "4") == "GEOSX00004-A-B1-4-1O"
        assert generate_vdc("GEOSX00005", "A", -3, "7") == "GEOSX00005-A-B3-7-7U"
        assert generate_vdc("GEOSX00007", "C", 120, "25B") == "GEOSX00007-C-F120-25B-QF"
        assert generate_vdc("GEOSX00011", "A", 999, "1234AB") == "GEOSX00011-A-F999-1234AB-KZ"
        assert generate_vdc("GEOSX00012", "D", -9, "3") == "GEOSX00012-D-B9-3-AS"

    def test_string_and_integer_level_apis_agree(self):
        for level in LEVELS:
            number = 0 if level == "G" else int(level[1:]) * (-1 if level[0] == "B" else 1)
            assert canonical_level(level) == canonical_level(number)
            assert generate_vdc("GEOSX00001", "A", level, "1") == generate_vdc(
                "GEOSX00001", "A", number, "1"
            )


class TestBasicGeneration:
    def test_basic_residential(self):
        assert generate_vdc("GEOSX00001", "A", "G", "1") == "GEOSX00001-A-G-1-ZY"

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_all_four_domain_codes(self, domain):
        vdc = generate_vdc("GEOSX00001", domain, "G", "1")
        assert vdc.split("-")[1] == domain
        assert vdc.startswith("GEOSX00001-")
        assert verify_checksum(vdc) is True

    @pytest.mark.parametrize("level", ["G"])
    def test_ground_level(self, level):
        assert generate_vdc("GEOSX00001", "A", level, "1").split("-")[2] == "G"

    @pytest.mark.parametrize("level", ["F1", "F5", "F12", "F120", "F999"])
    def test_positive_floors(self, level):
        vdc = _assert_valid("GEOSX00001", "A", level, "1")
        assert vdc.split("-")[2] == level
        assert not vdc.split("-")[2].startswith("+")

    @pytest.mark.parametrize("level", ["B1", "B3", "B9", "B999"])
    def test_basements(self, level):
        vdc = _assert_valid("GEOSX00001", "A", level, "1")
        assert vdc.split("-")[2] == level
        assert not vdc.split("-")[2].startswith("-")

    @pytest.mark.parametrize("unit", ["1", "9", "A", "Z"])
    def test_minimum_valid_unit(self, unit):
        assert generate_vdc("GEOSX00001", "A", "G", unit).split("-")[3] == unit

    @pytest.mark.parametrize("unit", ["123456", "1234AB", "ABCDEF", "A1B2C3"])
    def test_maximum_length_valid_unit(self, unit):
        assert _assert_valid("GEOSX00001", "A", "G", unit).split("-")[3] == unit

    @pytest.mark.parametrize("unit", ["25B", "9A", "1234AB", "AB12", "A1", "B2", "X9Y8Z7"])
    def test_alphanumeric_units(self, unit):
        assert _assert_valid("GEOSX00001", "A", "G", unit).split("-")[3] == unit

    def test_unit_length_boundaries(self):
        for unit in ("1", "123456"):
            assert 1 <= len(unit) <= 6
            assert _assert_valid("GEOSX00001", "A", "G", unit).split("-")[3] == unit

    def test_generated_vdc_is_canonical(self):
        for ulpin in ULPINS:
            for domain in DOMAINS:
                for level in LEVELS:
                    for unit in UNITS:
                        vdc = generate_vdc(ulpin, domain, level, unit)
                        assert vdc.count("-") == 4
                        assert 19 <= len(vdc) <= 27
                        assert vdc == vdc.upper()
                        assert vdc == vdc.strip()
                        assert vdc == vdc.replace("--", "-")


class TestCanonicalLevel:
    @pytest.mark.parametrize(
        "number,expected",
        [
            (0, "G"),
            (1, "F1"),
            (5, "F5"),
            (9, "F9"),
            (10, "F10"),
            (99, "F99"),
            (100, "F100"),
            (999, "F999"),
            (-1, "B1"),
            (-3, "B3"),
            (-9, "B9"),
            (-99, "B99"),
            (-999, "B999"),
        ],
    )
    def test_integer_to_canonical_level(self, number, expected):
        assert canonical_level(number) == expected

    @pytest.mark.parametrize("level", LEVELS)
    def test_canonical_level_is_idempotent(self, level):
        assert canonical_level(level) == level
        assert canonical_level(canonical_level(level)) == level

    @pytest.mark.parametrize("level", LEVELS)
    def test_canonical_level_output_parses(self, level):
        assert parse_vdc(generate_vdc("GEOSX00001", "A", level, "1")).level == level

    def test_no_sign_or_padding_in_integer_mapping(self):
        for number in range(-999, 1000):
            level = canonical_level(number)
            assert "+" not in level
            assert "-" not in level
            if len(level) > 1:
                assert not level[1:].startswith("0"), f"{number} -> {level}"

    def test_ground_is_reachable_only_from_zero(self):
        assert canonical_level(0) == "G"
        for level in ("0", "G0", "00"):
            with pytest.raises(VDCValidationError):
                generate_vdc("GEOSX00001", "A", level, "1")


class TestRoundTrip:
    def test_generation_parses_with_feature_15(self):
        vdc = generate_vdc("GEOSX00007", "C", "F120", "25B")
        assert parse_vdc(vdc).model_dump() == {
            "ulpin": "GEOSX00007",
            "domain": "C",
            "level": "F120",
            "unit": "25B",
            "checksum": "QF",
        }

    def test_generation_verifies_with_feature_16(self):
        for ulpin, domain, level, unit, _ in SPEC_EXAMPLES:
            assert verify_checksum(generate_vdc(ulpin, domain, level, unit)) is True

    def test_valid_combination_matrix(self):
        combinations = [
            (ulpin, domain, level, unit)
            for ulpin in ULPINS
            for domain in DOMAINS
            for level in LEVELS
            for unit in UNITS
        ]
        assert len(combinations) >= 50, "Feature 17 requires at least 50 valid combinations"
        for ulpin, domain, level, unit in combinations:
            _assert_valid(ulpin, domain, level, unit)

    def test_every_domain_level_unit_combination(self):
        count = 0
        for domain in DOMAINS:
            for level in LEVELS:
                for unit in UNITS:
                    vdc = _assert_valid("GEOSX00042", domain, level, unit)
                    assert vdc.startswith("GEOSX00042-")
                    count += 1
        assert count == 4 * 11 * 12

    def test_generated_segments_survive_a_second_generation(self):
        for ulpin, domain, level, unit, _ in SPEC_EXAMPLES:
            parsed = parse_vdc(generate_vdc(ulpin, domain, level, unit))
            regenerated = generate_vdc(parsed.ulpin, parsed.domain, parsed.level, parsed.unit)
            assert regenerated == generate_vdc(ulpin, domain, level, unit)


class TestInvalidUlpin:
    @pytest.mark.parametrize(
        "ulpin",
        [
            "GEOSX0001",
            "GEOSX000012",
            "GEOSX1234",
            "GEOS0000001",
            "ABCDE12345",
            "GEOSX0000A",
            "1234567890",
        ],
    )
    def test_invalid_ulpin(self, ulpin):
        error = _error_for(ulpin, "A", "G", "1", segment="ulpin")
        assert error.code in {"invalid_ulpin", "invalid_character", "empty_segment"}

    @pytest.mark.parametrize("ulpin", ["geosx00001", "Geosx00001", "gEoSx00001"])
    def test_lowercase_ulpin_is_rejected_not_folded(self, ulpin):
        assert _error_for(ulpin, "A", "G", "1", segment="ulpin").code == "lowercase_character"

    @pytest.mark.parametrize("ulpin", ["GEOSX_0001", "GEOSX 0001", "GEOSX\t0001"])
    def test_invalid_ulpin_characters(self, ulpin):
        assert _error_for(ulpin, "A", "G", "1", segment="ulpin").code == "invalid_character"

    @pytest.mark.parametrize("ulpin", [" GEOSX00001", "GEOSX00001 ", "\tGEOSX00001"])
    def test_ulpin_whitespace(self, ulpin):
        # The parser strips a whole padded string, so the generator rejects outer
        # whitespace itself rather than silently accepting " GEOSX00001".
        assert _error_for(ulpin, "A", "G", "1", segment="ulpin").code == "invalid_whitespace"

    @pytest.mark.parametrize("ulpin", [5, None, 1.0, ["GEOSX00001"], b"GEOSX00001"])
    def test_non_string_ulpin(self, ulpin):
        error = _error_for(ulpin, "A", "G", "1", segment="ulpin")
        assert error.code == "invalid_type"
        assert "ULPIN" in error.message

    def test_empty_ulpin(self):
        assert _error_for("", "A", "G", "1").code in {"empty_segment", "invalid_ulpin"}


class TestInvalidDomain:
    @pytest.mark.parametrize("domain", ["E", "Z", "K", "X", "1", "0", "AB", "AA", "_", "A1"])
    def test_invalid_domain(self, domain):
        error = _error_for("GEOSX00001", domain, "G", "1", segment="domain")
        assert error.code in {"invalid_domain", "invalid_character", "empty_segment"}

    def test_separator_in_domain_reports_structure(self):
        errors = _errors_for("GEOSX00001", "-", "G", "1")
        assert [error.segment for error in errors] == ["structure"]

    @pytest.mark.parametrize("domain", ["a", "b", "c", "d"])
    def test_lowercase_domain_is_rejected_not_folded(self, domain):
        error = _error_for("GEOSX00001", domain, "G", "1", segment="domain")
        assert error.code == "lowercase_character"
        assert domain in error.message

    @pytest.mark.parametrize("domain", [" A", "A ", "\tA", "A\n"])
    def test_domain_whitespace(self, domain):
        error = _error_for("GEOSX00001", domain, "G", "1", segment="domain")
        assert error.code in {"invalid_whitespace", "invalid_character"}

    @pytest.mark.parametrize("domain", [1, None, ["A"], 1.0])
    def test_non_string_domain(self, domain):
        assert _error_for("GEOSX00001", domain, "G", "1", segment="domain").code == "invalid_type"

    def test_empty_domain(self):
        assert _error_for("GEOSX00001", "", "G", "1").code in {"empty_segment", "invalid_domain"}


class TestInvalidLevel:
    @pytest.mark.parametrize(
        "level",
        ["F", "B", "X", "G1", "1", "123", "FF", "FG", "F1F1", "GG", "A", "F1.2", "F1_", "1F"],
    )
    def test_invalid_level_string(self, level):
        error = _error_for("GEOSX00001", "A", level, "1", segment="level")
        assert error.code in {"invalid_level", "lowercase_character"}

    @pytest.mark.parametrize("level", ["f1", "b3", "g", "f999", "b999"])
    def test_lowercase_level_is_rejected_not_folded(self, level):
        assert _error_for("GEOSX00001", "A", level, "1", segment="level").code == "invalid_level"

    @pytest.mark.parametrize("level", ["0", "00", "F0", "B0", "G0"])
    def test_zero_levels_are_invalid(self, level):
        # Feature 14 grammar: positive-int = nonzero *2DIGIT, so there is no F0 or
        # B0. Ground is spelled G and is only reachable from integer 0.
        assert _error_for("GEOSX00001", "A", level, "1", segment="level").code == "invalid_level"

    @pytest.mark.parametrize("level", ["F01", "F05", "F00", "B03", "B00", "F000", "B000"])
    def test_leading_zero_levels(self, level):
        error = _error_for("GEOSX00001", "A", level, "1", segment="level")
        assert error.code == "invalid_level"
        assert "leading zeros" in error.message

    @pytest.mark.parametrize("level", ["F1000", "B1000", "F1234", "B9999"])
    def test_out_of_range_level_strings(self, level):
        assert _error_for("GEOSX00001", "A", level, "1", segment="level").code == "invalid_level"

    @pytest.mark.parametrize("level", [1000, 1234, 9999, 10000, -1000, -1234, -9999, -10000])
    def test_out_of_range_level_numbers(self, level):
        error = _error_for("GEOSX00001", "A", level, "1", segment="level")
        assert error.code == "invalid_level"
        assert "out of range" in error.message

    @pytest.mark.parametrize("level", [1.5, 1.0, None, ["F1"], (1,), True, False])
    def test_invalid_level_type(self, level):
        error = _error_for("GEOSX00001", "A", level, "1", segment="level")
        assert error.code == "invalid_level"
        assert "expected str or int" in error.message

    @pytest.mark.parametrize("level", [True, False])
    def test_booleans_are_not_accepted_as_level_numbers(self, level):
        # bool is a subclass of int, so 0 -> G must not be reachable via False.
        assert _error_for("GEOSX00001", "A", level, "1", segment="level").code == "invalid_level"

    @pytest.mark.parametrize("level", ["", " F1", "F1 ", "F 1", "F\t1"])
    def test_invalid_level_whitespace(self, level):
        assert _error_for("GEOSX00001", "A", level, "1", segment="level").code == "invalid_level"

    def test_signed_and_padded_level_strings_are_rejected(self):
        # The work item proposed +012 / -003 level formatting. Feature 14 encodes
        # no sign and no leading zeros, so these forms are invalid, not canonical.
        for level in ["+012", "-003", "F+12", "B-3", "+1", "-1", "F+1", "B-1"]:
            error = _error_for("GEOSX00001", "A", level, "1", segment="level")
            assert error.code == "invalid_level", level

    def test_signed_level_strings_are_not_normalized(self):
        for level in ("+012", "-003"):
            with pytest.raises(VDCValidationError):
                generate_vdc("GEOSX00001", "A", level, "1")

    def test_integer_level_never_emits_a_sign_or_pad(self):
        assert canonical_level(12) == "F12"
        assert canonical_level(-3) == "B3"
        assert "+012" != canonical_level(12)
        assert "-003" != canonical_level(-3)


class TestInvalidUnit:
    @pytest.mark.parametrize("unit", ["0", "01", "007", "00A", "0A", "00", "0", "0ABCDEF"])
    def test_leading_zero_units(self, unit):
        error = _error_for("GEOSX00001", "A", "G", unit, segment="unit")
        assert error.code in {"invalid_unit", "invalid_character"}

    @pytest.mark.parametrize("unit", ["1234567", "1234ABC", "ABCDEFG", "A1234567", "12345678"])
    def test_unit_longer_than_six_characters(self, unit):
        assert _error_for("GEOSX00001", "A", "G", unit, segment="unit").code == "invalid_unit"

    @pytest.mark.parametrize("unit", ["25b", "ab12", "9a", "A1b", "z9", "25B9a"])
    def test_lowercase_unit_is_rejected_not_folded(self, unit):
        assert (
            _error_for("GEOSX00001", "A", "G", unit, segment="unit").code == "lowercase_character"
        )

    @pytest.mark.parametrize("unit", ["25*B", "A$", "12 3", "A.B", "1\t2", "A\nB", "A+B"])
    def test_invalid_unit_characters(self, unit):
        assert _error_for("GEOSX00001", "A", "G", unit, segment="unit").code == "invalid_character"

    @pytest.mark.parametrize("unit", [" 1", "1 ", "\t1", "1\n", " 1 "])
    def test_unit_whitespace(self, unit):
        assert _error_for("GEOSX00001", "A", "G", unit, segment="unit").code == "invalid_whitespace"

    @pytest.mark.parametrize("unit", [1, None, ["1"], 1.0, b"1"])
    def test_non_string_unit(self, unit):
        error = _error_for("GEOSX00001", "A", "G", unit, segment="unit")
        assert error.code == "invalid_type"
        assert "UNIT" in error.message

    def test_empty_unit_reports_structure(self):
        errors = _errors_for("GEOSX00001", "A", "G", "")
        assert [error.segment for error in errors] == ["structure"]
        assert errors[0].code == "empty_segment"

    def test_separator_in_a_segment_reports_structure(self):
        # "1-2" would make the candidate look like six segments; the generator must
        # surface that as a structural error rather than a checksum crash.
        errors = _errors_for("GEOSX00001", "A", "G", "1-2")
        assert [error.segment for error in errors] == ["structure"]
        assert errors[0].code in {"invalid_segment_count", "malformed"}

    def test_unit_is_never_zero_padded(self):
        # The work item mentioned unit zero-padding. Feature 14 forbids a leading
        # zero, so a short unit is emitted exactly as supplied.
        for unit in ("1", "5", "9", "10", "12", "25B"):
            assert generate_vdc("GEOSX00001", "A", "G", unit).split("-")[3] == unit
        for padded in ("01", "001", "0001", "00001", "000001"):
            with pytest.raises(VDCValidationError):
                generate_vdc("GEOSX00001", "A", "G", padded)


class TestErrorContract:
    def test_errors_are_value_errors(self):
        assert issubclass(VDCValidationError, ValueError)
        with pytest.raises(ValueError):
            generate_vdc("GEOSX1234", "A", "G", "1")

    def test_errors_carry_structured_detail(self):
        # The generator fails on the first offending segment, so each segment is
        # exercised on its own to prove the detail is structured.
        cases = [
            ("GEOSX1234", "A", "G", "1", "ulpin"),
            ("GEOSX00001", "Z", "G", "1", "domain"),
            ("GEOSX00001", "A", "F01", "1", "level"),
            ("GEOSX00001", "A", "G", "01", "unit"),
        ]
        for ulpin, domain, level, unit, segment in cases:
            error = _error_for(ulpin, domain, level, unit, segment=segment)
            assert isinstance(error, VDCErrorDetail)
            assert error.segment == segment
            assert error.code
            assert error.message

    def test_error_message_summarises_every_detail(self):
        with pytest.raises(VDCValidationError) as excinfo:
            generate_vdc("GEOSX1234", "A", "G", "1")
        message = str(excinfo.value)
        assert message.startswith("invalid VDC: ")
        assert "ulpin" in message
        assert "invalid_ulpin" in message

    def test_invalid_input_never_returns_a_string(self):
        for ulpin, domain, level, unit in [
            ("GEOSX1234", "A", "G", "1"),
            ("GEOSX00001", "E", "G", "1"),
            ("GEOSX00001", "A", "F1000", "1"),
            ("GEOSX00001", "A", 1000, "1"),
            ("GEOSX00001", "A", "G", "007"),
            ("GEOSX00001", "A", "G", "1234567"),
        ]:
            with pytest.raises(VDCValidationError):
                generate_vdc(ulpin, domain, level, unit)


class TestDeterminism:
    def test_repeated_generation_is_identical(self):
        for _ in range(1000):
            assert generate_vdc("GEOSX00007", "C", "F120", "25B") == "GEOSX00007-C-F120-25B-QF"

    def test_repeated_generation_across_all_examples(self):
        for ulpin, domain, level, unit, expected in SPEC_EXAMPLES:
            produced = {generate_vdc(ulpin, domain, level, unit) for _ in range(25)}
            assert produced == {expected}

    def test_generation_does_not_mutate_inputs(self):
        inputs = ["GEOSX00001", "A", "G", "1"]
        generate_vdc(*inputs)
        assert inputs == ["GEOSX00001", "A", "G", "1"]

    def test_no_module_level_mutable_state_is_exposed(self):
        exported = {
            name: value for name, value in vars(vdc_generator).items() if not name.startswith("__")
        }
        assert not any(isinstance(value, (list, dict, set)) for value in exported.values())


class TestPurity:
    def test_generator_module_performs_no_io(self):
        source = inspect.getsource(vdc_generator)
        for forbidden in [
            "import os",
            "import sys",
            "import random",
            "import datetime",
            "import time",
            "import socket",
            "sqlalchemy",
            "requests",
            "httpx",
            "open(",
            "Path(",
        ]:
            assert forbidden not in source, f"generator must not reference {forbidden!r}"

    def test_generator_module_does_not_import_services_or_routes(self):
        source = inspect.getsource(vdc_generator)
        for forbidden in ["app.services", "app.api", "app.models", "app.routers"]:
            assert forbidden not in source, f"generator must not reference {forbidden!r}"

    def test_generation_needs_no_database(self, monkeypatch):
        from app.core import database

        def explode(*args, **kwargs):
            raise AssertionError("generator must not touch the database")

        for name in ("get_db", "SessionLocal", "engine"):
            assert hasattr(database, name), f"app.core.database lost {name}"
            monkeypatch.setattr(database, name, explode)
        assert generate_vdc("GEOSX00001", "A", "G", "1") == "GEOSX00001-A-G-1-ZY"
