-- AIIMS Connect: patient self-service appointment approval workflow
-- Run ONCE against the existing Railway database before deploying this application version.
-- Safe for existing appointments: Scheduled/Completed/Cancelled values remain valid.
-- This migration does not create, delete, or modify any patient or appointment rows.

ALTER TABLE appointment
    DROP CHECK chk_appt_status;

ALTER TABLE appointment
    ADD CONSTRAINT chk_appt_status
    CHECK (Status IN ('Pending Approval', 'Scheduled', 'Completed', 'Cancelled'));

-- Verification
SELECT CONSTRAINT_NAME, CHECK_CLAUSE
FROM information_schema.CHECK_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = DATABASE()
  AND CONSTRAINT_NAME = 'chk_appt_status';

SELECT Status, COUNT(*) AS Appointment_Count
FROM appointment
GROUP BY Status
ORDER BY Status;
