import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from models import ClientModel
from schemas import ChangePasswordRequest, PortalLoginRequest
from security import hash_password, verify_password

router = APIRouter(prefix="/portal", tags=["Portal"])


@router.get(
    "", 
    summary="Client Portal access page",
    response_class=FileResponse
)
def serve_client_portal():
    """Serves the standalone client login and developer web portal."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, "portal.html")
    return FileResponse(html_path)


@router.post(
    "/login",     
    summary="Create login for the Client Portal",
    status_code=status.HTTP_200_OK
)
def portal_login(payload: PortalLoginRequest, db: Session = Depends(get_db)):
    """Authenticate with client email and password to retrieve API credentials."""
    client = db.query(ClientModel).filter(ClientModel.email == payload.email).first()

    if (
        not client
        or not client.password_hash
        or not client.password_salt
        or not verify_password(payload.password, client.password_salt, client.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support.",
        )

    return {
        "email": client.email,
        "name": client.name,
        "client_id": client.client_id,
        "client_secret": client.client_secret,
        "must_change_password": client.must_change_password,
    }


@router.post(
    "/change-password",     
    summary="Change password for the Client Portal",
    status_code=status.HTTP_200_OK
)
def portal_change_password(payload: ChangePasswordRequest, db: Session = Depends(get_db)):
    """Update password for client portal access."""
    client = db.query(ClientModel).filter(ClientModel.email == payload.email).first()

    if (
        not client
        or not client.password_hash
        or not client.password_salt
        or not verify_password(payload.current_password, client.password_salt, client.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password verification failed.",
        )

    p_hash, p_salt = hash_password(payload.new_password)
    client.password_hash = p_hash
    client.password_salt = p_salt
    client.must_change_password = False
    db.commit()

    return {"message": "Password updated successfully."}