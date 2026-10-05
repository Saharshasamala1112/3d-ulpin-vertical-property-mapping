"""Work Item #19: derive and generate a Vertical DNA Code for a unit.

The VDC grammar, canonicalization and checksum rules are owned by the Feature
17 generator and Feature 15/16 parser modules. This module does not restate
them: it only resolves the four input segments from the database hierarchy
``Unit -> Floor -> Building -> Parcel`` and hands them to ``generate_vdc``.

Two input decisions are specific to this work item and are deliberately *not*
taken from the VDC specification document:

1. ``DOMAIN`` comes from ``Building.building_type``. A VDC describes a
   property, so the parcel's building classification is the right source.
   ``UnitType`` is intentionally unused: it cannot express Industrial or
   Institutional, and mapping it would make a unit's code contradict its
   building.
2. ``LEVEL`` comes from ``Floor.floor_number`` together with
   ``Floor.floor_type``; the negative basement sign is applied here rather than
   in ``canonical_level``, which is left untouched.

The module is stateless and read-only. It never commits, rolls back, refreshes
or mutates any entity: the calling service owns the transaction.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.building import BuildingType
from app.models.floor import FloorType
from app.services.vdc_generator import generate_vdc
from app.validators.vdc_parser import VDCValidationError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.orm import Session

    from app.models.building import Building
    from app.models.floor import Floor
    from app.models.parcel import Parcel
    from app.models.unit import Unit

logger = logging.getLogger("geosix.vdc")

#: The VDC LEVEL grammar permits a magnitude of 1..999.
MAX_LEVEL_MAGNITUDE = 999

#: Section 6.1 maps a domain letter to a property class. ``MIXED_USE`` has no
#: letter because the VDC format reserves one character per domain.
DOMAIN_BY_BUILDING_TYPE: dict[BuildingType, str | None] = {
    BuildingType.RESIDENTIAL: "A",
    BuildingType.COMMERCIAL: "B",
    BuildingType.INDUSTRIAL: "C",
    BuildingType.INSTITUTIONAL: "D",
    BuildingType.MIXED_USE: None,
}

#: Floor types that sit above ground and therefore carry a positive level.
_RAISED_FLOOR_TYPES = frozenset({FloorType.TYPICAL, FloorType.PENTHOUSE, FloorType.ROOFTOP})


def resolve_domain(building_type: BuildingType | None) -> str | None:
    """Return the VDC domain letter for a building type, or ``None`` if unmapped."""
    if building_type is None:
        return None
    return DOMAIN_BY_BUILDING_TYPE.get(building_type)


def resolve_level(floor: Floor | None) -> int | None:
    """Return the signed VDC level for a floor, or ``None`` if it has no valid level.

    Section 6.1 encodes a basement as negative and everything above ground as
    positive or zero:

    * ``basement`` -> ``-abs(floor_number)``; a floor number of zero has no
      basement spelling and yields ``None`` rather than a misleading ``G``.
    * ``ground`` -> ``0``.
    * ``typical`` / ``penthouse`` / ``rooftop`` -> ``+abs(floor_number)``.

    A missing floor, missing floor type, missing floor number, or a magnitude
    wider than three digits yields ``None``. The value is passed to
    ``generate_vdc`` as an ``int`` and canonicalized by the generator.
    """
    if floor is None:
        return None

    floor_type = floor.floor_type
    floor_number = floor.floor_number
    if floor_type is None or floor_number is None:
        return None

    try:
        magnitude = abs(int(floor_number))
    except (TypeError, ValueError):
        logger.warning("Floor %s has a non-numeric floor_number %r", floor.id, floor_number)
        return None

    if magnitude > MAX_LEVEL_MAGNITUDE:
        logger.warning(
            "Floor %s level %r exceeds the three-digit VDC limit", floor.id, floor_number
        )
        return None

    if floor_type is FloorType.GROUND:
        return 0
    if floor_type is FloorType.BASEMENT:
        return None if magnitude == 0 else -magnitude
    if floor_type in _RAISED_FLOOR_TYPES:
        return magnitude
    return None


def resolve_ulpin(parcel: Parcel | None) -> str | None:
    """Return the ULPIN a unit inherits from its parcel, or ``None`` if absent.

    ``Parcel.ulpin`` is the property-level identifier the VDC is anchored to.
    It is deliberately read as-is: the generator rejects a value that does not
    match ``GEOSX`` plus five digits rather than repairing it.
    """
    if parcel is None:
        return None
    return parcel.ulpin


def resolve_unit_segment(unit_identifier: str | None) -> str | None:
    """Return the unit's VDC segment, or ``None`` when it cannot be one.

    The identifier is passed through verbatim. No uppercasing, padding or
    trimming happens here, so ``unit-101`` and ``U0101`` are rejected by the
    generator instead of being silently repaired into ``U101`` / ``U101``.
    Surrounding whitespace is the one exception, since it is a caller defect
    rather than a spelling of the unit's own name.
    """
    if not isinstance(unit_identifier, str):
        return None
    if not unit_identifier or unit_identifier != unit_identifier.strip():
        return None
    return unit_identifier


def vdc_for_unit(
    db: Session,
    unit: Unit,
    floor: Floor | None = None,
) -> str | None:
    """Generate the VDC for a unit, or return ``None`` when one cannot be produced.

    Walks ``Unit -> Floor -> Building -> Parcel`` and delegates to
    ``generate_vdc``. An incomplete hierarchy, an unmapped domain, an
    unrepresentable level or any segment the generator rejects yields ``None``
    rather than an exception, so a unit can always be saved.

    ``floor`` may be passed by a caller that has already loaded the floor (for
    example ``create_unit``); otherwise the relationship is loaded on demand.
    """
    if unit is None:
        return None

    if floor is None:
        floor = unit.floor
    if floor is None:
        logger.info("Unit %s has no floor; skipping VDC generation", unit.id)
        return None

    building: Building | None = floor.building
    if building is None:
        logger.info("Floor %s has no building; skipping VDC generation", floor.id)
        return None

    parcel: Parcel | None = building.parcel
    ulpin = resolve_ulpin(parcel)
    domain = resolve_domain(building.building_type)
    level = resolve_level(floor)
    unit_segment = resolve_unit_segment(unit.unit_identifier)

    missing = [
        name
        for name, value in (
            ("ulpin", ulpin),
            ("domain", domain),
            ("level", level),
            ("unit", unit_segment),
        )
        if value is None
    ]
    if missing:
        logger.info(
            "Unit %s cannot be encoded; unresolved segments: %s", unit.id, ", ".join(missing)
        )
        return None

    try:
        return generate_vdc(ulpin, domain, level, unit_segment)
    except VDCValidationError as exc:
        logger.info("Unit %s has an unencodable segment: %s", unit.id, exc)
        return None
