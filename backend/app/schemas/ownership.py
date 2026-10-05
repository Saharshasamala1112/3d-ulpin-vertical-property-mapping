from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OwnerKind(str, Enum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"


class OwnershipStatus(str, Enum):
    ACTIVE = "active"
    TRANSFERRED = "transferred"
    REVOKED = "revoked"


class OwnerCreate(BaseModel):
    kind: OwnerKind
    name: str = Field(min_length=1, max_length=255)
    identifier: str | None = Field(default=None, max_length=255)
    contact_metadata: dict[str, Any] = Field(default_factory=dict)


class OwnerUpdate(BaseModel):
    kind: OwnerKind | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    identifier: str | None = Field(default=None, max_length=255)
    contact_metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_mutable_field(self) -> OwnerUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one owner field must be supplied")
        if "kind" in self.model_fields_set and self.kind is None:
            raise ValueError("kind cannot be null")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "contact_metadata" in self.model_fields_set and self.contact_metadata is None:
            raise ValueError("contact_metadata cannot be null")
        return self


class OwnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: OwnerKind
    name: str
    identifier: str | None
    contact_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SubjectInput(BaseModel):
    subject_type: Literal["parcel", "unit"]
    subject_id: UUID


class OwnershipGrant(SubjectInput):
    owner_id: UUID
    share_basis_points: int = Field(ge=1, le=10000)
    valid_from: datetime

    @field_validator("valid_from")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("valid_from must include a timezone")
        return value


class TransferAllocation(BaseModel):
    owner_id: UUID
    share_basis_points: int = Field(ge=1, le=10000)


class OwnershipTransfer(SubjectInput):
    effective_at: datetime
    allocations: list[TransferAllocation] = Field(min_length=1)

    @field_validator("effective_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("effective_at must include a timezone")
        return value


class OwnershipRevocation(BaseModel):
    effective_at: datetime

    @field_validator("effective_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("effective_at must include a timezone")
        return value


class OwnershipInterestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    subject_type: Literal["parcel", "unit"]
    subject_id: UUID
    share_basis_points: int
    valid_from: datetime
    valid_to: datetime | None
    status: OwnershipStatus
    created_at: datetime
    updated_at: datetime


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class OwnerListResponse(BaseModel):
    data: list[OwnerResponse]
    meta: PaginationMeta


class OwnershipInterestListResponse(BaseModel):
    data: list[OwnershipInterestResponse]
    meta: PaginationMeta


class OwnershipTransferResponse(BaseModel):
    closed: list[OwnershipInterestResponse]
    created: list[OwnershipInterestResponse]
