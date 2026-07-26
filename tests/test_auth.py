from fastapi import status


def test_login_success(client):
    # Form data login
    response = client.post(
        "/auth/token", data={"username": "admin@test.com", "password": "password123"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    response = client.post(
        "/auth/token", data={"username": "admin@test.com", "password": "wrongpassword"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect email or password"


def test_register_user_success(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "newuser@test.com",
            "name": "New User",
            "password": "newpassword123",
            "role": "parent",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "newuser@test.com"
    assert data["name"] == "New User"
    assert data["role"] == "parent"
    assert "id" in data


def test_register_duplicate_email(client):
    # Try to register admin's email which already exists in seed test DB
    response = client.post(
        "/auth/register",
        json={
            "email": "admin@test.com",
            "name": "Admin Clone",
            "password": "password123",
            "role": "admin",
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Email already registered"


def test_seed_database(client):
    response = client.post("/auth/seed")
    assert response.status_code == status.HTTP_200_OK
    assert "seeded" in response.json()["message"].lower()
