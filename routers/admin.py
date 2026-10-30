from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import AccessTokenModel, ClientModel, OfferModel
from schemas import ClientCreateRequest, ClientStatusUpdate, SetClientCredentialsRequest
from security import authenticate_admin, generate_alphanumeric_str, hash_password

router = APIRouter(
    prefix="/admin",
    tags=["Admin Management"],
    dependencies=[Depends(authenticate_admin)],
)


@router.post(
    "/clients", 
    summary="Create client",
    status_code=status.HTTP_201_CREATED
)
def register_client(
    payload: ClientCreateRequest,
    db: Session = Depends(get_db),
):
    """Register a new client. Auto-generates alphanumeric credentials if omitted."""
    cid = payload.client_id or generate_alphanumeric_str(20)
    secret = payload.client_secret or generate_alphanumeric_str(36)

    if db.query(ClientModel).filter(ClientModel.client_id == cid).first():
        raise HTTPException(status_code=400, detail="Client ID already registered.")

    temp_password = payload.password or generate_alphanumeric_str(16)
    p_hash, p_salt = hash_password(temp_password)
    must_change = True if payload.password is None else False

    new_client = ClientModel(
        client_id=cid,
        client_secret=secret,
        name=payload.name,
        email=payload.email,
        password_hash=p_hash,
        password_salt=p_salt,
        must_change_password=must_change,
    )
    db.add(new_client)
    db.commit()
    db.refresh(new_client)

    return {
        "message": "Client registered successfully",
        "client_id": new_client.client_id,
        "client_secret": new_client.client_secret,
        "email": new_client.email,
        "name": new_client.name,
        "temporary_password": temp_password if payload.password is None else None,
        "must_change_password": new_client.must_change_password,
    }


@router.post(
    "/clients/{client_id}/credentials", 
    summary="Create client credentials",
    status_code=status.HTTP_200_OK
)
def set_client_credentials(
    client_id: str,
    payload: SetClientCredentialsRequest,
    db: Session = Depends(get_db),
):
    """Update or reset a client's email and portal login password."""
    client = db.query(ClientModel).filter(ClientModel.client_id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    temp_password = payload.password or generate_alphanumeric_str(16)
    p_hash, p_salt = hash_password(temp_password)

    client.email = payload.email
    client.password_hash = p_hash
    client.password_salt = p_salt
    client.must_change_password = True if payload.password is None else False
    db.commit()

    return {
        "message": f"Login credentials updated for client '{client_id}'.",
        "email": client.email,
        "temporary_password": temp_password if payload.password is None else None,
        "must_change_password": client.must_change_password,
    }


@router.get(
    "/clients", 
    summary="Get full client list",
    status_code=status.HTTP_200_OK
)
def list_clients(db: Session = Depends(get_db)):
    """List all registered clients and status details."""
    return db.query(ClientModel).order_by(ClientModel.id.asc()).all()


@router.patch(
    "/clients/{client_id}/status",
    summary="Update client status", 
    status_code=status.HTTP_200_OK
)
def update_client_status(
    client_id: str,
    payload: ClientStatusUpdate,
    db: Session = Depends(get_db),
):
    """Activate or deactivate a client."""
    client = db.query(ClientModel).filter(ClientModel.client_id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.is_active = payload.is_active
    db.commit()
    status_str = "activated" if client.is_active else "deactivated"
    return {"message": f"Client '{client_id}' {status_str}."}


@router.delete(
    "/clients/{client_id}", 
    summary="Delete client", 
    status_code=status.HTTP_200_OK
)
def delete_client(
    client_id: str,
    db: Session = Depends(get_db),
):
    """Permanently delete a client and purge their tokens and offers."""
    client = db.query(ClientModel).filter(ClientModel.client_id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    db.query(AccessTokenModel).filter(AccessTokenModel.client_id == client_id).delete(synchronize_session=False)
    deleted_offers = db.query(OfferModel).filter(OfferModel.client_id == client_id).delete(synchronize_session=False)
    db.delete(client)
    db.commit()
    return {"message": f"Client '{client_id}' deleted.", "deleted_offers": deleted_offers}