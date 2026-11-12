"""Preview or add a small, linked synthetic professor-demo dataset."""
from datetime import date, timedelta
import argparse
import bcrypt
from app.db import connect

TARGET = {"patients": 40, "appointments": 55, "prescriptions": 30, "admissions": 18, "bills": 12, "referrals": 10}
PASSWORD = "Demo@12345"
NAMES = ["Aarav Mehta","Aanya Kapoor","Vihaan Sharma","Diya Nair","Kabir Malhotra","Anaya Iyer","Reyansh Verma","Myra Joshi","Advait Rao","Ishita Das","Arjun Menon","Sara Khan","Dhruv Bansal","Meera Pillai","Rohan Sethi","Tara Chawla","Neil Reddy","Kavya Sood","Arnav Ghosh","Riya Kulkarni","Dev Malhotra","Samaira Das","Veer Khanna","Mira Shah"]
SLOTS = ["09:00:00","09:30:00","10:00:00","10:30:00","11:00:00","11:30:00","14:00:00","14:30:00","15:00:00","15:30:00"]
MEDICINES = [("Demo Medicine A","1 demo unit daily"),("Demo Medicine B","1 demo unit twice daily"),("Demo Medicine C","1 demo unit after meals")]


def count(cur, table):
    cur.execute("SELECT COUNT(*) FROM " + table)
    return int(cur.fetchone()[0])


def password_hash():
    return bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def callproc(cur, name, args):
    result = cur.callproc(name, args)
    for rc in cur.stored_results():
        rc.fetchall()
        rc.close()
    return result


def add_staff(cur, bid, name, role, username, dept_id=None, level=None):
    cur.execute("INSERT INTO staff(Branch_ID,Name,DOB,Phone,Staff_Type) VALUES(%s,%s,'1985-01-01',%s,%s)",
                (bid, name, "90000" + str(bid).zfill(2) + "101", role))
    sid = cur.lastrowid
    if role == "Doctor":
        cur.execute("INSERT INTO doctor(Staff_ID,Staff_Type,Dept_ID,Specialization,Qualification,Consultation_Fee) VALUES(%s,'Doctor',%s,'General Medicine','MBBS, MD',500)", (sid, dept_id))
    elif role == "Admin":
        cur.execute("INSERT INTO admin_staff(Staff_ID,Staff_Type,Access_Level) VALUES(%s,'Admin',%s)", (sid, level))
    elif role == "Receptionist":
        cur.execute("INSERT INTO receptionist(Staff_ID,Staff_Type,Counter_No) VALUES(%s,'Receptionist',1)", (sid,))
    cur.execute("INSERT INTO login(Username,Password_Hash,Role,Is_Active,Staff_ID) VALUES(%s,%s,%s,1,%s)",
                (username, password_hash(), role, sid))


def bootstrap_empty_network(cn, cur):
    if count(cur, "branch"):
        return
    other = sum(count(cur, t) for t in ("department","ward","staff","doctor","login","patient","appointment","prescription","admission","billing","referral"))
    if other:
        raise RuntimeError("Branch table is empty but other app tables contain data; refusing to bootstrap.")
    departments = ["General Medicine","Cardiology","Orthopaedics","Paediatrics","Anaesthesiology"]
    wards = [("General Ward","General",20,1700),("ICU Unit","ICU",6,5800),("Private Ward","Private",8,4100)]
    for name, city, main in [("AIIMS Connect - New Delhi (Main)","New Delhi",1),("AIIMS Connect - Jodhpur","Jodhpur",0),("AIIMS Connect - Bhopal","Bhopal",0)]:
        cur.execute("INSERT INTO branch(Branch_Name,City,Is_Main) VALUES(%s,%s,%s)", (name,city,main))
        bid = cur.lastrowid
        dept_ids = {}
        for d in departments:
            cur.execute("INSERT INTO department(Branch_ID,Dept_Name) VALUES(%s,%s)", (bid,d))
            dept_ids[d] = cur.lastrowid
        for w,t,beds,rate in wards:
            cur.execute("INSERT INTO ward(Branch_ID,Ward_Name,Ward_Type,Total_Beds,Available_Beds,Daily_Rate) VALUES(%s,%s,%s,%s,%s,%s)", (bid,w,t,beds,beds,rate))
        if main:
            add_staff(cur,bid,"Demo Chain Administrator","Admin","chain.admin",level="Chain")
        add_staff(cur,bid,"Demo "+city+" Administrator","Admin","admin."+city.lower().replace(" ","."),level="Branch")
        add_staff(cur,bid,"Demo "+city+" Doctor","Doctor","doctor."+city.lower().replace(" ",".")+".01",dept_ids["General Medicine"])
        add_staff(cur,bid,"Demo "+city+" Receptionist","Receptionist","reception."+city.lower().replace(" ",".")+".01")
    cn.commit()
    print("Created synthetic New Delhi, Jodhpur and Bhopal demo network.")


def ensure_branch_doctors(cn, cur):
    cur.execute("SELECT Branch_ID,City FROM branch ORDER BY Branch_ID")
    for bid, city in cur.fetchall():
        cur.execute("SELECT COUNT(*) FROM doctor d JOIN staff s ON s.Staff_ID=d.Staff_ID WHERE s.Branch_ID=%s", (bid,))
        if cur.fetchone()[0]:
            continue
        cur.execute("SELECT Dept_ID FROM department WHERE Branch_ID=%s ORDER BY Dept_ID LIMIT 1", (bid,))
        row = cur.fetchone()
        if row:
            dept_id = row[0]
        else:
            cur.execute("INSERT INTO department(Branch_ID,Dept_Name) VALUES(%s,'General Medicine')", (bid,))
            dept_id = cur.lastrowid
        username = "demo.doctor.branch" + str(bid)
        cur.execute("SELECT 1 FROM login WHERE Username=%s", (username,))
        if cur.fetchone():
            username += ".new"
        add_staff(cur,bid,"Demo Doctor - "+city,"Doctor",username,dept_id)
        cn.commit()
        print("Added one synthetic doctor for "+city+": "+username)


def add_patients(cn, cur):
    current = count(cur, "patient")
    cur.execute("SELECT Patient_UHID FROM login WHERE Username LIKE 'demo.patient.%' AND Patient_UHID IS NOT NULL ORDER BY Username")
    patients = [r[0] for r in cur.fetchall()]
    seq = 1
    while current < TARGET["patients"]:
        username = "demo.patient." + str(seq).zfill(2)
        cur.execute("SELECT Patient_UHID FROM login WHERE Username=%s", (username,))
        row = cur.fetchone()
        if row:
            if row[0] and row[0] not in patients:
                patients.append(row[0])
            seq += 1
            continue
        name = NAMES[(seq-1) % len(NAMES)] if seq <= len(NAMES) else "Demo Patient " + str(seq).zfill(2)
        gender = "Female" if seq % 2 == 0 else "Male"
        blood = ["A+","B+","O+","AB+","A-","B-"][seq % 6]
        dob = date(1995+seq%10, 1+seq%12, 1+seq%26).isoformat()
        result = callproc(cur, "RegisterPatient", (name,dob,gender,blood,"9001"+str(seq).zfill(6),"Synthetic demo address",username,password_hash(),None))
        cn.commit()
        patients.append(result[-1])
        current += 1
        seq += 1
        print("Added synthetic patient "+username+" / "+str(result[-1]))
    return patients


def add_appointments(cn, cur, patients):
    current = count(cur, "appointment")
    cur.execute("SELECT d.Staff_ID,s.Branch_ID FROM doctor d JOIN staff s ON s.Staff_ID=d.Staff_ID ORDER BY s.Branch_ID,d.Staff_ID")
    doctors = cur.fetchall()
    if not doctors or not patients:
        print("Appointments skipped: no doctors or demo patients.")
        return
    index = 0
    for offset in range(1,100):
        day = (date.today()+timedelta(days=offset)).isoformat()
        for doctor_id, branch_id in doctors:
            for slot in SLOTS:
                if current >= TARGET["appointments"]:
                    return
                patient = patients[index % len(patients)]
                index += 1
                cur.execute("SELECT 1 FROM appointment WHERE Doctor_ID=%s AND Appt_Date=%s AND Time_Slot=%s AND Status<>'Cancelled' LIMIT 1",(doctor_id,day,slot))
                if cur.fetchone():
                    continue
                try:
                    result = callproc(cur,"BookAppointment",(patient,doctor_id,day,slot,None,None))
                    cn.commit()
                    current += 1
                    print("Added synthetic appointment #"+str(result[-1]))
                except Exception:
                    cn.rollback()


def add_prescriptions(cn, cur):
    current = count(cur,"prescription")
    cur.execute("SELECT a.Appt_ID FROM appointment a JOIN login l ON l.Patient_UHID=a.Patient_UHID AND l.Username LIKE 'demo.patient.%' LEFT JOIN prescription p ON p.Appt_ID=a.Appt_ID WHERE a.Status<>'Cancelled' AND p.Prescription_ID IS NULL ORDER BY a.Appt_Date,a.Appt_ID")
    for i,row in enumerate(cur.fetchall()):
        if current >= TARGET["prescriptions"]:
            break
        medicine,dosage = MEDICINES[i % len(MEDICINES)]
        result = callproc(cur,"CreatePrescription",(row[0],medicine,dosage,"Synthetic academic demo record",None))
        cn.commit()
        current += 1
        print("Added synthetic prescription #"+str(result[-1]))


def add_admissions_and_bills(cn, cur, patients):
    active = count(cur,"admission")
    bills = count(cur,"billing")
    if active >= TARGET["admissions"] or not patients:
        return
    placeholders = ",".join(["%s"]*len(patients))
    cur.execute("SELECT p.UHID FROM patient p WHERE p.UHID IN ("+placeholders+") AND NOT EXISTS(SELECT 1 FROM admission a WHERE a.Patient_UHID=p.UHID AND a.Discharge_Date IS NULL) ORDER BY p.UHID",tuple(patients))
    created = []
    for row in cur.fetchall():
        if len(created) >= TARGET["admissions"]-active:
            break
        cur.execute("SELECT Ward_ID FROM ward WHERE Available_Beds>0 ORDER BY Branch_ID,Ward_ID LIMIT 1")
        ward = cur.fetchone()
        if not ward:
            print("Admission top-up stopped: no beds available.")
            break
        try:
            result = callproc(cur,"AdmitPatient",(row[0],ward[0],"Synthetic demo attendant","9000009999",None))
            cn.commit()
            created.append(result[-1])
            print("Added synthetic admission #"+str(result[-1]))
        except Exception:
            cn.rollback()
    for admission_id in created:
        if bills >= TARGET["bills"]:
            break
        try:
            result = callproc(cur,"DischargePatient",(admission_id,500,100,None))
            cn.commit()
            bills += 1
            print("Discharged demo admission; generated bill #"+str(result[-1]))
        except Exception:
            cn.rollback()


def add_referrals(cn, cur, patients):
    current = count(cur,"referral")
    if current >= TARGET["referrals"] or not patients:
        return
    cur.execute("SELECT Branch_ID FROM branch ORDER BY Branch_ID")
    branches = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT d.Staff_ID,s.Branch_ID FROM doctor d JOIN staff s ON s.Staff_ID=d.Staff_ID ORDER BY s.Branch_ID,d.Staff_ID")
    doctors = cur.fetchall()
    if len(branches)<2 or not doctors:
        return
    for i in range(TARGET["referrals"]-current):
        doctor_id,source = doctors[i % len(doctors)]
        dests = [bid for bid in branches if bid != source]
        dest = dests[i % len(dests)]
        patient = patients[i % len(patients)]
        cur.execute("SELECT Login_ID FROM login WHERE Staff_ID=%s LIMIT 1",(doctor_id,))
        actor = cur.fetchone()
        cur.execute("SET @app_login_id=%s",(actor[0] if actor else None,))
        cur.execute("INSERT INTO referral(Patient_UHID,Initiator_Staff_ID,Source_Branch_ID,Dest_Branch_ID,Reason,Status) VALUES(%s,%s,%s,%s,%s,'Pending')",(patient,doctor_id,source,dest,"Synthetic specialist review referral "+str(i+1)))
        cn.commit()
        print("Added synthetic referral #"+str(cur.lastrowid))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true",help="insert synthetic records; default is read-only preview")
    args = parser.parse_args()
    cn = connect()
    cur = cn.cursor()
    try:
        cur.execute("SELECT DATABASE(),VERSION()")
        db,version = cur.fetchone()
        print("Database:",db,"| MySQL:",version)
        for label,table in (("patients","patient"),("appointments","appointment"),("prescriptions","prescription"),("admissions","admission"),("bills","billing"),("referrals","referral")):
            current = count(cur,table)
            print(f"  {label:16} {current:4} -> {max(current,TARGET[label]):4}")
        print("Existing rows and passwords are never updated or deleted.")
        if not args.apply:
            print("PREVIEW ONLY. Use --apply only if this DB contains synthetic demo/test data.")
            return
        bootstrap_empty_network(cn,cur)
        ensure_branch_doctors(cn,cur)
        cur.execute("SELECT Login_ID FROM login WHERE Role='Admin' ORDER BY Login_ID LIMIT 1")
        actor = cur.fetchone()
        cur.execute("SET @app_login_id=%s",(actor[0] if actor else None,))
        patients = add_patients(cn,cur)
        add_appointments(cn,cur,patients)
        add_prescriptions(cn,cur)
        add_admissions_and_bills(cn,cur,patients)
        add_referrals(cn,cur,patients)
        print("Final counts:")
        for label,table in (("patients","patient"),("appointments","appointment"),("prescriptions","prescription"),("admissions","admission"),("bills","billing"),("referrals","referral")):
            print(" ",label,count(cur,table))
        print("New synthetic patient credentials use password:",PASSWORD)
    finally:
        cur.close()
        cn.close()


if __name__ == "__main__":
    main()
