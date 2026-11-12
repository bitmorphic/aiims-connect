# Database design
15 entities: BRANCH, DEPARTMENT, WARD, LOGIN, STAFF, DOCTOR, RECEPTIONIST, ADMIN_STAFF, PATIENT, APPOINTMENT, PRESCRIPTION, ADMISSION, BILLING, REFERRAL, AUDIT_LOG.

Branch has many departments, wards and staff. Login links to staff or patient. Staff specializes into Doctor, Receptionist and Admin Staff. Patient has many appointments, admissions and referrals. Appointment has prescriptions. Admission has at most one bill. Referral links source/destination branches and an optional accepted appointment.

UHID is chain-wide. Appointment.Branch_ID is its care location. Baseline design assigns each doctor to one branch. Ward.Available_Beds is trigger-maintained; Billing.Total and Appointment.Active_Flag are generated. MySQL does not natively enforce total/disjoint specialization across subtype tables; provisioning and application logic must enforce it.
