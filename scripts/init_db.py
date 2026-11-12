from pathlib import Path
import os,sys
from dotenv import load_dotenv
import mysql.connector
ROOT=Path(__file__).resolve().parents[1];load_dotenv(ROOT/'.env')
def split_sql(text):
    delim=';';buf=[];out=[]
    for line in text.splitlines():
        s=line.strip()
        if not s or s.startswith('--') or s.startswith('#'):continue
        if s.upper().startswith('DELIMITER '):delim=s.split(None,1)[1];continue
        buf.append(line);joined='\n'.join(buf).rstrip()
        if joined.endswith(delim):
            stmt=joined[:-len(delim)].strip()
            if stmt:out.append(stmt)
            buf=[]
    if '\n'.join(buf).strip():out.append('\n'.join(buf).strip())
    return out
def main():
    cfg=dict(host=os.getenv('DB_HOST','localhost'),port=int(os.getenv('DB_PORT','3306')),user=os.getenv('DB_USER','aiims_app'),password=os.getenv('DB_PASSWORD',''),database=os.getenv('DB_NAME','aiims_connect'))
    if not cfg['password']:sys.exit('DB_PASSWORD missing from .env')
    cn=mysql.connector.connect(**cfg);cur=cn.cursor()
    try:
        cur.execute('SELECT VERSION(),CURRENT_USER(),DATABASE()');print('Connected:',cur.fetchone())
        for name in ['schema.sql','triggers.sql','procedures.sql','views.sql','seed.sql']:
            stmts=split_sql((ROOT/'sql'/name).read_text(encoding='utf-8'));print(name,len(stmts),'statements')
            for i,stmt in enumerate(stmts,1):
                try:cur.execute(stmt)
                except Exception as e:
                    cn.rollback();raise RuntimeError(f'{name} statement {i}/{len(stmts)} failed: {e}\\n{stmt[:250]}')
            cn.commit()
        cur.execute('SHOW TABLES');print('Tables:',[x[0] for x in cur.fetchall()])
        print('Initialization completed.')
    finally:cur.close();cn.close()
if __name__=='__main__':main()
