from __future__ import annotations

import pytest

from app.schemas.vdc import VDCErrorDetail, VDCParsed
from app.validators.vdc_parser import (
    VDCValidationError,
    parse_vdc,
    validate_vdc,
)

WORKED_EXAMPLES = [
    # (vdc, ulpin, domain, level, unit, checksum)
    ("GEOSX00001-A-G-1-ZY", "GEOSX00001", "A", "G", "1", "ZY"),
    ("GEOSX00002-A-F5-3-6I", "GEOSX00002", "A", "F5", "3", "6I"),
    ("GEOSX00003-A-F12-804-E6", "GEOSX00003", "A", "F12", "804", "E6"),
    ("GEOSX00004-A-B1-4-1O", "GEOSX00004", "A", "B1", "4", "1O"),
    ("GEOSX00005-A-B3-7-7U", "GEOSX00005", "A", "B3", "7", "7U"),
    ("GEOSX00006-B-G-105-AQ", "GEOSX00006", "B", "G", "105", "AQ"),
    ("GEOSX00007-C-F120-25B-QF", "GEOSX00007", "C", "F120", "25B", "QF"),
    ("GEOSX00008-A-G-1001-7C", "GEOSX00008", "A", "G", "1001", "7C"),
    ("GEOSX00009-B-B2-9A-NU", "GEOSX00009", "B", "B2", "9A", "NU"),
    ("GEOSX00010-A-F9-5-BF", "GEOSX00010", "A", "F9", "5", "BF"),
    ("GEOSX00011-A-F999-1234AB-KZ", "GEOSX00011", "A", "F999", "1234AB", "KZ"),
    ("GEOSX00012-D-B9-3-AS", "GEOSX00012", "D", "B9", "3", "AS"),
]

VALID_LEVELS = ["G", "F1", "F5", "F9", "F12", "F120", "F999", "B1", "B3", "B9", "B999"]
INVALID_LEVELS = ["F0", "F01", "F000", "B0", "B03", "B000", "F1000", "B1000"]
VALID_UNITS = ["1", "804", "1001", "25B", "9A", "1234AB", "AB12", "A"]


def _error_for(vdc: str, *, name: str) -> VDCErrorDetail:
    errors = validate_vdc(vdc)
    assert len(errors) == 1, f"expected exactly 1 error for {vdc!r}, got {errors}"
    assert errors[0].segment == name
    return errors[0]


class TestWorkedExamples:
    @pytest.mark.parametrize("vdc,ulpin,domain,level,unit,checksum", WORKED_EXAMPLES)
    def test_worked_example_parses(self, vdc, ulpin, domain, level, unit, checksum):
        result = parse_vdc(vdc)
        assert isinstance(result, VDCParsed)
        assert result.model_dump() == {
            "ulpin": ulpin,
            "domain": domain,
            "level": level,
            "unit": unit,
            "checksum": checksum,
        }

    def test_successful_decomposition_into_all_five_fields(self):
        parsed = parse_vdc("GEOSX00001-A-G-1-ZY")
        assert parsed.ulpin == "GEOSX00001"
        assert parsed.domain == "A"
        assert parsed.level == "G"
        assert parsed.unit == "1"
        assert parsed.checksum == "ZY"


class TestStructure:
    @pytest.mark.parametrize(
        "vdc,count",
        [
            ("GEOSX00001-A-G-1", 4),
            ("GEOSX00001-A-G-1-ZY-extra", 6),
            ("GEOSX00001-A-G-1-ZY-1-2", 7),
            ("GEOSX00001AG1ZY", 1),
            ("-GEOSX00001-A-G-1-ZY", 6),
            ("GEOSX00001-A-G-1-ZY-", 6),
            ("GEOSX00001-A-G-25-B-ZY", 6),
            ("", 1),
        ],
    )
    def test_wrong_segment_count(self, vdc, count):
        error = _error_for(vdc, name="structure")
        assert error.code == "invalid_segment_count"
        assert str(count) in error.message

    def test_missing_hyphens(self):
        error = _error_for("GEOSX00001AG1ZY", name="structure")
        assert error.code == "invalid_segment_count"

    def test_extra_hyphens(self):
        error = _error_for("GEOSX00001-A-G-1-ZY-extra", name="structure")
        assert error.code == "invalid_segment_count"

    @pytest.mark.parametrize(
        "vdc",
        [
            "GEOSX00001--G-1-ZY",
            "GEOSX00001-A--1-ZY",
            "GEOSX00001-A-G--ZY",
        ],
    )
    def test_empty_segments(self, vdc):
        error = _error_for(vdc, name="structure")
        assert error.code == "empty_segment"
        assert "empty" in error.message

    def test_all_blank_segments(self):
        errors = validate_vdc("----")
        assert len(errors) == 5
        assert all(
            error.segment == "structure" and error.code == "empty_segment" for error in errors
        )


class TestUlipin:
    @pytest.mark.parametrize(
        "vdc",
        [
            "GEOSX0001-A-G-1-ZY",
            "GEOSX00001A-A-G-1-ZY",
            "ABCDE12345-A-G-1-ZY",
            "GEOSX0000A-A-G-1-ZY",
            "GEOSX1234-A-G-1-ZY",
        ],
    )
    def test_invalid_ulpin(self, vdc):
        error = _error_for(vdc, name="ulpin")
        assert error.code == "invalid_ulpin"
        assert "GEOSX" in error.message


class TestDomain:
    @pytest.mark.parametrize("code", ["E", "Z", "K", "X"])
    def test_invalid_domain(self, code):
        error = _error_for(f"GEOSX00001-{code}-G-1-ZY", name="domain")
        assert error.code == "invalid_domain"
        assert "A, B, C, D" in error.message

    def test_lowercase_domain(self):
        error = _error_for("GEOSX00001-a-G-1-ZY", name="domain")
        assert error.code == "lowercase_character"
        assert "a" in error.message


class TestLevel:
    @pytest.mark.parametrize("level", INVALID_LEVELS)
    def test_invalid_level(self, level):
        error = _error_for(f"GEOSX00001-A-{level}-1-ZY", name="level")
        assert error.code == "invalid_level"

    @pytest.mark.parametrize("level", ["F01", "F05", "B03", "B000", "F000"])
    def test_level_leading_zeros(self, level):
        error = _error_for(f"GEOSX00001-A-{level}-1-ZY", name="level")
        assert error.code == "invalid_level"

    @pytest.mark.parametrize("level", ["F", "B", "X", "FG", "FF", "123"])
    def test_malformed_level(self, level):
        error = _error_for(f"GEOSX00001-A-{level}-1-ZY", name="level")
        assert error.code == "invalid_level"


class TestUnit:
    @pytest.mark.parametrize("unit", ["25*B", "A$", "12 3"])
    def test_invalid_unit_characters(self, unit):
        error = _error_for(f"GEOSX00001-A-G-{unit}-ZY", name="unit")
        assert error.code == "invalid_character"

    @pytest.mark.parametrize("unit", ["0", "01", "007", "00A"])
    def test_unit_leading_zero(self, unit):
        error = _error_for(f"GEOSX00001-A-G-{unit}-ZY", name="unit")
        assert error.code == "invalid_unit"
        assert "leading" in error.message.lower() or "non-zero" in error.message.lower()

    @pytest.mark.parametrize("unit", ["25b", "1234aa", "ab12"])
    def test_unit_lowercase(self, unit):
        error = _error_for(f"GEOSX00001-A-G-{unit}-ZY", name="unit")
        assert error.code == "lowercase_character"

    def test_unit_length_gt_6(self):
        error = _error_for("GEOSX00001-A-G-1234ABC-ZY", name="unit")
        assert error.code == "invalid_unit"


class TestChecksum:
    @pytest.mark.parametrize("checksum", ["A!", "Z.", "A_", "1$"])
    def test_invalid_checksum_characters(self, checksum):
        error = _error_for(f"GEOSX00001-A-G-1-{checksum}", name="checksum")
        assert error.code == "invalid_character"

    @pytest.mark.parametrize("checksum", ["zy", "a0", "bC"])
    def test_checksum_lowercase(self, checksum):
        error = _error_for(f"GEOSX00001-A-G-1-{checksum}", name="checksum")
        assert error.code == "lowercase_character"

    @pytest.mark.parametrize("checksum", ["Z", "ZY1", "00A"])
    def test_checksum_wrong_length(self, checksum):
        error = _error_for(f"GEOSX00001-A-G-1-{checksum}", name="checksum")
        assert error.code == "invalid_checksum"

    def test_valid_checksum_format_accepted(self):
        # Any 2 uppercase base-36 chars should be structurally accepted
        # (checksum verification is Feature 16)
        for checksum in ["ZY", "AB", "12", "Z9", "00", "9Z"]:
            parsed = parse_vdc(f"GEOSX00001-A-G-1-{checksum}")
            assert parsed.checksum == checksum


class TestWhitespace:
    @pytest.mark.parametrize(
        "vdc",
        [
            "GEOSX00001-A-G-1-Z Y",
            "GEOSX00001-A-G -1-ZY",
            "GEOSX00001-A-G\n-1-ZY",
            "\tGEOSX00001-A-G\t-1-ZY\t",
        ],
    )
    def test_internal_whitespace(self, vdc):
        assert validate_vdc(vdc), f"expected internal whitespace to be rejected: {vdc!r}"

    @pytest.mark.parametrize(
        "vdc",
        [
            "  GEOSX00001-A-G-1-ZY  ",
            "\tGEOSX00001-A-G-1-ZY\t",
            "\nGEOSX00001-A-G-1-ZY\r\n",
            " \t GEOSX00001-A-G-1-ZY \t ",
        ],
    )
    def test_leading_trailing_whitespace_stripped_before_validation(self, vdc):
        parsed = parse_vdc(vdc)
        assert parsed.model_dump() == {
            "ulpin": "GEOSX00001",
            "domain": "A",
            "level": "G",
            "unit": "1",
            "checksum": "ZY",
        }


class TestDeterminism:
    def test_repeated_parsing_is_deterministic(self):
        vdc = "GEOSX00007-C-F120-25B-QF"
        expected = parse_vdc(vdc)
        for _ in range(25):
            assert parse_vdc(vdc).model_dump() == expected.model_dump()

    def test_repeated_validation_errors_are_deterministic(self):
        vdc = "GEOSX00001-A-G-01-ZY"
        expected = [error.model_dump() for error in validate_vdc(vdc)]
        assert expected
        for _ in range(25):
            assert [error.model_dump() for error in validate_vdc(vdc)] == expected


class TestBoundaryValues:
    @pytest.mark.parametrize("level", VALID_LEVELS)
    def test_boundary_levels_are_valid(self, level):
        parsed = parse_vdc(f"GEOSX00001-A-{level}-1-ZY")
        assert parsed.level == level

    @pytest.mark.parametrize("unit", VALID_UNITS)
    def test_boundary_units_are_valid(self, unit):
        parsed = parse_vdc(f"GEOSX00001-A-G-{unit}-ZY")
        assert parsed.unit == unit

    def test_min_and_max_canonical_lengths(self):
        assert len("GEOSX00001-A-G-1-ZY") == 19
        assert len("GEOSX00011-A-F999-1234AB-KZ") == 27
        assert parse_vdc("GEOSX00001-A-G-1-ZY").checksum == "ZY"
        assert parse_vdc("GEOSX00011-A-F999-1234AB-KZ").unit == "1234AB"


class TestValidationError:
    def test_validation_error_structure(self):
        with pytest.raises(VDCValidationError) as excinfo:
            parse_vdc("GEOSX00001-A-G-1-zy")
        assert isinstance(excinfo.value, ValueError)
        assert isinstance(excinfo.value.errors, tuple)
        detail = excinfo.value.error
        assert isinstance(detail, VDCErrorDetail)
        assert detail.segment == "checksum"
        assert detail.code == "lowercase_character"
        assert detail.message
        assert "checksum" in str(excinfo.value)

    @pytest.mark.parametrize(
        "vdc,segment,code",
        [
            ("GEOSX00001-Z-G-1-ZY", "domain", "invalid_domain"),
            ("GEOSX00001-A-F01-1-ZY", "level", "invalid_level"),
            ("GEOSX00001-A-G-01-ZY", "unit", "invalid_unit"),
            ("GEOSX00001-A-G-1-zy", "checksum", "lowercase_character"),
            ("GEOSX00001-A-G-1", "structure", "invalid_segment_count"),
            ("GEOSX00001-A-G-1-ZY-extra", "structure", "invalid_segment_count"),
        ],
    )
    def test_task_examples_identify_affected_segment(self, vdc, segment, code):
        error = _error_for(vdc, name=segment)
        assert error.code == code

    def test_multiple_segment_errors_are_collected(self):
        errors = validate_vdc("GEOSX00001-Z-F01-01-zy")
        codes = {error.segment: error.code for error in errors}
        assert codes == {
            "domain": "invalid_domain",
            "level": "invalid_level",
            "unit": "invalid_unit",
            "checksum": "lowercase_character",
        }

    def test_no_silent_uppercasing_of_lowercase_input(self):
        errors = validate_vdc("GEOSX00001-a-G-25b-zy")
        assert [error.code for error in errors] == [
            "lowercase_character",
            "lowercase_character",
            "lowercase_character",
        ]

    def test_validate_vdc_returns_empty_list_for_valid(self):
        assert validate_vdc("GEOSX00001-A-G-1-ZY") == []

    def test_validate_vdc_does_not_raise(self):
        errors = validate_vdc("GEOSX00001-A-G-1")
        assert errors and errors[0].code == "invalid_segment_count"

    def test_non_string_input_raises_type_error(self):
        with pytest.raises(TypeError):
            parse_vdc(None)  # type: ignore[arg-type]
