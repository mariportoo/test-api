from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from database import get_db
from models import OfferModel
from security import authenticate_client

router = APIRouter(tags=["Offers"])


# ------------------------------------------------------------------------------
# Pydantic Schemas for Strict Field Validation
# ------------------------------------------------------------------------------
class OfferUpsertSchema(BaseModel):
    availability: str
    status: Optional[str] = None
    name: Optional[str] = None
    url: Optional[str] = None
    price: Optional[float] = None
    previous_price: Optional[float] = None
    image_url: Optional[str] = None
    category_identifier: Optional[str] = None
    category_name: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="allow")


def serialize_offer(offer: OfferModel) -> Dict[str, Any]:
    """Helper to ensure consistent dictionary representation of an offer."""
    availability_val = (
        getattr(offer, "availability", None)
        or getattr(offer, "status", None)
        or "in stock"
    )
    return {
        "id": offer.identifier,
        "identifier": offer.identifier,
        "client_id": offer.client_id,
        "availability": availability_val,
        "status": getattr(offer, "status", availability_val),
        "name": getattr(offer, "name", None),
        "url": getattr(offer, "url", None),
        "image_url": getattr(offer, "image_url", None),
        "price": getattr(offer, "price", None),
        "previous_price": getattr(offer, "previous_price", None),
        "category_identifier": getattr(offer, "category_identifier", None),
        "category_name": getattr(offer, "category_name", None),
        "description": getattr(offer, "description", None),
    }


def _extract_model_attributes(data_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Map validated payload keys to attributes that exist on OfferModel."""
    avail_val = data_dict.get("availability")
    status_val = data_dict.get("status") or avail_val or "active"

    valid_attrs: Dict[str, Any] = {}
    for k, v in data_dict.items():
        if hasattr(OfferModel, k):
            valid_attrs[k] = v

    if hasattr(OfferModel, "status") and "status" not in valid_attrs:
        valid_attrs["status"] = status_val
    if hasattr(OfferModel, "availability") and "availability" not in valid_attrs:
        valid_attrs["availability"] = avail_val

    return valid_attrs


# ==============================================================================
# BATCH ENDPOINTS
# ==============================================================================
@router.post("/offers-batch/{client_id}")
def batch_upsert_offers(
    client_id: str,
    payload: Any = Body(...),
    db: Session = Depends(get_db),
    _: Any = Depends(authenticate_client),
):
    """
    Bulk upsert up to 3,000 offers.
    Isolates invalid offers with their identifier and failure reason while saving valid items.
    """
    if not isinstance(payload, list) or len(payload) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload cannot be empty. Expecting a JSON array of offer objects.",
        )

    if len(payload) > 3000:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Payload exceeds 3000 offers limit.",
        )

    failed_offers: List[Dict[str, str]] = []
    updated_count = 0

    for item in payload:
        if not isinstance(item, dict):
            failed_offers.append({
                "identifier": "UNKNOWN_ID",
                "reason": "Offer item must be a JSON object.",
            })
            continue

        raw_id = item.get("id") or item.get("identifier")
        if not raw_id:
            failed_offers.append({
                "identifier": "UNKNOWN_ID",
                "reason": "Missing required 'id' attribute.",
            })
            continue

        identifier = str(raw_id).strip()

        try:
            validated_data = OfferUpsertSchema(**item)
        except ValidationError as val_err:
            error_msgs = [f"{err['loc'][-1]}: {err['msg']}" for err in val_err.errors()]
            failed_offers.append({
                "identifier": identifier,
                "reason": "; ".join(error_msgs),
            })
            continue

        try:
            existing = db.query(OfferModel).filter(
                OfferModel.client_id == client_id,
                OfferModel.identifier == identifier,
            ).first()

            data_dict = validated_data.model_dump(exclude_unset=True)
            data_dict.pop("id", None)
            data_dict.pop("identifier", None)
            valid_attrs = _extract_model_attributes(data_dict)

            if existing:
                for k, v in valid_attrs.items():
                    setattr(existing, k, v)
            else:
                new_offer = OfferModel(
                    client_id=client_id,
                    identifier=identifier,
                    **valid_attrs,
                )
                db.add(new_offer)

            updated_count += 1
        except Exception as db_err:
            failed_offers.append({
                "identifier": identifier,
                "reason": f"Database error: {str(db_err)}",
            })

    db.commit()

    return {
        "message": f"Updated offers: {updated_count}. Failed offers: {len(failed_offers)}",
        "data": {
            "updatedOffers": updated_count,
            "failedOffers": failed_offers,
        },
    }


@router.get("/offers-batch/{client_id}")
def batch_get_offers(
    client_id: str,
    identifiers: Optional[str] = Query(None, description="Comma-separated identifiers"),
    db: Session = Depends(get_db),
    _: Any = Depends(authenticate_client),
):
    """Retrieve multiple offers in a single batch request."""
    if not identifiers:
        return {"found_count": 0, "missing_identifiers": [], "data": []}

    id_list = [i.strip() for i in identifiers.split(",") if i.strip()]
    found = db.query(OfferModel).filter(
        OfferModel.client_id == client_id,
        OfferModel.identifier.in_(id_list),
    ).all()

    found_ids = {o.identifier for o in found}
    missing = [i for i in id_list if i not in found_ids]

    return {
        "found_count": len(found),
        "missing_identifiers": missing,
        "data": [serialize_offer(o) for o in found],
    }


@router.delete("/offers-batch/{client_id}")
def batch_delete_offers(
    client_id: str,
    payload: Dict[str, List[str]] = Body(...),
    db: Session = Depends(get_db),
    _: Any = Depends(authenticate_client),
):
    """Delete multiple offers matching the specified identifiers."""
    id_list = payload.get("identifiers", [])
    if not id_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must include a non-empty 'identifiers' list.",
        )

    deleted_count = db.query(OfferModel).filter(
        OfferModel.client_id == client_id,
        OfferModel.identifier.in_(id_list),
    ).delete(synchronize_session=False)
    db.commit()

    return {
        "message": f"Successfully deleted {deleted_count} offers.",
        "deleted_count": deleted_count,
    }


# ==============================================================================
# CATALOG & INDIVIDUAL OFFER ENDPOINTS
# ==============================================================================
@router.get("/offers/{client_id}")
def list_offers(
    client_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Any = Depends(authenticate_client),
):
    """Paginated catalog retrieval for a specific client."""
    total = db.query(OfferModel).filter(OfferModel.client_id == client_id).count()
    offers = db.query(OfferModel).filter(
        OfferModel.client_id == client_id,
    ).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": (offset + limit) < total,
        "data": [serialize_offer(o) for o in offers],
    }


@router.get("/offers/{client_id}/{identifier}")
def get_single_offer(
    client_id: str,
    identifier: str,
    db: Session = Depends(get_db),
    _: Any = Depends(authenticate_client),
):
    """Retrieve an individual offer by its identifier."""
    offer = db.query(OfferModel).filter(
        OfferModel.client_id == client_id,
        OfferModel.identifier == identifier,
    ).first()

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Offer '{identifier}' not found.",
        )

    return serialize_offer(offer)


@router.post("/offers/{client_id}/{identifier}")
def upsert_single_offer(
    client_id: str,
    identifier: str,
    payload: Any = Body(...),
    db: Session = Depends(get_db),
    _: Any = Depends(authenticate_client),
):
    """
    Create or update a single offer.
    Returns HTTP 400 with the exact identifier and cause if validation fails.
    """
    if not isinstance(payload, dict) or not payload:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "identifier": identifier,
                "reason": "Payload must be a non-empty JSON object.",
                "detail": f"Offer '{identifier}' validation failed: Payload cannot be empty.",
            },
        )

    try:
        validated_data = OfferUpsertSchema(**payload)
    except ValidationError as val_err:
        error_msgs = [f"{err['loc'][-1]}: {err['msg']}" for err in val_err.errors()]
        reason = "; ".join(error_msgs)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "identifier": identifier,
                "reason": reason,
                "detail": f"Offer '{identifier}' validation failed: {reason}",
            },
        )

    existing = db.query(OfferModel).filter(
        OfferModel.client_id == client_id,
        OfferModel.identifier == identifier,
    ).first()

    data_dict = validated_data.model_dump(exclude_unset=True)
    data_dict.pop("id", None)
    data_dict.pop("identifier", None)
    valid_attrs = _extract_model_attributes(data_dict)

    if existing:
        for k, v in valid_attrs.items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return {
            "message": f"Offer '{identifier}' updated successfully.",
            "data": serialize_offer(existing),
        }

    new_offer = OfferModel(
        client_id=client_id,
        identifier=identifier,
        **valid_attrs,
    )
    db.add(new_offer)
    db.commit()
    db.refresh(new_offer)

    return {
        "message": f"Offer '{identifier}' created successfully.",
        "data": serialize_offer(new_offer),
    }


@router.delete("/offers/{client_id}/{identifier}")
def delete_single_offer(
    client_id: str,
    identifier: str,
    db: Session = Depends(get_db),
    _: Any = Depends(authenticate_client),
):
    """Delete an individual offer."""
    offer = db.query(OfferModel).filter(
        OfferModel.client_id == client_id,
        OfferModel.identifier == identifier,
    ).first()

    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Offer '{identifier}' not found.",
        )

    db.delete(offer)
    db.commit()

    return {"message": f"Offer '{identifier}' deleted successfully."}