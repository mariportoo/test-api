from datetime import datetime, timedelta, timezone
from models import AccessTokenModel, ClientModel
from security import hash_password


def test_issue_token_success(client, db_session):
    """Exchange valid client_id and client_secret for an alphanumeric access token."""
    cid = "valid_client_1"
    secret = "valid_secret_12345"

    p_hash, p_salt = hash_password("Password123!")
    db_session.add(
        ClientModel(
            client_id=cid,
            client_secret=secret,
            name="Auth Test Client",
            email="auth@example.com",
            password_hash=p_hash,
            password_salt=p_salt,
            is_active=True,
        )
    )
    db_session.commit()

    res = client.post(
        "/auth/token",
        json={"client_id": cid, "client_secret": secret},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert len(data["access_token"]) == 40
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 86400  # 24 hours in seconds


def test_issue_token_invalid_secret(client, db_session):
    """Reject token issuance when client_secret does not match."""
    cid = "client_wrong_secret"
    db_session.add(
        ClientModel(
            client_id=cid,
            client_secret="correct_secret",
            name="Wrong Secret Corp",
            is_active=True,
        )
    )
    db_session.commit()

    res = client.post(
        "/auth/token",
        json={"client_id": cid, "client_secret": "incorrect_secret"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid client ID or client secret."


def test_issue_token_inactive_client(client, db_session):
    """Deactivated clients cannot generate access tokens."""
    cid = "inactive_client_id"
    secret = "secret_active_check"

    db_session.add(
        ClientModel(
            client_id=cid,
            client_secret=secret,
            name="Inactive Client",
            is_active=False,
        )
    )
    db_session.commit()

    res = client.post(
        "/auth/token",
        json={"client_id": cid, "client_secret": secret},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid client ID or client secret."


def test_token_expiration_blocks_requests(client, db_session):
    """Expired tokens must be denied access with 403."""
    cid = "expired_token_client"
    expired_token_str = "expired_token_99999"

    db_session.add(
        ClientModel(
            client_id=cid,
            client_secret="secret123",
            name="Expired Client",
            is_active=True,
        )
    )
    # Seed token expired 10 minutes ago
    db_session.add(
        AccessTokenModel(
            token=expired_token_str,
            client_id=cid,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
    )
    db_session.commit()

    res = client.get(f"/offers/{cid}", headers={"X-Token": expired_token_str})
    assert res.status_code == 403
    assert "Token expired" in res.json()["detail"]