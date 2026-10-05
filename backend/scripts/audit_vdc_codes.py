from __future__ import annotations

import csv
import sys

from app.core.database import SessionLocal
from app.services.unit import audit_invalid_vdc_codes


def main() -> int:
    """Print invalid stored unit VDCs as CSV to stdout."""
    with SessionLocal() as db:
        invalid = audit_invalid_vdc_codes(db)

    writer = csv.writer(sys.stdout)
    writer.writerow(("unit_id", "vdc_code", "validation_errors"))
    writer.writerows((unit_id, code, "; ".join(errors)) for unit_id, code, errors in invalid)
    print(f"Invalid VDC codes: {len(invalid)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
