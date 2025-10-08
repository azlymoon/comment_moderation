from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"


class RequestStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ModerationDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class CategoryType(str, Enum):
    TOXICITY = "TOXICITY"
    SPAM = "SPAM"
    HATE_SPEECH = "HATE_SPEECH"
    NSFW = "NSFW"
    ILLEGAL_CONTENT = "ILLEGAL_CONTENT"


class RuleAction(str, Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    AUTO_REJECT = "AUTO_REJECT"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    CONTENT_MODERATOR = "CONTENT_MODERATOR"
    ANALYST = "ANALYST"


class AdminUserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: UserRole = UserRole.CONTENT_MODERATOR


class AdminUser(BaseModel):
    user_id: str
    username: str
    email: str
    role: UserRole
    is_active: bool = True
    last_login: Optional[datetime] = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminToken(BaseModel):
    token: str
    expires_at: datetime


class ViolationCategory(BaseModel):
    category_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: CategoryType
    name: str
    description: Optional[str] = None
    auto_reject_threshold: float = 0.9
    human_review_threshold: float = 0.6
    is_enabled: bool = True


class ModerationRule(BaseModel):
    rule_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    category_id: str
    action: RuleAction
    priority: int = 100
    conditions: List[str] = Field(default_factory=list)


class ModerationRequestIn(BaseModel):
    service_id: str
    content_text: str = Field(..., min_length=1, max_length=10_000)


class ModerationRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    service_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    content_type: ContentType = ContentType.TEXT
    content_text: str
    status: RequestStatus = RequestStatus.PENDING


class ModerationResult(BaseModel):
    result_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    request_id: str
    decision: ModerationDecision
    confidence_score: float
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = "baseline-0"
    label_scores: Optional[Dict[str, float]] = None


class Statistics(BaseModel):
    service_id: str
    date_period: datetime
    total_requests: int = 0
    text_requests: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    human_review_count: int = 0

    def register_result(self, result: ModerationResult) -> None:
        if result.decision == ModerationDecision.APPROVED:
            self.approved_count += 1
        elif result.decision == ModerationDecision.REJECTED:
            self.rejected_count += 1
        elif result.decision == ModerationDecision.HUMAN_REVIEW:
            self.human_review_count += 1


class ModerationResponse(BaseModel):
    request: ModerationRequest
    result: ModerationResult


class ModerationUpdate(BaseModel):
    decision: ModerationDecision
    confidence_score: Optional[float] = None
    model_version: Optional[str] = None


class StatisticsResponse(BaseModel):
    totals: Statistics
    pending_requests: int


class WebServiceBase(BaseModel):
    name: str
    description: Optional[str] = None
    contact_email: str
    is_active: bool = True


class WebServiceCreate(WebServiceBase):
    pass


class WebService(BaseModel):
    service_id: str
    name: str
    description: Optional[str]
    contact_email: str
    registration_date: datetime
    is_active: bool


class APIKeyResponse(BaseModel):
    key_id: str
    key_prefix: str
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    last_used: Optional[datetime]


class APIKeyIssueResponse(APIKeyResponse):
    api_key: str
