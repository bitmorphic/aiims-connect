#!/usr/bin/env python3
"""Idempotently import a Synthea FHIR R4 ZIP into AIIMS Connect's FHIR store.

Run the accompanying SQL migration first. The ZIP is kept outside Git and can
be supplied from a local path; records are synthetic and are never inserted
into the operational AIIMS patient/appointment tables.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


INSERT_RESOURCE = """INSERT INTO fhir_resource
    (resource_type, resource_id, patient_fhir_id, version_id, last_updated,
     payload, source_bundle, import_batch_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
      patient_fhir_id=COALESCE(VALUES(patient_fhir_id),patient_fhir_id),
      version_id=VALUES(version_id), last_updated=VALUES(last_updated),
      payload=VALUES(payload), source_bundle=VALUES(source_bundle),
      import_batch_id=VALUES(import_batch_id)"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_last_updated(resource):
    raw = resource.get("meta", {}).get("lastUpdated")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError):
        return None


def _patient_reference_map(entries):
    mapping = {}
    for entry in entries:
        resource = entry.get("resource") or {}
        resource_type, resource_id = resource.get("resourceType"), resource.get("id")
        if resource_type and resource_id:
            mapping[f"{resource_type}/{resource_id}"] = (resource_type, resource_id)
            mapping[f"urn:uuid:{resource_id}"] = (resource_type, resource_id)
        full_url = entry.get("fullUrl")
        if full_url and resource_type and resource_id:
            mapping[full_url] = (resource_type, resource_id)
    return mapping


def _referenced_patient_id(value, reference_map, found):
    if isinstance(value, dict):
        reference = value.get("reference")
        if isinstance(reference, str):
            target = reference_map.get(reference)
            if target and target[0] == "Patient":
                found.add(target[1])
            elif reference.startswith("Patient/"):
                found.add(reference.split("/", 1)[1])
            elif "/Patient/" in reference:
                found.add(reference.rsplit("/Patient/", 1)[1].split("/", 1)[0])
        for child in value.values():
            _referenced_patient_id(child, reference_map, found)
    elif isinstance(value, list):
        for child in value:
            _referenced_patient_id(child, reference_map, found)


def iter_bundle_resources(archive, info):
    bundle = json.loads(archive.read(info))
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        raise ValueError(f"{info.filename}: expected a FHIR Bundle")
    entries = bundle.get("entry") or []
    reference_map = _patient_reference_map(entries)
    for entry in entries:
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if not resource_type or not resource_id:
            raise ValueError(f"{info.filename}: resource missing resourceType or id")
        patient_refs = set()
        if resource_type == "Patient":
            patient_refs.add(resource_id)
        else:
            _referenced_patient_id(resource, reference_map, patient_refs)
        if len(patient_refs) > 1:
            raise ValueError(f"{info.filename}: {resource_type}/{resource_id} references multiple patients")
        patient_id = next(iter(patient_refs), None)
        payload = json.dumps(resource, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        yield (
            resource_type,
            resource_id,
            patient_id,
            resource.get("meta", {}).get("versionId"),
            parse_last_updated(resource),
            payload,
            Path(info.filename).name,
        )


def inspect_archive(path: Path):
    counts = Counter()
    bundle_count = 0
    patients = set()
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".json"):
                continue
            bundle_count += 1
            for row in iter_bundle_resources(archive, info):
                counts[row[0]] += 1
                if row[0] == "Patient":
                    patients.add(row[1])
    return bundle_count, counts, patients


def import_archive(path: Path, force=False):
    from app.db import connect

    source_hash = sha256_file(path)
    connection = connect()
    cursor = connection.cursor(dictionary=True)
    batch_id = None
    try:
        cursor.execute(
            "SELECT batch_id,status FROM fhir_import_batch WHERE source_sha256=%s",
            (source_hash,),
        )
        existing = cursor.fetchone()
        if existing and existing["status"] == "completed" and not force:
            print("This exact ZIP has already been imported successfully; skipping.")
            return
        if existing:
            batch_id = existing["batch_id"]
            cursor.execute(
                "UPDATE fhir_import_batch SET source_filename=%s,status='running',"
                "resource_count=0,patient_count=0,bundle_count=0,error_message=NULL,"
                "started_at=CURRENT_TIMESTAMP,finished_at=NULL WHERE batch_id=%s",
                (path.name, batch_id),
            )
        else:
            cursor.execute(
                "INSERT INTO fhir_import_batch (source_filename,source_sha256,status) "
                "VALUES (%s,%s,'running')",
                (path.name, source_hash),
            )
            batch_id = cursor.lastrowid
        connection.commit()

        total_resources = 0
        patient_ids = set()
        bundle_count = 0
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".json"):
                    continue
                bundle_count += 1
                pending = []
                for row in iter_bundle_resources(archive, info):
                    if row[0] == "Patient":
                        patient_ids.add(row[1])
                    pending.append(row + (batch_id,))
                    if len(pending) >= 250:
                        cursor.executemany(INSERT_RESOURCE, pending)
                        connection.commit()
                        total_resources += len(pending)
                        pending.clear()
                if pending:
                    cursor.executemany(INSERT_RESOURCE, pending)
                    connection.commit()
                    total_resources += len(pending)
                cursor.execute(
                    "UPDATE fhir_import_batch SET resource_count=%s,patient_count=%s,bundle_count=%s "
                    "WHERE batch_id=%s",
                    (total_resources, len(patient_ids), bundle_count, batch_id),
                )
                connection.commit()

        cursor.execute(
            "UPDATE fhir_import_batch SET status='completed',resource_count=%s,patient_count=%s,"
            "bundle_count=%s,finished_at=CURRENT_TIMESTAMP WHERE batch_id=%s",
            (total_resources, len(patient_ids), bundle_count, batch_id),
        )
        connection.commit()
        print(f"FHIR import complete: {total_resources:,} resources, {len(patient_ids):,} patients, {bundle_count:,} Bundles.")
    except Exception as exc:
        connection.rollback()
        if batch_id is not None:
            try:
                cursor.execute(
                    "UPDATE fhir_import_batch SET status='failed',error_message=%s,"
                    "finished_at=CURRENT_TIMESTAMP WHERE batch_id=%s",
                    (str(exc)[:4000], batch_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def main():
    parser = argparse.ArgumentParser(description="Import Synthea FHIR R4 ZIP data into AIIMS Connect")
    parser.add_argument("zip_file", type=Path, help="Path to synthea_sample_data_fhir_latest.zip")
    parser.add_argument("--dry-run", action="store_true", help="Parse and count resources without connecting to MySQL")
    parser.add_argument("--force", action="store_true", help="Re-import an already completed ZIP (upserts resources)")
    args = parser.parse_args()
    if not args.zip_file.is_file():
        parser.error(f"ZIP file does not exist: {args.zip_file}")
    try:
        with zipfile.ZipFile(args.zip_file) as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise ValueError(f"Corrupt ZIP member: {bad_member}")
        if args.dry_run:
            bundles, counts, patients = inspect_archive(args.zip_file)
            print(f"ZIP: {args.zip_file.name}")
            print(f"Bundles: {bundles:,}; unique Patient resources: {len(patients):,}; total resources: {sum(counts.values()):,}")
            for resource_type, count in counts.most_common():
                print(f"{resource_type:28} {count:>10,}")
            print("Dry run only: no MySQL connection was opened.")
        else:
            import_archive(args.zip_file, force=args.force)
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        print(f"FHIR import failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
