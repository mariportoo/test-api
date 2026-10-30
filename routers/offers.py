from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models import ClientModel, OfferModel
from schemas import BatchIdentifiersPayload, OfferPayload, SingleOfferPayload
from security import authenticate_client

router = APIRouter(tags=["Offer Feed"])


# --- Batch Operations ---

@router.post(
    "/offers-batch/{client_id}",
    summary="Create or update offers in batch",
    status_code=status.HTTP_200_OK,
)
async def update_offers_post(
    client_id: str,
    request: Request,
    auth_client: ClientModel = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """Ingest or update multiple offers (up to 3000 items) using a JSON payload."""
    try:
        raw_body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body cannot be empty.")

    if not raw_body:
        raise HTTPException(status_code=400, detail="Request body cannot be empty.")

    items = raw_body if isinstance(raw_body, list) else [raw_body]
    if len(items) > 3000:
        raise HTTPException(status_code=413, detail="Request body exceeds 3000 offers limit.")

    updated_count = 0
    failed_offers = []

    for item in items:
        try:
            offer_data = OfferPayload.model_validate(item)
            existing = (
                db.query(OfferModel)
                .filter(OfferModel.client_id == client_id, OfferModel.identifier == offer_data.identifier)
                .first()
            )
            if existing:
                for key, val in offer_data.model_dump().items():
                    setattr(existing, key, val)
            else:
                db.add(OfferModel(client_id=client_id, **offer_data.model_dump()))
            db.commit()
            updated_count += 1
        except Exception as e:
            db.rollback()
            failed_offers.append({
                "identifier": item.get("id") or item.get("identifier"),
                "name": item.get("name"),
                "url": item.get("url"),
                "status": item.get("availability") or item.get("status"),
                "error": str(e),
            })

    return {
        "status": 200,
        "message": f"Updated offers: {updated_count}. Failed offers: {len(failed_offers)}",
        "data": {"updatedOffers": updated_count, "failedOffers": failed_offers},
    }


@router.get(
    "/offers-batch/{client_id}",
    summary="Get multiple offers by IDs",
    status_code=status.HTTP_200_OK,
)
def get_offers_batch(
    client_id: str,
    identifiers: List[str] = Query(
        ...,
        description="List of product identifiers (e.g. ?identifiers=SKU1&identifiers=SKU2 or comma-separated ?identifiers=SKU1,SKU2)",
    ),
    auth_client: ClientModel = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """Retrieve multiple offers at once matching the provided list of identifiers."""
    cleaned_ids = []
    for raw_id in identifiers:
        for split_id in raw_id.split(","):
            val = split_id.strip()
            if val and val not in cleaned_ids:
                cleaned_ids.append(val)

    if not cleaned_ids:
        raise HTTPException(status_code=400, detail="At least one valid identifier must be provided.")

    offers = (
        db.query(OfferModel)
        .filter(
            OfferModel.client_id == client_id,
            OfferModel.identifier.in_(cleaned_ids),
        )
        .all()
    )

    found_ids = {offer.identifier for offer in offers}
    missing_ids = [ident for ident in cleaned_ids if ident not in found_ids]

    return {
        "client_id": client_id,
        "requested_count": len(cleaned_ids),
        "found_count": len(offers),
        "missing_identifiers": missing_ids,
        "data": offers,
    }


@router.delete(
    "/offers-batch/{client_id}",
    summary="Delete multiple offers by IDs",
    status_code=status.HTTP_200_OK,
)
def delete_offers_batch(
    client_id: str,
    payload: BatchIdentifiersPayload,
    auth_client: ClientModel = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """Delete multiple offers in a single operation by providing a list of identifiers."""
    if not payload.identifiers:
        raise HTTPException(status_code=400, detail="Identifier list cannot be empty.")

    deleted_count = (
        db.query(OfferModel)
        .filter(
            OfferModel.client_id == client_id,
            OfferModel.identifier.in_(payload.identifiers),
        )
        .delete(synchronize_session=False)
    )
    db.commit()

    return {
        "status": 200,
        "message": f"Successfully deleted {deleted_count} offers.",
        "deleted_count": deleted_count,
    }


# --- Individual & Paginated Operations ---

@router.get(
    "/offers/{client_id}",
    summary="List all offers",
    status_code=status.HTTP_200_OK,
)
def list_offers_paginated(
    client_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    auth_client: ClientModel = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """Retrieve catalog offers with offset-based pagination."""
    query = db.query(OfferModel).filter(OfferModel.client_id == client_id)
    total_count = query.count()
    offers = query.order_by(OfferModel.id.desc()).offset(offset).limit(limit).all()

    return {
        "client_id": client_id,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total_count,
        "data": offers,
    }


@router.get(
    "/offers/{client_id}/{identifier}",
    summary="Get offer by ID",
    status_code=status.HTTP_200_OK,
)
def get_single_offer(
    client_id: str,
    identifier: str,
    auth_client: ClientModel = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """Retrieve details for a specific single offer by its product identifier."""
    offer = (
        db.query(OfferModel)
        .filter(OfferModel.client_id == client_id, OfferModel.identifier == identifier)
        .first()
    )
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@router.post(
    "/offers/{client_id}/{identifier}",
    summary="Create or update an offer by ID",
    status_code=status.HTTP_200_OK,
)
def upsert_single_offer(
    client_id: str,
    identifier: str,
    payload: SingleOfferPayload,
    auth_client: ClientModel = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """
    Upsert an individual offer:
    - Checks if the identifier exists in the database for this client.
    - If it exists, updates the offer attributes.
    - If it does not exist, creates the new offer.
    """
    existing = (
        db.query(OfferModel)
        .filter(OfferModel.client_id == client_id, OfferModel.identifier == identifier)
        .first()
    )

    data = payload.model_dump(exclude_unset=True)
    data["identifier"] = identifier
    data["client_id"] = client_id

    if existing:
        for key, val in data.items():
            setattr(existing, key, val)
        db.commit()
        db.refresh(existing)
        return {
            "status": 200,
            "message": f"Offer '{identifier}' updated successfully.",
            "data": existing,
        }
    else:
        new_offer = OfferModel(**data)
        db.add(new_offer)
        db.commit()
        db.refresh(new_offer)
        return {
            "status": 200,
            "message": f"Offer '{identifier}' created successfully.",
            "data": new_offer,
        }


@router.delete(
    "/offers/{client_id}/{identifier}",
    summary="Delete offer by ID",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_offer(
    client_id: str,
    identifier: str,
    auth_client: ClientModel = Depends(authenticate_client),
    db: Session = Depends(get_db),
):
    """Delete a specific offer by its product identifier."""
    offer = db.query(OfferModel).filter(OfferModel.client_id == client_id, OfferModel.identifier == identifier).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    db.delete(offer)
    db.commit()
    return None