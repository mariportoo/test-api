import sys
import time
import httpx

# ==============================================================================
# CONFIGURATION
# ==============================================================================
BASE_URL = "https://test-offers-api.onrender.com"
ADMIN_KEY = "Kam9_Gem8=Zuk8"


def run_seeder():
    admin_headers = {"X-Admin-Key": ADMIN_KEY}

    # 60.0s timeout ensures Render and Neon have time to complete cold-start wakeups
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        print(f"\n🚀 Target Deployment: {BASE_URL}")

        # ----------------------------------------------------------------------
        # 0. WAKE UP SERVICE (Warm up Render & Neon)
        # ----------------------------------------------------------------------
        print("\n[0/4] Checking service availability (waking up if sleeping)...")
        start_time = time.time()
        try:
            ping = client.get("/docs")
            elapsed = round(time.time() - start_time, 2)
            if ping.status_code == 200:
                print(f"  ✔ Service is online and responsive ({elapsed}s)")
            else:
                print(f"  ⚠️ Service responded with status {ping.status_code} ({elapsed}s)")
        except httpx.RequestError as e:
            sys.exit(f"❌ Could not reach {BASE_URL}. Error: {e}")

        # ----------------------------------------------------------------------
        # 1. REGISTER CLIENTS
        # ----------------------------------------------------------------------
        print("\n[1/4] Registering test clients...")
        res_c1 = client.post(
            "/admin/clients",
            json={"name": "Alpha Electronics Live", "email": "alpha_live@example.com"},
            headers=admin_headers,
        )
        if res_c1.status_code != 201:
            sys.exit(f"❌ Failed to create Client Alpha: {res_c1.status_code} - {res_c1.text}")
        c1 = res_c1.json()
        print(f"  ✔ Created: {c1['name']} (ID: {c1['client_id']})")

        res_c2 = client.post(
            "/admin/clients",
            json={"name": "Beta Apparel Live", "email": "beta_live@example.com"},
            headers=admin_headers,
        )
        if res_c2.status_code != 201:
            sys.exit(f"❌ Failed to create Client Beta: {res_c2.status_code} - {res_c2.text}")
        c2 = res_c2.json()
        print(f"  ✔ Created: {c2['name']} (ID: {c2['client_id']})")

        # ----------------------------------------------------------------------
        # 2. ISSUE OAUTH2 ACCESS TOKENS
        # ----------------------------------------------------------------------
        print("\n[2/4] Requesting OAuth2 access tokens via /auth/token...")
        token_c1 = client.post(
            "/auth/token",
            json={"client_id": c1["client_id"], "client_secret": c1["client_secret"]},
        ).json()["access_token"]
        print(f"  ✔ Token Alpha: {token_c1[:12]}...")

        token_c2 = client.post(
            "/auth/token",
            json={"client_id": c2["client_id"], "client_secret": c2["client_secret"]},
        ).json()["access_token"]
        print(f"  ✔ Token Beta:  {token_c2[:12]}...")

        # ----------------------------------------------------------------------
        # 3. GENERATE 50 OFFERS PER CLIENT
        # ----------------------------------------------------------------------
        print("\n[3/4] Generating 50 distinct offers per catalog...")
        alpha_offers = [
            {
                "id": f"ALPHA_PROD_{i:03d}",
                "name": f"Smart Device Model {i}",
                "availability": "in stock" if i % 4 != 0 else "out of stock",
                "price": round(49.99 + (i * 2.5), 2),
                "url": f"https://alpha-store.example.com/products/{i}",
                "image_url": f"https://images.example.com/alpha/{i}.jpg",
                "category_identifier": "CAT_TECH",
                "category_name": "Consumer Electronics",
            }
            for i in range(1, 51)
        ]

        beta_offers = [
            {
                "id": f"BETA_PROD_{i:03d}",
                "name": f"Apparel Item {i}",
                "availability": "in stock",
                "price": round(19.99 + (i * 1.75), 2),
                "previous_price": round(29.99 + (i * 1.75), 2),
                "url": f"https://beta-apparel.example.com/items/{i}",
                "image_url": f"https://images.example.com/beta/{i}.jpg",
                "category_identifier": "CAT_FASHION",
                "category_name": "Clothing & Accessories",
            }
            for i in range(1, 51)
        ]

        # ----------------------------------------------------------------------
        # 4. INGEST BATCHES VIA /offers-batch
        # ----------------------------------------------------------------------
        print("\n[4/4] Ingesting batches into Neon PostgreSQL...")
        push_c1 = client.post(
            f"/offers-batch/{c1['client_id']}",
            json=alpha_offers,
            headers={"X-Token": token_c1},
        )
        if push_c1.status_code == 200:
            print(f"  ✔ Client Alpha: {push_c1.json()['message']}")
        else:
            print(f"  ❌ Client Alpha batch failed: {push_c1.status_code} - {push_c1.text}")

        push_c2 = client.post(
            f"/offers-batch/{c2['client_id']}",
            json=beta_offers,
            headers={"X-Token": token_c2},
        )
        if push_c2.status_code == 200:
            print(f"  ✔ Client Beta:  {push_c2.json()['message']}")
        else:
            print(f"  ❌ Client Beta batch failed: {push_c2.status_code} - {push_c2.text}")

        # ----------------------------------------------------------------------
        # 5. VERIFY PRODUCTION DATABASE
        # ----------------------------------------------------------------------
        print("\n🔎 Querying live catalogs via GET /offers/{client_id}...")
        v1 = client.get(f"/offers/{c1['client_id']}", headers={"X-Token": token_c1}).json()
        v2 = client.get(f"/offers/{c2['client_id']}", headers={"X-Token": token_c2}).json()

        print("-" * 60)
        print(f"Client Alpha ({c1['name']}) -> Total Live Offers: {v1.get('total')}")
        print(f"Client Beta  ({c2['name']})  -> Total Live Offers: {v2.get('total')}")
        print("-" * 60)
        print(f"Alpha Temporary Password: {c1['temporary_password']}")
        print(f"Beta Temporary Password:  {c2['temporary_password']}")
        print("-" * 60)
        print("🎉 Live seeding completed successfully!\n")


if __name__ == "__main__":
    run_seeder()