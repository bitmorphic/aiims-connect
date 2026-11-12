USE aiims_connect;
DELIMITER $$
CREATE TRIGGER trg_admission_bi BEFORE INSERT ON admission FOR EACH ROW BEGIN DECLARE n INT; SELECT Available_Beds INTO n FROM ward WHERE Ward_ID=NEW.Ward_ID FOR UPDATE; IF n IS NULL OR n<=0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='No beds available'; END IF; END$$
CREATE TRIGGER trg_admission_ai AFTER INSERT ON admission FOR EACH ROW BEGIN UPDATE ward SET Available_Beds=Available_Beds-1 WHERE Ward_ID=NEW.Ward_ID; END$$
CREATE TRIGGER trg_admission_au AFTER UPDATE ON admission FOR EACH ROW BEGIN IF OLD.Status='Active' AND NEW.Status='Discharged' THEN UPDATE ward SET Available_Beds=Available_Beds+1 WHERE Ward_ID=NEW.Ward_ID; INSERT INTO audit_log(Action,Table_Affected,Record_ID) VALUES('DISCHARGE','admission',CAST(NEW.Admission_ID AS CHAR)); END IF; END$$
CREATE TRIGGER trg_prescription_ai AFTER INSERT ON prescription FOR EACH ROW BEGIN INSERT INTO audit_log(Action,Table_Affected,Record_ID) VALUES('INSERT','prescription',CAST(NEW.Prescription_ID AS CHAR)); END$$
CREATE TRIGGER trg_prescription_au AFTER UPDATE ON prescription FOR EACH ROW BEGIN INSERT INTO audit_log(Action,Table_Affected,Record_ID) VALUES('UPDATE','prescription',CAST(NEW.Prescription_ID AS CHAR)); END$$
CREATE TRIGGER trg_billing_ai AFTER INSERT ON billing FOR EACH ROW BEGIN INSERT INTO audit_log(Action,Table_Affected,Record_ID) VALUES('INSERT','billing',CAST(NEW.Bill_ID AS CHAR)); END$$
CREATE TRIGGER trg_billing_au AFTER UPDATE ON billing FOR EACH ROW BEGIN INSERT INTO audit_log(Action,Table_Affected,Record_ID) VALUES('UPDATE','billing',CAST(NEW.Bill_ID AS CHAR)); END$$
CREATE TRIGGER trg_referral_ai AFTER INSERT ON referral FOR EACH ROW BEGIN INSERT INTO audit_log(Action,Table_Affected,Record_ID) VALUES('INSERT','referral',CAST(NEW.Referral_ID AS CHAR)); END$$
CREATE TRIGGER trg_referral_au AFTER UPDATE ON referral FOR EACH ROW BEGIN INSERT INTO audit_log(Action,Table_Affected,Record_ID) VALUES('UPDATE','referral',CAST(NEW.Referral_ID AS CHAR)); END$$
DELIMITER ;
