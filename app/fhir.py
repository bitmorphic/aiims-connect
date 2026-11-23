"""Read-only HL7 FHIR R4 API for imported synthetic clinical records.

This is an explicitly scoped interoperability layer, not a complete FHIR server.
It supports CapabilityStatement, resource read, and a documented subset of search.
All clinical-resource access is restricted to authenticated hospital staff.
"""
from datetime import datetime, timezone
import json
from urllib.parse import urlencode

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for

from .db import fetch_all, fetch_one

bp = Blueprint("fhir", __name__, url_prefix="/fhir")
FHIR_CONTENT_TYPE = "application/fhir+json; charset=utf-8"
FHIR_VERSION = "4.0.1"

RESOURCE_TYPES = (
    "AllergyIntolerance", "CarePlan", "CareTeam", "Claim", "Condition",
    "Device", "DiagnosticReport", "DocumentReference", "Encounter",
    "ExplanationOfBenefit", "ImagingStudy", "Immunization", "Location",
    "Medication", "MedicationAdministration", "MedicationRequest",
    "Observation", "Organization", "Patient", "Practitioner",
    "PractitionerRole", "Procedure", "Provenance", "SupplyDelivery",
)

# Patient references are indexed only for resources with patient links in the
# imported FHIR data. Shared Organization/Practitioner/Location records are not
# incorrectly assigned to one patient's compartment.
PATIENT_SEARCH_TYPES = {
    "AllergyIntolerance", "CarePlan", "CareTeam", "Claim", "Condition",
    "Device", "DiagnosticReport", "DocumentReference", "Encounter",
    "ExplanationOfBenefit", "ImagingStudy", "Immunization",
    "MedicationAdministration", "MedicationRequest", "Observation",
    "Procedure", "SupplyDelivery",
}
CODE_SEARCH_TYPES = {
    "AllergyIntolerance", "Condition", "DiagnosticReport",
    "MedicationRequest", "Observation", "Procedure",
}
STATUS_SEARCH_TYPES = {
    "CarePlan", "CareTeam", "Claim", "Device", "DiagnosticReport",
    "DocumentReference", "Encounter", "ExplanationOfBenefit",
    "ImagingStudy", "Immunization", "MedicationAdministration",
    "MedicationRequest", "Procedure", "SupplyDelivery",
}
CLINICAL_STATUS_TYPES = {"AllergyIntolerance", "Condition"}
VERIFICATION_STATUS_TYPES = {"AllergyIntolerance", "Condition"}


def _fhir_response(payload, status=200):
    response = current_app.response_class(
        response=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status=status,
        content_type=FHIR_CONTENT_TYPE,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _outcome(status, code, diagnostics):
    return _fhir_response({
        "resourceType": "OperationOutcome",
        "issue": [{
            "severity": "error",
            "code": code,
            "diagnostics": diagnostics,
        }],
    }, status)


def _staff_authorized():
    if not session.get("login_id"):
        return _outcome(401, "login", "Authentication is required to access clinical FHIR resources.")
    if session.get("role") not in ("chain_admin", "branch_admin", "doctor", "receptionist"):
        return _outcome(403, "forbidden", "FHIR dataset access is limited to authenticated hospital staff.")
    return None


def _capability_resource(resource_type):
    search_params = [
        {"name": "_id", "type": "token", "documentation": "Match the logical resource id."},
        {"name": "_count", "type": "number", "documentation": "Page size; maximum 100."},
    ]
    if resource_type in PATIENT_SEARCH_TYPES:
        search_params.append({"name": "patient", "type": "reference", "documentation": "Match the Patient referenced by the resource."})
    if resource_type == "Patient":
        search_params.extend([
            {"name": "name", "type": "string"},
            {"name": "gender", "type": "token"},
            {"name": "birthdate", "type": "date"},
            {"name": "identifier", "type": "token"},
        ])
    if resource_type in CODE_SEARCH_TYPES:
        search_params.append({"name": "code", "type": "token"})
    if resource_type in STATUS_SEARCH_TYPES:
        search_params.append({"name": "status", "type": "token"})
    if resource_type in CLINICAL_STATUS_TYPES:
        search_params.append({"name": "clinical-status", "type": "token"})
    if resource_type in VERIFICATION_STATUS_TYPES:
        search_params.append({"name": "verification-status", "type": "token"})
    return {
        "type": resource_type,
        "interaction": [{"code": "read"}, {"code": "search-type"}],
        "searchParam": search_params,
    }


@bp.get("/metadata")
def capability_statement():
    """Publish the FHIR version and the interactions/searches implemented here."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return _fhir_response({
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": now,
        "kind": "instance",
        "software": {"name": "AIIMS Connect FHIR Gateway", "version": "1.0.0"},
        "implementation": {
            "description": "Read-only FHIR R4 API for the separately imported synthetic Synthea dataset.",
            "url": request.url_root.rstrip("/") + "/fhir",
        },
        "fhirVersion": FHIR_VERSION,
        "format": ["json"],
        "rest": [{
            "mode": "server",
            "documentation": "Authenticated staff-only read/search API. Writes and transactions are not supported. The server uses _offset for paging.",
            "resource": [_capability_resource(item) for item in RESOURCE_TYPES],
        }],
    })


def _normalize_reference(value):
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("Patient/"):
        return value.split("/", 1)[1]
    if value.startswith("urn:uuid:"):
        return value.split("urn:uuid:", 1)[1]
    marker = "/Patient/"
    if marker in value:
        return value.rsplit(marker, 1)[1].split("/", 1)[0]
    return value


def _json_resource(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    raise ValueError("Stored FHIR payload is not JSON.")


def _build_search(resource_type):
    allowed = {"_id", "_count", "_offset", "_summary"}
    if resource_type in PATIENT_SEARCH_TYPES:
        allowed.add("patient")
    if resource_type == "Patient":
        allowed.update({"name", "gender", "birthdate", "identifier"})
    if resource_type in CODE_SEARCH_TYPES:
        allowed.add("code")
    if resource_type in STATUS_SEARCH_TYPES:
        allowed.add("status")
    if resource_type in CLINICAL_STATUS_TYPES:
        allowed.add("clinical-status")
    if resource_type in VERIFICATION_STATUS_TYPES:
        allowed.add("verification-status")
    unknown = sorted(set(request.args.keys()) - allowed)
    if unknown:
        raise ValueError("Unsupported search parameter(s): " + ", ".join(unknown))

    clauses = ["resource_type = %s"]
    params = [resource_type]

    resource_id = request.args.get("_id", "").strip()
    if resource_id:
        clauses.append("resource_id = %s")
        params.append(resource_id)

    patient_id = request.args.get("patient", "").strip()
    if patient_id:
        patient_id = _normalize_reference(patient_id)
        if not patient_id:
            raise ValueError("The patient search parameter must contain a Patient reference or id.")
        clauses.append("patient_fhir_id = %s")
        params.append(patient_id)

    if resource_type == "Patient":
        name = request.args.get("name", "").strip()
        if name:
            clauses.append("JSON_SEARCH(payload, 'one', %s, NULL, '$.name[*].family', '$.name[*].given[*]', '$.name[*].text') IS NOT NULL")
            params.append("%" + name + "%")
        gender = request.args.get("gender", "").strip()
        if gender:
            clauses.append("JSON_UNQUOTE(JSON_EXTRACT(payload, '$.gender')) = %s")
            params.append(gender)
        birthdate = request.args.get("birthdate", "").strip()
        if birthdate:
            clauses.append("JSON_UNQUOTE(JSON_EXTRACT(payload, '$.birthDate')) = %s")
            params.append(birthdate)
        identifier = request.args.get("identifier", "").strip()
        if identifier:
            identifier_parts = identifier.split("|", 1)
            clauses.append("JSON_SEARCH(payload, 'one', %s, NULL, '$.identifier[*].value') IS NOT NULL")
            params.append(identifier_parts[-1])
            if len(identifier_parts) == 2 and identifier_parts[0]:
                clauses.append("JSON_SEARCH(payload, 'one', %s, NULL, '$.identifier[*].system') IS NOT NULL")
                params.append(identifier_parts[0])

    code = request.args.get("code", "").strip()
    if code:
        parts = code.split("|", 1)
        clauses.append("JSON_SEARCH(payload, 'one', %s, NULL, '$.code.coding[*].code', '$.type.coding[*].code', '$.category[*].coding[*].code', '$.category[*].code', '$.medicationCodeableConcept.coding[*].code') IS NOT NULL")
        params.append(parts[-1])
        if len(parts) == 2 and parts[0]:
            clauses.append("JSON_SEARCH(payload, 'one', %s, NULL, '$.code.coding[*].system', '$.type.coding[*].system', '$.category[*].coding[*].system', '$.category[*].system', '$.medicationCodeableConcept.coding[*].system') IS NOT NULL")
            params.append(parts[0])

    status = request.args.get("status", "").strip()
    if status:
        clauses.append("JSON_UNQUOTE(JSON_EXTRACT(payload, '$.status')) = %s")
        params.append(status)

    clinical_status = request.args.get("clinical-status", "").strip()
    if clinical_status:
        clauses.append("JSON_SEARCH(payload, 'one', %s, NULL, '$.clinicalStatus.coding[*].code') IS NOT NULL")
        params.append(clinical_status.split("|", 1)[-1])

    verification_status = request.args.get("verification-status", "").strip()
    if verification_status:
        clauses.append("JSON_SEARCH(payload, 'one', %s, NULL, '$.verificationStatus.coding[*].code') IS NOT NULL")
        params.append(verification_status.split("|", 1)[-1])

    try:
        count = int(request.args.get("_count", "20"))
        offset = int(request.args.get("_offset", "0"))
    except ValueError as exc:
        raise ValueError("_count and _offset must be whole numbers.") from exc
    if count < 1 or count > 100 or offset < 0:
        raise ValueError("_count must be 1–100 and _offset must be zero or greater.")
    summary = request.args.get("_summary", "").lower()
    if summary not in ("", "count"):
        raise ValueError("Only _summary=count is supported.")
    return " AND ".join(clauses), params, count, offset, summary == "count"


@bp.get("/<resource_type>/<resource_id>")
def read_resource(resource_type, resource_id):
    denied = _staff_authorized()
    if denied:
        return denied
    if resource_type not in RESOURCE_TYPES:
        return _outcome(404, "not-found", "The requested FHIR resource type is not supported by this server.")
    try:
        row = fetch_one(
            "SELECT payload FROM fhir_resource WHERE resource_type=%s AND resource_id=%s",
            (resource_type, resource_id),
        )
        if not row:
            return _outcome(404, "not-found", "No resource with that type and id was found.")
        return _fhir_response(_json_resource(row["payload"]))
    except Exception:
        current_app.logger.exception("FHIR resource read failed")
        return _outcome(500, "exception", "The FHIR resource could not be read.")


@bp.get("/<resource_type>")
def search_resources(resource_type):
    denied = _staff_authorized()
    if denied:
        return denied
    if resource_type not in RESOURCE_TYPES:
        return _outcome(404, "not-found", "The requested FHIR resource type is not supported by this server.")
    try:
        where_sql, params, count, offset, count_only = _build_search(resource_type)
        total_row = fetch_one("SELECT COUNT(*) AS total FROM fhir_resource WHERE " + where_sql, tuple(params))
        total = int((total_row or {}).get("total", 0))
        entries = []
        if not count_only:
            rows = fetch_all(
                "SELECT resource_id,payload FROM fhir_resource WHERE " + where_sql
                + " ORDER BY resource_id LIMIT %s OFFSET %s",
                tuple(params) + (count, offset),
            )
            for row in rows:
                resource = _json_resource(row["payload"])
                entries.append({
                    "fullUrl": request.url_root.rstrip("/") + "/fhir/" + resource_type + "/" + row["resource_id"],
                    "resource": resource,
                    "search": {"mode": "match"},
                })
        bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "total": total,
            "link": [{"relation": "self", "url": request.url}],
            "entry": entries,
        }
        if not count_only and offset + len(entries) < total:
            next_args = request.args.to_dict(flat=True)
            next_args["_offset"] = str(offset + count)
            bundle["link"].append({
                "relation": "next",
                "url": request.base_url + "?" + urlencode(next_args),
            })
        return _fhir_response(bundle)
    except ValueError as exc:
        return _outcome(400, "value", str(exc))
    except Exception:
        current_app.logger.exception("FHIR resource search failed")
        return _outcome(500, "exception", "The FHIR search could not be completed.")


def _patient_display(resource):
    names = resource.get("name") or []
    if names:
        name = names[0].get("text")
        if not name:
            name = " ".join((names[0].get("given") or []) + ([names[0]["family"]] if names[0].get("family") else []))
    else:
        name = ""
    address = resource.get("address") or []
    address_text = ""
    if address:
        first = address[0]
        address_text = ", ".join(
            str(part) for part in (
                " ".join(first.get("line") or []),
                first.get("city"),
                first.get("state"),
                first.get("postalCode"),
                first.get("country"),
            ) if part
        )
    return {
        "name": name or "Unnamed synthetic patient",
        "gender": resource.get("gender") or "Not recorded",
        "birth_date": resource.get("birthDate") or "Not recorded",
        "address": address_text,
    }


def _resource_display(resource):
    concept = (
        resource.get("code")
        or resource.get("type")
        or resource.get("medicationCodeableConcept")
        or resource.get("vaccineCode")
        or {}
    )
    display = concept.get("text") if isinstance(concept, dict) else None
    if not display and isinstance(concept, dict):
        codings = concept.get("coding") or []
        if codings:
            display = codings[0].get("display") or codings[0].get("code")
    status = resource.get("status")
    if not status:
        for key in ("clinicalStatus", "verificationStatus"):
            value = resource.get(key) or {}
            codings = value.get("coding") or []
            if codings:
                status = codings[0].get("display") or codings[0].get("code")
                break
    event_date = (
        resource.get("effectiveDateTime")
        or resource.get("issued")
        or resource.get("onsetDateTime")
        or resource.get("recordedDate")
        or resource.get("performedDateTime")
        or resource.get("authoredOn")
        or resource.get("date")
        or ""
    )
    return display or resource.get("resourceType", "FHIR resource"), status or "—", event_date


@bp.get("/explorer")
def explorer():
    """Staff-only browser for the imported, deliberately separate Synthea dataset."""
    if not session.get("login_id"):
        return redirect(url_for("main.login", portal="staff", next=request.path))
    if session.get("role") not in ("chain_admin", "branch_admin", "doctor", "receptionist"):
        abort(403)

    query = request.args.get("q", "").strip()[:120]
    selected_id = request.args.get("patient", "").strip()[:64]
    if query:
        patients = fetch_all(
            """SELECT resource_id,payload
               FROM fhir_resource
               WHERE resource_type='Patient'
                 AND (resource_id=%s OR
                   JSON_SEARCH(payload,'one',%s,NULL,
                     '$.name[*].family','$.name[*].given[*]','$.name[*].text') IS NOT NULL)
               ORDER BY resource_id LIMIT 50""",
            (query, "%" + query + "%"),
        )
    else:
        patients = fetch_all(
            """SELECT resource_id,payload FROM fhir_resource
               WHERE resource_type='Patient' ORDER BY resource_id LIMIT 30"""
        )

    patient_options = []
    for row in patients:
        resource = _json_resource(row["payload"])
        patient_options.append({"id": row["resource_id"], **_patient_display(resource)})

    selected = None
    counts = []
    records = []
    if selected_id:
        selected_row = fetch_one(
            "SELECT payload FROM fhir_resource WHERE resource_type='Patient' AND resource_id=%s",
            (selected_id,),
        )
        if selected_row:
            patient_resource = _json_resource(selected_row["payload"])
            selected = {"id": selected_id, **_patient_display(patient_resource)}
            counts = fetch_all(
                """SELECT resource_type,COUNT(*) AS total
                   FROM fhir_resource
                   WHERE patient_fhir_id=%s AND resource_type<>'Patient'
                   GROUP BY resource_type ORDER BY total DESC,resource_type""",
                (selected_id,),
            )
            rows = fetch_all(
                """SELECT resource_type,resource_id,last_updated,payload
                   FROM fhir_resource
                   WHERE patient_fhir_id=%s AND resource_type<>'Patient'
                   ORDER BY last_updated DESC,resource_type,resource_id LIMIT 50""",
                (selected_id,),
            )
            for row in rows:
                resource = _json_resource(row["payload"])
                label, status, event_date = _resource_display(resource)
                records.append({
                    "resource_type": row["resource_type"],
                    "resource_id": row["resource_id"],
                    "label": label,
                    "status": status,
                    "event_date": event_date,
                    "json": json.dumps(resource, ensure_ascii=False, indent=2),
                })
    elif patient_options:
        # Show the first search result's demographics without implicitly loading
        # the entire clinical history; selection is an explicit staff action.
        selected_id = patient_options[0]["id"]

    return render_template(
        "fhir_explorer.html", query=query, patients=patient_options,
        selected=selected, selected_id=selected_id,
        counts=counts, records=records,
    )
