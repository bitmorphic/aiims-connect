-- Additive FHIR R4 relational layer. Existing operational ER diagram and tables are unchanged.
-- Patient IDs from FHIR are NOT AIIMS UHIDs. A verified, optional mapping is stored separately.

CREATE TABLE IF NOT EXISTS fhir_patient (
  fhir_patient_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  full_name VARCHAR(255) DEFAULT NULL,
  birth_date DATE DEFAULT NULL,
  gender VARCHAR(32) DEFAULT NULL,
  phone VARCHAR(64) DEFAULT NULL,
  email VARCHAR(254) DEFAULT NULL,
  raw_resource JSON NOT NULL,
  synced_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (fhir_patient_id),
  KEY idx_fhir_patient_name (full_name),
  KEY idx_fhir_patient_birth_date (birth_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Relational projection of the original FHIR Patient resource';

CREATE TABLE IF NOT EXISTS fhir_patient_link (
  fhir_patient_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  UHID CHAR(10) DEFAULT NULL,
  link_status VARCHAR(12) NOT NULL DEFAULT 'unlinked',
  link_note VARCHAR(255) DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (fhir_patient_id),
  UNIQUE KEY uq_fhir_patient_link_uhid (UHID),
  CONSTRAINT fk_fhir_patient_link_patient FOREIGN KEY (fhir_patient_id)
    REFERENCES fhir_patient (fhir_patient_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_fhir_patient_link_uhid FOREIGN KEY (UHID)
    REFERENCES patient (UHID) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_fhir_patient_link_status CHECK (
    (link_status='unlinked' AND UHID IS NULL) OR
    (link_status='linked' AND UHID IS NOT NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Manual, auditable link between FHIR Patient and operational AIIMS UHID';

CREATE TABLE IF NOT EXISTS fhir_encounter (
  fhir_encounter_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  fhir_patient_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  status VARCHAR(32) DEFAULT NULL,
  class_code VARCHAR(64) DEFAULT NULL,
  class_display VARCHAR(255) DEFAULT NULL,
  type_display VARCHAR(255) DEFAULT NULL,
  period_start DATETIME(6) DEFAULT NULL,
  period_end DATETIME(6) DEFAULT NULL,
  raw_resource JSON NOT NULL,
  synced_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (fhir_encounter_id),
  KEY idx_fhir_encounter_patient_date (fhir_patient_id,period_start),
  CONSTRAINT fk_fhir_encounter_patient FOREIGN KEY (fhir_patient_id)
    REFERENCES fhir_patient (fhir_patient_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Historical FHIR encounters, not bookable OPD appointments';

CREATE TABLE IF NOT EXISTS fhir_observation (
  fhir_observation_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  fhir_patient_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  fhir_encounter_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  status VARCHAR(32) DEFAULT NULL,
  code_system VARCHAR(255) DEFAULT NULL,
  code VARCHAR(64) DEFAULT NULL,
  code_display VARCHAR(255) DEFAULT NULL,
  effective_at DATETIME(6) DEFAULT NULL,
  value_numeric DECIMAL(24,8) DEFAULT NULL,
  value_text TEXT DEFAULT NULL,
  value_unit VARCHAR(64) DEFAULT NULL,
  raw_resource JSON NOT NULL,
  synced_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (fhir_observation_id),
  KEY idx_fhir_observation_patient_date (fhir_patient_id,effective_at),
  KEY idx_fhir_observation_code (code),
  CONSTRAINT fk_fhir_observation_patient FOREIGN KEY (fhir_patient_id)
    REFERENCES fhir_patient (fhir_patient_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Normalized FHIR measurements and observation results';

CREATE TABLE IF NOT EXISTS fhir_condition (
  fhir_condition_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  fhir_patient_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  fhir_encounter_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  clinical_status_code VARCHAR(64) DEFAULT NULL,
  verification_status_code VARCHAR(64) DEFAULT NULL,
  code_system VARCHAR(255) DEFAULT NULL,
  code VARCHAR(64) DEFAULT NULL,
  code_display VARCHAR(255) DEFAULT NULL,
  onset_at DATETIME(6) DEFAULT NULL,
  recorded_date DATE DEFAULT NULL,
  raw_resource JSON NOT NULL,
  synced_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (fhir_condition_id),
  KEY idx_fhir_condition_patient (fhir_patient_id,clinical_status_code),
  KEY idx_fhir_condition_code (code),
  CONSTRAINT fk_fhir_condition_patient FOREIGN KEY (fhir_patient_id)
    REFERENCES fhir_patient (fhir_patient_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Normalized FHIR diagnoses and clinical conditions';

CREATE TABLE IF NOT EXISTS fhir_procedure (
  fhir_procedure_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  fhir_patient_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  fhir_encounter_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  status VARCHAR(32) DEFAULT NULL,
  code_system VARCHAR(255) DEFAULT NULL,
  code VARCHAR(64) DEFAULT NULL,
  code_display VARCHAR(255) DEFAULT NULL,
  performed_start DATETIME(6) DEFAULT NULL,
  performed_end DATETIME(6) DEFAULT NULL,
  raw_resource JSON NOT NULL,
  synced_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (fhir_procedure_id),
  KEY idx_fhir_procedure_patient_date (fhir_patient_id,performed_start),
  CONSTRAINT fk_fhir_procedure_patient FOREIGN KEY (fhir_patient_id)
    REFERENCES fhir_patient (fhir_patient_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Normalized FHIR procedure history';

CREATE TABLE IF NOT EXISTS fhir_medication_request (
  fhir_medication_request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  fhir_patient_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  fhir_encounter_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  status VARCHAR(32) DEFAULT NULL,
  intent VARCHAR(32) DEFAULT NULL,
  medication_display VARCHAR(255) DEFAULT NULL,
  authored_on DATE DEFAULT NULL,
  dosage_text TEXT DEFAULT NULL,
  raw_resource JSON NOT NULL,
  synced_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (fhir_medication_request_id),
  KEY idx_fhir_medication_patient_date (fhir_patient_id,authored_on),
  CONSTRAINT fk_fhir_medication_patient FOREIGN KEY (fhir_patient_id)
    REFERENCES fhir_patient (fhir_patient_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Normalized FHIR medication requests; not local AIIMS prescriptions';

SELECT TABLE_NAME,ENGINE
FROM information_schema.TABLES
WHERE TABLE_SCHEMA=DATABASE()
AND TABLE_NAME IN ('fhir_patient','fhir_patient_link','fhir_encounter','fhir_observation',
                   'fhir_condition','fhir_procedure','fhir_medication_request')
ORDER BY TABLE_NAME;
