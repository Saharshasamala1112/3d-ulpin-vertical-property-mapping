from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.vdc import VDCErrorDetail
from app.validators.vdc_checksum import verify_checksum
from app.validators.vdc_parser import parse_vdc, validate_vdc
from tests.auth_support import bearer_headers

client = TestClient(app, headers=bearer_headers("admin"))

GENERATE_URL = "/api/v1/vdc/generate"
VALIDATE_URL = "/api/v1/vdc/validate"
PARSE_URL = "/api/v1/vdc/parse"

# Worked examples from docs/vdc-specification.md section 11.
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


def _generate(**body):
    return client.post(GENERATE_URL, json=body)


def _validate(vdc: str):
    return client.post(VALIDATE_URL, json={"vdc": vdc})


def _parse(vdc: str):
    return client.post(PARSE_URL, json={"vdc": vdc})


def _assert_standard_error(response, error_code: str = "VALIDATION_ERROR") -> dict:
    """Assert the Feature 12 error envelope and return the body."""
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error_code", "message", "details"}
    assert body["error_code"] == error_code
    assert body["message"]
    assert isinstance(body["details"], dict)
    return body


@pytest.fixture(scope="module")
def schema() -> dict:
    return app.openapi()


class TestGenerateEndpoint:
    def test_ground_level(self):
        response = _generate(ulpin="GEOSX00001", domain="A", level="G", unit="1")
        assert response.status_code == 200
        assert response.json() == {"vdc": "GEOSX00001-A-G-1-ZY"}

    @pytest.mark.parametrize("level", ["F1", "F5", "F12", "F120", "F999"])
    def test_positive_floor(self, level):
        response = _generate(ulpin="GEOSX00001", domain="A", level=level, unit="1")
        assert response.status_code == 200
        assert response.json()["vdc"].split("-")[2] == level

    @pytest.mark.parametrize("level", ["B1", "B3", "B9", "B999"])
    def test_basement(self, level):
        response = _generate(ulpin="GEOSX00001", domain="A", level=level, unit="1")
        assert response.status_code == 200
        assert response.json()["vdc"].split("-")[2] == level

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_all_domain_codes(self, domain):
        response = _generate(ulpin="GEOSX00001", domain=domain, level="G", unit="1")
        assert response.status_code == 200
        assert response.json()["vdc"].split("-")[1] == domain

    @pytest.mark.parametrize("unit", ["1", "9", "25B", "9A", "1234AB", "A", "123456"])
    def test_alphanumeric_unit(self, unit):
        response = _generate(ulpin="GEOSX00001", domain="A", level="G", unit=unit)
        assert response.status_code == 200
        assert response.json()["vdc"].split("-")[3] == unit

    @pytest.mark.parametrize(
        "level,expected_level",
        [(0, "G"), (1, "F1"), (12, "F12"), (120, "F120"), (999, "F999"), (-1, "B1"), (-9, "B9")],
    )
    def test_integer_level_is_canonicalized(self, level, expected_level):
        response = _generate(ulpin="GEOSX00001", domain="A", level=level, unit="1")
        assert response.status_code == 200
        assert response.json()["vdc"].split("-")[2] == expected_level

    def test_never_emits_a_sign_or_zero_padding(self):
        # The work item's +012 / -003 forms must never reach the response.
        for level, expected_level in [(12, "F12"), (-3, "B3")]:
            vdc = _generate(ulpin="GEOSX00001", domain="A", level=level, unit="1").json()["vdc"]
            segments = vdc.split("-")
            assert segments[2] == expected_level
            assert "+" not in vdc
            assert not segments[2].startswith("-")
            assert not segments[3].startswith("0")

    @pytest.mark.parametrize("level", ["+012", "-003", "F01", "B03", "0", "F0", "B0"])
    def test_non_canonical_level_is_rejected(self, level):
        response = _generate(ulpin="GEOSX00001", domain="A", level=level, unit="1")
        _assert_standard_error(response)

    @pytest.mark.parametrize("level", [1000, -1000, 5000])
    def test_out_of_range_integer_level_is_rejected(self, level):
        response = _generate(ulpin="GEOSX00001", domain="A", level=level, unit="1")
        body = _assert_standard_error(response)
        assert body["details"]["vdc_errors"][0]["segment"] == "level"

    @pytest.mark.parametrize("ulpin", ["GEOSX1234", "GEOSX000012", "geosx00001", "ABCDE12345"])
    def test_invalid_ulpin_is_rejected(self, ulpin):
        body = _assert_standard_error(_generate(ulpin=ulpin, domain="A", level="G", unit="1"))
        assert body["details"]["vdc_errors"][0]["segment"] == "ulpin"

    @pytest.mark.parametrize("domain", ["E", "Z", "a", "1", "AB"])
    def test_invalid_domain_is_rejected(self, domain):
        body = _assert_standard_error(
            _generate(ulpin="GEOSX00001", domain=domain, level="G", unit="1")
        )
        assert body["details"]["vdc_errors"][0]["segment"] == "domain"

    @pytest.mark.parametrize("unit", ["0", "01", "007", "25b", "1234567", "25*B"])
    def test_invalid_unit_is_rejected(self, unit):
        body = _assert_standard_error(
            _generate(ulpin="GEOSX00001", domain="A", level="G", unit=unit)
        )
        assert body["details"]["vdc_errors"][0]["segment"] == "unit"

    def test_empty_unit_is_reported_as_a_structure_error(self):
        # Feature 15 short-circuits on an empty segment before per-segment checks.
        body = _assert_standard_error(_generate(ulpin="GEOSX00001", domain="A", level="G", unit=""))
        assert body["details"]["vdc_errors"][0]["segment"] == "structure"

    def test_error_detail_is_structured_and_preserves_segment_info(self):
        body = _assert_standard_error(_generate(ulpin="GEOSX1234", domain="A", level="G", unit="1"))
        details = body["details"]["vdc_errors"]
        assert details
        for detail in details:
            assert set(detail) == {"segment", "code", "message"}
            assert detail["segment"] == "ulpin"
            assert detail["code"] == "invalid_ulpin"
            assert "ULPIN" in detail["message"]

    def test_error_response_never_exposes_a_traceback(self):
        response = _generate(ulpin="BAD", domain="A", level="G", unit="1")
        text = response.text
        assert "Traceback" not in text
        assert "app/api/v1/vdc.py" not in text
        assert "app.services.vdc_generator" not in text

    @pytest.mark.parametrize("ulpin,domain,level,unit,expected", SPEC_EXAMPLES)
    def test_specification_examples(self, ulpin, domain, level, unit, expected):
        response = _generate(ulpin=ulpin, domain=domain, level=level, unit=unit)
        assert response.status_code == 200
        assert response.json() == {"vdc": expected}

    def test_generated_vdc_parses_correctly(self):
        for ulpin, domain, level, unit, _ in SPEC_EXAMPLES:
            vdc = _generate(ulpin=ulpin, domain=domain, level=level, unit=unit).json()["vdc"]
            parsed = parse_vdc(vdc)
            assert (parsed.ulpin, parsed.domain, parsed.level, parsed.unit) == (
                ulpin,
                domain,
                level,
                unit,
            )

    def test_generated_vdc_checksum_verifies(self):
        for ulpin, domain, level, unit, _ in SPEC_EXAMPLES:
            vdc = _generate(ulpin=ulpin, domain=domain, level=level, unit=unit).json()["vdc"]
            assert verify_checksum(vdc) is True

    def test_generated_vdc_is_accepted_by_the_validate_endpoint(self):
        vdc = _generate(ulpin="GEOSX00007", domain="C", level="F120", unit="25B").json()["vdc"]
        assert _validate(vdc).json() == {"valid": True, "errors": []}

    def test_generated_vdc_is_accepted_by_the_parse_endpoint(self):
        vdc = _generate(ulpin="GEOSX00007", domain="C", level=120, unit="25B").json()["vdc"]
        assert _parse(vdc).json() == {
            "ulpin": "GEOSX00007",
            "domain": "C",
            "level": "F120",
            "unit": "25B",
            "checksum": "QF",
        }


class TestValidateEndpoint:
    def test_valid_vdc(self):
        response = _validate("GEOSX00001-A-G-1-ZY")
        assert response.status_code == 200
        assert response.json() == {"valid": True, "errors": []}

    @pytest.mark.parametrize("ulpin,domain,level,unit,expected", SPEC_EXAMPLES)
    def test_all_specification_examples_are_valid(self, ulpin, domain, level, unit, expected):
        assert _validate(expected).json()["valid"] is True

    @pytest.mark.parametrize(
        "vdc,segment,code",
        [
            ("GEOSX1234-A-G-1-ZY", "ulpin", "invalid_ulpin"),
            ("GEOSX00001-E-G-1-ZY", "domain", "invalid_domain"),
            ("GEOSX00001-A-F0-1-ZY", "level", "invalid_level"),
            ("GEOSX00001-A-F01-1-ZY", "level", "invalid_level"),
            ("GEOSX00001-A-007-1-ZY", "level", "invalid_level"),
            ("GEOSX00001-A-G-0-ZY", "unit", "invalid_unit"),
            ("GEOSX00001-A-G-007-ZY", "unit", "invalid_unit"),
            ("GEOSX00001-A-G-1234567-ZY", "unit", "invalid_unit"),
        ],
    )
    def test_invalid_segment_is_reported(self, vdc, segment, code):
        response = _validate(vdc)
        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is False
        assert body["errors"]
        assert {"segment": segment, "code": code}.items() <= body["errors"][0].items()
        assert body["errors"][0]["message"]

    @pytest.mark.parametrize("vdc", ["nonsense", "GEOSX00001-A-G-1", "a-b-c-d-e-f", "GEOSX00001"])
    def test_malformed_vdc_is_reported(self, vdc):
        response = _validate(vdc)
        assert response.status_code == 200
        body = response.json()
        assert body["valid"] is False
        assert body["errors"][0]["segment"] in {"structure", "ulpin", "domain", "level", "unit"}

    @pytest.mark.parametrize("vdc", ["", "   ", "-", "----"])
    def test_empty_and_separator_only_input_is_reported(self, vdc):
        body = _validate(vdc).json()
        assert body["valid"] is False
        assert body["errors"]

    def test_invalid_checksum_is_reported(self):
        body = _validate("GEOSX00001-A-G-1-ZZ").json()
        assert body["valid"] is False
        assert len(body["errors"]) == 1
        error = body["errors"][0]
        assert error["segment"] == "checksum"
        assert error["code"] == "checksum_mismatch"
        assert "ZY" in error["message"] and "ZZ" in error["message"]

    def test_single_character_edit_is_detected_by_the_checksum(self):
        # Each edit keeps the VDC syntactically valid, so the only failure the
        # checksum engine can report is the checksum itself.
        for vdc in [
            "GEOSX00001-A-G-2-ZY",  # unit 1 -> 2
            "GEOSX00001-A-F1-1-ZY",  # ground -> first floor
            "GEOSX00001-A-B1-1-ZY",  # ground -> first basement
            "GEOSX00002-A-G-1-ZY",  # ULPIN digit
            "GEOSX00001-A-G-1-YY",  # checksum character
        ]:
            assert validate_vdc(vdc) == [], vdc
            body = _validate(vdc).json()
            assert body["valid"] is False
            assert body["errors"][0]["segment"] == "checksum"
            assert body["errors"][0]["code"] == "checksum_mismatch"

    @pytest.mark.parametrize(
        "vdc", ["geosx00001-a-g-1-zy", "GEOSx00001-A-G-1-ZY", "geosx00001-A-G-1-ZY"]
    )
    def test_lowercase_is_rejected_not_folded(self, vdc):
        body = _validate(vdc).json()
        assert body["valid"] is False
        assert any(error["code"] == "lowercase_character" for error in body["errors"])

    def test_outer_whitespace_is_ignored_per_feature_15(self):
        # Feature 15 strips the whole string; the API must not change that.
        for vdc in ["GEOSX00001-A-G-1-ZY", " GEOSX00001-A-G-1-ZY", "GEOSX00001-A-G-1-ZY "]:
            assert _validate(vdc).json() == {"valid": True, "errors": []}

    def test_inner_whitespace_is_rejected(self):
        body = _validate("GEOSX00001-A-G-1 5-ZY").json()
        assert body["valid"] is False
        assert body["errors"][0]["code"] == "invalid_character"

    def test_errors_are_structured_details(self):
        errors = _validate("GEOSX1234-A-G-1-ZY").json()["errors"]
        assert errors
        for error in errors:
            assert isinstance(VDCErrorDetail(**error), VDCErrorDetail)

    def test_lowercase_error_keeps_all_offending_segments(self):
        errors = _validate("geosx00001-a-g-1-zy").json()["errors"]
        assert {error["segment"] for error in errors} == {"ulpin", "domain", "level", "checksum"}

    def test_response_shape_is_exactly_valid_and_errors(self):
        body = _validate("GEOSX00001-A-G-1-ZZ").json()
        assert set(body) == {"valid", "errors"}
        assert isinstance(body["valid"], bool)
        assert isinstance(body["errors"], list)

    def test_invalid_vdc_is_not_an_http_error(self):
        # A malformed VDC is an expected answer here, so the status stays 200.
        assert _validate("nonsense").status_code == 200


class TestParseEndpoint:
    def test_returns_all_five_segments(self):
        response = _parse("GEOSX00001-A-G-1-ZY")
        assert response.status_code == 200
        assert response.json() == {
            "ulpin": "GEOSX00001",
            "domain": "A",
            "level": "G",
            "unit": "1",
            "checksum": "ZY",
        }

    @pytest.mark.parametrize("ulpin,domain,level,unit,expected", SPEC_EXAMPLES)
    def test_specification_examples(self, ulpin, domain, level, unit, expected):
        body = _parse(expected).json()
        assert body == {
            "ulpin": ulpin,
            "domain": domain,
            "level": level,
            "unit": unit,
            "checksum": expected.rsplit("-", 1)[1],
        }

    def test_parses_every_canonical_level_form(self):
        for level in ["G", "F1", "F12", "F999", "B1", "B3", "B999"]:
            vdc = _generate(ulpin="GEOSX00001", domain="A", level=level, unit="1").json()["vdc"]
            assert _parse(vdc).json()["level"] == level

    def test_outer_whitespace_is_ignored_per_feature_15(self):
        assert _parse("  GEOSX00001-A-G-1-ZY  ").json()["ulpin"] == "GEOSX00001"

    @pytest.mark.parametrize("vdc", ["nonsense", "", "GEOSX00001-A-G-1", "geosx00001-a-g-1-zy"])
    def test_invalid_vdc_returns_the_standard_error(self, vdc):
        body = _assert_standard_error(_parse(vdc))
        assert body["details"]["vdc_errors"]
        assert {"segment", "code", "message"} == set(body["details"]["vdc_errors"][0])

    def test_invalid_checksum_still_parses(self):
        # Parsing is structural; the checksum is reported by /validate.
        assert _parse("GEOSX00001-A-G-1-ZZ").json()["checksum"] == "ZZ"

    def test_never_splits_the_vdc_in_the_router(self):
        # Whatever the router does, the segments must equal the parser's output.
        for vdc in ["GEOSX00007-C-F120-25B-QF", "GEOSX00011-A-F999-1234AB-KZ"]:
            assert _parse(vdc).json() == parse_vdc(vdc).model_dump()


class TestRequestValidation:
    @pytest.mark.parametrize("url", [GENERATE_URL, VALIDATE_URL, PARSE_URL])
    def test_missing_body_is_rejected(self, url):
        assert client.post(url, json={}).status_code == 422

    @pytest.mark.parametrize("url", [VALIDATE_URL, PARSE_URL])
    def test_missing_vdc_field_is_rejected(self, url):
        response = client.post(url, json={"not_vdc": "GEOSX00001-A-G-1-ZY"})
        body = _assert_standard_error(response)
        assert body["message"] == "Request validation failed"
        assert "vdc" in body["details"]

    @pytest.mark.parametrize("url", [VALIDATE_URL, PARSE_URL])
    @pytest.mark.parametrize("value", [123, 1.5, None, True, ["GEOSX00001-A-G-1-ZY"], {"a": 1}])
    def test_wrong_field_type_is_rejected(self, url, value):
        _assert_standard_error(client.post(url, json={"vdc": value}))

    def test_invalid_json_body_is_rejected(self):
        response = client.post(
            VALIDATE_URL,
            content=b"{not json",
            headers={"Content-Type": "application/json"},
        )
        _assert_standard_error(response)

    @pytest.mark.parametrize("missing", ["ulpin", "domain", "level", "unit"])
    def test_missing_generate_field_is_rejected(self, missing):
        body = {"ulpin": "GEOSX00001", "domain": "A", "level": "G", "unit": "1"}
        del body[missing]
        response = _generate(**body)
        _assert_standard_error(response)
        assert missing in response.json()["details"]

    @pytest.mark.parametrize("value", [None, 12.5, ["G"], {"level": "G"}])
    def test_wrong_level_type_is_rejected(self, value):
        response = _generate(ulpin="GEOSX00001", domain="A", level=value, unit="1")
        _assert_standard_error(response)
        # The str | int union reports one entry per rejected member.
        assert any(key.startswith("level") for key in response.json()["details"])

    def test_empty_vdc_string_reaches_the_vdc_validator(self):
        # An empty value is a semantic VDC question, answered by /validate.
        assert _validate("").json()["valid"] is False
        _assert_standard_error(_parse(""))

    def test_wrong_method_is_not_allowed(self):
        assert client.get(GENERATE_URL).status_code == 405
        assert client.get(VALIDATE_URL).status_code == 405
        assert client.get(PARSE_URL).status_code == 405


class TestRequestIdHeader:
    def _assert_request_id(self, response) -> None:
        assert response.status_code < 500
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert request_id
        # A UUID4 string, as generated by the existing middleware.
        assert len(request_id) == 36
        assert request_id.count("-") == 4

    def test_generate_success(self):
        self._assert_request_id(_generate(ulpin="GEOSX00001", domain="A", level="G", unit="1"))

    def test_validate_success(self):
        self._assert_request_id(_validate("GEOSX00001-A-G-1-ZY"))

    def test_validate_invalid_vdc_still_succeeds(self):
        self._assert_request_id(_validate("nonsense"))

    def test_parse_success(self):
        self._assert_request_id(_parse("GEOSX00001-A-G-1-ZY"))

    def test_generate_error(self):
        self._assert_request_id(_generate(ulpin="BAD", domain="A", level="G", unit="1"))

    def test_parse_error(self):
        self._assert_request_id(_parse("nonsense"))

    def test_request_validation_error(self):
        self._assert_request_id(client.post(PARSE_URL, json={}))

    def test_request_id_is_not_constant_across_requests(self):
        first = _validate("GEOSX00001-A-G-1-ZY").headers["X-Request-ID"]
        second = _validate("GEOSX00001-A-G-1-ZY").headers["X-Request-ID"]
        assert first != second


class TestOpenApi:
    @pytest.mark.parametrize("url", [GENERATE_URL, VALIDATE_URL, PARSE_URL])
    def test_route_is_documented(self, schema, url):
        assert url in schema["paths"]
        assert "post" in schema["paths"][url]

    @pytest.mark.parametrize("url", [GENERATE_URL, VALIDATE_URL, PARSE_URL])
    def test_route_is_tagged_vdc(self, schema, url):
        assert schema["paths"][url]["post"]["tags"] == ["VDC"]

    def test_vdc_tag_is_declared(self, schema):
        assert "VDC" in [tag["name"] for tag in schema["tags"]]

    @pytest.mark.parametrize(
        "name",
        [
            "VDCGenerateRequest",
            "VDCGenerateResponse",
            "VDCValidateRequest",
            "VDCValidateResponse",
            "VDCParseRequest",
            "VDCParsed",
            "VDCErrorDetail",
        ],
    )
    def test_schema_is_registered(self, schema, name):
        assert name in schema["components"]["schemas"]

    def test_request_schemas_are_referenced(self, schema):
        for url in [GENERATE_URL, VALIDATE_URL, PARSE_URL]:
            body = schema["paths"][url]["post"]["requestBody"]
            assert body["content"]["application/json"]["schema"]["$ref"].startswith(
                "#/components/schemas/"
            )

    def test_response_schemas_are_referenced(self, schema):
        expected = {
            GENERATE_URL: "VDCGenerateResponse",
            VALIDATE_URL: "VDCValidateResponse",
            PARSE_URL: "VDCParsed",
        }
        for url, schema_name in expected.items():
            ref = schema["paths"][url]["post"]["responses"]["200"]["content"]["application/json"][
                "schema"
            ]["$ref"]
            assert ref == f"#/components/schemas/{schema_name}"

    def test_parse_reuses_the_parser_model(self, schema):
        assert (
            schema["paths"][PARSE_URL]["post"]["responses"]["200"]["content"]["application/json"][
                "schema"
            ]["$ref"]
            == "#/components/schemas/VDCParsed"
        )

    def test_standard_error_response_is_documented(self, schema):
        for url in [GENERATE_URL, VALIDATE_URL, PARSE_URL]:
            ref = schema["paths"][url]["post"]["responses"]["422"]["content"]["application/json"][
                "schema"
            ]["$ref"]
            assert ref == "#/components/schemas/ErrorResponse"

    def test_error_response_uses_the_standardized_shape(self, schema):
        properties = schema["components"]["schemas"]["ErrorResponse"]["properties"]
        assert set(properties) == {"error_code", "message", "details"}

    def test_request_fields_are_described(self, schema):
        for field in ["ulpin", "domain", "level", "unit"]:
            field_schema = schema["components"]["schemas"]["VDCGenerateRequest"]["properties"][
                field
            ]
            assert field_schema["description"]

    def test_level_accepts_string_or_integer(self, schema):
        types = schema["components"]["schemas"]["VDCGenerateRequest"]["properties"]["level"][
            "anyOf"
        ]
        assert {"type": "string"} in types
        assert {"type": "integer"} in types

    def test_endpoints_have_a_summary_and_description(self, schema):
        for url in [GENERATE_URL, VALIDATE_URL, PARSE_URL]:
            operation = schema["paths"][url]["post"]
            assert operation["summary"]
            assert operation["description"]


class TestIdempotency:
    def test_repeated_generate_returns_the_same_vdc(self):
        body = {"ulpin": "GEOSX00007", "domain": "C", "level": "F120", "unit": "25B"}
        responses = [_generate(**body) for _ in range(10)]
        assert {response.json()["vdc"] for response in responses} == {"GEOSX00007-C-F120-25B-QF"}

    def test_repeated_validate_returns_the_same_result(self):
        responses = [_validate("GEOSX00001-A-G-1-ZZ") for _ in range(10)]
        assert len({str(response.json()) for response in responses}) == 1

    def test_repeated_parse_returns_the_same_result(self):
        responses = [_parse("GEOSX00007-C-F120-25B-QF") for _ in range(10)]
        assert len({str(response.json()) for response in responses}) == 1

    def test_responses_contain_no_volatile_fields(self):
        # X-Request-ID varies by design, but the body must not.
        for url, body in [
            (GENERATE_URL, {"ulpin": "GEOSX00001", "domain": "A", "level": "G", "unit": "1"}),
            (VALIDATE_URL, {"vdc": "GEOSX00001-A-G-1-ZY"}),
            (PARSE_URL, {"vdc": "GEOSX00001-A-G-1-ZY"}),
        ]:
            keys = set(client.post(url, json=body).json())
            assert not keys & {"timestamp", "created_at", "request_id", "id", "sequence"}

    def test_integer_and_string_level_agree_through_the_api(self):
        for number, text in [(0, "G"), (12, "F12"), (-3, "B3"), (999, "F999")]:
            by_int = _generate(ulpin="GEOSX00001", domain="A", level=number, unit="1")
            by_text = _generate(ulpin="GEOSX00001", domain="A", level=text, unit="1")
            assert by_int.json() == by_text.json()

    def test_endpoints_do_not_persist_anything(self):
        # The same request is still valid after many other requests have run.
        for _ in range(5):
            assert _validate("GEOSX00001-A-G-1-ZY").json()["valid"] is True
            assert (
                _generate(ulpin="GEOSX00001", domain="A", level="G", unit="1").json()["vdc"]
                == "GEOSX00001-A-G-1-ZY"
            )
