from models import AccessTokenModel, ClientModel, OfferModel


def test_admin_unauthorized_access(client):
    """Admin endpoints without X-Admin-Key must return 401."""
    res = client.get("/admin/clients")
    assert res.status_code == 401
    assert res.json()["detail"] == "Unauthorized: Invalid admin credentials."


def test_admin_register_client_and_portal_first_login(client, admin_headers):
    """Admin registers a client; client logs into the portal using the temporary password."""
    # 1. Admin creates client without specifying password or IDs
    payload = {
        "name": "Acme Retargeting",
        "email": "developer@acme.com",
    }
    create_res = client.post("/admin/clients", json=payload, headers=admin_headers)
    assert create_res.status_code == 201
    created_data = create_res.json()

    assert created_data["email"] == "developer@acme.com"
    assert created_data["must_change_password"] is True
    temp_password = created_data["temporary_password"]
    assert temp_password is not None
    assert len(temp_password) == 16

    # 2. Client logs into portal with the temporary password
    login_res = client.post(
        "/portal/login",
        json={"email": "developer@acme.com", "password": temp_password},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["must_change_password"] is True
    assert login_data["client_id"] == created_data["client_id"]
    assert login_data["client_secret"] == created_data["client_secret"]


def test_portal_password_change_flow(client, admin_headers):
    """Mandatory first-login password change revokes the old password and activates the new one."""
    # Register client
    reg_res = client.post(
        "/admin/clients",
        json={"name": "Password Tester", "email": "pwd@test.com"},
        headers=admin_headers,
    )
    temp_password = reg_res.json()["temporary_password"]
    new_secure_pwd = "NewPermanentPassword456!"

    # Change password
    change_res = client.post(
        "/portal/change-password",
        json={
            "email": "pwd@test.com",
            "current_password": temp_password,
            "new_password": new_secure_pwd,
        },
    )
    assert change_res.status_code == 200
    assert change_res.json()["message"] == "Password updated successfully."

    # Verify old password fails
    old_login = client.post(
        "/portal/login",
        json={"email": "pwd@test.com", "password": temp_password},
    )
    assert old_login.status_code == 401

    # Verify new password succeeds with must_change_password=False
    new_login = client.post(
        "/portal/login",
        json={"email": "pwd@test.com", "password": new_secure_pwd},
    )
    assert new_login.status_code == 200
    assert new_login.json()["must_change_password"] is False


def test_admin_deactivate_blocks_portal_login(client, admin_headers):
    """Deactivating a client immediately locks them out of the portal."""
    # Register client
    reg = client.post(
        "/admin/clients",
        json={"name": "Lockout Inc", "email": "lockout@inc.com"},
        headers=admin_headers,
    ).json()
    cid = reg["client_id"]
    pwd = reg["temporary_password"]

    # Deactivate client
    status_res = client.patch(
        f"/admin/clients/{cid}/status",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert status_res.status_code == 200
    assert "deactivated" in status_res.json()["message"]

    # Portal login is now forbidden
    login_res = client.post(
        "/portal/login",
        json={"email": "lockout@inc.com", "password": pwd},
    )
    assert login_res.status_code == 403
    assert "Account is inactive" in login_res.json()["detail"]


def test_admin_cascade_delete_client_and_related_records(client, admin_headers, db_session):
    """Deleting a client purges their records, active tokens, and catalog offers."""
    # 1. Register client
    reg = client.post(
        "/admin/clients",
        json={"name": "Delete Target", "email": "purge@target.com"},
        headers=admin_headers,
    ).json()
    cid = reg["client_id"]
    secret = reg["client_secret"]

    # 2. Issue a token and add an offer
    token_res = client.post("/auth/token", json={"client_id": cid, "client_secret": secret}).json()
    token_str = token_res["access_token"]

    client.post(
        f"/offers/{cid}/PURGE_SKU_1",
        json={"name": "Item to be purged", "availability": "in stock", "url": "https://purge.com"},
        headers={"X-Token": token_str},
    )

    # 3. Cascade delete via admin
    del_res = client.delete(f"/admin/clients/{cid}", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["deleted_offers"] == 1

    # 4. Verify database state
    assert db_session.query(ClientModel).filter(ClientModel.client_id == cid).first() is None
    assert db_session.query(AccessTokenModel).filter(AccessTokenModel.client_id == cid).count() == 0
    assert db_session.query(OfferModel).filter(OfferModel.client_id == cid).count() == 0