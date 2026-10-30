import copy
from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy import text

from database import Base, SessionLocal, engine
from models import ClientModel
from security import authenticate_admin_docs, hash_password
from routers import admin, auth, offers, portal

# 1. Database Initialization & Migrations
Base.metadata.create_all(bind=engine)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE clients ALTER COLUMN token DROP NOT NULL;"))
        conn.commit()
    except Exception:
        conn.rollback()

    for col in [
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS email VARCHAR;",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS password_hash VARCHAR;",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS password_salt VARCHAR;",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS client_secret VARCHAR;",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP;",
    ]:
        try:
            conn.execute(text(col))
            conn.commit()
        except Exception:
            conn.rollback()


def seed_default_client():
    db = SessionLocal()
    try:
        cid = "GAXLneNkZ8tVqrQvgka5"
        client = db.query(ClientModel).filter(ClientModel.client_id == cid).first()
        p_hash, p_salt = hash_password("ClientPassword123!")
        if not client:
            db.add(
                ClientModel(
                    client_id=cid,
                    client_secret="RmJZBsXfIldbcyFIBhmAM9lEqcEpNJjK",
                    name="Default Test Client",
                    email="client@example.com",
                    password_hash=p_hash,
                    password_salt=p_salt,
                    must_change_password=False,
                )
            )
            db.commit()
        elif not client.email:
            client.email = "client@example.com"
            client.password_hash = p_hash
            client.password_salt = p_salt
            db.commit()
    finally:
        db.close()

seed_default_client()


# 2. Application Setup
app = FastAPI(
    title="Offer Feed API",
    version="6.3.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# 3. Mount Routers
app.include_router(portal.router)
app.include_router(auth.router)
app.include_router(offers.router)
app.include_router(admin.router)


# 4. Helper: Recursively Extract Schema $refs
def extract_schema_refs(item, collected: set):
    if isinstance(item, dict):
        for k, v in item.items():
            if k == "$ref" and isinstance(v, str):
                if v.startswith("#/components/schemas/"):
                    collected.add(v.rsplit("/", 1)[-1])
            else:
                extract_schema_refs(v, collected)
    elif isinstance(item, list):
        for elem in item:
            extract_schema_refs(elem, collected)


def generate_base_openapi():
    return get_openapi(
        title="Offer Feed API",
        version="1.0.0",
        routes=app.routes,
    )


# 5. Documentation Endpoints

@app.get("/client-openapi.json", include_in_schema=False)
def client_openapi():
    """Public client OpenAPI specification."""
    schema = copy.deepcopy(generate_base_openapi())
    schema["info"]["title"] = "Client Offer Feed API"
    schema["info"]["description"] = "Official documentation for Client Feed Updates and Token Authentication."

    client_paths = {
        path: methods
        for path, methods in schema.get("paths", {}).items()
        if not path.startswith("/admin") and not path.startswith("/portal")
    }
    schema["paths"] = client_paths

    all_schemas = schema.get("components", {}).get("schemas", {})
    referenced_schemas = set()
    extract_schema_refs(client_paths, referenced_schemas)

    resolved_schemas = set()
    queue = list(referenced_schemas)
    while queue:
        current = queue.pop()
        if current in resolved_schemas:
            continue
        resolved_schemas.add(current)
        if current in all_schemas:
            nested_refs = set()
            extract_schema_refs(all_schemas[current], nested_refs)
            for ref in nested_refs:
                if ref not in resolved_schemas:
                    queue.append(ref)

    if "components" in schema and "schemas" in schema["components"]:
        schema["components"]["schemas"] = {
            name: definition
            for name, definition in all_schemas.items()
            if name in resolved_schemas
        }

    return JSONResponse(
        content=schema,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get(
    "/admin-openapi.json",
    include_in_schema=False,
    dependencies=[Depends(authenticate_admin_docs)],
)
def admin_openapi():
    """Protected master OpenAPI specification."""
    schema = copy.deepcopy(generate_base_openapi())
    schema["info"]["title"] = "Admin Management & Master API"
    schema["info"]["description"] = "Master administrative console for managing clients, portal, and feed operations."

    return JSONResponse(
        content=schema,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/docs", include_in_schema=False)
def client_swagger_ui():
    """Public client documentation."""
    return get_swagger_ui_html(
        openapi_url="/client-openapi.json",
        title="Client Offer Feed API - Docs",
    )


@app.get(
    "/admindocs",
    include_in_schema=False,
    dependencies=[Depends(authenticate_admin_docs)],
)
def admin_swagger_ui():
    """Protected admin documentation."""
    return get_swagger_ui_html(
        openapi_url="/admin-openapi.json",
        title="Admin Management API - Docs",
    )