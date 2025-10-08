from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from passlib.context import CryptContext
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Base(DeclarativeBase):
    pass


def uuid_pk() -> uuid.UUID:
    return uuid.uuid4()


class WebService(Base):
    __tablename__ = "webservice"

    service_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255))
    registration_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    api_keys: Mapped[List["APIKey"]] = relationship(
        "APIKey", back_populates="service", cascade="all, delete-orphan"
    )
    requests: Mapped[List["ModerationRequest"]] = relationship(
        "ModerationRequest", back_populates="service", cascade="all, delete-orphan"
    )


class APIKey(Base):
    __tablename__ = "apikey"

    key_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    service_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("webservice.service_id"), index=True)
    key_hash: Mapped[str] = mapped_column(String(255))
    key_prefix: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    service: Mapped[WebService] = relationship("WebService", back_populates="api_keys")

    @staticmethod
    def generate_plain_key() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_key(plain_key: str) -> tuple[str, str]:
        key_hash = pwd_context.hash(plain_key)
        return key_hash, plain_key[:8]

    def verify(self, plain_key: str) -> bool:
        return pwd_context.verify(plain_key, self.key_hash)


class AdminUser(Base):
    __tablename__ = "adminuser"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions: Mapped[List["AdminSession"]] = relationship(
        "AdminSession", back_populates="user", cascade="all, delete-orphan"
    )

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.password_hash)


class AdminSession(Base):
    __tablename__ = "adminsession"

    token: Mapped[str] = mapped_column(String(128), primary_key=True, default=lambda: secrets.token_urlsafe(32))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("adminuser.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow() + timedelta(days=7)
    )

    user: Mapped[AdminUser] = relationship("AdminUser", back_populates="sessions")

    def is_valid(self) -> bool:
        return datetime.utcnow() < self.expires_at


class ViolationCategory(Base):
    __tablename__ = "violationcategory"

    category_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    type: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_reject_threshold: Mapped[float] = mapped_column(Float, default=0.9)
    human_review_threshold: Mapped[float] = mapped_column(Float, default=0.6)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    rules: Mapped[List["ModerationRule"]] = relationship(
        "ModerationRule", back_populates="category", cascade="all, delete-orphan"
    )


class ModerationRule(Base):
    __tablename__ = "moderationrule"

    rule_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("violationcategory.category_id"))
    action: Mapped[str] = mapped_column(String(32))
    priority: Mapped[int] = mapped_column(default=100)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[ViolationCategory] = relationship("ViolationCategory", back_populates="rules")


class ModerationRequest(Base):
    __tablename__ = "moderationrequest"

    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    service_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("webservice.service_id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    content_type: Mapped[str] = mapped_column(String(16), default="TEXT")
    content_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))

    service: Mapped[WebService] = relationship("WebService", back_populates="requests")
    result: Mapped[Optional["ModerationResult"]] = relationship(
        "ModerationResult", back_populates="request", cascade="all, delete-orphan"
    )


class ModerationResult(Base):
    __tablename__ = "moderationresult"

    result_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("moderationrequest.request_id"), unique=True)
    decision: Mapped[str] = mapped_column(String(32))
    confidence_score: Mapped[float] = mapped_column(Float)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    model_version: Mapped[str] = mapped_column(String(64))
    label_scores: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    request: Mapped[ModerationRequest] = relationship("ModerationRequest", back_populates="result")
