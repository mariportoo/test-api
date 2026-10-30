from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from database import Base


class ClientModel(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, unique=True, index=True, nullable=False)
    client_secret = Column(String, nullable=False)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    password_salt = Column(String, nullable=True)
    must_change_password = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime, nullable=True)


class AccessTokenModel(Base):
    __tablename__ = "access_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    client_id = Column(String, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OfferModel(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, index=True, nullable=False)
    identifier = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    previous_price = Column(Float, nullable=True)
    category_identifier = Column(String, nullable=True)
    category_name = Column(String, nullable=True)
    custom_properties = Column(JSON, nullable=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("client_id", "identifier", name="uix_client_identifier"),
    )