import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.stdout.reconfigure(encoding='utf-8')
from backend.database import get_connection

with get_connection() as conn:
    users = conn.execute("SELECT id, nome, email, telefone FROM users WHERE nome LIKE '%Carlos%'").fetchall()
    print("Users Carlos:", [dict(u) for u in users])
    contacts = conn.execute("SELECT * FROM contacts WHERE name LIKE '%Carlos%' OR nickname LIKE '%Carlos%'").fetchall()
    print("Contacts Carlos:", [dict(c) for c in contacts])
