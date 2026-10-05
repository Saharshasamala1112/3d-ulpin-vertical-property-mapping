import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
error_client = TestClient(app, raise_server_exceptions=False)


@app.get("/__test__/unhandled-error", include_in_schema=False)
async def _unhandled_error_route():
    raise RuntimeError("boom")


class TestHealth:
    def test_health_endpoint(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "geosix-api"

    def test_legacy_health_endpoint(self):
        response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # The allow-origin header now comes from the application's CORSMiddleware
        # (cors_origins defaults to the Vite dev origin), not from the handler.
        # The response is byte-identical either way, so this is not a regression.
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_root_endpoint(self):
        response = client.get("/api/v1")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "GEOSIX API"
        assert "version" in data
        assert data["docs"] == "/docs"

    def test_environment_settings_read_values(self):
        from app.core.config import Settings

        settings = Settings(
            database_url="postgresql://user:pass@localhost:5432/geosix",
            API_V1_PREFIX="/api/v1",
            debug="true",
        )
        assert settings.database_url == "postgresql://user:pass@localhost:5432/geosix"
        assert settings.api_v1_prefix == "/api/v1"
        assert settings.debug is True


class TestRegistration:
    def test_register_success(self):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "securepass123",
                "full_name": "Test User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"
        assert data["is_active"] is True
        assert "id" in data

    def test_register_duplicate_email(self):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@example.com",
                "password": "securepass123",
                "full_name": "Dup User",
            },
        )
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@example.com",
                "password": "securepass456",
                "full_name": "Dup User 2",
            },
        )
        assert response.status_code == 409
        data = response.json()
        assert data["error_code"] == "CONFLICT"
        assert data["message"] == "Email already registered"
        assert data["details"] == {}

    def test_register_short_password(self):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@example.com",
                "password": "123",
                "full_name": "Short",
            },
        )
        assert response.status_code == 422

    def test_register_invalid_email(self):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "securepass123",
                "full_name": "Bad Email",
            },
        )
        assert response.status_code == 422


class TestLogin:
    def test_login_success(self):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "securepass123",
                "full_name": "Login User",
            },
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "securepass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrong@example.com",
                "password": "securepass123",
                "full_name": "Wrong User",
            },
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        data = response.json()
        error = data.get("detail", data).get("error", data)
        assert error["code"] == "AUTHENTICATION_FAILED"

    def test_login_nonexistent_user(self):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "anything123"},
        )
        assert response.status_code == 401


class TestProtectedEndpoints:
    def _get_token(self):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "protected@example.com",
                "password": "securepass123",
                "full_name": "Protected User",
            },
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "protected@example.com", "password": "securepass123"},
        )
        return response.json()["access_token"]

    def test_me_authenticated(self):
        token = self._get_token()
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "protected@example.com"

    def test_me_unauthenticated(self):
        response = client.get("/api/v1/auth/me")
        assert response.status_code in (401, 403)

    def test_me_invalid_token(self):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token-here"},
        )
        assert response.status_code == 401

    def test_logout(self):
        token = self._get_token()
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"


class TestRefreshToken:
    def test_refresh_success(self):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@example.com",
                "password": "securepass123",
                "full_name": "Refresh User",
            },
        )
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "refresh@example.com", "password": "securepass123"},
        )
        refresh_token = login_response.json()["refresh_token"]
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_refresh_invalid_token(self):
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401


class TestErrorFormat:
    def test_error_response_format(self):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "bad@example.com", "password": "wrong"},
        )
        assert response.status_code == 401
        data = response.json()
        # FastAPI wraps in detail; our error is inside
        error_obj = data.get("detail", data)
        assert "error" in error_obj
        assert "code" in error_obj["error"]
        assert "message" in error_obj["error"]

    def test_request_id_header(self):
        response = client.get("/api/v1/health")
        assert "X-Request-ID" in response.headers

    def test_response_time_header(self):
        response = client.get("/api/v1/health")
        assert "X-Response-Time" in response.headers


class TestSwaggerEndpoints:
    def test_docs_accessible(self):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_accessible(self):
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_json_accessible(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "GEOSIX API"


class TestStandardizedErrors:
    def test_unknown_route_returns_standardized_not_found(self):
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        data = response.json()
        assert data == {
            "error_code": "NOT_FOUND",
            "message": "The requested resource was not found",
            "details": {},
        }

    def test_error_responses_include_request_id(self):
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        assert "X-Request-ID" in response.headers

    def test_validation_errors_expose_field_level_details(self):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "123", "full_name": ""},
        )
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert data["message"] == "Request validation failed"
        assert "email" in data["details"]
        assert "password" in data["details"]

    def test_duplicate_registration_returns_standardized_conflict(self):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "conflict@example.com",
                "password": "securepass123",
                "full_name": "Conflict User",
            },
        )
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "conflict@example.com",
                "password": "securepass456",
                "full_name": "Conflict User 2",
            },
        )
        assert response.status_code == 409
        data = response.json()
        assert data == {
            "error_code": "CONFLICT",
            "message": "Email already registered",
            "details": {},
        }

    def test_unhandled_exception_returns_standardized_internal_error(self):
        response = error_client.get("/__test__/unhandled-error")
        assert response.status_code == 500
        assert response.headers.get("X-Request-ID")
        data = response.json()
        assert data == {
            "error_code": "INTERNAL_ERROR",
            "message": "Internal server error",
            "details": {},
        }

    def test_unhandled_exception_is_logged_with_request_context(self, caplog):
        with caplog.at_level(logging.ERROR, logger="geosix"):
            response = error_client.get("/__test__/unhandled-error")
            request_id = response.headers["X-Request-ID"]
        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert request_id in message
        assert "GET" in message
        assert "/__test__/unhandled-error" in message
        assert "boom" in message

    def test_auth_401_preserves_legacy_error_body(self):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token-here"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"]["code"] == "INVALID_TOKEN"
        assert response.headers.get("WWW-Authenticate") == "Bearer"


class TestOpenAPIErrorContract:
    def test_openapi_defines_standardized_error_response(self):
        schema = client.get("/openapi.json").json()
        component = schema["components"]["schemas"]["ErrorResponse"]
        assert component["title"] == "ErrorResponse"
        assert set(component["properties"]) == {"error_code", "message", "details"}
        assert component["required"] == ["error_code", "message"]

    def test_openapi_standardizes_errors_on_register(self):
        schema = client.get("/openapi.json").json()
        register = schema["paths"]["/api/v1/auth/register"]["post"]
        error_ref = {"$ref": "#/components/schemas/ErrorResponse"}
        for status_code in ("404", "409", "422", "500"):
            response_schema = register["responses"][status_code]
            assert response_schema["content"]["application/json"]["schema"] == error_ref
            assert response_schema["description"]

    def test_openapi_adds_standardized_errors_to_health(self):
        schema = client.get("/openapi.json").json()
        health = schema["paths"]["/api/v1/health"]["get"]
        error_ref = {"$ref": "#/components/schemas/ErrorResponse"}
        assert health["responses"]["404"]["content"]["application/json"]["schema"] == error_ref
        assert health["responses"]["500"]["content"]["application/json"]["schema"] == error_ref
        assert "422" not in health["responses"]

    def test_openapi_401_keeps_legacy_error_model(self):
        schema = client.get("/openapi.json").json()
        me = schema["paths"]["/api/v1/auth/me"]["get"]
        response_schema = me["responses"]["401"]["content"]["application/json"]["schema"]
        assert response_schema == {"$ref": "#/components/schemas/LegacyAuthErrorResponse"}
        assert "LegacyAuthErrorResponse" in schema["components"]["schemas"]
