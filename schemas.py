from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PortalLoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    email: str
    current_password: str
    new_password: str


class ClientCreateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


class SetClientCredentialsRequest(BaseModel):
    email: str
    password: Optional[str] = None


class ClientStatusUpdate(BaseModel):
    is_active: bool


class AuthTokenRequest(BaseModel):
    client_id: str
    client_secret: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class OfferPayload(BaseModel):
    """Schema for batch ingestion via /offers-batch/{client_id}"""
    model_config = ConfigDict(populate_by_name=True)

    identifier: str = Field(..., validation_alias="id")
    status: str = Field(..., validation_alias="availability")
    name: str
    url: str
    image_url: Optional[str] = None
    price: Optional[float] = None
    previous_price: Optional[float] = None
    category_identifier: Optional[str] = None
    category_name: Optional[str] = None
    custom_properties: Optional[Dict[str, Any]] = None


class SingleOfferPayload(BaseModel):
    """Schema for single offer upsert via /offers/{client_id}/{identifier}"""
    model_config = ConfigDict(populate_by_name=True)

    identifier: Optional[str] = Field(None, validation_alias="id")
    status: str = Field(..., validation_alias="availability")
    name: str
    url: str
    image_url: Optional[str] = None
    price: Optional[float] = None
    previous_price: Optional[float] = None
    category_identifier: Optional[str] = None
    category_name: Optional[str] = None
    custom_properties: Optional[Dict[str, Any]] = None


class BatchIdentifiersPayload(BaseModel):
    """Schema for batch operations requiring an identifier list"""
    identifiers: List[str]