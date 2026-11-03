import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
from backend.database import get_connection

USER_ID = '2e0a4847-d1a9-48a6-86de-40229a125b58'

with get_connection() as conn:
    # Check what tables exist
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("Tables:", [t[0] for t in tables])
    
    # For each table, check columns
    for table in [t[0] for t in tables]:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        print(f"\n{table} cols:", [c[1] for c in cols])
    
    # Check incomes table
    print("\n--- INCOMES ---")
    try:
        rows = conn.execute("SELECT * FROM incomes LIMIT 5").fetchall()
        if rows:
            for r in rows: print(dict(r))
        else:
            print("Empty")
    except Exception as e:
        print(f"Error: {e}")
    
    # Check accounts table
    print("\n--- ACCOUNTS ---")
    try:
        rows = conn.execute("SELECT * FROM accounts LIMIT 5").fetchall()
        if rows:
            for r in rows: print(dict(r))
        else:
            print("Empty")
    except Exception as e:
        print(f"Error: {e}")

