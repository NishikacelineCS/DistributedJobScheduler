import pytest

def test_register_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpassword",
            "organization_name": "Test Org"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "user" in data
    assert "organization" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["role"] == "admin"
    assert data["organization"]["name"] == "Test Org"

def test_register_duplicate_user(client):
    # Register first user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpassword",
            "organization_name": "Test Org"
        }
    )
    
    # Try duplicate registration
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "anotherpassword",
            "organization_name": "Another Org"
        }
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "A user with this email address already exists."

def test_login_and_get_me(client):
    # Register user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "password": "mysecretpassword",
            "organization_name": "Login Corp"
        }
    )

    # Login
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "login@example.com",
            "password": "mysecretpassword"
        }
    )
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Get /me with token
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    me_response = client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["email"] == "login@example.com"
    assert "organization_id" in me_data

def test_get_me_unauthorized(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

def test_get_me_invalid_token(client):
    headers = {"Authorization": "Bearer invalidtokenhere"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
