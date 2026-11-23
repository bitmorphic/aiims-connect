-- AIIMS Connect: FHIR R4 interoperability storage
-- Apply once to the existing Railway database before deploying the FHIR API.
-- These tables are isolated from operational patient, appointment and billing tables.
-- The imported Synthea data is synthetic and is not mapped to AIIMS UHIDs.

CREATE TABLE IF NOT EXISTS fhir_import_batch (
    batch_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_filename VARCHAR(255) NOT NULL,
    source_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'running',
    resource_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    patient_count INT UNSIGNED NOT NULL DEFAULT 0,
    bundle_count INT UNSIGNED NOT NULL DEFAULT 0,
    error_message TEXT DEFAULT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME DEFAULT NULL,
    PRIMARY KEY (batch_id),
    UNIQUE KEY uq_fhir_batch_sha256 (source_sha256),
    CONSTRAINT chk_fhir_batch_status CHECK (status IN ('running','completed','failed'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Idempotent imports of synthetic or approved FHIR datasets';

CREATE TABLE IF NOT EXISTS fhir_resource (
    resource_type VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    resource_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    patient_fhir_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
    version_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
    last_updated DATETIME(6) DEFAULT NULL,
    payload JSON NOT NULL,
    source_bundle VARCHAR(255) DEFAULT NULL,
    import_batch_id BIGINT UNSIGNED DEFAULT NULL,
    imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (resource_type, resource_id),
    KEY idx_fhir_patient_resource (patient_fhir_id, resource_type, resource_id),
    KEY idx_fhir_resource_updated (resource_type, last_updated),
    KEY idx_fhir_import_batch (import_batch_id),
    CONSTRAINT fk_fhir_resource_batch FOREIGN KEY (import_batch_id)
        REFERENCES fhir_import_batch (batch_id) ON DELETE SET NULL ON UPDATE RESTRICT,
    CONSTRAINT chk_fhir_resource_type CHECK (CHAR_LENGTH(TRIM(resource_type)) > 0),
    CONSTRAINT chk_fhir_resource_id CHECK (CHAR_LENGTH(TRIM(resource_id)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='FHIR R4 resources stored as original JSON with patient-compartment index';

-- Verification: both tables should appear below.
SELECT TABLE_NAME, ENGINE
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('fhir_import_batch', 'fhir_resource')
ORDER BY TABLE_NAME;
