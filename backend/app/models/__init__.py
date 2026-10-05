"""Domain models for the GEOSIX backend."""

# Registers the ``before_flush`` listener that stamps ``created_by`` /
# ``updated_by`` on audit-enabled models. The import is a deliberate side
# effect placed here so every entry point that touches the models (API, tests,
# scripts) gets the behaviour without a manual call.
import app.core.audit as _audit  # noqa: F401
from app.models.building import Building, BuildingType, ConstructionStatus
from app.models.floor import Floor, FloorType
from app.models.geometry3d import GeometryType, PropertyGeometry
from app.models.login_attempt import LoginAttempt
from app.models.ownership import Owner, OwnerKind, OwnershipInterest, OwnershipStatus
from app.models.parcel import ULPIN, Parcel, ParcelStatus
from app.models.password_reset_token import PasswordResetToken
from app.models.unit import Unit, UnitStatus, UnitType
from app.models.user import User, UserRole

__all__ = [
    "ULPIN",
    "Building",
    "BuildingType",
    "ConstructionStatus",
    "Floor",
    "FloorType",
    "GeometryType",
    "LoginAttempt",
    "Owner",
    "OwnerKind",
    "OwnershipInterest",
    "OwnershipStatus",
    "Parcel",
    "ParcelStatus",
    "PasswordResetToken",
    "PropertyGeometry",
    "Unit",
    "UnitStatus",
    "UnitType",
    "User",
    "UserRole",
]
