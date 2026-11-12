from datetime import datetime,timedelta
import bcrypt
from flask import Blueprint,render_template,request,redirect,url_for,session,flash,abort
from .db import connect,query,one
bp=Blueprint('main',__name__)
def auth():
    if not session.get('login_id'): return False
    last=session.get('last_seen')
    if last and datetime.utcnow()-datetime.fromisoformat(last)>timedelta(minutes=15):
        session.clear(); return False
    session['last_seen']=datetime.utcnow().isoformat()
    return True
@bp.before_app_request
def timeout():
    if session.get('login_id') and not auth():
        flash('Session expired. Please sign in again.','warning')
@bp.route('/')
def home(): return redirect(url_for('main.dashboard' if session.get('login_id') else 'main.login'))
@bp.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=one("SELECT * FROM login WHERE Username=%s AND Is_Active=1",(request.form['username'].strip(),))
        if u and bcrypt.checkpw(request.form['password'].encode(),u['Password_Hash'].encode()):
            session.clear(); session.update(login_id=u['Login_ID'],username=u['Username'],role=u['Role'])
            s=one("SELECT * FROM staff WHERE Login_ID=%s",(u['Login_ID'],))
            p=one("SELECT * FROM patient WHERE Login_ID=%s",(u['Login_ID'],))
            if s: session.update(staff_id=s['Staff_ID'],branch_id=s['Branch_ID'],display_name=s['Name'])
            if p: session.update(uhid=p['UHID'],display_name=p['Name'])
            return redirect(url_for('main.dashboard'))
        flash('Invalid username or password.','danger')
    return render_template('login.html')
@bp.route('/logout')
def logout(): session.clear(); return redirect(url_for('main.login'))
@bp.route('/dashboard')
def dashboard():
    if not auth(): return redirect(url_for('main.login'))
    role=session['role']; branch=session.get('branch_id'); uhid=session.get('uhid')
    def count(sql,args=()): return one(sql,args)['n']
    filt=' WHERE Branch_ID=%s' if branch else ''
    stats={'patients':count("SELECT COUNT(*) n FROM patient") if role!='patient' else 1,
           'appointments':count("SELECT COUNT(*) n FROM appointment WHERE "+("UHID=%s" if role=='patient' else "Branch_ID=%s"),(uhid,) if role=='patient' else (branch,)) if role in ('patient','branch_admin','doctor','receptionist') else count("SELECT COUNT(*) n FROM appointment"),
           'admissions':count("SELECT COUNT(*) n FROM admission a JOIN ward w ON a.Ward_ID=w.Ward_ID WHERE "+("a.UHID=%s" if role=='patient' else "w.Branch_ID=%s"),(uhid,) if role=='patient' else (branch,)) if role in ('patient','branch_admin','doctor','receptionist') else count("SELECT COUNT(*) n FROM admission"),
           'referrals':count("SELECT COUNT(*) n FROM referral WHERE "+("UHID=%s" if role=='patient' else "To_Branch_ID=%s"),(uhid,) if role=='patient' else (branch,)) if role in ('patient','branch_admin','doctor','receptionist') else count("SELECT COUNT(*) n FROM referral")}
    branches=query("SELECT b.Branch_Name,COALESCE(SUM(w.Total_Beds-w.Available_Beds),0) Occupied,COALESCE(SUM(w.Total_Beds),0) Total FROM branch b LEFT JOIN ward w ON w.Branch_ID=b.Branch_ID GROUP BY b.Branch_ID")
    return render_template('dashboard.html',stats=stats,branches=branches)
def page(title,sql,args=(),kind='list',extra=None):
    rows=query(sql,args)
    return render_template('table.html',title=title,rows=rows,kind=kind,extra=extra or {})
@bp.route('/patients',methods=['GET','POST'])
def patients():
    if not auth(): return redirect(url_for('main.login'))
    if request.method=='POST':
        if session['role'] not in ('chain_admin','branch_admin','receptionist'): abort(403)
        uhid='AI'+datetime.utcnow().strftime('%y%m%d%H%M%S%f')[:17]
        c=connect(); cur=c.cursor()
        try:
            cur.execute("INSERT INTO patient(UHID,Name,DOB,Gender,Address,Phone,Blood_Group) VALUES(%s,%s,%s,%s,%s,%s,%s)",(uhid,request.form['name'],request.form['dob'],request.form.get('gender') or None,request.form.get('address'),request.form.get('phone'),request.form.get('blood_group') or None))
            c.commit(); flash('Patient registered. UHID: '+uhid,'success')
        except Exception as e: c.rollback(); flash(str(e),'danger')
        finally: cur.close(); c.close()
        return redirect(url_for('main.patients'))
    if session['role']=='patient': return page('Patient Registry',"SELECT * FROM patient WHERE UHID=%s",(session['uhid'],))
    return page('Patient Registry',"SELECT * FROM patient ORDER BY Created_At DESC",kind='patient')
@bp.route('/appointments',methods=['GET','POST'])
def appointments():
    if not auth(): return redirect(url_for('main.login'))
    role=session['role']
    if request.method=='POST':
        uhid=session.get('uhid') if role=='patient' else request.form['uhid']
        c=connect(); cur=c.cursor()
        try:
            c.start_transaction()
            cur.execute("SELECT Branch_ID FROM staff WHERE Staff_ID=%s AND Staff_Type='Doctor' FOR UPDATE",(request.form['staff_id'],)); d=cur.fetchone()
            if not d or str(d[0])!=request.form['branch_id']: raise ValueError('Doctor is not assigned to this branch')
            cur.execute("SELECT COALESCE(MAX(Token_No),0)+1 FROM appointment WHERE Branch_ID=%s AND Appt_Date=%s",(request.form['branch_id'],request.form['appt_date'])); token=cur.fetchone()[0]
            cur.execute("INSERT INTO appointment(UHID,Staff_ID,Branch_ID,Appt_Date,Time_Slot,Token_No) VALUES(%s,%s,%s,%s,%s,%s)",(uhid,request.form['staff_id'],request.form['branch_id'],request.form['appt_date'],request.form['time_slot'],token))
            c.commit(); flash('Appointment booked. Token '+str(token),'success')
        except Exception as e: c.rollback(); flash('Booking failed: '+str(e),'danger')
        finally: cur.close(); c.close()
        return redirect(url_for('main.appointments'))
    sql="SELECT a.Appt_ID,a.UHID,p.Name Patient,a.Appt_Date,a.Time_Slot,a.Token_No,a.Status,s.Name Doctor,b.Branch_Name FROM appointment a JOIN patient p ON p.UHID=a.UHID JOIN staff s ON s.Staff_ID=a.Staff_ID JOIN branch b ON b.Branch_ID=a.Branch_ID"
    args=()
    if role=='patient': sql+=" WHERE a.UHID=%s"; args=(session['uhid'],)
    elif role=='doctor': sql+=" WHERE a.Staff_ID=%s"; args=(session['staff_id'],)
    elif role in ('branch_admin','receptionist'): sql+=" WHERE a.Branch_ID=%s"; args=(session['branch_id'],)
    sql+=" ORDER BY a.Appt_Date DESC"
    extra={'doctors':query("SELECT s.Staff_ID,s.Name,b.Branch_ID,b.Branch_Name FROM staff s JOIN doctor d ON d.Staff_ID=s.Staff_ID JOIN branch b ON b.Branch_ID=s.Branch_ID"),'branches':query("SELECT * FROM branch"),'patients':query("SELECT UHID,Name FROM patient")}
    return page('Appointments',sql,args,'appointment',extra)
@bp.route('/appointments/<int:i>/cancel',methods=['POST'])
def cancel(i):
    if not auth(): return redirect(url_for('main.login'))
    c=connect(); cur=c.cursor()
    try:
        if session['role']=='patient': cur.execute("UPDATE appointment SET Status='Cancelled' WHERE Appt_ID=%s AND UHID=%s AND Status='Booked'",(i,session['uhid']))
        elif session['role']=='doctor': cur.execute("UPDATE appointment SET Status='Cancelled' WHERE Appt_ID=%s AND Staff_ID=%s AND Status='Booked'",(i,session['staff_id']))
        else: cur.execute("UPDATE appointment SET Status='Cancelled' WHERE Appt_ID=%s AND Status='Booked' AND (%s='chain_admin' OR Branch_ID=%s)",(i,session['role'],session.get('branch_id')))
        c.commit(); flash('Cancellation processed.','success')
    except Exception as e: c.rollback(); flash(str(e),'danger')
    finally: cur.close(); c.close()
    return redirect(url_for('main.appointments'))
@bp.route('/wards')
def wards():
    if not auth(): return redirect(url_for('main.login'))
    role=session['role']; sql="SELECT w.Ward_ID,w.Ward_Name,w.Ward_Type,w.Total_Beds,w.Available_Beds,w.Daily_Rate,b.Branch_Name FROM ward w JOIN branch b ON b.Branch_ID=w.Branch_ID"
    args=()
    if role in ('branch_admin','doctor','receptionist'): sql+=" WHERE w.Branch_ID=%s"; args=(session['branch_id'],)
    return page('Ward & ICU Availability',sql,args)
@bp.route('/admissions',methods=['GET','POST'])
def admissions():
    if not auth(): return redirect(url_for('main.login'))
    role=session['role']
    if request.method=='POST':
        if role not in ('chain_admin','branch_admin','receptionist'): abort(403)
        c=connect(); cur=c.cursor()
        try:
            c.start_transaction(); cur.execute("SELECT Branch_ID,Available_Beds FROM ward WHERE Ward_ID=%s FOR UPDATE",(request.form['ward_id'],)); w=cur.fetchone()
            if not w or w[1]<1: raise ValueError('No beds available')
            if role=='branch_admin' and str(w[0])!=str(session['branch_id']): raise ValueError('Ward is outside your branch')
            cur.execute("INSERT INTO admission(UHID,Ward_ID,Admitting_Staff_ID,Admit_Date,Attendant_Name,Attendant_Phone) VALUES(%s,%s,%s,CURDATE(),%s,%s)",(request.form['uhid'],request.form['ward_id'],session.get('staff_id'),request.form.get('attendant_name'),request.form.get('attendant_phone')))
            c.commit(); flash('Admission completed.','success')
        except Exception as e: c.rollback(); flash('Admission failed: '+str(e),'danger')
        finally: cur.close(); c.close()
        return redirect(url_for('main.admissions'))
    sql="SELECT a.Admission_ID,a.UHID,p.Name Patient,w.Ward_Name,b.Branch_Name,a.Admit_Date,a.Discharge_Date,a.Status FROM admission a JOIN patient p ON p.UHID=a.UHID JOIN ward w ON w.Ward_ID=a.Ward_ID JOIN branch b ON b.Branch_ID=w.Branch_ID"
    args=()
    if role=='patient': sql+=" WHERE a.UHID=%s"; args=(session['uhid'],)
    elif role in ('branch_admin','doctor','receptionist'): sql+=" WHERE w.Branch_ID=%s"; args=(session['branch_id'],)
    extra={'patients':query("SELECT UHID,Name FROM patient"),'wards':query("SELECT * FROM ward WHERE Available_Beds>0")}
    return page('IPD Admissions',sql,args,'admission',extra)
@bp.route('/admissions/<int:i>/discharge',methods=['POST'])
def discharge(i):
    if not auth(): return redirect(url_for('main.login'))
    if session['role'] not in ('chain_admin','branch_admin','receptionist'): abort(403)
    c=connect(); cur=c.cursor()
    try:
        c.start_transaction(); cur.execute("SELECT a.Ward_ID,a.Status,w.Branch_ID,w.Daily_Rate FROM admission a JOIN ward w ON w.Ward_ID=a.Ward_ID WHERE a.Admission_ID=%s FOR UPDATE",(i,)); r=cur.fetchone()
        if not r or r[1]!='Active': raise ValueError('Admission not active')
        if session['role']=='branch_admin' and str(r[2])!=str(session['branch_id']): raise ValueError('Outside branch')
        cur.execute("SELECT DATEDIFF(CURDATE(),Admit_Date)+1 FROM admission WHERE Admission_ID=%s",(i,)); days=cur.fetchone()[0]
        cur.execute("INSERT INTO billing(Admission_ID,Consultation_Fee,Room_Charges,Medicine_Charges) VALUES(%s,0,%s,0)",(i,float(r[3])*days))
        cur.execute("UPDATE admission SET Status='Discharged',Discharge_Date=CURDATE() WHERE Admission_ID=%s",(i,))
        c.commit(); flash('Discharged; bill generated and bed released.','success')
    except Exception as e: c.rollback(); flash('Discharge failed: '+str(e),'danger')
    finally: cur.close(); c.close()
    return redirect(url_for('main.admissions'))
@bp.route('/referrals',methods=['GET','POST'])
def referrals():
    if not auth(): return redirect(url_for('main.login'))
    role=session['role']
    if request.method=='POST':
        if role!='doctor': abort(403)
        c=connect(); cur=c.cursor()
        try:
            cur.execute("INSERT INTO referral(UHID,From_Branch_ID,To_Branch_ID,Created_By_Staff_ID,Reason) VALUES(%s,%s,%s,%s,%s)",(request.form['uhid'],session['branch_id'],request.form['to_branch_id'],session['staff_id'],request.form['reason']))
            c.commit(); flash('Referral created.','success')
        except Exception as e: c.rollback(); flash(str(e),'danger')
        finally: cur.close(); c.close()
        return redirect(url_for('main.referrals'))
    sql="SELECT r.Referral_ID,p.Name Patient,f.Branch_Name From_Branch,t.Branch_Name To_Branch,r.Reason,r.Status,r.Created_At FROM referral r JOIN patient p ON p.UHID=r.UHID JOIN branch f ON f.Branch_ID=r.From_Branch_ID JOIN branch t ON t.Branch_ID=r.To_Branch_ID"
    args=()
    if role=='patient': sql+=" WHERE r.UHID=%s"; args=(session['uhid'],)
    elif role=='doctor': sql+=" WHERE r.Created_By_Staff_ID=%s"; args=(session['staff_id'],)
    elif role in ('branch_admin','receptionist'): sql+=" WHERE r.From_Branch_ID=%s OR r.To_Branch_ID=%s"; args=(session['branch_id'],session['branch_id'])
    return page('Inter-Branch Referrals',sql,args,'referral',{'patients':query("SELECT * FROM patient"),'branches':query("SELECT * FROM branch"),'doctors':query("SELECT s.Staff_ID,s.Name,s.Branch_ID FROM staff s JOIN doctor d ON d.Staff_ID=s.Staff_ID")})
@bp.route('/prescriptions',methods=['GET','POST'])
def prescriptions():
    if not auth(): return redirect(url_for('main.login'))
    role=session['role']
    if request.method=='POST':
        if role!='doctor': abort(403)
        c=connect(); cur=c.cursor()
        try:
            cur.execute("SELECT 1 FROM appointment WHERE Appt_ID=%s AND Staff_ID=%s",(request.form['appt_id'],session['staff_id']))
            if not cur.fetchone(): raise ValueError('Appointment is not assigned to you')
            cur.execute("INSERT INTO prescription(Appt_ID,Medicine_Name,Dosage,Notes) VALUES(%s,%s,%s,%s)",(request.form['appt_id'],request.form['medicine_name'],request.form['dosage'],request.form.get('notes')))
            c.commit(); flash('Prescription saved.','success')
        except Exception as e: c.rollback(); flash(str(e),'danger')
        finally: cur.close(); c.close()
        return redirect(url_for('main.prescriptions'))
    sql="SELECT pr.Prescription_ID,p.Name Patient,a.UHID,pr.Medicine_Name,pr.Dosage,pr.Notes,b.Branch_Name FROM prescription pr JOIN appointment a ON a.Appt_ID=pr.Appt_ID JOIN patient p ON p.UHID=a.UHID JOIN branch b ON b.Branch_ID=a.Branch_ID"
    args=()
    if role=='patient': sql+=" WHERE a.UHID=%s"; args=(session['uhid'],)
    elif role=='doctor': sql+=" WHERE a.Staff_ID=%s"; args=(session['staff_id'],)
    elif role in ('branch_admin','receptionist'): sql+=" WHERE a.Branch_ID=%s"; args=(session['branch_id'],)
    return page('Prescriptions & History',sql,args,'prescription',{'appointments':query("SELECT * FROM appointment WHERE Staff_ID=%s",(session.get('staff_id'),))})
@bp.route('/billing')
def billing():
    if not auth(): return redirect(url_for('main.login'))
    role=session['role']; sql="SELECT bi.Bill_ID,p.Name Patient,b.Branch_Name,bi.Consultation_Fee,bi.Room_Charges,bi.Medicine_Charges,bi.Total,bi.Status FROM billing bi JOIN admission a ON a.Admission_ID=bi.Admission_ID JOIN patient p ON p.UHID=a.UHID JOIN ward w ON w.Ward_ID=a.Ward_ID JOIN branch b ON b.Branch_ID=w.Branch_ID"; args=()
    if role=='patient': sql+=" WHERE a.UHID=%s"; args=(session['uhid'],)
    elif role in ('branch_admin','receptionist'): sql+=" WHERE w.Branch_ID=%s"; args=(session['branch_id'],)
    elif role=='doctor': sql+=" WHERE 1=0"
    return page('Billing',sql,args)
@bp.app_errorhandler(403)
def forbidden(e): return render_template('error.html',code=403,message='You are not authorized to access this page.'),403

@bp.route('/referrals/<int:i>/accept',methods=['POST'])
def accept_referral(i):
    if not auth(): return redirect(url_for('main.login'))
    role=session['role']
    if role not in ('chain_admin','branch_admin','receptionist'): abort(403)
    c=connect(); cur=c.cursor()
    try:
        c.start_transaction()
        cur.execute("SELECT UHID,To_Branch_ID,Status FROM referral WHERE Referral_ID=%s FOR UPDATE",(i,))
        ref=cur.fetchone()
        if not ref or ref[2]!='Pending': raise ValueError('Referral is not pending')
        if role=='branch_admin' and str(ref[1])!=str(session.get('branch_id')): raise ValueError('Referral belongs to another branch')
        cur.execute("SELECT Branch_ID FROM staff WHERE Staff_ID=%s AND Staff_Type='Doctor' FOR UPDATE",(request.form['doctor_id'],))
        doc=cur.fetchone()
        if not doc or str(doc[0])!=str(ref[1]): raise ValueError('Doctor is not assigned to the receiving branch')
        cur.execute("SELECT COALESCE(MAX(Token_No),0)+1 FROM appointment WHERE Branch_ID=%s AND Appt_Date=%s",(ref[1],request.form['appt_date']))
        token=cur.fetchone()[0]
        cur.execute("INSERT INTO appointment(UHID,Staff_ID,Branch_ID,Appt_Date,Time_Slot,Token_No) VALUES(%s,%s,%s,%s,%s,%s)",(ref[0],request.form['doctor_id'],ref[1],request.form['appt_date'],request.form['time_slot'],token))
        appt_id=cur.lastrowid
        cur.execute("UPDATE referral SET Status='Accepted',Destination_Doctor_ID=%s,Appt_ID=%s WHERE Referral_ID=%s",(request.form['doctor_id'],appt_id,i))
        c.commit(); flash('Referral accepted and appointment created.','success')
    except Exception as e:
        c.rollback(); flash('Referral acceptance failed: '+str(e),'danger')
    finally:
        cur.close(); c.close()
    return redirect(url_for('main.referrals'))
