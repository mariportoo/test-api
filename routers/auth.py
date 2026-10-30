from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import AccessTokenModel, ClientModel
from schemas import AuthTokenRequest, AuthTokenResponse
from security import ACCESS_TOKEN_EXPIRE_HOURS, generate_alphanumeric_str

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/token", 
    summary="Get or refresh access token",
    response_model=AuthTokenResponse, 
    status_code=status.HTTP_200_OK
)
def issue_access_token(payload: AuthTokenRequest, db: Session = Depends(get_db)):
    """Exchange a valid client_id and client_secret for an alphanumeric access token."""
    client = (
        db.query(ClientModel)
        .filter(
            ClientModel.client_id == payload.client_id,
            ClientModel.client_secret == payload.client_secret,
            ClientModel.is_active == True,
        )
        .first()
    )

    if not client:
        raise HTTPException(status_code=401, detail="Invalid client ID or client secret.")

    new_token = generate_alphanumeric_str(40)
    expires_in_seconds = ACCESS_TOKEN_EXPIRE_HOURS * 3600
    expiration_time = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

    token_entry = AccessTokenModel(
        token=new_token,
        client_id=client.client_id,
        expires_at=expiration_time,
    )
    db.add(token_entry)
    db.commit()

    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in": expires_in_seconds,
    }