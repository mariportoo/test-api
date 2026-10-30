def test_auth_missing_token(client, active_client_fixture):
    """Requests without auth tokens must be rejected with 403."""
    cid = active_client_fixture["client_id"]
    res = client.get(f"/offers/{cid}")
    assert res.status_code == 403
    assert res.json()["detail"] == "Authentication token missing."


def test_auth_cross_tenant_forbidden(client, active_client_fixture):
    """Client A's token cannot be used to read or modify Client B's offers."""
    res = client.get("/offers/another_unauthorized_client", headers=active_client_fixture["headers"])
    assert res.status_code == 403
    assert res.json()["detail"] == "Invalid token or client ID."


def test_batch_upsert_boundary_exceeded(client, active_client_fixture):
    """Batch payload containing over 3,000 items must trigger 413."""
    cid = active_client_fixture["client_id"]
    headers = active_client_fixture["headers"]

    oversized_payload = [
        {"id": f"item_{i}", "availability": "in stock", "name": f"P_{i}", "url": f"https://a.com/{i}"}
        for i in range(3001)
    ]

    res = client.post(f"/offers-batch/{cid}", json=oversized_payload, headers=headers)
    assert res.status_code == 413
    assert "exceeds 3000 offers limit" in res.json()["detail"]


def test_batch_upsert_empty_body(client, active_client_fixture):
    """Empty JSON array or body must return 400."""
    cid = active_client_fixture["client_id"]
    headers = active_client_fixture["headers"]

    res = client.post(f"/offers-batch/{cid}", json=[], headers=headers)
    assert res.status_code == 400
    assert "cannot be empty" in res.json()["detail"]


def test_batch_upsert_partial_failures(client, active_client_fixture):
    """Batch upsert succeeds on valid items and isolates malformed ones in failedOffers."""
    cid = active_client_fixture["client_id"]
    headers = active_client_fixture["headers"]

    payload = [
        {"id": "valid_sku_1", "availability": "in stock", "name": "Valid Item", "url": "https://a.com/1"},
        {"id": "broken_sku_2", "name": "Missing Required Availability", "url": "https://a.com/2"},
    ]

    res = client.post(f"/offers-batch/{cid}", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["updatedOffers"] == 1
    assert len(data["failedOffers"]) == 1
    assert data["failedOffers"][0]["identifier"] == "broken_sku_2"


def test_single_offer_upsert_create_then_update(client, active_client_fixture):
    """POST /offers/{client_id}/{identifier} inserts when missing, updates when existing."""
    cid = active_client_fixture["client_id"]
    headers = active_client_fixture["headers"]
    sku = "SKU_PHONE_001"

    # 1. Create offer
    create_payload = {
        "availability": "in stock",
        "name": "Smartphone",
        "url": "https://example.com/phone",
        "price": 799.99,
    }
    res_create = client.post(f"/offers/{cid}/{sku}", json=create_payload, headers=headers)
    assert res_create.status_code == 200
    assert "created successfully" in res_create.json()["message"]
    assert res_create.json()["data"]["price"] == 799.99

    # 2. Update offer
    update_payload = {
        "availability": "out of stock",
        "name": "Smartphone Pro",
        "url": "https://example.com/phone-pro",
        "price": 699.99,
    }
    res_update = client.post(f"/offers/{cid}/{sku}", json=update_payload, headers=headers)
    assert res_update.status_code == 200
    assert "updated successfully" in res_update.json()["message"]
    assert res_update.json()["data"]["price"] == 699.99

    # 3. Verify single item in catalog
    res_get = client.get(f"/offers/{cid}/{sku}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "Smartphone Pro"


def test_batch_get_with_missing_identifiers(client, active_client_fixture):
    """GET /offers-batch returns existing items and flags missing identifiers."""
    cid = active_client_fixture["client_id"]
    headers = active_client_fixture["headers"]

    # Ingest 2 items
    client.post(
        f"/offers-batch/{cid}",
        json=[
            {"id": "item_1", "availability": "in stock", "name": "Item 1", "url": "https://a.com/1"},
            {"id": "item_2", "availability": "in stock", "name": "Item 2", "url": "https://a.com/2"},
        ],
        headers=headers,
    )

    # Query with 2 existing items + 1 non-existent item
    res = client.get(
        f"/offers-batch/{cid}?identifiers=item_1,item_2,item_does_not_exist",
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["found_count"] == 2
    assert body["missing_identifiers"] == ["item_does_not_exist"]
    assert len(body["data"]) == 2


def test_batch_delete_offers(client, active_client_fixture):
    """DELETE /offers-batch removes all specified identifiers."""
    cid = active_client_fixture["client_id"]
    headers = active_client_fixture["headers"]

    # Ingest 3 items
    client.post(
        f"/offers-batch/{cid}",
        json=[
            {"id": "del_1", "availability": "in stock", "name": "Item 1", "url": "https://a.com/1"},
            {"id": "del_2", "availability": "in stock", "name": "Item 2", "url": "https://a.com/2"},
            {"id": "keep_3", "availability": "in stock", "name": "Item 3", "url": "https://a.com/3"},
        ],
        headers=headers,
    )

    # Delete first 2 items
    del_res = client.request(
        "DELETE",
        f"/offers-batch/{cid}",
        json={"identifiers": ["del_1", "del_2"]},
        headers=headers,
    )
    assert del_res.status_code == 200
    assert del_res.json()["deleted_count"] == 2

    # Check remaining count in catalog
    list_res = client.get(f"/offers/{cid}", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1
    assert list_res.json()["data"][0]["identifier"] == "keep_3"