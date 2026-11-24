# FHIR relational extension

The integrated ER diagram at `docs/AIIMS_Connect_Integrated_ER_Diagram.png` shows the complete operational and FHIR data model. FHIR is the standardized clinical-history layer; operational hospital transactions remain in their existing entities.

```mermaid
erDiagram
    PATIENT ||--o| FHIR_PATIENT_LINK : "optional verified link"
    FHIR_PATIENT ||--o| FHIR_PATIENT_LINK : "may be linked"
    FHIR_PATIENT ||--o{ FHIR_ENCOUNTER : has
    FHIR_PATIENT ||--o{ FHIR_OBSERVATION : has
    FHIR_PATIENT ||--o{ FHIR_CONDITION : has
    FHIR_PATIENT ||--o{ FHIR_PROCEDURE : has
    FHIR_PATIENT ||--o{ FHIR_MEDICATION_REQUEST : has

    PATIENT {
      char UHID PK
      varchar Name
    }
    FHIR_PATIENT {
      varchar fhir_patient_id PK
      varchar full_name
      date birth_date
      varchar gender
      json raw_resource
    }
    FHIR_PATIENT_LINK {
      varchar fhir_patient_id PK,FK
      char UHID FK,UK
      varchar link_status
    }
    FHIR_ENCOUNTER {
      varchar fhir_encounter_id PK
      varchar fhir_patient_id FK
      varchar status
      datetime period_start
    }
    FHIR_OBSERVATION {
      varchar fhir_observation_id PK
      varchar fhir_patient_id FK
      varchar code
      decimal value_numeric
      varchar value_unit
    }
    FHIR_CONDITION {
      varchar fhir_condition_id PK
      varchar fhir_patient_id FK
      varchar code
      varchar clinical_status_code
    }
    FHIR_PROCEDURE {
      varchar fhir_procedure_id PK
      varchar fhir_patient_id FK
      varchar code
      varchar status
    }
    FHIR_MEDICATION_REQUEST {
      varchar fhir_medication_request_id PK
      varchar fhir_patient_id FK
      varchar medication_display
      varchar status
    }
```

## Safeguards

- FHIR logical IDs and AIIMS UHIDs remain distinct.
- `fhir_patient_link` is the only bridge to `patient.UHID`. It starts unlinked;
  linking must be a verified/manual action. The sync never matches patients by name.
- FHIR Encounters are historical clinical visits, not appointment slots.
- FHIR MedicationRequests are source medication orders, not local prescription transactions.
- The selected relational rows keep their original JSON payload. All other imported
  FHIR resource types remain available in the lossless `fhir_resource` archive.
- Sync is repeatable: each projection is upserted by its FHIR resource logical ID.


## Unified patient clinical timeline

The staff patient registry and patient portal open `/clinical/patients/<UHID>/history`. This view combines appointments, admissions, prescriptions, referrals and bills from the operational schema with linked FHIR Encounters, Observations, Conditions, Procedures and MedicationRequests. The FHIR identity link is manually verified, one-to-one and reversible. Doctors can view only patients with an existing appointment assignment; patient users can view only their own UHID. FHIR source rows remain read-only in this workflow.
