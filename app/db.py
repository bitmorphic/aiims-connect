import os,mysql.connector
from dotenv import load_dotenv
load_dotenv()
def connect():
    return mysql.connector.connect(host=os.getenv('DB_HOST','localhost'),port=int(os.getenv('DB_PORT','3306')),user=os.getenv('DB_USER','aiims_app'),password=os.getenv('DB_PASSWORD',''),database=os.getenv('DB_NAME','aiims_connect'))
def query(sql,args=()):
    c=connect(); cur=c.cursor(dictionary=True)
    try: cur.execute(sql,args); return cur.fetchall()
    finally: cur.close(); c.close()
def one(sql,args=()):
    r=query(sql,args); return r[0] if r else None
