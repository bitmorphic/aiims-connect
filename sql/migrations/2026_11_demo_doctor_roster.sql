-- AIIMS Connect: curated synthetic doctor roster for academic demonstrations.
-- These are fictional doctors, NOT real AIIMS clinicians.
-- Idempotent: safe to re-run. Does not modify existing staff, doctors or appointments.
-- Run after the operational schema and branch/department master data are installed.

INSERT INTO staff (Branch_ID, Name, DOB, Phone, Staff_Type)
SELECT b.Branch_ID, r.Name, r.DOB, r.Phone, 'Doctor'
FROM branch b
JOIN (
    SELECT 'AIIMS Connect - New Delhi (Main)' AS Branch_Name,
           'Demo Dr. Aditi Sharma' AS Name, DATE('1982-04-12') AS DOB,
           '9000000101' AS Phone
    UNION ALL
    SELECT 'AIIMS Connect - New Delhi (Main)',
           'Demo Dr. Kabir Mehta', DATE('1978-07-22'), '9000000102'
    UNION ALL
    SELECT 'AIIMS Connect - New Delhi (Main)',
           'Demo Dr. Rohan Verma', DATE('1984-01-15'), '9000000103'
    UNION ALL
    SELECT 'AIIMS Connect - Jodhpur',
           'Demo Dr. Meera Rathore', DATE('1981-08-09'), '9000000104'
    UNION ALL
    SELECT 'AIIMS Connect - Bhopal',
           'Demo Dr. Arjun Nair', DATE('1980-03-18'), '9000000105'
) AS r ON r.Branch_Name = b.Branch_Name
WHERE NOT EXISTS (
    SELECT 1
    FROM staff existing
    WHERE existing.Branch_ID = b.Branch_ID
      AND existing.Staff_Type = 'Doctor'
      AND existing.Name = r.Name
);

INSERT INTO doctor
    (Staff_ID, Staff_Type, Dept_ID, Specialization, Qualification, Consultation_Fee)
SELECT s.Staff_ID, 'Doctor', d.Dept_ID, r.Specialization, r.Qualification, r.Consultation_Fee
FROM branch b
JOIN (
    SELECT 'AIIMS Connect - New Delhi (Main)' AS Branch_Name,
           'Demo Dr. Aditi Sharma' AS Name, 'General Medicine' AS Dept_Name,
           'General Medicine' AS Specialization,
           'MBBS, MD (General Medicine)' AS Qualification, 650.00 AS Consultation_Fee
    UNION ALL
    SELECT 'AIIMS Connect - New Delhi (Main)',
           'Demo Dr. Kabir Mehta', 'Cardiology', 'Cardiology',
           'MBBS, DM (Cardiology)', 900.00
    UNION ALL
    SELECT 'AIIMS Connect - New Delhi (Main)',
           'Demo Dr. Rohan Verma', 'Orthopaedics', 'Orthopaedics',
           'MBBS, MS (Orthopaedics)', 750.00
    UNION ALL
    SELECT 'AIIMS Connect - Jodhpur',
           'Demo Dr. Meera Rathore', 'General Medicine', 'General Medicine',
           'MBBS, MD (General Medicine)', 600.00
    UNION ALL
    SELECT 'AIIMS Connect - Bhopal',
           'Demo Dr. Arjun Nair', 'Cardiology', 'Cardiology',
           'MBBS, DM (Cardiology)', 850.00
) AS r ON r.Branch_Name = b.Branch_Name
JOIN staff s
  ON s.Branch_ID = b.Branch_ID
 AND s.Staff_Type = 'Doctor'
 AND s.Name = r.Name
JOIN department d
  ON d.Branch_ID = b.Branch_ID
 AND d.Dept_Name = r.Dept_Name
WHERE NOT EXISTS (
    SELECT 1 FROM doctor existing WHERE existing.Staff_ID = s.Staff_ID
);

-- Verification: 5 demo doctors across all 3 branches, unless some exact rows
-- already existed before this migration.
SELECT b.Branch_Name, COUNT(d.Staff_ID) AS Doctor_Count
FROM branch b
LEFT JOIN staff s ON s.Branch_ID = b.Branch_ID AND s.Staff_Type = 'Doctor'
LEFT JOIN doctor d ON d.Staff_ID = s.Staff_ID
GROUP BY b.Branch_ID, b.Branch_Name
ORDER BY b.Branch_Name;
