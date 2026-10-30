import json
import sys
import httpx

# ==============================================================================
# CONFIGURATION
# ==============================================================================
BASE_URL = "https://test-offers-api.onrender.com"
ADMIN_KEY = "test"


def run_failure_tests():
    with httpx.Client(base_url=BASE_URL, timeout=45.0) as client:
        print(f"\n🚀 Connecting to: {BASE_URL}")

        # 1. Fetch Client Alpha credentials via Admin
        print("\n[1/3] Retrieving client credentials via Admin API...")
        admin_res = client.get("/admin/clients", headers={"X-Admin-Key": ADMIN_KEY})
        if admin_res.status_code != 200:
            sys.exit(f"❌ Failed to reach admin endpoint: {admin_res.status_code} - {admin_res.text}")

        clients = admin_res.json()
        if not clients:
            sys.exit("❌ No clients found in database. Run seed_live_test.py first.")

        target_client = clients[0]
        cid = target_client["client_id"]
        secret = target_client["client_secret"]
        print(f"  ✔ Targeting Client: {target_client['name']} ({cid})")

        # 2. Get Access Token
        token_res = client.post("/auth/token", json={"client_id": cid, "client_secret": secret})
        token = token_res.json()["access_token"]
        auth_headers = {"X-Token": token}
        print("  ✔ OAuth2 Token acquired successfully")

        # ----------------------------------------------------------------------
        # TEST 1: POST /offers-batch with 5 FAILED OFFERS + 1 VALID OFFER
        # ----------------------------------------------------------------------
        print("\n" + "=" * 70)
        print("[2/3] TEST 1: POST /offers-batch with 5 distinct failed offers")
        print("=" * 70)

        batch_payload = [
            # 1. Valid Offer (Must succeed)
            {
                "id": "LIVE_BATCH_VALID_001",
                "availability": "in stock",
                "name": "Legitimate Item",
                "price": 29.99,
                "url": "https://example.com/valid-1",
            },
            # Failure 1: Missing required 'availability'
            {
                "id": "FAIL_NO_AVAILABILITY",
                "name": "Broken Availability Item",
                "price": 49.99,
                "url": "https://example.com/fail-1",
            },
            # Failure 2: Price is a non-numeric string
            {
                "id": "FAIL_INVALID_PRICE",
                "availability": "in stock",
                "name": "Corrupted Price Item",
                "price": "not_a_valid_number",
                "url": "https://example.com/fail-2",
            },
            # Failure 3: Previous price is non-numeric
            {
                "id": "FAIL_INVALID_PREV_PRICE",
                "availability": "in stock",
                "name": "Bad Previous Price Item",
                "price": 19.99,
                "previous_price": "free_discount",
                "url": "https://example.com/fail-3",
            },
            # Failure 4: Completely missing 'id' key
            {
                "availability": "in stock",
                "name": "Item Without Identifier",
                "price": 9.99,
                "url": "https://example.com/fail-4",
            },
            # Failure 5: Empty dictionary payload (no id, no availability)
            {},
        ]

        batch_res = client.post(f"/offers-batch/{cid}", json=batch_payload, headers=auth_headers)
        print(f"HTTP Status: {batch_res.status_code}")
        print("Response Body:")
        print(json.dumps(batch_res.json(), indent=2))

        # ----------------------------------------------------------------------
        # TEST 2: POST /offers/{client_id}/{identifier} with 1 FAILED OFFER
        # ----------------------------------------------------------------------
        print("\n" + "=" * 70)
        print("[3/3] TEST 2: POST /offers/{cid}/{id} with 1 failed offer")
        print("=" * 70)

        single_sku = "FAIL_SINGLE_ITEM_001"
        single_payload = {
            "name": "Single Broken Offer",
            "price": "invalid_currency_text",
            "url": "https://example.com/single-broken",
            # 'availability' is omitted
        }

        single_res = client.post(f"/offers/{cid}/{single_sku}", json=single_payload, headers=auth_headers)
        print(f"HTTP Status: {single_res.status_code}")
        print("Response Body:")
        print(json.dumps(single_res.json(), indent=2))

        print("\n" + "=" * 70)
        print("🎉 Both error handling tests completed!")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    run_failure_tests()