import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealth:
    def test_health_endpoint(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "geosix-api"

    def test_root_endpoint(self):
        response = client.get("/api/v1")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "GEOSIX API"
        assert "version" in data
        assert data["docs"] == "/docs"


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
        error = data.get("detail", data).get("error", data)
        assert error["code"] == "EMAIL_EXISTS"

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
