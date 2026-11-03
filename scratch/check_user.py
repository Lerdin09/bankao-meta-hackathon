import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from backend.database import get_connection
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, email, password_hash FROM users WHERE email LIKE '%makiesse%'")
rows = cur.fetchall()
for r in rows:
    print("id:", r[0])
    print("email:", r[1])
    print("hash:", r[2][:60])
conn.close()
