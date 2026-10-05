from __future__ import annotations

import time

import pytest

from app.schemas.vdc import VDCParsed
from app.validators.vdc_checksum import BASE, CHARSET, VALUE, compute_checksum, verify_checksum
from app.validators.vdc_parser import parse_vdc

# Worked examples, verbatim from docs/vdc-specification.md section 11.
SPEC_EXAMPLES = [
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

# Additional vectors spanning the full legal segment space. Expected values are
# cross-checked against the reference transcription of the specification in
# TestSpecificationAlgorithm, not against the implementation under test.
EXTRA_VECTORS = [
    ("GEOSX00000-A-F1-1-YQ", "GEOSX00000", "A", "F1", "1", "YQ"),
    ("GEOSX12345-B-B1-10-AB", "GEOSX12345", "B", "B1", "10", "AB"),
    ("GEOSX54321-C-F999-AB12-SC", "GEOSX54321", "C", "F999", "AB12", "SC"),
    ("GEOSX77777-A-G-1234AB-RH", "GEOSX77777", "A", "G", "1234AB", "RH"),
    ("GEOSX10000-A-G-1-ZU", "GEOSX10000", "A", "G", "1", "ZU"),
    ("GEOSX99999-D-B999-Z9-3V", "GEOSX99999", "D", "B999", "Z9", "3V"),
    # Checksums that legitimately contain '0' (specification section 12).
    ("GEOSX00002-A-G-1-08", "GEOSX00002", "A", "G", "1", "08"),
    ("GEOSX00001-A-G-2-0B", "GEOSX00001", "A", "G", "2", "0B"),
    ("GEOSX00024-A-B1-1-00", "GEOSX00024", "A", "B1", "1", "00"),
]

DOMAINS = ["A", "B", "C", "D"]
LEVELS = ["G", "F1", "F5", "F9", "F12", "F120", "F999", "B1", "B3", "B9", "B999"]
UNITS = ["1", "5", "9", "10", "105", "804", "1001", "25B", "9A", "1234AB", "AB12", "Z9"]
ULPINS = ["GEOSX00000", "GEOSX00001", "GEOSX00042", "GEOSX12345", "GEOSX99999"]


def _reference_checksum(ulpin: str, domain: str, level: str, unit: str) -> str:
    """Specification section 9.3 pseudocode, transcribed literally and independently."""
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    checksum_input = ulpin + domain + level + unit
    c1 = 0
    c2 = 0
    for i in range(len(checksum_input)):
        v = chars.index(checksum_input[i])
        c1 = (c1 + v) % 36
        c2 = (c2 + ((i + 1) * v)) % 36
    return chars[c1] + chars[c2]


def _segments(ulpin: str, domain: str, level: str, unit: str, checksum: str = "ZZ") -> VDCParsed:
    return VDCParsed(ulpin=ulpin, domain=domain, level=level, unit=unit, checksum=checksum)


def _reference_vdc(ulpin: str, domain: str, level: str, unit: str) -> str:
    checksum = _reference_checksum(ulpin, domain, level, unit)
    return f"{ulpin}-{domain}-{level}-{unit}-{checksum}"


class TestSpecExamples:
    @pytest.mark.parametrize("vdc,ulpin,domain,level,unit,checksum", SPEC_EXAMPLES)
    def test_spec_example_computes_spec_checksum(self, vdc, ulpin, domain, level, unit, checksum):
        parsed = parse_vdc(vdc)
        assert compute_checksum(parsed) == checksum

    @pytest.mark.parametrize("vdc,ulpin,domain,level,unit,checksum", SPEC_EXAMPLES)
    def test_spec_example_verifies(self, vdc, ulpin, domain, level, unit, checksum):
        assert verify_checksum(vdc) is True

    @pytest.mark.parametrize("vdc,ulpin,domain,level,unit,checksum", SPEC_EXAMPLES)
    def test_spec_example_segments_are_canonical(self, vdc, ulpin, domain, level, unit, checksum):
        parsed = parse_vdc(vdc)
        assert parsed.model_dump() == {
            "ulpin": ulpin,
            "domain": domain,
            "level": level,
            "unit": unit,
            "checksum": checksum,
        }

    def test_worked_example_1_accumulator_derivation(self):
        # docs/vdc-specification.md section 9.3 / 11.1: c1 = 143 mod 36 = 35 ('Z'),
        # c2 = 718 mod 36 = 34 ('Y').
        checksum_input = "GEOSX00001" + "A" + "G" + "1"
        assert checksum_input == "GEOSX00001AG1"
        c1 = sum(VALUE[char] for char in checksum_input)
        c2 = sum((i + 1) * VALUE[char] for i, char in enumerate(checksum_input))
        assert c1 == 143
        assert c2 == 718
        assert CHARSET[c1 % BASE] + CHARSET[c2 % BASE] == "ZY"
        assert compute_checksum(_segments("GEOSX00001", "A", "G", "1")) == "ZY"

    @pytest.mark.parametrize("vdc,ulpin,domain,level,unit,checksum", EXTRA_VECTORS)
    def test_additional_vector(self, vdc, ulpin, domain, level, unit, checksum):
        assert compute_checksum(parse_vdc(vdc)) == checksum
        assert verify_checksum(vdc) is True


class TestSpecificationAlgorithm:
    @pytest.mark.parametrize("vdc,ulpin,domain,level,unit,checksum", SPEC_EXAMPLES)
    def test_reference_reproduces_spec_checksums(self, vdc, ulpin, domain, level, unit, checksum):
        assert _reference_checksum(ulpin, domain, level, unit) == checksum

    def test_implementation_matches_reference_across_segment_space(self):
        mismatches = []
        for ulpin in ULPINS:
            for domain in DOMAINS:
                for level in LEVELS:
                    for unit in UNITS:
                        segments = _segments(ulpin, domain, level, unit)
                        if compute_checksum(segments) != _reference_checksum(
                            ulpin, domain, level, unit
                        ):
                            mismatches.append(segments.model_dump())
        assert mismatches == []

    def test_reference_vdc_strings_round_trip_through_verify(self):
        for vdc in (_reference_vdc("GEOSX00003", "A", "F12", "804"),):
            assert verify_checksum(vdc) is True

    def test_charset_is_base_36_in_spec_order(self):
        assert CHARSET == "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        assert BASE == 36
        assert VALUE["0"] == 0
        assert VALUE["9"] == 9
        assert VALUE["A"] == 10
        assert VALUE["Z"] == 35
        assert len(VALUE) == 36

    def test_checksum_output_is_always_two_base_36_characters(self):
        for ulpin in ULPINS:
            for domain in DOMAINS:
                for level in LEVELS:
                    for unit in UNITS:
                        result = compute_checksum(_segments(ulpin, domain, level, unit))
                        assert len(result) == 2
                        assert all(char in CHARSET for char in result)
                        assert result == result.upper()

    def test_checksum_ignores_the_supplied_checksum_field(self):
        digests = {
            compute_checksum(_segments("GEOSX00007", "C", "F120", "25B", checksum))
            for checksum in ["ZZ", "00", "QF", "A1"]
        }
        assert digests == {"QF"}

    def test_single_character_substitution_always_changes_the_checksum(self):
        base = "GEOSX00001-A-G-1"
        original = verify_checksum(f"{base}-ZY")
        assert original is True
        for index, char in enumerate(base):
            for replacement in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                if replacement == char:
                    continue
                candidate = base[:index] + replacement + base[index + 1 :]
                assert verify_checksum(f"{candidate}-ZY") is False, (candidate, char, replacement)

    def test_positional_weight_detects_transposition_of_different_characters(self):
        # F12 and F21 have the same digit sum, so c1 ('E') is unchanged; only the
        # positionally weighted c2 ('6' vs '5') differs.
        assert compute_checksum(_segments("GEOSX00003", "A", "F12", "804")) == "E6"
        assert compute_checksum(_segments("GEOSX00003", "A", "F21", "804")) == "E5"
        assert verify_checksum("GEOSX00003-A-F12-804-E6") is True
        assert verify_checksum("GEOSX00003-A-F21-804-E6") is False
        assert verify_checksum("GEOSX00003-A-F12-804-E5") is False

    def test_checksum_input_length_boundaries(self):
        # ULPIN(10) + DOMAIN(1) + LEVEL(1..4) + UNIT(1..6) => 13..21 characters.
        assert len("GEOSX00001" + "A" + "G" + "1") == 13
        assert len("GEOSX00001" + "A" + "F999" + "1234AB") == 21
        for level in LEVELS:
            for unit in UNITS:
                assert 13 <= len("GEOSX00001" + "A" + level + unit) <= 21
        # LEVEL contributes 1..4 characters, UNIT contributes 1..6.
        assert len("GEOSX00001" + "A" + "G" + "1") == len("GEOSX00001" + "A" + "G" + "9")
        assert len("GEOSX00001" + "A" + "F999" + "1") == 16
        assert len("GEOSX00001" + "A" + "G" + "1234AB") == 18

    def test_appending_a_zero_character_is_a_known_collision(self):
        # A trailing '0' contributes 0 to c1 and (position * 0) = 0 to c2, so it is
        # invisible to the Feature 14 algorithm. Specification section 15 states the
        # checksum cannot detect every error; the algorithm is implemented as written
        # rather than strengthened here.
        assert compute_checksum(_segments("GEOSX00001", "A", "G", "1")) == "ZY"
        assert compute_checksum(_segments("GEOSX00001", "A", "G", "10")) == "ZY"
        assert compute_checksum(_segments("GEOSX00001", "A", "G", "9A")) == "HQ"
        assert compute_checksum(_segments("GEOSX00001", "A", "G", "9A0")) == "HQ"
        assert verify_checksum("GEOSX00001-A-G-1-ZY") is True
        assert verify_checksum("GEOSX00001-A-G-10-ZY") is True
        # A zero inserted anywhere other than the end is still detected.
        assert verify_checksum("GEOSX00001-A-G-105-ZY") is False

    def test_minimum_and_maximum_length_vectors(self):
        minimum = "GEOSX00001-A-G-1-ZY"
        maximum = "GEOSX00011-A-F999-1234AB-KZ"
        assert len(minimum) == 19
        assert len(maximum) == 27
        assert verify_checksum(minimum) is True
        assert verify_checksum(maximum) is True

    def test_non_base_36_segment_character_is_not_coerced(self):
        with pytest.raises(KeyError):
            compute_checksum(_segments("geosx00001", "A", "G", "1"))


class TestDeterminism:
    def test_repeated_computation_is_identical(self):
        parsed = parse_vdc("GEOSX00007-C-F120-25B-QF")
        expected = compute_checksum(parsed)
        for _ in range(1000):
            assert compute_checksum(parsed) == expected == "QF"

    def test_repeated_verification_is_identical(self):
        vdc = "GEOSX00009-B-B2-9A-NU"
        results = {verify_checksum(vdc) for _ in range(500)}
        assert results == {True}

    def test_computation_does_not_mutate_input(self):
        parsed = parse_vdc("GEOSX00006-B-G-105-AQ")
        before = parsed.model_dump()
        for _ in range(25):
            compute_checksum(parsed)
        assert parsed.model_dump() == before

    def test_equivalent_instances_agree(self):
        first = _segments("GEOSX00011", "A", "F999", "1234AB")
        second = parse_vdc("GEOSX00011-A-F999-1234AB-00")
        assert compute_checksum(first) == compute_checksum(second) == "KZ"

    def test_verification_is_side_effect_free(self):
        vdc = "GEOSX00012-D-B9-3-AS"
        expected = verify_checksum(vdc)
        for _ in range(100):
            assert verify_checksum(vdc) is expected


class TestTampering:
    @pytest.mark.parametrize(
        "tampered",
        ["ZZ", "ZY1", "Z1", "00", "AB", "0Z", "1O", "zy", "Z!", "AA"],
    )
    def test_tampered_checksum_detected(self, tampered):
        assert verify_checksum(f"GEOSX00001-A-G-1-{tampered}") is False

    @pytest.mark.parametrize(
        "ulpin",
        [
            "GEOSX00002",
            "GEOSX00010",
            "GEOSX00099",
            "GEOSX99999",
            "GEOSX00000",
        ],
    )
    def test_tampered_ulpin_detected(self, ulpin):
        assert verify_checksum(f"{ulpin}-A-G-1-ZY") is False
        assert verify_checksum(_reference_vdc(ulpin, "A", "G", "1")) is True

    @pytest.mark.parametrize("ulpin", ["GEOSX0001O", "GEOSXOOO01", "GEOSX000012"])
    def test_structurally_invalid_ulpin_never_verifies(self, ulpin):
        assert verify_checksum(f"{ulpin}-A-G-1-ZY") is False
        assert verify_checksum(_reference_vdc(ulpin, "A", "G", "1")) is False

    @pytest.mark.parametrize("domain", ["B", "C", "D"])
    def test_tampered_domain_detected(self, domain):
        assert verify_checksum(f"GEOSX00001-{domain}-G-1-ZY") is False
        assert verify_checksum(_reference_vdc("GEOSX00001", domain, "G", "1")) is True

    @pytest.mark.parametrize("level", ["F1", "F5", "F12", "B1", "B9", "F999"])
    def test_tampered_level_detected(self, level):
        assert verify_checksum(f"GEOSX00001-A-{level}-1-ZY") is False
        assert verify_checksum(_reference_vdc("GEOSX00001", "A", level, "1")) is True

    @pytest.mark.parametrize("unit", ["2", "5", "9", "105", "804", "25B", "1234AB", "A1"])
    def test_tampered_unit_detected(self, unit):
        assert verify_checksum(f"GEOSX00001-A-G-{unit}-ZY") is False
        assert verify_checksum(_reference_vdc("GEOSX00001", "A", "G", unit)) is True

    def test_cross_segment_substitution_detected(self):
        assert verify_checksum("GEOSX00001-A-G-1-AQ") is False
        assert verify_checksum("GEOSX00006-A-G-105-AQ") is False

    def test_segments_swapped_between_ulpins_detected(self):
        assert verify_checksum("GEOSX00002-A-G-1-ZY") is False
        assert verify_checksum("GEOSX00001-A-G-2-ZY") is False

    def test_truncated_vdc_detected(self):
        assert verify_checksum("GEOSX00001-A-G-1-Z") is False
        assert verify_checksum("GEOSX00001-A-G-1-") is False


class TestMalformedInput:
    @pytest.mark.parametrize(
        "vdc",
        [
            "",
            "   ",
            "not a vdc",
            "GEOSX00001AG1ZY",
            "GEOSX00001-A-G-1-ZY-extra",
            "GEOSX00001-A-G-1-ZY-1-2",
            "GEOSX00001--G-1-ZY",
            "GEOSX00001-A--1-ZY",
            "GEOSX00001-A-G--ZY",
            "----",
            "-GEOSX00001-A-G-1-ZY",
            "GEOSX00001-A-G-1-ZY-",
            "GEOSX00001-A-G-25-B-ZY",
            "GEOSX00001,A,G,1,ZY",
            "GEOSX00001_A_G_1_ZY",
        ],
    )
    def test_malformed_vdc_returns_false(self, vdc):
        assert verify_checksum(vdc) is False

    @pytest.mark.parametrize(
        "ulpin",
        ["GEOSX0001", "GEOSX000012", "GEOS123456", "geosx00001", "GEOSX0000A", "ABCDE12345", ""],
    )
    def test_invalid_ulpin_returns_false(self, ulpin):
        assert verify_checksum(f"{ulpin}-A-G-1-ZY") is False

    @pytest.mark.parametrize("domain", ["E", "Z", "X", "1", "", "AB"])
    def test_invalid_domain_returns_false(self, domain):
        assert verify_checksum(f"GEOSX00001-{domain}-G-1-ZY") is False

    @pytest.mark.parametrize(
        "level", ["F0", "F01", "F000", "B0", "B03", "F1000", "B1000", "F", "B", "X", "123", "G1"]
    )
    def test_invalid_level_returns_false(self, level):
        assert verify_checksum(f"GEOSX00001-A-{level}-1-ZY") is False

    @pytest.mark.parametrize("unit", ["0", "01", "007", "00A", "1234ABC", "25b", "ab12", "A$B", ""])
    def test_invalid_unit_returns_false(self, unit):
        assert verify_checksum(f"GEOSX00001-A-G-{unit}-ZY") is False

    @pytest.mark.parametrize("checksum", ["A!", "Z.", "A_", "1$", "Z-Y", "A*B", "Z Y", "Z\tY"])
    def test_invalid_checksum_characters_return_false(self, checksum):
        assert verify_checksum(f"GEOSX00001-A-G-1-{checksum}") is False

    @pytest.mark.parametrize("checksum", ["Z", "", "ZY1", "000", "ZYZZ"])
    def test_invalid_checksum_length_returns_false(self, checksum):
        assert verify_checksum(f"GEOSX00001-A-G-1-{checksum}") is False

    @pytest.mark.parametrize(
        "vdc,uppercase_result",
        [
            ("geosx00001-A-G-1-ZY", True),
            ("GEOSX00001-a-G-1-ZY", True),
            ("GEOSX00001-A-g-1-ZY", True),
            ("geosx00001-a-g-1-zy", True),
            # Structurally fine once uppercased, but the checksum no longer matches
            # the segments, and internal whitespace is never legal.
            ("GEOSX00001-A-F1-1-zy", False),
            ("GEOSX00001-A-G-1-z y", False),
        ],
    )
    def test_lowercase_input_is_rejected_not_folded(self, vdc, uppercase_result):
        assert verify_checksum(vdc) is False
        assert verify_checksum(vdc.upper()) is uppercase_result

    def test_wrong_segment_count_returns_false(self):
        assert verify_checksum("GEOSX00001-A-G-1") is False
        assert verify_checksum("GEOSX00001-A-G") is False
        assert verify_checksum("GEOSX00001") is False

    def test_non_string_input_raises_type_error(self):
        with pytest.raises(TypeError):
            verify_checksum(None)  # type: ignore[arg-type]


class TestWhitespace:
    @pytest.mark.parametrize(
        "vdc",
        [
            "  GEOSX00001-A-G-1-ZY  ",
            "\tGEOSX00001-A-G-1-ZY\t",
            "\nGEOSX00001-A-G-1-ZY\r\n",
            " \t GEOSX00001-A-G-1-ZY \t ",
        ],
    )
    def test_outer_whitespace_is_stripped_before_validation(self, vdc):
        assert verify_checksum(vdc) is True

    @pytest.mark.parametrize(
        "vdc",
        [
            "GEOSX00001-A-G-1-Z Y",
            "GEOSX00001-A-G -1-ZY",
            "GEOSX00001-A-G\n-1-ZY",
            "GEOSX 00001-A-G-1-ZY",
            "GEOSX00001 -A-G-1-ZY",
        ],
    )
    def test_internal_whitespace_returns_false(self, vdc):
        assert verify_checksum(vdc) is False


class TestPerformance:
    def test_computation_is_well_under_one_millisecond(self):
        # Methodology: time.perf_counter around a batch of calls, reported as
        # the mean wall-clock cost of a single compute_checksum call. The
        # 1ms budget from Feature 16 is asserted with ~2 orders of magnitude of
        # headroom so the check stays stable on a loaded CI runner.
        parsed = parse_vdc("GEOSX00011-A-F999-1234AB-KZ")
        iterations = 2000
        compute_checksum(parsed)
        start = time.perf_counter()
        for _ in range(iterations):
            compute_checksum(parsed)
        elapsed = time.perf_counter() - start
        per_call_ms = elapsed / iterations * 1000
        assert per_call_ms < 1.0, f"compute_checksum took {per_call_ms:.4f}ms per call"

    def test_verification_is_well_under_one_millisecond(self):
        vdc = "GEOSX00007-C-F120-25B-QF"
        iterations = 1000
        verify_checksum(vdc)
        start = time.perf_counter()
        for _ in range(iterations):
            verify_checksum(vdc)
        elapsed = time.perf_counter() - start
        per_call_ms = elapsed / iterations * 1000
        assert per_call_ms < 1.0, f"verify_checksum took {per_call_ms:.4f}ms per call"
