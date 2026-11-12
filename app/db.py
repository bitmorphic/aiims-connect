"""Small, schema-compatible MySQL access layer for AIIMS Connect."""
import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector import Error as MySQLError
from dotenv import load_dotenv

load_dotenv()


def connect():
    """Open a fresh connection using local or Railway environment variables."""
    config = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "aiims_connect"),
        "connection_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "8")),
        "autocommit": False,
    }
    if os.getenv("DB_SSL_CA"):
        config["ssl_ca"] = os.getenv("DB_SSL_CA")
        config["ssl_verify_cert"] = True
    return mysql.connector.connect(**config)


@contextmanager
def session(actor_login_id=None):
    """Yield a connection and cursor while setting the audit actor variable."""
    cn = connect()
    cur = cn.cursor()
    try:
        cur.execute("SET @app_login_id = %s", (actor_login_id,))
        yield cn, cur
        cn.commit()
    except Exception:
        cn.rollback()
        raise
    finally:
        cur.close()
        cn.close()


def fetch_all(sql, params=()):
    cn = connect()
    cur = cn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        cn.close()


def fetch_one(sql, params=()):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=(), actor_login_id=None):
    with session(actor_login_id) as (_, cur):
        cur.execute(sql, params)
        return cur.lastrowid, cur.rowcount


def call_procedure(name, args=(), actor_login_id=None, returns_output=False):
    """Call a stored procedure; OUT parameters must be the final argument."""
    cn = connect()
    cur = cn.cursor()
    try:
        cur.execute("SET @app_login_id = %s", (actor_login_id,))
        call_args = tuple(args) + ((None,) if returns_output else ())
        result = cur.callproc(name, call_args)
        for result_cursor in cur.stored_results():
            result_cursor.fetchall()
            result_cursor.close()
        cn.commit()
        return result[-1] if returns_output else None
    except Exception:
        cn.rollback()
        raise
    finally:
        cur.close()
        cn.close()


def ping():
    row = fetch_one("SELECT DATABASE() AS db_name, VERSION() AS version")
    return row
