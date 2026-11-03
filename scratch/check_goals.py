import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')
from backend.database import get_connection

conn = get_connection()
user = conn.execute("SELECT id, nome FROM users WHERE email='joao.makiesse@bankao.ao'").fetchone()
user_id = user["id"]
print("User:", user["nome"], user_id)

# Goals schema
cols = [c[1] for c in conn.execute("PRAGMA table_info(savings_goals)").fetchall()]
print("savings_goals columns:", cols)

goals = conn.execute("SELECT * FROM savings_goals WHERE user_id=?", (user_id,)).fetchall()
print("Goals count:", len(goals))
for g in goals:
    print(dict(g))

conn.close()

