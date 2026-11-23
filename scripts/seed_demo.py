#!/usr/bin/env python3
"""Legacy synthetic demo seeder disabled in favour of the FHIR-first data flow.

Use scripts/import_fhir.py to load the supplied Synthea FHIR R4 dataset.
Use scripts/clean_demo_data.py to preview and safely remove records created
by the old demo seeder. This script intentionally creates no accounts or rows.
"""
import sys


def main():
    print("Demo data seeding is disabled.")
    print("Use scripts/import_fhir.py for the synthetic FHIR dataset.")
    print("Use scripts/clean_demo_data.py to preview legacy demo-record cleanup.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
