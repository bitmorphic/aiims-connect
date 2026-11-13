-- AIIMS Connect database schema (MySQL 8.4 compatible)
-- Portable bootstrap for a NEW, EMPTY database. Select the target schema in MySQL Workbench
-- before executing this file. Do not run it against a database containing existing data.
-- Inventory: 15 tables, 14 triggers, 11 stored procedures and 7 views.
-- No patient, account, appointment, prescription, admission or billing rows are included.
-- Trigger and procedure table references use lower-case names for Linux MySQL compatibility.
-- The importing MySQL account becomes the definer for views and stored programs.

SET NAMES utf8mb4;

SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE `branch` (
  `Branch_ID` int unsigned NOT NULL AUTO_INCREMENT,
  `Branch_Name` varchar(100) NOT NULL,
  `City` varchar(60) NOT NULL,
  `Is_Main` tinyint(1) NOT NULL DEFAULT '0',
  `Created_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`Branch_ID`),
  UNIQUE KEY `uq_branch_name` (`Branch_Name`),
  CONSTRAINT `chk_branch_is_main` CHECK ((`Is_Main` in (0,1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Hospital branches in the AIIMS Connect chain';

CREATE TABLE `patient` (
  `UHID` char(10) NOT NULL,
  `Name` varchar(100) NOT NULL,
  `DOB` date NOT NULL,
  `Gender` varchar(10) NOT NULL,
  `Blood_Group` varchar(5) DEFAULT NULL,
  `Phone` varchar(15) NOT NULL,
  `Address` varchar(255) NOT NULL,
  `Created_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`UHID`),
  KEY `idx_patient_name` (`Name`),
  KEY `idx_patient_phone` (`Phone`),
  CONSTRAINT `chk_patient_blood` CHECK (((`Blood_Group` is null) or (`Blood_Group` in (_utf8mb4'A+',_utf8mb4'A-',_utf8mb4'B+',_utf8mb4'B-',_utf8mb4'AB+',_utf8mb4'AB-',_utf8mb4'O+',_utf8mb4'O-')))),
  CONSTRAINT `chk_patient_dob` CHECK ((`DOB` > _utf8mb4'1900-01-01')),
  CONSTRAINT `chk_patient_gender` CHECK ((`Gender` in (_utf8mb4'Male',_utf8mb4'Female',_utf8mb4'Other'))),
  CONSTRAINT `chk_patient_phone` CHECK (regexp_like(`Phone`,_utf8mb4'^[0-9+ -]{8,15}$')),
  CONSTRAINT `chk_uhid_format` CHECK (regexp_like(`UHID`,_utf8mb4'^AIC[0-9]{7}$'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Central patient registry;

CREATE TABLE `staff` (
  `Staff_ID` int unsigned NOT NULL AUTO_INCREMENT,
  `Branch_ID` int unsigned NOT NULL,
  `Name` varchar(100) NOT NULL,
  `DOB` date NOT NULL,
  `Phone` varchar(15) NOT NULL,
  `Staff_Type` varchar(15) NOT NULL,
  `Created_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`Staff_ID`),
  UNIQUE KEY `uq_staff_id_type` (`Staff_ID`,`Staff_Type`),
  KEY `idx_staff_branch_type` (`Branch_ID`,`Staff_Type`),
  CONSTRAINT `chk_staff_dob` CHECK ((`DOB` > _utf8mb4'1930-01-01')),
  CONSTRAINT `chk_staff_phone` CHECK (regexp_like(`Phone`,_utf8mb4'^[0-9+ -]{8,15}$')),
  CONSTRAINT `chk_staff_type` CHECK ((`Staff_Type` in (_utf8mb4'Doctor',_utf8mb4'Receptionist',_utf8mb4'Admin')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Staff superclass;

CREATE TABLE `admin_staff` (
  `Staff_ID` int unsigned NOT NULL,
  `Staff_Type` varchar(15) NOT NULL DEFAULT 'Admin',
  `Access_Level` varchar(10) NOT NULL,
  PRIMARY KEY (`Staff_ID`),
  KEY `fk_admstaff_staff` (`Staff_ID`,`Staff_Type`),
  CONSTRAINT `fk_admstaff_staff` FOREIGN KEY (`Staff_ID`, `Staff_Type`) REFERENCES `staff` (`Staff_ID`, `Staff_Type`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_admstaff_level` CHECK ((`Access_Level` in (_utf8mb4'Chain',_utf8mb4'Branch'))),
  CONSTRAINT `chk_admstaff_type` CHECK ((`Staff_Type` = _utf8mb4'Admin'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Administrative staff subclass;

CREATE TABLE `department` (
  `Dept_ID` int unsigned NOT NULL AUTO_INCREMENT,
  `Branch_ID` int unsigned NOT NULL,
  `Dept_Name` varchar(100) NOT NULL,
  PRIMARY KEY (`Dept_ID`),
  UNIQUE KEY `uq_dept_branch_name` (`Branch_ID`,`Dept_Name`),
  CONSTRAINT `fk_dept_branch` FOREIGN KEY (`Branch_ID`) REFERENCES `branch` (`Branch_ID`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Clinical departments, owned per branch';

CREATE TABLE `login` (
  `Login_ID` int unsigned NOT NULL AUTO_INCREMENT,
  `Username` varchar(50) NOT NULL,
  `Password_Hash` varchar(255) NOT NULL,
  `Role` varchar(20) NOT NULL,
  `Is_Active` tinyint(1) NOT NULL DEFAULT '1',
  `Staff_ID` int unsigned DEFAULT NULL,
  `Patient_UHID` char(10) DEFAULT NULL,
  `Created_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`Login_ID`),
  UNIQUE KEY `uq_login_username` (`Username`),
  UNIQUE KEY `uq_login_staff` (`Staff_ID`),
  UNIQUE KEY `uq_login_patient` (`Patient_UHID`),
  CONSTRAINT `fk_login_patient` FOREIGN KEY (`Patient_UHID`) REFERENCES `patient` (`UHID`),
  CONSTRAINT `fk_login_staff` FOREIGN KEY (`Staff_ID`) REFERENCES `staff` (`Staff_ID`),
  CONSTRAINT `chk_login_hash` CHECK ((char_length(`Password_Hash`) = 60)),
  CONSTRAINT `chk_login_owner` CHECK ((((`Staff_ID` is not null) and (`Patient_UHID` is null)) or ((`Staff_ID` is null) and (`Patient_UHID` is not null)))),
  CONSTRAINT `chk_login_role` CHECK ((`Role` in (_utf8mb4'Patient',_utf8mb4'Doctor',_utf8mb4'Receptionist',_utf8mb4'Admin')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Login identities for staff and patients;

CREATE TABLE `receptionist` (
  `Staff_ID` int unsigned NOT NULL,
  `Staff_Type` varchar(15) NOT NULL DEFAULT 'Receptionist',
  `Counter_No` int unsigned NOT NULL,
  PRIMARY KEY (`Staff_ID`),
  KEY `fk_rec_staff` (`Staff_ID`,`Staff_Type`),
  CONSTRAINT `fk_rec_staff` FOREIGN KEY (`Staff_ID`, `Staff_Type`) REFERENCES `staff` (`Staff_ID`, `Staff_Type`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_rec_type` CHECK ((`Staff_Type` = _utf8mb4'Receptionist'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Receptionist subclass of STAFF';

CREATE TABLE `ward` (
  `Ward_ID` int unsigned NOT NULL AUTO_INCREMENT,
  `Branch_ID` int unsigned NOT NULL,
  `Ward_Name` varchar(80) NOT NULL,
  `Ward_Type` varchar(20) NOT NULL,
  `Total_Beds` int unsigned NOT NULL,
  `Available_Beds` int unsigned NOT NULL,
  `Daily_Rate` decimal(10,2) NOT NULL,
  PRIMARY KEY (`Ward_ID`),
  UNIQUE KEY `uq_ward_branch_name` (`Branch_ID`,`Ward_Name`),
  CONSTRAINT `fk_ward_branch` FOREIGN KEY (`Branch_ID`) REFERENCES `branch` (`Branch_ID`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_ward_beds` CHECK (((`Available_Beds` >= 0) and (`Available_Beds` <= `Total_Beds`))),
  CONSTRAINT `chk_ward_rate` CHECK ((`Daily_Rate` >= 0)),
  CONSTRAINT `chk_ward_total` CHECK ((`Total_Beds` > 0)),
  CONSTRAINT `chk_ward_type` CHECK ((`Ward_Type` in (_utf8mb4'General',_utf8mb4'Semi-Private',_utf8mb4'Private',_utf8mb4'ICU')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Wards/ICUs per branch;

CREATE TABLE `admission` (
  `Admission_ID` int unsigned NOT NULL AUTO_INCREMENT,
  `Patient_UHID` char(10) NOT NULL,
  `Ward_ID` int unsigned NOT NULL,
  `Admit_Date` datetime NOT NULL,
  `Discharge_Date` datetime DEFAULT NULL,
  `Attendant_Name` varchar(100) NOT NULL,
  `Attendant_Phone` varchar(15) NOT NULL,
  `Active_Patient_Key` char(10) GENERATED ALWAYS AS (if((`Discharge_Date` is null),`Patient_UHID`,NULL)) STORED,
  PRIMARY KEY (`Admission_ID`),
  UNIQUE KEY `uq_adm_active_patient` (`Active_Patient_Key`),
  KEY `fk_adm_patient` (`Patient_UHID`),
  KEY `idx_adm_ward_discharge` (`Ward_ID`,`Discharge_Date`),
  CONSTRAINT `fk_adm_patient` FOREIGN KEY (`Patient_UHID`) REFERENCES `patient` (`UHID`),
  CONSTRAINT `fk_adm_ward` FOREIGN KEY (`Ward_ID`) REFERENCES `ward` (`Ward_ID`),
  CONSTRAINT `chk_adm_attendant` CHECK ((char_length(trim(`Attendant_Name`)) > 0)),
  CONSTRAINT `chk_adm_dates` CHECK (((`Discharge_Date` is null) or (`Discharge_Date` >= `Admit_Date`))),
  CONSTRAINT `chk_adm_phone` CHECK (regexp_like(`Attendant_Phone`,_utf8mb4'^[0-9+ -]{8,15}$'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='IPD admissions;

CREATE TABLE `audit_log` (
  `Log_ID` bigint unsigned NOT NULL AUTO_INCREMENT,
  `Actor_Login_ID` int unsigned DEFAULT NULL,
  `Table_Affected` varchar(20) NOT NULL,
  `Record_ID` varchar(30) NOT NULL,
  `Action` varchar(15) NOT NULL,
  `Logged_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`Log_ID`),
  KEY `fk_audit_actor` (`Actor_Login_ID`),
  KEY `idx_audit_table_record` (`Table_Affected`,`Record_ID`),
  KEY `idx_audit_logged_at` (`Logged_At`),
  CONSTRAINT `fk_audit_actor` FOREIGN KEY (`Actor_Login_ID`) REFERENCES `login` (`Login_ID`),
  CONSTRAINT `chk_audit_action` CHECK ((`Action` in (_utf8mb4'INSERT',_utf8mb4'UPDATE',_utf8mb4'DISCHARGE'))),
  CONSTRAINT `chk_audit_table` CHECK ((`Table_Affected` in (_utf8mb4'PRESCRIPTION',_utf8mb4'BILLING',_utf8mb4'REFERRAL',_utf8mb4'ADMISSION')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Audit trail for Prescription/Billing/Referral/Discharge changes';

CREATE TABLE `doctor` (
  `Staff_ID` int unsigned NOT NULL,
  `Staff_Type` varchar(15) NOT NULL DEFAULT 'Doctor',
  `Dept_ID` int unsigned NOT NULL,
  `Specialization` varchar(80) NOT NULL,
  `Qualification` varchar(80) NOT NULL,
  `Consultation_Fee` decimal(10,2) NOT NULL,
  PRIMARY KEY (`Staff_ID`),
  KEY `fk_doc_staff` (`Staff_ID`,`Staff_Type`),
  KEY `fk_doc_dept` (`Dept_ID`),
  CONSTRAINT `fk_doc_dept` FOREIGN KEY (`Dept_ID`) REFERENCES `department` (`Dept_ID`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_doc_staff` FOREIGN KEY (`Staff_ID`, `Staff_Type`) REFERENCES `staff` (`Staff_ID`, `Staff_Type`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_doc_fee` CHECK ((`Consultation_Fee` >= 0)),
  CONSTRAINT `chk_doc_type` CHECK ((`Staff_Type` = _utf8mb4'Doctor'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Doctor subclass of STAFF';

CREATE TABLE `billing` (
  `Bill_ID` int unsigned NOT NULL AUTO_INCREMENT,
  `Admission_ID` int unsigned NOT NULL,
  `Consultation_Fee` decimal(10,2) NOT NULL DEFAULT '0.00',
  `Room_Charges` decimal(10,2) NOT NULL DEFAULT '0.00',
  `Medicine_Charges` decimal(10,2) NOT NULL DEFAULT '0.00',
  `Total` decimal(12,2) GENERATED ALWAYS AS (((`Consultation_Fee` + `Room_Charges`) + `Medicine_Charges`)) STORED,
  `Status` varchar(10) NOT NULL DEFAULT 'Unpaid',
  `Generated_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Paid_At` datetime DEFAULT NULL,
  PRIMARY KEY (`Bill_ID`),
  UNIQUE KEY `uq_bill_admission` (`Admission_ID`),
  KEY `idx_bill_status` (`Status`),
  CONSTRAINT `fk_bill_admission` FOREIGN KEY (`Admission_ID`) REFERENCES `admission` (`Admission_ID`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_bill_amounts` CHECK (((`Consultation_Fee` >= 0) and (`Room_Charges` >= 0) and (`Medicine_Charges` >= 0))),
  CONSTRAINT `chk_bill_paid_at` CHECK ((((`Status` = _utf8mb4'Paid') and (`Paid_At` is not null)) or ((`Status` = _utf8mb4'Unpaid') and (`Paid_At` is null)))),
  CONSTRAINT `chk_bill_status` CHECK ((`Status` in (_utf8mb4'Unpaid',_utf8mb4'Paid')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Discharge bills;

CREATE TABLE `referral` (
  `Referral_ID` int unsigned NOT NULL AUTO_INCREMENT,
  `Patient_UHID` char(10) NOT NULL,
  `Initiator_Staff_ID` int unsigned NOT NULL,
  `Source_Branch_ID` int unsigned NOT NULL,
  `Dest_Branch_ID` int unsigned NOT NULL,
  `Reason` varchar(255) NOT NULL,
  `Status` varchar(15) NOT NULL DEFAULT 'Pending',
  `Created_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Updated_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`Referral_ID`),
  KEY `fk_ref_patient` (`Patient_UHID`),
  KEY `fk_ref_initiator` (`Initiator_Staff_ID`),
  KEY `idx_ref_dest_status` (`Dest_Branch_ID`,`Status`),
  KEY `idx_ref_source` (`Source_Branch_ID`),
  CONSTRAINT `fk_ref_dest` FOREIGN KEY (`Dest_Branch_ID`) REFERENCES `branch` (`Branch_ID`),
  CONSTRAINT `fk_ref_initiator` FOREIGN KEY (`Initiator_Staff_ID`) REFERENCES `doctor` (`Staff_ID`),
  CONSTRAINT `fk_ref_patient` FOREIGN KEY (`Patient_UHID`) REFERENCES `patient` (`UHID`),
  CONSTRAINT `fk_ref_source` FOREIGN KEY (`Source_Branch_ID`) REFERENCES `branch` (`Branch_ID`),
  CONSTRAINT `chk_ref_distinct_branches` CHECK ((`Source_Branch_ID` <> `Dest_Branch_ID`)),
  CONSTRAINT `chk_ref_reason` CHECK ((char_length(trim(`Reason`)) > 0)),
  CONSTRAINT `chk_ref_status` CHECK ((`Status` in (_utf8mb4'Pending',_utf8mb4'Accepted',_utf8mb4'Rejected',_utf8mb4'Completed')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Inter-branch patient referrals';

CREATE TABLE `appointment` (
  `Appt_ID` int unsigned NOT NULL AUTO_INCREMENT,
  `Patient_UHID` char(10) NOT NULL,
  `Doctor_ID` int unsigned NOT NULL,
  `Branch_ID` int unsigned NOT NULL,
  `Appt_Date` date NOT NULL,
  `Time_Slot` time NOT NULL,
  `Token_No` int unsigned NOT NULL,
  `Status` varchar(15) NOT NULL DEFAULT 'Scheduled',
  `Referral_ID` int unsigned DEFAULT NULL,
  `Created_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Slot_Key` varchar(64) GENERATED ALWAYS AS (if((`Status` = _utf8mb4'Cancelled'),NULL,concat_ws(_utf8mb4'|',`Doctor_ID`,`Appt_Date`,`Time_Slot`))) STORED,
  `Token_Key` varchar(64) GENERATED ALWAYS AS (if((`Status` = _utf8mb4'Cancelled'),NULL,concat_ws(_utf8mb4'|',`Doctor_ID`,`Appt_Date`,`Token_No`))) STORED,
  PRIMARY KEY (`Appt_ID`),
  UNIQUE KEY `uq_appt_referral` (`Referral_ID`),
  UNIQUE KEY `uq_appt_slot` (`Slot_Key`),
  UNIQUE KEY `uq_appt_token` (`Token_Key`),
  KEY `idx_appt_doctor_date` (`Doctor_ID`,`Appt_Date`),
  KEY `idx_appt_branch_date` (`Branch_ID`,`Appt_Date`),
  KEY `idx_appt_patient_date` (`Patient_UHID`,`Appt_Date`),
  CONSTRAINT `fk_appt_branch` FOREIGN KEY (`Branch_ID`) REFERENCES `branch` (`Branch_ID`),
  CONSTRAINT `fk_appt_doctor` FOREIGN KEY (`Doctor_ID`) REFERENCES `doctor` (`Staff_ID`),
  CONSTRAINT `fk_appt_patient` FOREIGN KEY (`Patient_UHID`) REFERENCES `patient` (`UHID`),
  CONSTRAINT `fk_appt_referral` FOREIGN KEY (`Referral_ID`) REFERENCES `referral` (`Referral_ID`),
  CONSTRAINT `chk_appt_slot_grid` CHECK ((((`Time_Slot` between '09:00:00' and '12:30:00') or (`Time_Slot` between '14:00:00' and '16:30:00')) and ((minute(`Time_Slot`) % 30) = 0) and (second(`Time_Slot`) = 0))),
  CONSTRAINT `chk_appt_status` CHECK ((`Status` in (_utf8mb4'Scheduled',_utf8mb4'Completed',_utf8mb4'Cancelled'))),
  CONSTRAINT `chk_appt_token` CHECK ((`Token_No` between 1 and 200))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='OPD appointments;

CREATE TABLE `prescription` (
  `Prescription_ID` int unsigned NOT NULL AUTO_INCREMENT,
  `Appt_ID` int unsigned NOT NULL,
  `Medicine_Name` varchar(120) NOT NULL,
  `Dosage` varchar(60) NOT NULL,
  `Notes` varchar(255) DEFAULT NULL,
  `Created_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Updated_At` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`Prescription_ID`),
  KEY `idx_rx_appt` (`Appt_ID`),
  CONSTRAINT `fk_rx_appt` FOREIGN KEY (`Appt_ID`) REFERENCES `appointment` (`Appt_ID`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `chk_rx_dosage` CHECK ((char_length(trim(`Dosage`)) > 0)),
  CONSTRAINT `chk_rx_medicine` CHECK ((char_length(trim(`Medicine_Name`)) > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Prescription medicine lines per appointment';

capacity-based allocation';



SET FOREIGN_KEY_CHECKS = 1;

DELIMITER $$

CREATE TRIGGER `trg_admission_capacity_bi` BEFORE INSERT ON `admission` FOR EACH ROW BEGIN IF NEW.Discharge_Date IS NULL THEN UPDATE ward SET Available_Beds = Available_Beds - 1 WHERE Ward_ID = NEW.Ward_ID; END IF; END$$
CREATE TRIGGER `trg_admission_discharge_bu` BEFORE UPDATE ON `admission` FOR EACH ROW BEGIN IF OLD.Ward_ID <> NEW.Ward_ID THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ADMISSION: Ward_ID is immutable after admission'; END IF; IF OLD.Discharge_Date IS NOT NULL AND NOT (OLD.Discharge_Date <=> NEW.Discharge_Date) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ADMISSION: Discharge_Date is immutable once set'; END IF; IF OLD.Discharge_Date IS NULL AND NEW.Discharge_Date IS NOT NULL THEN UPDATE ward SET Available_Beds = Available_Beds + 1 WHERE Ward_ID = NEW.Ward_ID; INSERT INTO audit_log (Actor_Login_ID, Table_Affected, Record_ID, Action) VALUES (@app_login_id, 'ADMISSION', CAST(NEW.Admission_ID AS CHAR), 'DISCHARGE'); END IF; END$$
CREATE TRIGGER `trg_appt_doctor_branch_bi` BEFORE INSERT ON `appointment` FOR EACH ROW BEGIN DECLARE v_doc_branch INT UNSIGNED; SELECT Branch_ID INTO v_doc_branch FROM staff WHERE Staff_ID = NEW.Doctor_ID; IF v_doc_branch <> NEW.Branch_ID THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'APPOINTMENT: Doctor is not employed at the appointment branch'; END IF; END$$
CREATE TRIGGER `trg_appt_doctor_branch_bu` BEFORE UPDATE ON `appointment` FOR EACH ROW BEGIN DECLARE v_doc_branch INT UNSIGNED; SELECT Branch_ID INTO v_doc_branch FROM staff WHERE Staff_ID = NEW.Doctor_ID; IF v_doc_branch <> NEW.Branch_ID THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'APPOINTMENT: Doctor is not employed at the appointment branch'; END IF; END$$
CREATE TRIGGER `trg_bill_audit_ai` AFTER INSERT ON `billing` FOR EACH ROW BEGIN INSERT INTO audit_log (Actor_Login_ID, Table_Affected, Record_ID, Action) VALUES (@app_login_id, 'BILLING', CAST(NEW.Bill_ID AS CHAR), 'INSERT'); END$$
CREATE TRIGGER `trg_bill_audit_au` AFTER UPDATE ON `billing` FOR EACH ROW BEGIN INSERT INTO audit_log (Actor_Login_ID, Table_Affected, Record_ID, Action) VALUES (@app_login_id, 'BILLING', CAST(NEW.Bill_ID AS CHAR), 'UPDATE'); END$$
CREATE TRIGGER `trg_login_role_consistency_bi` BEFORE INSERT ON `login` FOR EACH ROW BEGIN IF NEW.Role = 'Patient' THEN IF NEW.Staff_ID IS NOT NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'LOGIN: Role Patient must not reference a staff member'; END IF; ELSE IF NEW.Staff_ID IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'LOGIN: Staff roles require Staff_ID'; END IF; IF NEW.Role = 'Doctor' AND NOT EXISTS (SELECT 1 FROM doctor WHERE Staff_ID = NEW.Staff_ID) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'LOGIN: Role Doctor requires a DOCTOR subclass record'; END IF; IF NEW.Role = 'Receptionist' AND NOT EXISTS (SELECT 1 FROM receptionist WHERE Staff_ID = NEW.Staff_ID) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'LOGIN: Role Receptionist requires a RECEPTIONIST subclass record'; END IF; IF NEW.Role = 'Admin' AND NOT EXISTS (SELECT 1 FROM admin_staff WHERE Staff_ID = NEW.Staff_ID) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'LOGIN: Role Admin requires an ADMIN_STAFF subclass record'; END IF; END IF; END$$
CREATE TRIGGER `trg_login_role_consistency_bu` BEFORE UPDATE ON `login` FOR EACH ROW BEGIN IF NEW.Role = 'Patient' THEN IF NEW.Staff_ID IS NOT NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'LOGIN: Role Patient must not reference a staff member'; END IF; ELSE IF NEW.Staff_ID IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'LOGIN: Staff roles require Staff_ID'; END IF; IF NEW.Role = 'Doctor' AND NOT EXISTS (SELECT 1 FROM doctor WHERE Staff_ID = NEW.Staff_ID) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'LOGIN: Role Doctor requires a DOCTOR subclass record'; END IF; IF NEW.Role = 'Receptionist' AND NOT EXISTS (SELECT 1 FROM receptionist WHERE Staff_ID = NEW.Staff_ID) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'LOGIN: Role Receptionist requires a RECEPTIONIST subclass record'; END IF; IF NEW.Role = 'Admin' AND NOT EXISTS (SELECT 1 FROM admin_staff WHERE Staff_ID = NEW.Staff_ID) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'LOGIN: Role Admin requires an ADMIN_STAFF subclass record'; END IF; END IF; END$$
CREATE TRIGGER `trg_rx_audit_ai` AFTER INSERT ON `prescription` FOR EACH ROW BEGIN INSERT INTO audit_log (Actor_Login_ID, Table_Affected, Record_ID, Action) VALUES (@app_login_id, 'PRESCRIPTION', CAST(NEW.Prescription_ID AS CHAR), 'INSERT'); END$$
CREATE TRIGGER `trg_rx_audit_au` AFTER UPDATE ON `prescription` FOR EACH ROW BEGIN INSERT INTO audit_log (Actor_Login_ID, Table_Affected, Record_ID, Action) VALUES (@app_login_id, 'PRESCRIPTION', CAST(NEW.Prescription_ID AS CHAR), 'UPDATE'); END$$
CREATE TRIGGER `trg_ref_initiator_branch_bi` BEFORE INSERT ON `referral` FOR EACH ROW BEGIN DECLARE v_init_branch INT UNSIGNED; SELECT Branch_ID INTO v_init_branch FROM staff WHERE Staff_ID = NEW.Initiator_Staff_ID; IF v_init_branch <> NEW.Source_Branch_ID THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'REFERRAL: Initiating doctor must belong to the source branch'; END IF; END$$
CREATE TRIGGER `trg_ref_audit_ai` AFTER INSERT ON `referral` FOR EACH ROW BEGIN INSERT INTO audit_log (Actor_Login_ID, Table_Affected, Record_ID, Action) VALUES (@app_login_id, 'REFERRAL', CAST(NEW.Referral_ID AS CHAR), 'INSERT'); END$$
CREATE TRIGGER `trg_ref_initiator_branch_bu` BEFORE UPDATE ON `referral` FOR EACH ROW BEGIN DECLARE v_init_branch INT UNSIGNED; SELECT Branch_ID INTO v_init_branch FROM staff WHERE Staff_ID = NEW.Initiator_Staff_ID; IF v_init_branch <> NEW.Source_Branch_ID THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'REFERRAL: Initiating doctor must belong to the source branch'; END IF; END$$
CREATE TRIGGER `trg_ref_audit_au` AFTER UPDATE ON `referral` FOR EACH ROW BEGIN INSERT INTO audit_log (Actor_Login_ID, Table_Affected, Record_ID, Action) VALUES (@app_login_id, 'REFERRAL', CAST(NEW.Referral_ID AS CHAR), 'UPDATE'); END$$

CREATE PROCEDURE `AcceptReferral`( IN p_referral_id INT UNSIGNED, IN p_doctor_id INT UNSIGNED, IN p_appt_date DATE, IN p_time_slot TIME, OUT o_appt_id INT UNSIGNED ) BEGIN DECLARE v_status VARCHAR(15) DEFAULT NULL; DECLARE v_patient CHAR(10) DEFAULT NULL; DECLARE v_dest INT UNSIGNED DEFAULT NULL; DECLARE v_doc_branch INT UNSIGNED DEFAULT NULL; DECLARE v_new_appt INT UNSIGNED DEFAULT NULL; SELECT Status, Patient_UHID, Dest_Branch_ID INTO v_status, v_patient, v_dest FROM referral WHERE Referral_ID = p_referral_id FOR UPDATE; IF v_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'AcceptReferral: referral not found'; END IF; IF v_status <> 'Pending' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'AcceptReferral: only Pending referrals can be accepted'; END IF; SELECT Branch_ID INTO v_doc_branch FROM staff WHERE Staff_ID = p_doctor_id FOR UPDATE; IF v_doc_branch IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'AcceptReferral: doctor not found'; END IF; IF v_doc_branch <> v_dest THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'AcceptReferral: doctor must belong to the referral destination branch'; END IF; CALL BookAppointment(v_patient, p_doctor_id, p_appt_date, p_time_slot, p_referral_id, v_new_appt); UPDATE referral SET Status = 'Accepted' WHERE Referral_ID = p_referral_id; SET o_appt_id = v_new_appt; END$$
CREATE PROCEDURE `AdmitPatient`( IN p_patient_uhid CHAR(10), IN p_ward_id INT UNSIGNED, IN p_attendant_name VARCHAR(100), IN p_attendant_phone VARCHAR(15), OUT o_admission_id INT UNSIGNED ) BEGIN DECLARE v_total INT UNSIGNED DEFAULT NULL; DECLARE v_avail INT UNSIGNED DEFAULT NULL; IF NOT EXISTS (SELECT 1 FROM patient WHERE UHID = p_patient_uhid) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'AdmitPatient: patient UHID not found'; END IF; SELECT Total_Beds, Available_Beds INTO v_total, v_avail FROM ward WHERE Ward_ID = p_ward_id FOR UPDATE; IF v_total IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'AdmitPatient: ward not found'; END IF; IF v_avail = 0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'AdmitPatient: ward has no available beds'; END IF; IF EXISTS (SELECT 1 FROM admission WHERE Patient_UHID = p_patient_uhid AND Discharge_Date IS NULL) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'AdmitPatient: patient already has an active admission'; END IF; INSERT INTO admission (Patient_UHID, Ward_ID, Admit_Date, Attendant_Name, Attendant_Phone) VALUES (p_patient_uhid, p_ward_id, NOW(), p_attendant_name, p_attendant_phone); SET o_admission_id = LAST_INSERT_ID(); END$$
CREATE PROCEDURE `BookAppointment`( IN p_patient_uhid CHAR(10), IN p_doctor_id INT UNSIGNED, IN p_appt_date DATE, IN p_time_slot TIME, IN p_referral_id INT UNSIGNED, OUT o_appt_id INT UNSIGNED ) BEGIN DECLARE v_doc_branch INT UNSIGNED DEFAULT NULL; DECLARE v_token INT UNSIGNED; DECLARE v_existing INT UNSIGNED DEFAULT NULL; DECLARE v_ref_status VARCHAR(15) DEFAULT NULL; DECLARE v_ref_dest INT UNSIGNED DEFAULT NULL; IF NOT EXISTS (SELECT 1 FROM patient WHERE UHID = p_patient_uhid) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BookAppointment: patient UHID not found'; END IF; SELECT Branch_ID INTO v_doc_branch FROM staff WHERE Staff_ID = p_doctor_id FOR UPDATE; IF v_doc_branch IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BookAppointment: doctor not found'; END IF; IF p_appt_date < CURDATE() THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BookAppointment: appointment date is in the past'; END IF; IF p_referral_id IS NOT NULL THEN SELECT Status, Dest_Branch_ID INTO v_ref_status, v_ref_dest FROM referral WHERE Referral_ID = p_referral_id; IF v_ref_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BookAppointment: referral not found'; END IF; IF v_ref_dest <> v_doc_branch THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BookAppointment: doctor does not belong to the referral destination branch'; END IF; END IF; SELECT Appt_ID INTO v_existing FROM appointment WHERE Doctor_ID = p_doctor_id AND Appt_Date = p_appt_date AND Time_Slot = p_time_slot AND Status <> 'Cancelled' LIMIT 1; IF v_existing IS NOT NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BookAppointment: doctor slot already booked'; END IF; SELECT COALESCE(MAX(Token_No), 0) + 1 INTO v_token FROM appointment WHERE Doctor_ID = p_doctor_id AND Appt_Date = p_appt_date AND Status <> 'Cancelled'; INSERT INTO appointment (Patient_UHID, Doctor_ID, Branch_ID, Appt_Date, Time_Slot, Token_No, Status, Referral_ID) VALUES (p_patient_uhid, p_doctor_id, v_doc_branch, p_appt_date, p_time_slot, v_token, 'Scheduled', p_referral_id); SET o_appt_id = LAST_INSERT_ID(); END$$
CREATE PROCEDURE `CancelAppointment`( IN p_appt_id INT UNSIGNED ) BEGIN DECLARE v_status VARCHAR(15) DEFAULT NULL; SELECT Status INTO v_status FROM appointment WHERE Appt_ID = p_appt_id FOR UPDATE; IF v_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CancelAppointment: appointment not found'; END IF; IF v_status <> 'Scheduled' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CancelAppointment: only Scheduled appointments can be cancelled'; END IF; UPDATE appointment SET Status = 'Cancelled' WHERE Appt_ID = p_appt_id; END$$
CREATE PROCEDURE `CompleteAppointment`( IN p_appt_id INT UNSIGNED ) BEGIN DECLARE v_status VARCHAR(15) DEFAULT NULL; DECLARE v_referral INT UNSIGNED DEFAULT NULL; DECLARE v_ref_status VARCHAR(15) DEFAULT NULL; SELECT Status, Referral_ID INTO v_status, v_referral FROM appointment WHERE Appt_ID = p_appt_id FOR UPDATE; IF v_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CompleteAppointment: appointment not found'; END IF; IF v_status <> 'Scheduled' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CompleteAppointment: only Scheduled appointments can be completed'; END IF; UPDATE appointment SET Status = 'Completed' WHERE Appt_ID = p_appt_id; IF v_referral IS NOT NULL THEN SELECT Status INTO v_ref_status FROM referral WHERE Referral_ID = v_referral FOR UPDATE; IF v_ref_status = 'Accepted' THEN UPDATE referral SET Status = 'Completed' WHERE Referral_ID = v_referral; END IF; END IF; END$$
CREATE PROCEDURE `CreatePrescription`( IN p_appt_id INT UNSIGNED, IN p_medicine_name VARCHAR(120), IN p_dosage VARCHAR(60), IN p_notes VARCHAR(255), OUT o_prescription_id INT UNSIGNED ) BEGIN DECLARE v_status VARCHAR(15) DEFAULT NULL; SELECT Status INTO v_status FROM appointment WHERE Appt_ID = p_appt_id FOR UPDATE; IF v_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CreatePrescription: appointment not found'; END IF; IF v_status = 'Cancelled' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CreatePrescription: cannot prescribe for a cancelled appointment'; END IF; IF CHAR_LENGTH(TRIM(p_medicine_name)) = 0 OR CHAR_LENGTH(TRIM(p_dosage)) = 0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CreatePrescription: medicine name and dosage are required'; END IF; INSERT INTO prescription (Appt_ID, Medicine_Name, Dosage, Notes) VALUES (p_appt_id, TRIM(p_medicine_name), TRIM(p_dosage), p_notes); SET o_prescription_id = LAST_INSERT_ID(); END$$
CREATE PROCEDURE `DischargePatient`( IN p_admission_id INT UNSIGNED, IN p_consultation_fee DECIMAL(10,2), IN p_medicine_charges DECIMAL(10,2), OUT o_bill_id INT UNSIGNED ) BEGIN DECLARE v_discharged DATETIME DEFAULT NULL; IF NOT EXISTS (SELECT 1 FROM admission WHERE Admission_ID = p_admission_id) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DischargePatient: admission not found'; END IF; SELECT Discharge_Date INTO v_discharged FROM admission WHERE Admission_ID = p_admission_id FOR UPDATE; IF v_discharged IS NOT NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DischargePatient: admission already discharged'; END IF; IF p_consultation_fee < 0 OR p_medicine_charges < 0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DischargePatient: charges cannot be negative'; END IF; UPDATE admission SET Discharge_Date = NOW() WHERE Admission_ID = p_admission_id; CALL GenerateBill(p_admission_id, p_consultation_fee, p_medicine_charges, o_bill_id); END$$
CREATE PROCEDURE `GenerateBill`( IN p_admission_id INT UNSIGNED, IN p_consultation_fee DECIMAL(10,2), IN p_medicine_charges DECIMAL(10,2), OUT o_bill_id INT UNSIGNED ) BEGIN DECLARE v_admit DATETIME DEFAULT NULL; DECLARE v_discharge DATETIME DEFAULT NULL; DECLARE v_ward INT UNSIGNED DEFAULT NULL; DECLARE v_rate DECIMAL(10,2) DEFAULT NULL; DECLARE v_days INT; IF NOT EXISTS (SELECT 1 FROM admission WHERE Admission_ID = p_admission_id) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'GenerateBill: admission not found'; END IF; SELECT Admit_Date, Discharge_Date, Ward_ID INTO v_admit, v_discharge, v_ward FROM admission WHERE Admission_ID = p_admission_id FOR UPDATE; IF v_discharge IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'GenerateBill: bill can only be generated after discharge'; END IF; IF EXISTS (SELECT 1 FROM billing WHERE Admission_ID = p_admission_id) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'GenerateBill: bill already exists for this admission'; END IF; IF p_consultation_fee < 0 OR p_medicine_charges < 0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'GenerateBill: charges cannot be negative'; END IF; SELECT Daily_Rate INTO v_rate FROM ward WHERE Ward_ID = v_ward; SET v_days = GREATEST(DATEDIFF(v_discharge, v_admit), 1); INSERT INTO billing (Admission_ID, Consultation_Fee, Room_Charges, Medicine_Charges) VALUES (p_admission_id, p_consultation_fee, v_rate * v_days, p_medicine_charges); SET o_bill_id = LAST_INSERT_ID(); END$$
CREATE PROCEDURE `MarkBillPaid`( IN p_bill_id INT UNSIGNED ) BEGIN DECLARE v_status VARCHAR(10) DEFAULT NULL; SELECT Status INTO v_status FROM billing WHERE Bill_ID = p_bill_id FOR UPDATE; IF v_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'MarkBillPaid: bill not found'; END IF; IF v_status = 'Paid' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'MarkBillPaid: bill is already paid'; END IF; UPDATE billing SET Status = 'Paid', Paid_At = NOW() WHERE Bill_ID = p_bill_id; END$$
CREATE PROCEDURE `RegisterPatient`( IN p_name VARCHAR(100), IN p_dob DATE, IN p_gender VARCHAR(10), IN p_blood_group VARCHAR(5), IN p_phone VARCHAR(15), IN p_address VARCHAR(255), IN p_username VARCHAR(50), IN p_password_hash VARCHAR(255), OUT o_uhid CHAR(10) ) proc: BEGIN DECLARE v_last CHAR(10); DECLARE v_seq INT UNSIGNED; DECLARE v_attempt INT UNSIGNED DEFAULT 0; DECLARE v_uhid CHAR(10); IF CHAR_LENGTH(TRIM(p_name)) = 0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'RegisterPatient: patient name is required'; END IF; IF p_dob > CURDATE() THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'RegisterPatient: date of birth cannot be in the future'; END IF; IF p_username IS NULL OR CHAR_LENGTH(TRIM(p_username)) < 4 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'RegisterPatient: username must be at least 4 characters'; END IF; IF EXISTS (SELECT 1 FROM login WHERE Username = p_username) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'RegisterPatient: username already taken'; END IF; uhid_retry: LOOP SET v_last = NULL; SELECT UHID INTO v_last FROM patient ORDER BY UHID DESC LIMIT 1 FOR UPDATE; IF v_last IS NULL THEN SET v_seq = 1; ELSE SET v_seq = CAST(SUBSTRING(v_last, 4) AS UNSIGNED) + 1; END IF; IF v_seq > 9999999 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'RegisterPatient: UHID sequence exhausted'; END IF; SET v_uhid = CONCAT('AIC', LPAD(v_seq, 7, '0')); BEGIN DECLARE EXIT HANDLER FOR 1062 BEGIN SET v_attempt = v_attempt + 1; IF v_attempt >= 3 THEN RESIGNAL; END IF; END; INSERT INTO patient (UHID, Name, DOB, Gender, Blood_Group, Phone, Address) VALUES (v_uhid, p_name, p_dob, p_gender, p_blood_group, p_phone, p_address); INSERT INTO login (Username, Password_Hash, Role, Is_Active, Patient_UHID) VALUES (p_username, p_password_hash, 'Patient', 1, v_uhid); SET o_uhid = v_uhid; LEAVE uhid_retry; END; END LOOP uhid_retry; END$$
CREATE PROCEDURE `RejectReferral`( IN p_referral_id INT UNSIGNED ) BEGIN DECLARE v_status VARCHAR(15) DEFAULT NULL; SELECT Status INTO v_status FROM referral WHERE Referral_ID = p_referral_id FOR UPDATE; IF v_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'RejectReferral: referral not found'; END IF; IF v_status <> 'Pending' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'RejectReferral: only Pending referrals can be rejected'; END IF; UPDATE referral SET Status = 'Rejected' WHERE Referral_ID = p_referral_id; END$$

DELIMITER ;

CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `branch_revenue_view` AS select `b`.`Branch_ID` AS `Branch_ID`,`b`.`Branch_Name` AS `Branch_Name`,count(`bi`.`Bill_ID`) AS `Bills_Generated`,coalesce(sum(`bi`.`Total`),0) AS `Total_Billed`,coalesce(sum((case when (`bi`.`Status` = 'Paid') then `bi`.`Total` end)),0) AS `Total_Collected`,coalesce(sum((case when (`bi`.`Status` = 'Unpaid') then `bi`.`Total` end)),0) AS `Total_Outstanding` from (((`branch` `b` left join `ward` `w` on((`w`.`Branch_ID` = `b`.`Branch_ID`))) left join `admission` `a` on(((`a`.`Ward_ID` = `w`.`Ward_ID`) and (`a`.`Discharge_Date` is not null)))) left join `billing` `bi` on((`bi`.`Admission_ID` = `a`.`Admission_ID`))) group by `b`.`Branch_ID`,`b`.`Branch_Name`;

CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `branch_ward_view` AS select `w`.`Ward_ID` AS `Ward_ID`,`w`.`Branch_ID` AS `Branch_ID`,`b`.`Branch_Name` AS `Branch_Name`,`w`.`Ward_Name` AS `Ward_Name`,`w`.`Ward_Type` AS `Ward_Type`,`w`.`Total_Beds` AS `Total_Beds`,`w`.`Available_Beds` AS `Available_Beds`,(`w`.`Total_Beds` - `w`.`Available_Beds`) AS `Occupied_Beds`,round(((100 * (`w`.`Total_Beds` - `w`.`Available_Beds`)) / `w`.`Total_Beds`),1) AS `Occupancy_Pct`,`w`.`Daily_Rate` AS `Daily_Rate` from (`ward` `w` join `branch` `b` on((`b`.`Branch_ID` = `w`.`Branch_ID`)));

CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `chain_occupancy_view` AS select `b`.`Branch_ID` AS `Branch_ID`,`b`.`Branch_Name` AS `Branch_Name`,`b`.`City` AS `City`,(select count(0) from `ward` `w` where (`w`.`Branch_ID` = `b`.`Branch_ID`)) AS `Wards`,(select coalesce(sum(`w`.`Total_Beds`),0) from `ward` `w` where (`w`.`Branch_ID` = `b`.`Branch_ID`)) AS `Total_Beds`,(select coalesce(sum(`w`.`Available_Beds`),0) from `ward` `w` where (`w`.`Branch_ID` = `b`.`Branch_ID`)) AS `Available_Beds`,(select count(0) from (`admission` `a` join `ward` `w2` on((`w2`.`Ward_ID` = `a`.`Ward_ID`))) where ((`w2`.`Branch_ID` = `b`.`Branch_ID`) and (`a`.`Discharge_Date` is null))) AS `Active_Admissions`,round(((100 * (select coalesce(sum((`w`.`Total_Beds` - `w`.`Available_Beds`)),0) from `ward` `w` where (`w`.`Branch_ID` = `b`.`Branch_ID`))) / nullif((select sum(`w`.`Total_Beds`) from `ward` `w` where (`w`.`Branch_ID` = `b`.`Branch_ID`)),0)),1) AS `Occupancy_Pct` from `branch` `b`;

CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `doctor_schedule_view` AS select `a`.`Appt_ID` AS `Appt_ID`,`a`.`Appt_Date` AS `Appt_Date`,`a`.`Time_Slot` AS `Time_Slot`,`a`.`Token_No` AS `Token_No`,`a`.`Status` AS `Status`,`a`.`Doctor_ID` AS `Doctor_ID`,`s`.`Name` AS `Doctor_Name`,`d`.`Specialization` AS `Specialization`,`dp`.`Dept_Name` AS `Dept_Name`,`a`.`Branch_ID` AS `Branch_ID`,`b`.`Branch_Name` AS `Branch_Name`,`a`.`Patient_UHID` AS `Patient_UHID`,`p`.`Name` AS `Patient_Name`,`p`.`Phone` AS `Patient_Phone`,`a`.`Referral_ID` AS `Referral_ID` from (((((`appointment` `a` join `doctor` `d` on((`d`.`Staff_ID` = `a`.`Doctor_ID`))) join `staff` `s` on((`s`.`Staff_ID` = `d`.`Staff_ID`))) join `department` `dp` on((`dp`.`Dept_ID` = `d`.`Dept_ID`))) join `branch` `b` on((`b`.`Branch_ID` = `a`.`Branch_ID`))) join `patient` `p` on((`p`.`UHID` = `a`.`Patient_UHID`)));

CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `patient_history_view` AS select `a`.`Patient_UHID` AS `UHID`,'APPOINTMENT' AS `Record_Type`,`a`.`Appt_ID` AS `Record_ID`,`a`.`Appt_Date` AS `Event_Date`,`a`.`Branch_ID` AS `Branch_ID`,`b`.`Branch_Name` AS `Branch_Name`,`a`.`Status` AS `Status`,concat(`s`.`Name`,' - ',`dp`.`Dept_Name`) AS `Summary` from ((((`appointment` `a` join `doctor` `d` on((`d`.`Staff_ID` = `a`.`Doctor_ID`))) join `staff` `s` on((`s`.`Staff_ID` = `d`.`Staff_ID`))) join `department` `dp` on((`dp`.`Dept_ID` = `d`.`Dept_ID`))) join `branch` `b` on((`b`.`Branch_ID` = `a`.`Branch_ID`))) union all select `ad`.`Patient_UHID` AS `Patient_UHID`,'ADMISSION' AS `ADMISSION`,`ad`.`Admission_ID` AS `Admission_ID`,cast(`ad`.`Admit_Date` as date) AS `DATE(ad.Admit_Date)`,`w`.`Branch_ID` AS `Branch_ID`,`b`.`Branch_Name` AS `Branch_Name`,(case when (`ad`.`Discharge_Date` is null) then 'Active' else 'Discharged' end) AS `Name_exp_15`,concat(`w`.`Ward_Name`,' (',`w`.`Ward_Type`,')') AS `CONCAT(w.Ward_Name, ' (', w.Ward_Type, ')')` from ((`admission` `ad` join `ward` `w` on((`w`.`Ward_ID` = `ad`.`Ward_ID`))) join `branch` `b` on((`b`.`Branch_ID` = `w`.`Branch_ID`)));

CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `patient_self_view` AS select `p`.`UHID` AS `UHID`,`p`.`Name` AS `Name`,`p`.`DOB` AS `DOB`,`p`.`Gender` AS `Gender`,`p`.`Blood_Group` AS `Blood_Group`,`p`.`Phone` AS `Phone`,`p`.`Address` AS `Address`,`p`.`Created_At` AS `Created_At`,`l`.`Username` AS `Username`,`l`.`Is_Active` AS `Login_Active` from (`patient` `p` join `login` `l` on((`l`.`Patient_UHID` = `p`.`UHID`)));

CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `referral_flow_view` AS select `r`.`Referral_ID` AS `Referral_ID`,`r`.`Patient_UHID` AS `Patient_UHID`,`p`.`Name` AS `Patient_Name`,`r`.`Source_Branch_ID` AS `Source_Branch_ID`,`bs`.`Branch_Name` AS `Source_Branch`,`r`.`Dest_Branch_ID` AS `Dest_Branch_ID`,`bd`.`Branch_Name` AS `Destination_Branch`,`r`.`Initiator_Staff_ID` AS `Initiator_Staff_ID`,`si`.`Name` AS `Initiator_Doctor`,`r`.`Reason` AS `Reason`,`r`.`Status` AS `Status`,`r`.`Created_At` AS `Created_At`,`r`.`Updated_At` AS `Updated_At`,`a`.`Appt_ID` AS `Created_Appt_ID`,`a`.`Appt_Date` AS `Created_Appt_Date`,`a`.`Time_Slot` AS `Created_Appt_Slot`,`a`.`Status` AS `Created_Appt_Status`,`sd`.`Name` AS `Destination_Doctor` from ((((((((`referral` `r` join `patient` `p` on((`p`.`UHID` = `r`.`Patient_UHID`))) join `branch` `bs` on((`bs`.`Branch_ID` = `r`.`Source_Branch_ID`))) join `branch` `bd` on((`bd`.`Branch_ID` = `r`.`Dest_Branch_ID`))) join `doctor` `di` on((`di`.`Staff_ID` = `r`.`Initiator_Staff_ID`))) join `staff` `si` on((`si`.`Staff_ID` = `di`.`Staff_ID`))) left join `appointment` `a` on((`a`.`Referral_ID` = `r`.`Referral_ID`))) left join `doctor` `dd` on((`dd`.`Staff_ID` = `a`.`Doctor_ID`))) left join `staff` `sd` on((`sd`.`Staff_ID` = `dd`.`Staff_ID`)));



-- Bootstrap completed.
