USE aiims_connect;
DELIMITER $$
CREATE PROCEDURE BookAppointment(IN u VARCHAR(24),IN s INT,IN b INT,IN d DATE,IN t TIME,IN tok INT,OUT aid BIGINT)
BEGIN
 IF NOT EXISTS(SELECT 1 FROM patient WHERE UHID=u) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unknown UHID'; END IF;
 IF NOT EXISTS(SELECT 1 FROM staff WHERE Staff_ID=s AND Staff_Type='Doctor' AND Branch_ID=b) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Doctor branch mismatch'; END IF;
 INSERT INTO appointment(UHID,Staff_ID,Branch_ID,Appt_Date,Time_Slot,Token_No) VALUES(u,s,b,d,t,tok); SET aid=LAST_INSERT_ID();
END$$
CREATE PROCEDURE GenerateBill(IN a BIGINT,IN cfee DECIMAL(10,2),IN room DECIMAL(10,2),IN med DECIMAL(10,2),OUT bid BIGINT)
BEGIN INSERT INTO billing(Admission_ID,Consultation_Fee,Room_Charges,Medicine_Charges) VALUES(a,cfee,room,med); SET bid=LAST_INSERT_ID(); END$$
CREATE PROCEDURE AcceptReferral(IN rid BIGINT,IN doc INT,IN d DATE,IN t TIME,IN tok INT,OUT aid BIGINT)
BEGIN
 DECLARE u VARCHAR(24); DECLARE b INT; DECLARE st VARCHAR(20);
 SELECT UHID,To_Branch_ID,Status INTO u,b,st FROM referral WHERE Referral_ID=rid FOR UPDATE;
 IF st IS NULL OR st<>'Pending' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Referral not pending'; END IF;
 IF NOT EXISTS(SELECT 1 FROM doctor d1 JOIN staff s ON s.Staff_ID=d1.Staff_ID WHERE d1.Staff_ID=doc AND s.Branch_ID=b) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Doctor not in destination branch'; END IF;
 INSERT INTO appointment(UHID,Staff_ID,Branch_ID,Appt_Date,Time_Slot,Token_No) VALUES(u,doc,b,d,t,tok); SET aid=LAST_INSERT_ID();
 UPDATE referral SET Status='Accepted',Destination_Doctor_ID=doc,Appt_ID=aid WHERE Referral_ID=rid;
END$$
DELIMITER ;
