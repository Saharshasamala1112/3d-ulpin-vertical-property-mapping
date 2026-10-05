from __future__ import annotations

import math
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ownership import (
    Owner,
    OwnershipInterest,
)
from app.models.ownership import (
    OwnerKind as ModelOwnerKind,
)
from app.models.ownership import (
    OwnershipStatus as ModelOwnershipStatus,
)
from app.models.parcel import Parcel
from app.models.unit import Unit
from app.schemas.ownership import (
    OwnerCreate,
    OwnerListResponse,
    OwnerResponse,
    OwnershipGrant,
    OwnershipInterestListResponse,
    OwnershipInterestResponse,
    OwnershipRevocation,
    OwnershipTransfer,
    OwnershipTransferResponse,
    OwnerUpdate,
    PaginationMeta,
)

SubjectType = Literal["parcel", "unit"]


@dataclass
class OwnershipError(Exception):
    status_code: int
    code: str
    message: str
    details: dict[str, str] | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _subject_column(subject_type: SubjectType):
    return OwnershipInterest.parcel_id if subject_type == "parcel" else OwnershipInterest.unit_id


def _subject_kwargs(
    subject_type: SubjectType, subject_id: uuid.UUID
) -> dict[str, uuid.UUID | None]:
    return {
        "parcel_id": subject_id if subject_type == "parcel" else None,
        "unit_id": subject_id if subject_type == "unit" else None,
    }


def _subject_values(interest: OwnershipInterest) -> tuple[SubjectType, uuid.UUID]:
    if interest.parcel_id is not None:
        return "parcel", interest.parcel_id
    if interest.unit_id is not None:
        return "unit", interest.unit_id
    raise RuntimeError("Ownership interest has no subject despite the database constraint")


def _interest_response(interest: OwnershipInterest) -> OwnershipInterestResponse:
    subject_type, subject_id = _subject_values(interest)
    return OwnershipInterestResponse(
        id=interest.id,
        owner_id=interest.owner_id,
        subject_type=subject_type,
        subject_id=subject_id,
        share_basis_points=interest.share_basis_points,
        valid_from=interest.valid_from,
        valid_to=interest.valid_to,
        status=interest.status.value,
        created_at=interest.created_at,
        updated_at=interest.updated_at,
    )


def _owner_not_found() -> OwnershipError:
    return OwnershipError(404, "NOT_FOUND", "Owner not found")


def _subject_not_found(subject_type: SubjectType) -> OwnershipError:
    return OwnershipError(404, "NOT_FOUND", f"{subject_type.title()} not found")


@contextmanager
def _atomic(db: Session):
    """Run one service write in a savepoint and commit the session once."""
    try:
        with db.begin_nested():
            yield
            db.flush()
        db.commit()
    except IntegrityError as error:
        raise OwnershipError(
            409,
            "OWNERSHIP_CONFLICT",
            "The ownership change conflicts with existing records",
        ) from error


def _lock_subject(db: Session, subject_type: SubjectType, subject_id: uuid.UUID) -> None:
    model = Parcel if subject_type == "parcel" else Unit
    found = db.scalar(select(model.id).where(model.id == subject_id).with_for_update())
    if found is None:
        raise _subject_not_found(subject_type)


def _subject_interests(
    db: Session, subject_type: SubjectType, subject_id: uuid.UUID
) -> list[OwnershipInterest]:
    column = _subject_column(subject_type)
    return list(db.scalars(select(OwnershipInterest).where(column == subject_id)).all())


def _active_at(interests: Iterable[OwnershipInterest], when: datetime) -> list[OwnershipInterest]:
    return [
        interest
        for interest in interests
        if interest.valid_from <= when and (interest.valid_to is None or when < interest.valid_to)
    ]


def _validate_total(interests: Iterable[OwnershipInterest]) -> None:
    events: list[tuple[datetime, int]] = []
    for interest in interests:
        events.append((interest.valid_from, interest.share_basis_points))
        if interest.valid_to is not None:
            events.append((interest.valid_to, -interest.share_basis_points))
    total = 0
    for _, delta in sorted(events, key=lambda event: (event[0], event[1])):
        total += delta
        if total > 10000:
            raise OwnershipError(
                409,
                "OWNERSHIP_SHARE_LIMIT_EXCEEDED",
                "Active ownership shares for a subject cannot exceed 10000 basis points",
                {"share_basis_points": "The effective allocation exceeds 10000"},
            )


def _validate_owner_intervals(interests: Iterable[OwnershipInterest]) -> None:
    ordered = sorted(interests, key=lambda row: (row.owner_id, row.valid_from))
    previous_by_owner: dict[uuid.UUID, OwnershipInterest] = {}
    for interest in ordered:
        previous = previous_by_owner.get(interest.owner_id)
        if previous is not None and (
            previous.valid_to is None or interest.valid_from < previous.valid_to
        ):
            raise OwnershipError(
                409,
                "OWNERSHIP_INTERVAL_OVERLAP",
                "The same owner cannot have overlapping intervals for the same subject",
                {"owner_id": str(interest.owner_id)},
            )
        previous_by_owner[interest.owner_id] = interest


def _owner_response(owner: Owner) -> OwnerResponse:
    return OwnerResponse.model_validate(owner)


def create_owner(db: Session, data: OwnerCreate) -> OwnerResponse:
    now = _now()
    with _atomic(db):
        owner = Owner(
            kind=ModelOwnerKind(data.kind.value),
            name=data.name.strip(),
            identifier=data.identifier,
            contact_metadata=data.contact_metadata,
            created_at=now,
            updated_at=now,
        )
        if not owner.name:
            raise OwnershipError(
                422, "VALIDATION_ERROR", "Name cannot be blank", {"name": "Required"}
            )
        db.add(owner)
        db.flush()
    return _owner_response(owner)


def list_owners(
    db: Session, page: int = 1, per_page: int = 20, search: str | None = None
) -> OwnerListResponse:
    query = select(Owner)
    if search:
        query = query.where(Owner.name.ilike(f"%{search}%"))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    owners = db.scalars(
        query.order_by(Owner.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    ).all()
    return OwnerListResponse(
        data=[_owner_response(owner) for owner in owners],
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=math.ceil(total / per_page) if total else 1,
        ),
    )


def get_owner(db: Session, owner_id: uuid.UUID) -> OwnerResponse:
    owner = db.get(Owner, owner_id)
    if owner is None:
        raise _owner_not_found()
    return _owner_response(owner)


def update_owner(db: Session, owner_id: uuid.UUID, data: OwnerUpdate) -> OwnerResponse:
    with _atomic(db):
        owner = db.get(Owner, owner_id)
        if owner is None:
            raise _owner_not_found()
        changes = data.model_dump(exclude_unset=True)
        if "kind" in changes:
            changes["kind"] = ModelOwnerKind(changes["kind"].value)
        if "name" in changes:
            changes["name"] = changes["name"].strip()
            if not changes["name"]:
                raise OwnershipError(
                    422, "VALIDATION_ERROR", "Name cannot be blank", {"name": "Required"}
                )
        for field, value in changes.items():
            setattr(owner, field, value)
        owner.updated_at = _now()
        db.flush()
    return _owner_response(owner)


def delete_owner(db: Session, owner_id: uuid.UUID) -> None:
    with _atomic(db):
        owner = db.get(Owner, owner_id)
        if owner is None:
            raise _owner_not_found()
        if db.scalar(
            select(OwnershipInterest.id).where(OwnershipInterest.owner_id == owner_id).limit(1)
        ):
            raise OwnershipError(
                409,
                "OWNERSHIP_HISTORY_IMMUTABLE",
                "An owner with ownership history cannot be deleted",
            )
        db.delete(owner)


def grant_interest(db: Session, data: OwnershipGrant) -> OwnershipInterestResponse:
    with _atomic(db):
        _lock_subject(db, data.subject_type, data.subject_id)
        owner = db.get(Owner, data.owner_id)
        if owner is None:
            raise _owner_not_found()
        existing = _subject_interests(db, data.subject_type, data.subject_id)
        candidate = OwnershipInterest(
            id=uuid.uuid4(),
            owner_id=data.owner_id,
            **_subject_kwargs(data.subject_type, data.subject_id),
            share_basis_points=data.share_basis_points,
            valid_from=data.valid_from.astimezone(timezone.utc),
            valid_to=None,
            status=ModelOwnershipStatus.ACTIVE,
            created_at=_now(),
            updated_at=_now(),
        )
        if any(
            row.owner_id == candidate.owner_id
            and row.valid_from < (candidate.valid_to or datetime.max.replace(tzinfo=timezone.utc))
            and (row.valid_to is None or candidate.valid_from < row.valid_to)
            for row in existing
        ):
            raise OwnershipError(
                409,
                "OWNERSHIP_INTERVAL_OVERLAP",
                "The same owner already has an overlapping interval for this subject",
                {"owner_id": str(candidate.owner_id)},
            )
        _validate_total([*existing, candidate])
        _validate_owner_intervals([*existing, candidate])
        db.add(candidate)
        db.flush()
    return _interest_response(candidate)


def transfer_ownership(db: Session, data: OwnershipTransfer) -> OwnershipTransferResponse:
    with _atomic(db):
        _lock_subject(db, data.subject_type, data.subject_id)
        when = data.effective_at.astimezone(timezone.utc)
        existing = _subject_interests(db, data.subject_type, data.subject_id)
        current = _active_at(existing, when)
        if not current:
            raise OwnershipError(
                409,
                "OWNERSHIP_TRANSFER_INVALID",
                "A transfer requires an allocation effective at the transfer time",
            )
        if any(row.valid_from > when for row in existing):
            raise OwnershipError(
                409,
                "OWNERSHIP_TRANSFER_INVALID",
                "A transfer cannot replace a subject with future-dated allocations",
            )
        if any(row.valid_to is not None and row.valid_to > when for row in current):
            raise OwnershipError(
                409,
                "OWNERSHIP_TRANSFER_INVALID",
                "A scheduled interval closure must be resolved before transfer",
            )
        if any(row.valid_from >= when for row in current):
            raise OwnershipError(
                409,
                "OWNERSHIP_TRANSFER_INVALID",
                "Transfer time must be later than each replaced interval start",
            )

        allocations: dict[uuid.UUID, int] = {}
        for allocation in data.allocations:
            if allocation.owner_id in allocations:
                raise OwnershipError(
                    422,
                    "VALIDATION_ERROR",
                    "Each owner may appear only once in a transfer allocation",
                    {"allocations": "Duplicate owner_id"},
                )
            if db.get(Owner, allocation.owner_id) is None:
                raise _owner_not_found()
            allocations[allocation.owner_id] = allocation.share_basis_points
        previous_total = sum(row.share_basis_points for row in current)
        if sum(allocations.values()) != previous_total:
            raise OwnershipError(
                409,
                "OWNERSHIP_TRANSFER_INVALID",
                "A transfer must preserve the complete allocation total",
                {"allocations": f"Expected {previous_total} total basis points"},
            )

        now = _now()
        for row in current:
            row.valid_to = when
            row.status = ModelOwnershipStatus.TRANSFERRED
            row.updated_at = now
        created = [
            OwnershipInterest(
                id=uuid.uuid4(),
                owner_id=owner_id,
                **_subject_kwargs(data.subject_type, data.subject_id),
                share_basis_points=share,
                valid_from=when,
                valid_to=None,
                status=ModelOwnershipStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            for owner_id, share in allocations.items()
        ]
        final = [row for row in existing if row not in current] + [
            *[row for row in current if row.valid_from < when],
            *created,
        ]
        _validate_total(final)
        _validate_owner_intervals(final)
        db.add_all(created)
        db.flush()
    return OwnershipTransferResponse(
        closed=[_interest_response(row) for row in current],
        created=[_interest_response(row) for row in created],
    )


def revoke_interest(
    db: Session, interest_id: uuid.UUID, data: OwnershipRevocation
) -> OwnershipInterestResponse:
    interest = db.get(OwnershipInterest, interest_id)
    if interest is None:
        raise OwnershipError(404, "NOT_FOUND", "Ownership interest not found")
    subject_type, subject_id = _subject_values(interest)
    with _atomic(db):
        _lock_subject(db, subject_type, subject_id)
        interest = db.scalar(
            select(OwnershipInterest).where(OwnershipInterest.id == interest_id).with_for_update()
        )
        if interest is None:
            raise OwnershipError(404, "NOT_FOUND", "Ownership interest not found")
        if interest.valid_to is not None:
            raise OwnershipError(
                409,
                "OWNERSHIP_HISTORY_IMMUTABLE",
                "A closed ownership interval cannot be revoked again",
            )
        when = data.effective_at.astimezone(timezone.utc)
        if when <= interest.valid_from:
            raise OwnershipError(
                422,
                "VALIDATION_ERROR",
                "Revocation must occur after the interval starts",
                {"effective_at": "Must be later than valid_from"},
            )
        interest.valid_to = when
        interest.status = ModelOwnershipStatus.REVOKED
        interest.updated_at = _now()
        db.flush()
    return _interest_response(interest)


def list_interests(
    db: Session,
    *,
    owner_id: uuid.UUID | None = None,
    subject_type: SubjectType | None = None,
    subject_id: uuid.UUID | None = None,
    page: int = 1,
    per_page: int = 20,
    history: bool = False,
    effective_at: datetime | None = None,
) -> OwnershipInterestListResponse:
    if owner_id is not None and db.get(Owner, owner_id) is None:
        raise _owner_not_found()
    if subject_type is not None and subject_id is not None:
        model = Parcel if subject_type == "parcel" else Unit
        if db.get(model, subject_id) is None:
            raise _subject_not_found(subject_type)
    query = select(OwnershipInterest)
    if owner_id is not None:
        query = query.where(OwnershipInterest.owner_id == owner_id)
    if subject_type is not None and subject_id is not None:
        query = query.where(_subject_column(subject_type) == subject_id)
    if not history:
        as_of = effective_at.astimezone(timezone.utc) if effective_at else _now()
        query = query.where(
            OwnershipInterest.valid_from <= as_of,
            (OwnershipInterest.valid_to.is_(None)) | (OwnershipInterest.valid_to > as_of),
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(OwnershipInterest.valid_from.desc(), OwnershipInterest.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()
    return OwnershipInterestListResponse(
        data=[_interest_response(row) for row in rows],
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=math.ceil(total / per_page) if total else 1,
        ),
    )
