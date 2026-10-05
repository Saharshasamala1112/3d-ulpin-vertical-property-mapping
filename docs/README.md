# Project Documentation

This directory holds project-level documentation for the GEOSIX foundation and future platform modules.

Typical contents include:

- architecture and design notes
- data model and API references
- setup and deployment guidance
- geospatial domain documentation
- module-specific planning documents
- operational and maintenance notes

Keep this directory focused on durable project documentation rather than generated files or local environment artifacts.

## Documents

- [architecture.md](architecture.md) — directory structure, backend and frontend conventions
- [development.md](development.md) — branching policy, merge request workflow, and verification commands
- [deployment.md](deployment.md) — Compose deployment, production configuration, secrets, migrations, and backup/restore
- [api.md](api.md) — endpoint reference
- [geojson-import.md](geojson-import.md) — GeoJSON parcel and building import
- [authentication.md](authentication.md) — JWT flow and token handling
- [vdc-specification.md](vdc-specification.md) — VDC domain specification
- [property-management.md](property-management.md) — parcel/building/floor/unit management UI, including known backend limitations
- [3D geometry validation](geometry-validation.md)
- [3D volumetric overlap detection](overlap-detection.md)
- [3D spatial gap detection](gap-detection.md)
- [3D topology validation API](topology-api.md)
- [Topology validation dashboard](topology-validation-dashboard.md)
- [Deterministic 3D topology validation dataset](topology-test-dataset.md)
- [Canonical unit bounding-box storage](unit-bounding-box-storage.md)
