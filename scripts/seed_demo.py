from pathlib import Path
import os,bcrypt,mysql.connector
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1];load_dotenv(ROOT/'.env')
c=mysql.connector.connect(host=os.getenv('DB_HOST','localhost'),port=int(os.getenv('DB_PORT','3306')),user=os.getenv('DB_USER','aiims_app'),password=os.getenv('DB_PASSWORD',''),database=os.getenv('DB_NAME','aiims_connect'))
cur=c.cursor()
def hashed():return bcrypt.hashpw(b'Demo@12345',bcrypt.gensalt()).decode()
try:
 data=[('chainadmin','chain_admin','Chain Admin',None,'Admin','chain_admin'),('delhiadmin','branch_admin','Delhi Admin',1,'Admin','branch_admin'),('doctor1','doctor','Dr Aditi Sharma',1,'Doctor',None),('reception1','receptionist','Riya Reception',1,'Receptionist',None),('patient1','patient','Demo Patient',None,None,None)]
 ids={}
 for u,r,n,b,t,l in data:
  cur.execute('SELECT Login_ID FROM login WHERE Username=%s',(u,));x=cur.fetchone()
  if x:lid=x[0]
  else:cur.execute('INSERT INTO login(Username,Password_Hash,Role) VALUES(%s,%s,%s)',(u,hashed(),r));lid=cur.lastrowid
  ids[u]=lid
  if t:
   cur.execute('SELECT Staff_ID FROM staff WHERE Login_ID=%s',(lid,));x=cur.fetchone()
   if x:sid=x[0]
   else:cur.execute('INSERT INTO staff(Login_ID,Branch_ID,Name,Staff_Type) VALUES(%s,%s,%s,%s)',(lid,b,n,t));sid=cur.lastrowid
   if t=='Doctor':cur.execute("INSERT IGNORE INTO doctor(Staff_ID,Dept_ID,Specialization,Consultation_Fee,Qualification) VALUES(%s,1,'General Medicine',500,'MBBS, MD')",(sid,))
   elif t=='Receptionist':cur.execute("INSERT IGNORE INTO receptionist(Staff_ID,Counter_No) VALUES(%s,'R-01')",(sid,))
   else:cur.execute('INSERT IGNORE INTO admin_staff(Staff_ID,Access_Level) VALUES(%s,%s)',(sid,l))
 cur.execute('SELECT UHID FROM patient WHERE Login_ID=%s',(ids['patient1'],))
 if not cur.fetchone():cur.execute("INSERT INTO patient(UHID,Login_ID,Name,DOB,Gender,Phone) VALUES('AIIMS-DEMO-0001',%s,'Demo Patient','2004-05-12','Other','9000000001')",(ids['patient1'],))
 c.commit();print('Demo accounts created. Password for all: Demo@12345')
finally:cur.close();c.close()
