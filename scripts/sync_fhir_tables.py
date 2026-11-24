#!/usr/bin/env python3
"""Project selected FHIR R4 resources into queryable MySQL clinical tables.

fhir_resource remains the lossless source archive. Operational AIIMS patient,
appointment, prescription, admission and billing tables are never rewritten.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import sys

from app.db import connect

PAGE_SIZE = 250
RESOURCE_TYPES = ("Patient", "Encounter", "Observation", "Condition", "Procedure", "MedicationRequest")
PATIENT_COLUMNS = ("fhir_patient_id", "full_name", "birth_date", "gender", "phone", "email", "raw_resource")
TABLES = {
    "Encounter": ("fhir_encounter", (
        "fhir_encounter_id","fhir_patient_id","status","class_code","class_display",
        "type_display","period_start","period_end","raw_resource")),
    "Observation": ("fhir_observation", (
        "fhir_observation_id","fhir_patient_id","fhir_encounter_id","status",
        "code_system","code","code_display","effective_at","value_numeric","value_text",
        "value_unit","raw_resource")),
    "Condition": ("fhir_condition", (
        "fhir_condition_id","fhir_patient_id","fhir_encounter_id","clinical_status_code",
        "verification_status_code","code_system","code","code_display","onset_at",
        "recorded_date","raw_resource")),
    "Procedure": ("fhir_procedure", (
        "fhir_procedure_id","fhir_patient_id","fhir_encounter_id","status",
        "code_system","code","code_display","performed_start","performed_end","raw_resource")),
    "MedicationRequest": ("fhir_medication_request", (
        "fhir_medication_request_id","fhir_patient_id","fhir_encounter_id","status",
        "intent","medication_display","authored_on","dosage_text","raw_resource")),
}


def _first(items):
    return items[0] if isinstance(items, list) and items else {}


def _concept(value):
    if not isinstance(value, dict):
        return None, None, None
    coding = _first(value.get("coding"))
    return (
        coding.get("system") or value.get("system"),
        coding.get("code") or value.get("code"),
        coding.get("display") or value.get("display") or value.get("text") or coding.get("code"),
    )


def _parse_date(value):
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_datetime(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        parsed_date = _parse_date(value)
        return datetime.combine(parsed_date, datetime.min.time()) if parsed_date else None


def reference_id(value, resource_type):
    reference = value.get("reference") if isinstance(value, dict) else value
    if not isinstance(reference, str):
        return None
    parts = reference.split("?", 1)[0].rstrip("/").split("/")
    for index, part in enumerate(parts[:-1]):
        if part == resource_type:
            return parts[index + 1]
    return None


def normalise_patient(resource):
    """Preserve the preferred FHIR name as supplied; never invent a replacement."""
    names = resource.get("name") or []
    selected = next((n for n in names if n.get("use") == "official"), None)
    selected = selected or next((n for n in names if n.get("use") == "usual"), None) or _first(names)
    selected = selected if isinstance(selected, dict) else {}
    given = " ".join(str(x) for x in (selected.get("given") or []) if x)
    family = selected.get("family")
    full_name = selected.get("text")
    if not full_name:
        pieces = (selected.get("prefix") or []) + ([given] if given else []) + ([family] if family else []) + (selected.get("suffix") or [])
        full_name = " ".join(str(x) for x in pieces if x) or None
    telecom = resource.get("telecom") or []
    phone = next((x.get("value") for x in telecom if x.get("system") == "phone"), None)
    email = next((x.get("value") for x in telecom if x.get("system") == "email"), None)
    return {
        "fhir_patient_id": resource.get("id"),
        "full_name": full_name,
        "birth_date": _parse_date(resource.get("birthDate")),
        "gender": resource.get("gender"),
        "phone": phone,
        "email": email,
        "raw_resource": json.dumps(resource, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
    }


def normalise_resource(resource_type, resource, patient_id):
    """Extract common query fields while retaining the complete original resource."""
    raw = json.dumps(resource, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    encounter_id = reference_id(resource.get("encounter"), "Encounter")
    base = {"fhir_patient_id": patient_id, "raw_resource": raw}

    if resource_type == "Encounter":
        cls = resource.get("class") or {}
        type_concept = _concept(_first(resource.get("type")))
        period = resource.get("period") or {}
        return {
            "fhir_encounter_id": resource.get("id"), **base,
            "status": resource.get("status"),
            "class_code": cls.get("code"),
            "class_display": cls.get("display") or cls.get("code"),
            "type_display": type_concept[2],
            "period_start": _parse_datetime(period.get("start")),
            "period_end": _parse_datetime(period.get("end")),
        }

    if resource_type == "Observation":
        system, code, display = _concept(resource.get("code"))
        quantity = resource.get("valueQuantity") or {}
        value_numeric = None
        value_text = resource.get("valueString")
        value_unit = quantity.get("unit") or quantity.get("code")
        if "value" in quantity:
            try:
                value_numeric = Decimal(str(quantity["value"]))
            except (InvalidOperation, TypeError, ValueError):
                value_text = str(quantity.get("value"))
        elif "valueInteger" in resource or "valueDecimal" in resource:
            raw_number = resource.get("valueInteger", resource.get("valueDecimal"))
            try:
                value_numeric = Decimal(str(raw_number))
            except (InvalidOperation, TypeError, ValueError):
                value_text = str(raw_number)
        elif "valueBoolean" in resource:
            value_text = str(resource["valueBoolean"]).lower()
        elif "valueCodeableConcept" in resource:
            value_text = _concept(resource["valueCodeableConcept"])[2]
        effective_period = resource.get("effectivePeriod") or {}
        effective = (resource.get("effectiveDateTime") or resource.get("effectiveInstant")
                     or resource.get("effectiveDate") or effective_period.get("start"))
        return {
            "fhir_observation_id": resource.get("id"), **base,
            "fhir_encounter_id": encounter_id, "status": resource.get("status"),
            "code_system": system, "code": code, "code_display": display,
            "effective_at": _parse_datetime(effective), "value_numeric": value_numeric,
            "value_text": value_text, "value_unit": value_unit,
        }

    if resource_type == "Condition":
        system, code, display = _concept(resource.get("code"))
        return {
            "fhir_condition_id": resource.get("id"), **base,
            "fhir_encounter_id": encounter_id,
            "clinical_status_code": _concept(_first(resource.get("clinicalStatus", {}).get("coding")))[1]
                if isinstance(resource.get("clinicalStatus"), dict) and resource["clinicalStatus"].get("coding")
                else (resource.get("clinicalStatus") or {}).get("text"),
            "verification_status_code": _concept(_first(resource.get("verificationStatus", {}).get("coding")))[1]
                if isinstance(resource.get("verificationStatus"), dict) and resource["verificationStatus"].get("coding")
                else (resource.get("verificationStatus") or {}).get("text"),
            "code_system": system, "code": code, "code_display": display,
            "onset_at": _parse_datetime(resource.get("onsetDateTime") or
                                        (resource.get("onsetPeriod") or {}).get("start")),
            "recorded_date": _parse_date(resource.get("recordedDate")),
        }

    if resource_type == "Procedure":
        system, code, display = _concept(resource.get("code"))
        period = resource.get("performedPeriod") or {}
        return {
            "fhir_procedure_id": resource.get("id"), **base,
            "fhir_encounter_id": encounter_id, "status": resource.get("status"),
            "code_system": system, "code": code, "code_display": display,
            "performed_start": _parse_datetime(resource.get("performedDateTime") or period.get("start")),
            "performed_end": _parse_datetime(period.get("end")),
        }

    if resource_type == "MedicationRequest":
        medication = resource.get("medicationCodeableConcept") or {}
        dosage = resource.get("dosageInstruction") or []
        dosage_text = "; ".join(x.get("text") for x in dosage if isinstance(x, dict) and x.get("text")) or None
        return {
            "fhir_medication_request_id": resource.get("id"), **base,
            "fhir_encounter_id": encounter_id, "status": resource.get("status"),
            "intent": resource.get("intent"),
            "medication_display": _concept(medication)[2] or
                (resource.get("medicationReference") or {}).get("display"),
            "authored_on": _parse_date(resource.get("authoredOn")),
            "dosage_text": dosage_text,
        }

    raise ValueError("Unsupported FHIR resource type: " + resource_type)


def _insert_sql(table, columns):
    names = ",".join(columns)
    marks = ",".join(["%s"] * len(columns))
    updates = ",".join(f"{name}=VALUES({name})" for name in columns[1:])
    return f"INSERT INTO {table} ({names}) VALUES ({marks}) ON DUPLICATE KEY UPDATE {updates}"


def _assert_schema(cursor):
    required = sorted({
        "fhir_resource","fhir_patient","fhir_patient_link","fhir_encounter",
        "fhir_observation","fhir_condition","fhir_procedure","fhir_medication_request",
    })
    cursor.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN (" +
        ",".join(["%s"] * len(required)) + ")",
        tuple(required),
    )
    present = {row[0] for row in cursor.fetchall()}
    missing = sorted(set(required) - present)
    if missing:
        raise RuntimeError(
            "Missing FHIR tables: " + ", ".join(missing) +
            ". Apply sql/migrations/2026_11_fhir_relational_clinical.sql in MySQL Workbench first."
        )


def sync_fhir_tables():
    """Idempotently sync selected rows from fhir_resource into the relational FHIR layer."""
    reader, writer = connect(), connect()
    read_cursor = reader.cursor(dictionary=True)
    write_cursor = writer.cursor()
    counts = {kind: 0 for kind in RESOURCE_TYPES}
    skipped = 0
    try:
        _assert_schema(write_cursor)
        for kind in RESOURCE_TYPES:
            last_id = ""
            while True:
                read_cursor.execute(
                    "SELECT resource_id,patient_fhir_id,payload FROM fhir_resource "
                    "WHERE resource_type=%s AND resource_id>%s ORDER BY resource_id LIMIT %s",
                    (kind, last_id, PAGE_SIZE),
                )
                page = read_cursor.fetchall()
                if not page:
                    break
                last_id = page[-1]["resource_id"]

                if kind == "Patient":
                    rows = []
                    links = []
                    for item in page:
                        record = normalise_patient(json.loads(item["payload"]))
                        if not record["fhir_patient_id"]:
                            continue
                        rows.append(tuple(record[c] for c in PATIENT_COLUMNS))
                        links.append((record["fhir_patient_id"],))
                    if rows:
                        write_cursor.executemany(_insert_sql("fhir_patient", PATIENT_COLUMNS), rows)
                        # INSERT IGNORE preserves any pre-existing manually verified UHID link.
                        write_cursor.executemany(
                            "INSERT IGNORE INTO fhir_patient_link (fhir_patient_id) VALUES (%s)", links
                        )
                        counts[kind] += len(rows)
                else:
                    prepared = []
                    for item in page:
                        patient_id = item.get("patient_fhir_id")
                        if not patient_id:
                            skipped += 1
                            continue
                        record = normalise_resource(kind, json.loads(item["payload"]), patient_id)
                        columns = TABLES[kind][1]
                        prepared.append(tuple(record[c] for c in columns))
                    if prepared:
                        patient_ids = sorted({row[1] for row in prepared})
                        write_cursor.execute(
                            "SELECT fhir_patient_id FROM fhir_patient WHERE fhir_patient_id IN (" +
                            ",".join(["%s"] * len(patient_ids)) + ")",
                            tuple(patient_ids),
                        )
                        known = {row[0] for row in write_cursor.fetchall()}
                        valid = [row for row in prepared if row[1] in known]
                        skipped += len(prepared) - len(valid)
                        if valid:
                            table, columns = TABLES[kind]
                            write_cursor.executemany(_insert_sql(table, columns), valid)
                            counts[kind] += len(valid)
                writer.commit()
    except Exception:
        writer.rollback()
        raise
    finally:
        read_cursor.close()
        write_cursor.close()
        reader.close()
        writer.close()
    return {"counts": counts, "skipped_without_patient": skipped,
            "total_projected": sum(counts.values())}


def main():
    try:
        result = sync_fhir_tables()
    except Exception as exc:
        print(f"FHIR relational sync failed: {exc}", file=sys.stderr)
        return 1
    print("FHIR relational sync complete.")
    for kind, count in result["counts"].items():
        print(f"{kind:20} {count:>10,}")
    print(f"{'Total projected':20} {result['total_projected']:>10,}")
    print(f"{'Skipped/no patient':20} {result['skipped_without_patient']:>10,}")
    print("The original JSON archive and operational patient/appointment data were not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
