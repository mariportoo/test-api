# Client Offer Feed API

![Tests](https://github.com/mariportoo/test-api/actions/workflows/test.yml/badge.svg)

A modular, multi-tenant FastAPI backend designed to manage e-commerce product offer feeds. Inspired by RTB House specifications, this API supports single and bulk offer ingestion, offset-based pagination, and secure OAuth2 client credential authentication.

## Features

* **Offer Feed Management**: Robust endpoints for single upserts, batch ingestion (up to 3,000 items), paginated retrieval, and batch deletion.
* **OAuth2 Authentication**: Secure token issuance (`POST /auth/token`) enforcing 24-hour expiration lifecycles.
* **Self-Service Portal**: An isolated, web-based portal (`/portal`) for clients to log in and retrieve their credentials, enforcing mandatory first-login password updates.
* **Master Admin Console**: Protected administrative endpoints (`/admin`) for creating clients, toggling statuses, cascading deletions, and resetting passwords.
* **Automated CI/CD**: Fully tested using an isolated in-memory SQLite database via `pytest`, with GitHub Actions continuous integration and deployment to Render backed by Neon PostgreSQL.

## Project Structure

```text
.
├── .github/workflows/   # GitHub Actions CI pipelines
├── routers/             # Modular API routes (admin, auth, offers, portal)
├── tests/               # Automated test suite (conftest.py, test_*.py)
├── database.py          # SQLAlchemy engine & Neon PostgreSQL connection
├── main.py              # FastAPI app setup, schemas pruning & route inclusion
├── models.py            # SQLAlchemy database models
├── portal.html          # Web-based Client Portal UI
├── requirements.txt     # Python dependencies
├── schemas.py           # Pydantic data validation models
└── security.py          # Hashing, validation, & dependency guards
```

## Authentication

The application implements three distinct security layers:

1. **Offer Feed Routes (`X-Token` / Bearer)**: Clients request a 24-hour access token from `POST /auth/token` using their `client_id` and `client_secret`. 
2. **Client Portal (Email/Password)**: Clients log into the UI at `/portal` using their email and password.
3. **Admin Suite (`X-Admin-Key` / HTTP Basic)**: Administrative endpoints and `/admindocs` are strictly protected by the `ADMIN_SECRET_KEY` environment variable.

## Core Endpoints

### 1. Client Offer Feed (Public Docs: `/docs`)
* `POST /offers-batch/{client_id}` - Batch upsert up to 3,000 offers.
* `GET /offers-batch/{client_id}` - Fetch multiple specific offers by ID.
* `DELETE /offers-batch/{client_id}` - Batch delete offers by ID.
* `POST /offers/{client_id}/{identifier}` - Single offer upsert.
* `GET /offers/{client_id}` - List all offers with offset-based pagination.
* `GET /offers/{client_id}/{identifier}` - Fetch a single offer.
* `DELETE /offers/{client_id}/{identifier}` - Delete a single offer.

### 2. Client Portal & Auth
* `POST /auth/token` - Exchange credentials for an access token.
* `GET /portal` - Web interface for client self-service.
* `POST /portal/login` - Authenticate to the portal.
* `POST /portal/change-password` - Update portal password.

### 3. Admin Management (Protected Docs: `/admindocs`)
* `POST /admin/clients` - Register a new client and generate a temporary password.
* `GET /admin/clients` - List all registered clients.
* `PATCH /admin/clients/{client_id}/status` - Activate/Deactivate a client.
* `DELETE /admin/clients/{client_id}` - Cascade delete a client and all related records.

## Local Development & Testing

### 1. Setup Environment
Clone the repository and install the dependencies:
```bash
pip install -r requirements.txt
```

Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql://user:password@hostname/dbname
ADMIN_SECRET_KEY=your_super_secret_admin_key
```

### 2. Run the Server
Launch the application using Uvicorn:
```bash
uvicorn main:app --reload
```

### 3. Run the Test Suite
Execute the automated test suite locally. The tests automatically bypass your PostgreSQL database and run entirely in isolated memory using SQLite (`sqlite:///:memory:`):
```bash
pytest -v
```